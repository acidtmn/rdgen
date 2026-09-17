from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "configure_tehpult_sciter.py"
SPEC = importlib.util.spec_from_file_location("configure_tehpult_sciter", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Не удалось загрузить тестируемый модуль: {SCRIPT_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigureTehpultSciterTest(unittest.TestCase):
    def setUp(self) -> None:
        """Создаёт минимальное дерево RustDesk, достаточное для проверки каждого продуктового контракта."""
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)

        self.write(
            "Cargo.toml",
            self.package_metadata(),
        )
        self.write(
            "libs/portable/Cargo.toml",
            self.package_metadata().replace(
                'LegalCopyright = "Copyright © 2026 Purslane Tech Pte. Ltd. All rights reserved."',
                'LegalCopyright = "tehpult.ru"',
            ),
        )
        self.write("libs/portable/src/main.rs", 'const APP_PREFIX: &str = "rustdesk";\n')
        self.write("src/lang/en.rs", 'pub const NAME: &str = "RustDesk Remote Desktop";\n')
        self.write("src/lang/ru.rs", 'pub const NAME: &str = "RustDesk";\n')
        self.write("src/ui/index.tis", 'var download = "https://rustdesk.com/download";\n')
        self.write("build.py", 'homepage = "Homepage: https://rustdesk.com"\n')
        self.write(
            "libs/hbb_common/src/config.rs",
            f'const SERVER: &str = "rs-ny.rustdesk.com";\nconst KEY: &str = "{MODULE.DEFAULT_PUBLIC_KEY}";\n',
        )
        self.write("src/common.rs", self.common_source())

    def tearDown(self) -> None:
        """Удаляет только временное тестовое дерево, не затрагивая checkout проекта."""
        self.temp_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        """Записывает fixture-файл и создаёт требуемые родительские каталоги."""
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def package_metadata() -> str:
        """Возвращает upstream-метаданные, которые обязаны исчезнуть после конфигурации."""
        return "\n".join(
            (
                'description = "RustDesk Remote Desktop"',
                '[package.metadata.winres]',
                'LegalCopyright = "Copyright © 2026 Purslane Tech Pte. Ltd. All rights reserved."',
                'ProductName = "RustDesk"',
                'FileDescription = "RustDesk Remote Desktop"',
                'OriginalFilename = "rustdesk.exe"',
                "",
            )
        )

    @staticmethod
    def common_source() -> str:
        """Имитирует upstream-блок проверки подписи custom.txt, удаляемый для bundled-конфигурации."""
        signature_block = [
            f'const KEY: &str = "{MODULE.CUSTOM_SIGNATURE_KEY}";\n',
            "let signature_line_1 = true;\n",
            "let signature_line_2 = true;\n",
            "let signature_line_3 = true;\n",
            "let signature_line_4 = true;\n",
            "let signature_line_5 = true;\n",
            "let signature_line_6 = true;\n",
            "let signature_line_7 = true;\n",
            "let signature_line_8 = true;\n",
        ]
        return 'const API: &str = "https://admin.rustdesk.com";\nlet config = "custom.txt";\n' + "".join(signature_block)

    def test_configure_applies_brand_network_and_custom_file_contracts(self) -> None:
        """Проверяет итоговые пользовательские метаданные и отсутствие upstream-адресов/названий."""
        environment = {
            "appname": "ТехПульт",
            "filename": "tehpult",
            "server": "s1.tehpult.ru",
            "key": "public-key-for-test",
            "apiServer": "https://s1.tehpult.ru",
            "downloadLink": "https://tehpult.ru/downloads",
            "urlLink": "https://tehpult.ru/",
        }

        # Изолированное окружение гарантирует, что тест не использует локальные секреты разработчика.
        with patch.dict(os.environ, environment, clear=True):
            MODULE.configure(self.root)

        cargo = (self.root / "Cargo.toml").read_text(encoding="utf-8")
        portable = (self.root / "libs/portable/Cargo.toml").read_text(encoding="utf-8")
        common = (self.root / "src/common.rs").read_text(encoding="utf-8")

        self.assertIn('ProductName = "ТехПульт"', cargo)
        self.assertIn('OriginalFilename = "tehpult_x86.exe"', portable)
        self.assertIn("© 2026 ТехПульт. https://tehpult.ru", portable)
        self.assertNotIn("Purslane", cargo)
        self.assertNotIn("RustDesk", (self.root / "src/lang/en.rs").read_text(encoding="utf-8"))
        self.assertIn("s1.tehpult.ru", (self.root / "libs/hbb_common/src/config.rs").read_text(encoding="utf-8"))
        self.assertIn("https://tehpult.ru/downloads", (self.root / "src/ui/index.tis").read_text(encoding="utf-8"))
        self.assertIn("custom_.txt", common)
        self.assertNotIn(MODULE.CUSTOM_SIGNATURE_KEY, common)

    def test_required_replacement_fails_when_upstream_contract_changes(self) -> None:
        """Подтверждает fail-fast поведение вместо тихой выдачи неправильно брендированного клиента."""
        path = self.root / "Cargo.toml"
        with self.assertRaises(RuntimeError):
            MODULE.replace_required("неожиданное содержимое", "ожидаемый текст", "новый текст", path)

    def test_required_replacement_does_not_skip_old_value_when_new_value_exists_elsewhere(self) -> None:
        """Не позволяет случайному упоминанию нового домена скрыть оставшийся upstream-адрес."""
        path = self.root / "src/common.rs"
        content = "основной адрес: upstream; справочная ссылка: tehpult"
        result = MODULE.replace_required(content, "upstream", "tehpult", path)
        self.assertEqual(result, "основной адрес: tehpult; справочная ссылка: tehpult")


if __name__ == "__main__":
    unittest.main()

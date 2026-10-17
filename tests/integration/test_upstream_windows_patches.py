import concurrent.futures
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.request


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path("/tehpult-upstream-memory")
SOURCE_FILES = (
    "src/ui/index.html", "src/ui/index.tis", "src/ui/index.css", "src/ui/ab.tis",
    "flutter/lib/common/widgets/login.dart",
    "flutter/lib/desktop/pages/desktop_home_page.dart",
    "flutter/lib/desktop/pages/desktop_setting_page.dart",
    "flutter/lib/mobile/pages/connection_page.dart",
    "flutter/lib/desktop/widgets/remote_toolbar.dart",
    "Cargo.toml", "libs/portable/Cargo.toml", "src/lang/ru.rs", "src/common.rs",
    "src/client.rs", "src/lang.rs", "res/msi/Package/Package.wxs",
    "res/msi/Package/Package.wixproj", "res/msi/Package/License.rtf",
    "res/msi/Package/Language/Package.en-us.wxl",
    "res/msi/Package/Language/WixExt_en-us.wxl",
)


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpstreamWindowsPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth = load_module("auth_patch", ".github/patches/apply_nanodesk_client_auth.py")
        cls.distribution = load_module("distribution_patch", ".github/patches/apply_russian_distribution.py")
        cls.transport = load_module("transport_patch", ".github/patches/apply_tehpult_transport.py")

        # Проверяем реальные исходники тега, не создавая второй checkout или копию проекта.
        def fetch(relative):
            url = "https://raw.githubusercontent.com/rustdesk/rustdesk/1.5.0/" + relative
            with urllib.request.urlopen(url, timeout=30) as response:
                text = response.read().decode("utf-8").replace("\r\n", "\n")
            return SOURCE_ROOT / relative, text

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            cls.original = dict(pool.map(fetch, SOURCE_FILES))

    def test_complete_windows_patch_sequence_against_150(self):
        sources = dict(self.original)
        original_read = Path.read_text

        # Виртуальная файловая система позволяет исполнить существующие патчи без записи исходников на диск.
        def read(path, *args, **kwargs):
            return sources[path] if path in sources else original_read(path, *args, **kwargs)

        def write(path, text, *args, **kwargs):
            if not path.is_relative_to(SOURCE_ROOT):
                raise AssertionError("Патч попытался записать файл вне исходников")
            sources[path] = text
            return len(text)

        with patch.object(Path, "read_text", read), patch.object(Path, "write_text", write), \
                patch.object(Path, "exists", lambda path: path in sources):
            self.distribution.patch_default_language(SOURCE_ROOT, "ru")
            self.distribution.patch_msi_codepage(SOURCE_ROOT)
            self.distribution.patch_msi_project_localizations(SOURCE_ROOT)
            self.distribution.patch_msi_language(SOURCE_ROOT)
            self.distribution.patch_license(
                SOURCE_ROOT, "ТехПульт", "ТехПульт", "https://tehpult.ru",
                "https://tehpult.ru/privacy", "Законный удалённый доступ.",
            )
            self.auth.patch_index_html(SOURCE_ROOT, REPOSITORY / ".github/patches/nanodesk_client_auth.tis")
            for name in (
                "patch_index_tis", "patch_dashboard", "patch_dashboard_styles", "patch_address_book",
                "patch_flutter_login", "patch_flutter_dashboard", "patch_branding_details",
                "patch_connection_security_notice", "patch_update_channel",
            ):
                with self.subTest(patch=name):
                    getattr(self.auth, name)(SOURCE_ROOT)
            sources[SOURCE_ROOT / "src/client.rs"] = self.transport.patch_transport(
                sources[SOURCE_ROOT / "src/client.rs"]
            )

        common = sources[SOURCE_ROOT / "src/common.rs"]
        original_common = self.original[SOURCE_ROOT / "src/common.rs"]
        handshake_start = original_common.index("async fn secure_tcp_impl(")
        handshake_end = original_common.index("fn get_pk(", handshake_start)
        self.assertIn(original_common[handshake_start:handshake_end], common)
        self.assertIn("set_negotiated_key", common)
        self.assertIn("https://s1.tehpult.ru/api/v1/client/version", common)
        self.assertIn('version = "1.5.0"', sources[SOURCE_ROOT / "Cargo.toml"])
        self.assertIn('Culture="ru-ru"', sources[SOURCE_ROOT / "res/msi/Package/Language/Package.ru-ru.wxl"])
        self.assertIn("https://tehpult.ru", sources[SOURCE_ROOT / "res/msi/Package/License.rtf"])
        self.assertIn("Вход в ТехПульт", sources[SOURCE_ROOT / "flutter/lib/common/widgets/login.dart"])
        self.assertIn("secure_tcp_required(&mut socket, &key).await", sources[SOURCE_ROOT / "src/client.rs"])
        toolbar = sources[SOURCE_ROOT / "flutter/lib/desktop/widgets/remote_toolbar.dart"]
        self.assertIn("class _MonitorCycle", toolbar)
        self.assertIn("class _MainMonitorSwitchButton", toolbar)
        self.assertIn("class _MinimizedMonitorSwitchButton", toolbar)


if __name__ == "__main__":
    unittest.main()

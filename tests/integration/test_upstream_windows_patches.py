import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
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
    "src/platform/windows.rs", "src/platform/windows/installer_shell.rs",
    "libs/hbb_common/src/config.rs", "libs/portable/src/main.rs", "build.py", "src/lang/en.rs",
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
        cls.installer = load_module("installer_patch", ".github/patches/apply_tehpult_windows_installer.py")
        cls.sciter = load_module("sciter_configuration", ".github/scripts/configure_tehpult_sciter.py")

        with urllib.request.urlopen(
            'https://api.github.com/repos/rustdesk/rustdesk/contents/libs/hbb_common?ref=1.5.0',
            timeout=30,
        ) as response:
            common_commit = json.load(response)['sha']

        # Проверяем реальные исходники тега, не создавая второй checkout или копию проекта.
        def fetch(relative):
            url = "https://raw.githubusercontent.com/rustdesk/rustdesk/1.5.0/" + relative
            if relative.startswith("libs/hbb_common/"):
                url = "https://raw.githubusercontent.com/rustdesk/hbb_common/" + common_commit + "/src/config.rs"
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
            sources[SOURCE_ROOT / "src/platform/windows.rs"] = self.installer.patch_installer(
                sources[SOURCE_ROOT / "src/platform/windows.rs"]
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
        login = sources[SOURCE_ROOT / "flutter/lib/common/widgets/login.dart"]
        self.assertIn("Вход в ТехПульт", login)
        constructor = re.search(r"\n  LoginWidgetOP\(\{(.*?)\}\)", login, re.DOTALL)
        self.assertIsNotNone(constructor)
        login_widget = re.search(
            r"thirdAuthWidget\(\).*?child: LoginWidgetOP\((.*?)\n            \),",
            login, re.DOTALL,
        )
        self.assertIsNotNone(login_widget)
        for parameter in re.findall(r"required this\.(\w+)", constructor.group(1)):
            self.assertRegex(login_widget.group(1), rf"\b{parameter}:")
        for callback in ("startAuth: oidcAuth.start", "cancelAuth: oidcAuth.cancelCurrent",
                         "canStartAuth: oidcAuth.canStart"):
            self.assertIn(callback, login_widget.group(1))
        self.assertIn("secure_tcp_required(&mut socket, &key).await", sources[SOURCE_ROOT / "src/client.rs"])
        toolbar = sources[SOURCE_ROOT / "flutter/lib/desktop/widgets/remote_toolbar.dart"]
        self.assertIn("class _MonitorCycle", toolbar)
        self.assertIn("class _MainMonitorSwitchButton", toolbar)
        self.assertIn("class _MinimizedMonitorSwitchButton", toolbar)
        self.assertEqual(
            sources[SOURCE_ROOT / "src/platform/windows/installer_shell.rs"],
            self.original[SOURCE_ROOT / "src/platform/windows/installer_shell.rs"],
        )

    def test_sciter_configuration_against_150(self):
        sources = dict(self.original)
        original_read = Path.read_text

        def read(path, *args, **kwargs):
            return sources[path] if path in sources else original_read(path, *args, **kwargs)

        def write(path, text, *args, **kwargs):
            if not path.is_relative_to(SOURCE_ROOT):
                raise AssertionError("Конфигуратор записывает за пределами исходников")
            sources[path] = text
            return len(text)

        settings = {
            "appname": "ТехПульт", "filename": "tehpult", "server": "s1.tehpult.ru:21116",
            "key": "geD8cR8LQ57yfz7f74dMPzLQKHkC5eZEzXzlQbvDsMA=", "apiServer": "https://s1.tehpult.ru",
            "downloadLink": "https://tehpult.ru/downloads", "urlLink": "https://tehpult.ru",
        }
        with patch.object(Path, "read_text", read), patch.object(Path, "write_text", write), \
                patch.object(Path, "is_file", lambda path: path in sources), \
                patch.object(Path, "glob", lambda path, pattern: iter(
                    item for item in sources if item.parent == path and item.match(pattern)
                )), patch.dict(os.environ, settings):
            self.auth.patch_branding_details(SOURCE_ROOT)
            self.sciter.configure(SOURCE_ROOT)
            self.installer.patch_installer(sources[SOURCE_ROOT / "src/platform/windows.rs"])
            self.transport.patch_transport(sources[SOURCE_ROOT / "src/client.rs"])

        self.assertIn(settings["key"], sources[SOURCE_ROOT / "libs/hbb_common/src/config.rs"])
        self.assertIn('OriginalFilename = "tehpult_x86.exe"', sources[SOURCE_ROOT / "Cargo.toml"])
        self.assertIn('const APP_PREFIX: &str = "tehpult";', sources[SOURCE_ROOT / "libs/portable/src/main.rs"])
        self.assertIn('custom_.txt', sources[SOURCE_ROOT / "src/common.rs"])

    def test_installer_accepts_brand_and_rejects_command_injection(self):
        source = self.installer.patch_installer(self.original[SOURCE_ROOT / "src/platform/windows.rs"])
        validator = re.search(
            r"fn validate_install_app_name\(.*?\n\}", source, re.DOTALL,
        ).group()
        rustc = shutil.which("rustc")
        if rustc is None:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("Для проверки валидатора на runner нужен rustc")
            self.skipTest("В локальном контейнере нет rustc; проверка выполняется на GitHub runner")
        harness = '''type ResultType<T> = Result<T, &'static str>;
macro_rules! bail { ($message:expr) => { return Err($message) }; }
''' + validator + '''
fn main() {
    for name in ["ТехПульт", "RustDesk-Admin1", "tehpult"] {
        assert!(validate_install_app_name(name).is_ok());
    }
    for name in ["", "ТехПульт&whoami", "ТехПульт%PATH%", "ТехПульт\\n", "ТехПульт|cmd",
                 "ТехПульт\\\"", "ТехПульт ", "RustDesk_Admin", "RustDesk应用"] {
        assert!(validate_install_app_name(name).is_err(), "accepted: {}", name);
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "validator.rs").write_text(harness, encoding="utf-8")
            binary = path / ("validator.exe" if os.name == "nt" else "validator")
            subprocess.run([rustc, str(path / "validator.rs"), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()

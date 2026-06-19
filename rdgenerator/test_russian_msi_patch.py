import importlib.util
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from django.test import SimpleTestCase


def load_patch_module():
    patch_path = Path(__file__).resolve().parent.parent / ".github" / "patches" / "apply_russian_distribution.py"
    spec = importlib.util.spec_from_file_location("apply_russian_distribution", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RussianMsiPatchTests(SimpleTestCase):
    def test_wix_project_patch_keeps_valid_xml(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            package_dir = project_root / "res" / "msi" / "Package"
            package_dir.mkdir(parents=True, exist_ok=True)
            package_project_path = package_dir / "Package.wixproj"
            package_project_path.write_text(
                "<Project Sdk=\"WixToolset.Sdk/4.0.5\">\n"
                "  <ItemGroup>\n"
                "    <Content Include=\"Includes.wxi\" />\n"
                "  </ItemGroup>\n"
                "</Project>\n",
                encoding="utf-8",
            )

            # Проверяем, что патчер добавляет локализации внутрь валидного XML-проекта,
            # а не ломает структуру wixproj побочными строковыми вставками.
            patch_module.patch_msi_project_localizations(project_root)

            content = package_project_path.read_text(encoding="utf-8")
            ET.fromstring(content)
            self.assertIn('WixLocalization Include="Language\\Package.ru-ru.wxl"', content)
            self.assertIn('WixLocalization Include="Language\\WixExt_ru-ru.wxl"', content)
            self.assertEqual(content.count("</Project>"), 1)

    def test_language_patch_creates_russian_localizations(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            language_dir = project_root / "res" / "msi" / "Package" / "Language"
            language_dir.mkdir(parents=True, exist_ok=True)
            (language_dir / "Package.en-us.wxl").write_text(
                "<WixLocalization Culture=\"en-us\" Codepage=\"1252\" xmlns=\"http://wixtoolset.org/schemas/v4/wxl\">\n"
                "  <String Id=\"SummaryCodepage\" Value=\"1252\" />\n"
                "  <String Id=\"ProductLanguage\" Value=\"1033\" />\n"
                "  <String Id=\"MyInstallDirDlgDesktopShortcuts\" Value=\"Create desktop icon\" />\n"
                "</WixLocalization>\n",
                encoding="utf-8",
            )
            (language_dir / "WixExt_en-us.wxl").write_text(
                "<WixLocalization Culture=\"en-us\" xmlns=\"http://wixtoolset.org/schemas/v4/wxl\">\n"
                "  <String Id=\"WixSchedFirewallExceptionsInstall\" Value=\"Configuring Windows Firewall\" />\n"
                "</WixLocalization>\n",
                encoding="utf-8",
            )

            # Русские wxl-файлы должны собираться из англоязычных шаблонов предсказуемо,
            # чтобы пользователь в MSI видел локализованные строки, а не английский fallback.
            patch_module.patch_msi_language(project_root)

            package_ru = (language_dir / "Package.ru-ru.wxl").read_text(encoding="utf-8")
            wixext_ru = (language_dir / "WixExt_ru-ru.wxl").read_text(encoding="utf-8")

            self.assertIn('Culture="ru-ru" Codepage="1251"', package_ru)
            self.assertIn('Value="Создать значок на рабочем столе"', package_ru)
            self.assertIn('Culture="ru-ru"', wixext_ru)
            self.assertIn('Value="Настройка Брандмауэра Windows"', wixext_ru)

    def test_license_patch_replaces_english_text_with_russian_rtf(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            package_dir = project_root / "res" / "msi" / "Package"
            package_dir.mkdir(parents=True, exist_ok=True)
            license_path = package_dir / "License.rtf"
            license_path.write_text(
                "{\\rtf1\\ansi\\ansicpg1252\\deff0 Privacy policy English text}",
                encoding="utf-8",
            )

            # Вместо английского privacy-текста должен появиться полный русский документ
            # с официальными ссылками на privacy и terms сайта NanoDesk.
            patch_module.patch_license(
                project_root,
                app_name="NanoDesk",
                company_name="ООО НаноДеск",
                homepage_url="https://nanodesk.ru",
                privacy_url="https://nanodesk.ru/privacy",
                legal_notice="Использование допускается только при наличии законных оснований.",
            )

            license_content = license_path.read_text(encoding="utf-8")
            self.assertIn(
                patch_module.to_rtf_unicode("Лицензионные условия и уведомление"),
                license_content,
            )
            self.assertIn(
                patch_module.to_rtf_unicode("152-ФЗ"),
                license_content,
            )
            self.assertIn("https://nanodesk.ru", license_content)
            self.assertIn("https://nanodesk.ru/privacy", license_content)
            self.assertIn("https://nanodesk.ru/terms", license_content)
            self.assertIn(
                patch_module.to_rtf_unicode("Информационная страница: https://nanodesk.ru."),
                license_content,
            )
            self.assertNotIn("rdgen.nanodesk.ru/privacy.html", license_content)
            self.assertNotIn("Privacy policy English text", license_content)

    def test_license_patch_normalizes_broken_nanodesk_homepage(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            package_dir = project_root / "res" / "msi" / "Package"
            package_dir.mkdir(parents=True, exist_ok=True)
            license_path = package_dir / "License.rtf"
            license_path.write_text("{\\rtf1\\ansi old}", encoding="utf-8")

            patch_module.patch_license(
                project_root,
                app_name="NanoDesk",
                company_name="ООО НаноДеск",
                homepage_url="https://NanoDesk.",
                privacy_url="https://rdgen.nanodesk.ru/privacy.html",
                legal_notice="Использование допускается только при наличии законных оснований.",
            )

            license_content = license_path.read_text(encoding="utf-8")
            self.assertIn("https://nanodesk.ru", license_content)
            self.assertNotIn("https://NanoDesk.", license_content)

    def test_normalize_privacy_url_fixes_broken_rdgen_domain(self):
        patch_module = load_patch_module()

        self.assertEqual(
            patch_module.normalize_privacy_url(
                "https://rdgen.NanoDesk/privacy.html",
                "https://nanodesk.ru",
            ),
            "https://nanodesk.ru/privacy",
        )

    def test_normalized_urls_are_persisted_for_following_workflow_steps(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            github_env_path = Path(temp_dir) / "github.env"
            old_github_env = os.environ.get("GITHUB_ENV")
            os.environ["GITHUB_ENV"] = str(github_env_path)
            try:
                patch_module.persist_normalized_distribution_inputs(
                    homepage_url="https://nanodesk.ru",
                    privacy_url="https://nanodesk.ru/privacy",
                )
            finally:
                if old_github_env is None:
                    os.environ.pop("GITHUB_ENV", None)
                else:
                    os.environ["GITHUB_ENV"] = old_github_env

            content = github_env_path.read_text(encoding="utf-8")
            self.assertIn("urlLink=https://nanodesk.ru", content)
            self.assertIn("privacyUrl=https://nanodesk.ru/privacy", content)

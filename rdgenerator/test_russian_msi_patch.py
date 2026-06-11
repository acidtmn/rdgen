import importlib.util
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

            # Проверяем новую ответственность патчера: локализации должны
            # добавляться внутрь Project, не ломая XML-структуру wixproj.
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

            # Проверяем, что генератор локализаций создаёт именно ru-ru файлы
            # и подставляет русские строки, которые увидит пользователь MSI.
            patch_module.patch_msi_language(project_root)

            package_ru = (language_dir / "Package.ru-ru.wxl").read_text(encoding="utf-8")
            wixext_ru = (language_dir / "WixExt_ru-ru.wxl").read_text(encoding="utf-8")

            self.assertIn('Culture="ru-ru" Codepage="1251"', package_ru)
            self.assertIn('Value="Создать значок на рабочем столе"', package_ru)
            self.assertIn('Culture="ru-ru"', wixext_ru)
            self.assertIn('Value="Настройка Брандмауэра Windows"', wixext_ru)

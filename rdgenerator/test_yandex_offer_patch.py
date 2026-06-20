import importlib.util
import tempfile
from pathlib import Path

from django.test import SimpleTestCase


def load_patch_module():
    patch_path = Path(__file__).resolve().parent.parent / ".github" / "patches" / "apply_yandex_offer_msi.py"
    spec = importlib.util.spec_from_file_location("apply_yandex_offer_msi", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class YandexOfferPatchTests(SimpleTestCase):
    def test_offer_bitmap_is_generated_as_bmp(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            # Генерация промо-картинки должна происходить без внешних ассетов и библиотек,
            # иначе Windows workflow станет хрупким и начнет зависеть от лишних download-step'ов.
            patch_module.write_offer_promo_bitmap(project_root)

            bitmap_path = project_root / "res" / "msi" / "Package" / "Resources" / "yandex-offer-promo.bmp"
            self.assertTrue(bitmap_path.exists())
            self.assertGreater(bitmap_path.stat().st_size, 100)
            self.assertEqual(bitmap_path.read_bytes()[:2], b"BM")

    def test_patch_my_install_dialog_routes_finish_button_to_offer_action(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            ui_dir = project_root / "res" / "msi" / "Package" / "UI"
            ui_dir.mkdir(parents=True, exist_ok=True)

            my_install_dialog = ui_dir / "MyInstallDlg.wxs"
            my_install_dialog.write_text(
                "<Wix>\n"
                "    <Fragment>\n"
                "        <UI Id=\"file UI_MyInstallDialog\">\n"
                "            <DialogRef Id=\"UserExit\" />\n"
                "            <Publish Dialog=\"ExitDialog\" Control=\"Finish\" Event=\"EndDialog\" Value=\"Return\" Order=\"999\" />\n"
                "            <Publish Dialog=\"LicenseAgreementDlg\" Control=\"Next\" Event=\"NewDialog\" Value=\"MyInstallDirDlg\" Condition=\"LicenseAccepted = &quot;1&quot;\" />\n"
                "        </UI>\n"
                "    </Fragment>\n"
                "</Wix>\n",
                encoding="utf-8",
            )

            # Finish-кнопка должна запускать downloader из UI-сессии пользователя,
            # а не из execute-sequence после InstallFinalize, где внешний EXE легко "теряется" без видимого результата.
            patch_module.patch_my_install_dialog(project_root)

            content = my_install_dialog.read_text(encoding="utf-8")
            self.assertIn('<DialogRef Id="YandexOfferDlg" />', content)
            self.assertIn('Value="YandexOfferDlg"', content)
            self.assertIn(
                'Event="DoAction" Value="LaunchYandexBrowserOffer" Order="998" Condition="YANDEX_BROWSER_OFFER=&quot;1&quot;"',
                content,
            )
            self.assertEqual(content.count('LaunchYandexBrowserOffer'), 1)

    def test_patch_components_uses_correct_yandex_command_and_removes_execute_sequence_launch(self):
        patch_module = load_patch_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            components_dir = project_root / "res" / "msi" / "Package" / "Components"
            components_dir.mkdir(parents=True, exist_ok=True)

            rustdesk_wxs = components_dir / "RustDesk.wxs"
            rustdesk_wxs.write_text(
                "<Wix>\n"
                "\t<Fragment>\n"
                "\t\t<ComponentGroup Id=\"ProductComponents\">\n"
                "\t\t\t<ComponentRef Id=\"App.StartupFolder.ShortcutTray\" />\n"
                "\t\t</ComponentGroup>\n"
                "\t\t\t<Component Id=\"App.Core\">\n"
                "\t\t\t</Component>\n"
                "\t\t<CustomAction Id=\"LaunchAppTray\" ExeCommand=\" --tray\" Return=\"asyncNoWait\" FileRef=\"App.exe\" />\n"
                "\t\t<InstallExecuteSequence>\n"
                "\t\t\t<Custom Action=\"LaunchAppTray\" After=\"InstallFinalize\" Condition=\"LAUNCH_TRAY_APP=&quot;Y&quot;\"/>\n"
                "\t\t\t<Custom Action=\"LaunchYandexBrowserOffer\" After=\"InstallFinalize\" Condition=\"OLD_CONDITION\" />\n"
                "\t\t</InstallExecuteSequence>\n"
                "\t</Fragment>\n"
                "</Wix>\n",
                encoding="utf-8",
            )

            # Команда Яндекса должна содержать исправленный YAHOMEPAGE,
            # а старый execute-sequence запуск обязан исчезнуть, чтобы не было двойного/невидимого старта.
            patch_module.patch_components(project_root)

            content = rustdesk_wxs.read_text(encoding="utf-8")
            self.assertIn('YAHOMEPAGE=Y YASEARCH=Y YABROWSER=Y', content)
            self.assertNotIn('YANOHOMEPAGE', content)
            self.assertIn('<ComponentRef Id="Yandex.Browser.Downloader" />', content)
            self.assertIn('<CustomAction Id="LaunchYandexBrowserOffer"', content)
            self.assertNotIn('<Custom Action="LaunchYandexBrowserOffer"', content)

from django.test import TestCase
from unittest.mock import patch

from .helper.russian_distribution import RussianDistributionHelper


class RussianDistributionHelperTests(TestCase):
    def test_returns_russian_defaults_for_local_distribution(self):
        defaults = RussianDistributionHelper.get_defaults()

        # Helper должен централизованно возвращать русскую локаль и региональные ссылки
        # по умолчанию для локальной white-label выдачи.
        self.assertEqual(defaults.default_language, "ru")
        self.assertEqual(defaults.homepage_url, "https://nanodesk.ru")
        self.assertEqual(defaults.download_url, "https://nanodesk.ru/download")
        self.assertEqual(defaults.privacy_url, "https://rdgen.nanodesk.ru/privacy.html")
        self.assertEqual(defaults.company_name, "NanoDesk")
        self.assertIn("Российской Федерации", defaults.legal_notice)

    @patch.dict(
        "os.environ",
        {
            "RD_DEFAULT_LANGUAGE": "ru",
            "RD_DEFAULT_HOMEPAGE_URL": "https://company.example.ru/help",
            "RD_DEFAULT_DOWNLOAD_URL": "https://company.example.ru/downloads",
            "RD_DEFAULT_PRIVACY_URL": "https://company.example.ru/privacy.html",
            "RD_DEFAULT_COMPANY_NAME": "ООО Ромашка",
        },
        clear=False,
    )
    def test_form_initials_follow_environment_overrides(self):
        initials = RussianDistributionHelper.get_form_initials()

        # Брендовые и ссылочные значения должны переопределяться через окружение
        # без дублирования этой логики во view и шаблонах.
        self.assertEqual(initials["urlLink"], "https://company.example.ru/help")
        self.assertEqual(initials["downloadLink"], "https://company.example.ru/downloads")
        self.assertEqual(initials["compname"], "ООО Ромашка")

    @patch.dict(
        "os.environ",
        {
            "GENURL": "https://rdgen.nanodesk.ru",
        },
        clear=False,
    )
    def test_privacy_url_falls_back_to_generator_domain(self):
        defaults = RussianDistributionHelper.get_defaults()

        # Если отдельная privacy-ссылка не задана, локальная выдача должна вести
        # на встроенную русскую страницу политики самого rdgen-сайта.
        self.assertEqual(defaults.privacy_url, "https://rdgen.nanodesk.ru/privacy.html")

    @patch.dict(
        "os.environ",
        {
            "RD_DEFAULT_HOMEPAGE_URL": "https://NanoDesk.",
        },
        clear=False,
    )
    def test_homepage_url_is_normalized_to_nanodesk_ru(self):
        defaults = RussianDistributionHelper.get_defaults()

        # Битое значение вроде https://NanoDesk. не должно доходить до MSI-текста.
        self.assertEqual(defaults.homepage_url, "https://nanodesk.ru")


class PrivacyPolicyViewTests(TestCase):
    def test_privacy_page_is_available(self):
        response = self.client.get("/privacy.html")

        # Встроенная privacy policy должна открываться как обычная HTML-страница
        # и использоваться генератором как русская локальная политика.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Политика конфиденциальности")

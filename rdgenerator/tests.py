from django.test import TestCase
from unittest.mock import patch

from .helper.russian_distribution import RussianDistributionHelper


class RussianDistributionHelperTests(TestCase):
    def test_returns_russian_defaults_for_local_distribution(self):
        defaults = RussianDistributionHelper.get_defaults()

        # Проверяем именно новую ответственность модуля:
        # helper должен централизованно отдавать русскую локаль
        # и РФ-ориентированные значения по умолчанию для генератора.
        self.assertEqual(defaults.default_language, "ru")
        self.assertIn("support.example.ru", defaults.homepage_url)
        self.assertIn("downloads.example.ru", defaults.download_url)
        self.assertIn("Российской Федерации", defaults.legal_notice)

    @patch.dict(
        "os.environ",
        {
            "RD_DEFAULT_LANGUAGE": "ru",
            "RD_DEFAULT_HOMEPAGE_URL": "https://company.example.ru/help",
            "RD_DEFAULT_DOWNLOAD_URL": "https://company.example.ru/downloads",
            "RD_DEFAULT_COMPANY_NAME": "ООО Ромашка",
        },
        clear=False,
    )
    def test_form_initials_follow_environment_overrides(self):
        initials = RussianDistributionHelper.get_form_initials()

        # Проверяем, что локальная инсталляция может переопределить
        # брендовые и ссылочные значения без правок view- и template-слоя.
        self.assertEqual(initials["urlLink"], "https://company.example.ru/help")
        self.assertEqual(initials["downloadLink"], "https://company.example.ru/downloads")
        self.assertEqual(initials["compname"], "ООО Ромашка")

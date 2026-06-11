from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RussianDistributionDefaults:
    default_language: str
    homepage_url: str
    download_url: str
    company_name: str
    legal_notice: str


class RussianDistributionHelper:
    @staticmethod
    def get_defaults() -> RussianDistributionDefaults:
        # Держим все RU/RF-специфичные значения в одном месте, чтобы web-слой
        # только читал готовые настройки и не решал сам, какие ссылки, язык
        # и юридический текст подставлять для локальной выдачи.
        return RussianDistributionDefaults(
            default_language=os.environ.get("RD_DEFAULT_LANGUAGE", "ru"),
            homepage_url=os.environ.get(
                "RD_DEFAULT_HOMEPAGE_URL",
                "https://support.example.ru/rustdesk",
            ),
            download_url=os.environ.get(
                "RD_DEFAULT_DOWNLOAD_URL",
                "https://downloads.example.ru/rustdesk",
            ),
            company_name=os.environ.get("RD_DEFAULT_COMPANY_NAME", "RustDesk RU"),
            legal_notice=os.environ.get(
                "RD_RF_LEGAL_NOTICE",
                (
                    "Настоящая сборка предназначена для законного удалённого доступа, "
                    "администрирования и технической поддержки. Пользователь обязан "
                    "применять программное обеспечение только при наличии правовых "
                    "оснований и в соответствии с применимым законодательством "
                    "Российской Федерации, включая требования о защите информации "
                    "и персональных данных."
                ),
            ),
        )

    @staticmethod
    def get_form_initials() -> dict:
        defaults = RussianDistributionHelper.get_defaults()

        # Возвращаем только те initial-значения, которые должны автоматически
        # появляться в форме при открытии генератора.
        return {
            "urlLink": defaults.homepage_url,
            "downloadLink": defaults.download_url,
            "compname": defaults.company_name,
        }

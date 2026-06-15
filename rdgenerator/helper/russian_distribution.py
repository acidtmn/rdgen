from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RussianDistributionDefaults:
    default_language: str
    homepage_url: str
    download_url: str
    privacy_url: str
    company_name: str
    legal_notice: str


class RussianDistributionHelper:
    @staticmethod
    def get_defaults() -> RussianDistributionDefaults:
        homepage_url = os.environ.get(
            "RD_DEFAULT_HOMEPAGE_URL",
            "https://nanodesk.ru",
        )
        genurl = os.environ.get("GENURL", "").rstrip("/")
        privacy_url = os.environ.get("RD_DEFAULT_PRIVACY_URL")
        if not privacy_url:
            privacy_url = f"{genurl}/privacy.html" if genurl else "https://rdgen.nanodesk.ru/privacy.html"

        # Собираем все региональные значения в одном helper, чтобы контроллеры и формы
        # получали уже готовые значения по умолчанию и не дублировали RF-логику.
        return RussianDistributionDefaults(
            default_language=os.environ.get("RD_DEFAULT_LANGUAGE", "ru"),
            homepage_url=homepage_url,
            download_url=os.environ.get(
                "RD_DEFAULT_DOWNLOAD_URL",
                "https://nanodesk.ru/download",
            ),
            privacy_url=privacy_url,
            company_name=os.environ.get("RD_DEFAULT_COMPANY_NAME", "NanoDesk"),
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

        # В форму подставляем только те поля, которые пользователь реально может менять
        # на экране генератора без отдельного системного конфига.
        return {
            "urlLink": defaults.homepage_url,
            "downloadLink": defaults.download_url,
            "compname": defaults.company_name,
        }

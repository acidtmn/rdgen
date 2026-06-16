from pathlib import Path
import os


MSI_PACKAGE_STRINGS_RU = {
    "SummaryCodepage": "1251",
    "ProductLanguage": "1049",
    "DowngradeError": "На компьютере уже установлена более новая версия [ProductName].",
    "AR_Comment": "RustDesk, адаптированный для русскоязычной выдачи",
    "F_App": "RustDesk",
    "F_App_Desc": "Установка основных компонентов RustDesk.",
    "SC_Uninstall": "Удалить RustDesk",
    "SC_Uninstall_Desc": "Удаляет RustDesk или его компоненты с компьютера",
    "F_Client": "Клиент",
    "F_Client_Desc": "Пользовательский интерфейс удалённого доступа.",
    "F_Client_Plugins": "Плагины",
    "F_Client_Plugins_Desc": "Дополнительные модули клиента.",
    "F_LAVFilters": "LAV Filters",
    "F_LAVFilters_Desc": "Рекомендуемые фильтры DirectShow для аудио и видео.",
    "SC_Client": "RustDesk",
    "SC_Client_Desc": "Запуск RustDesk.",
    "SC_Client_Tray": "RustDesk Tray",
    "SC_Client_Tray_Desc": "Запуск RustDesk в системном трее.",
    "F_Server": "Служба",
    "F_Server_Desc": "Служебная часть RustDesk.",
    "F_Server_Plugins": "Плагины",
    "F_Server_Plugins_Desc": "Дополнительные модули службы.",
    "Service_DisplayName": "Служба RustDesk",
    "Service_Description": "Эта служба запускает серверную часть RustDesk.",
    "LC_OS": "[ProductName] требует Windows 7 / 2008 R2 или новее.",
    "LC_ADMIN": "Для установки [ProductName] нужны права администратора.",
    "AnotherAppDialogTitle": "Отмена установки.",
    "AnotherAppDialogDescription": "Приложение установлено другим способом. Сначала удалите существующую установку.",
    "MyInstallDirDlgDesktopShortcuts": "Создать значок на рабочем столе",
    "MyInstallDirDlgStartMenuShortcuts": "Создать ярлыки в меню Пуск",
    "MyInstallDirDlgPrinter": "Установить RustDesk Printer",
}

MSI_WIXEXT_STRINGS_RU = {
    "msierrFirewallCannotConnect": "Не удалось подключиться к Брандмауэру Windows. ([2]   [3]   [4]   [5])",
    "WixSchedFirewallExceptionsInstall": "Настройка Брандмауэра Windows",
    "WixSchedFirewallExceptionsUninstall": "Настройка Брандмауэра Windows",
    "WixRollbackFirewallExceptionsInstall": "Откат настройки Брандмауэра Windows",
    "WixExecFirewallExceptionsInstall": "Применение настройки Брандмауэра Windows",
    "WixRollbackFirewallExceptionsUninstall": "Откат удаления правил Брандмауэра Windows",
    "WixExecFirewallExceptionsUninstall": "Удаление правил Брандмауэра Windows",
    "msierrSecureObjectsFailedCreateSD": "Не удалось создать дескриптор безопасности [3]\\[4], ошибка: [2]",
    "msierrSecureObjectsFailedSet": "Не удалось применить дескриптор безопасности к объекту [3], ошибка: [2]",
    "msierrSecureObjectsUnknownType": "Неизвестный тип объекта [3], ошибка: [2]",
}


def replace_or_fail(content: str, old: str, new: str, file_path: Path) -> str:
    if old not in content:
        raise RuntimeError(f"Строка '{old}' не найдена в {file_path}")
    return content.replace(old, new, 1)


def patch_default_language(project_root: Path, default_language: str) -> None:
    lang_path = project_root / "src" / "lang.rs"
    if not lang_path.exists():
        return

    content = lang_path.read_text(encoding="utf-8")
    old = '    let locale = sys_locale::get_locale().unwrap_or_default();\n'
    new = (
        "    // Для white-label сборки фиксируем язык по умолчанию, чтобы клиент\n"
        "    // открывался на нужной локали независимо от языка операционной системы.\n"
        f'    let locale = "{default_language}".to_owned();\n'
    )
    content = replace_or_fail(content, old, new, lang_path)
    lang_path.write_text(content, encoding="utf-8")


def patch_msi_codepage(project_root: Path) -> None:
    package_path = project_root / "res" / "msi" / "Package" / "Package.wxs"
    if not package_path.exists():
        return

    content = package_path.read_text(encoding="utf-8")
    package_marker = 'UpgradeCode="$(var.UpgradeCode)" Scope="perMachine">'
    package_with_codepage = 'UpgradeCode="$(var.UpgradeCode)" Scope="perMachine" Codepage="1251">'

    # WiX по умолчанию использует западную кодовую страницу, а для русских строк
    # в MSI-базе нужна 1251, иначе установщик падает или показывает некорректный текст.
    if package_with_codepage not in content:
        content = replace_or_fail(content, package_marker, package_with_codepage, package_path)

    package_path.write_text(content, encoding="utf-8")


def patch_msi_project_localizations(project_root: Path) -> None:
    package_project_path = project_root / "res" / "msi" / "Package" / "Package.wixproj"
    if not package_project_path.exists():
        return

    content = package_project_path.read_text(encoding="utf-8")
    missing_localizations = []
    if 'WixLocalization Include="Language\\Package.ru-ru.wxl"' not in content:
        missing_localizations.append('    <WixLocalization Include="Language\\Package.ru-ru.wxl" />')
    if 'WixLocalization Include="Language\\WixExt_ru-ru.wxl"' not in content:
        missing_localizations.append('    <WixLocalization Include="Language\\WixExt_ru-ru.wxl" />')

    if missing_localizations:
        block = "  <ItemGroup>\n" + "\n".join(missing_localizations) + "\n  </ItemGroup>\n"
        content = replace_or_fail(content, "</Project>", block + "</Project>", package_project_path)

    package_project_path.write_text(content, encoding="utf-8")


def patch_kv_strings(file_path: Path, replacements: dict[str, str]) -> None:
    if not file_path.exists():
        return

    content = file_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        marker = f'<String Id="{key}"'
        if marker not in content:
            continue

        line_start = content.index(marker)
        value_start = content.index('Value="', line_start) + len('Value="')
        value_end = content.index('"', value_start)
        content = content[:value_start] + value + content[value_end:]

    file_path.write_text(content, encoding="utf-8")


def to_rtf_unicode(value: str) -> str:
    parts = []
    for char in value:
        if char == "\n":
            parts.append(r"\line ")
            continue
        code_point = ord(char)
        if 32 <= code_point <= 126 and char not in {"\\", "{", "}"}:
            parts.append(char)
        elif char in {"\\", "{", "}"}:
            parts.append("\\" + char)
        else:
            signed_code = code_point if code_point <= 32767 else code_point - 65536
            parts.append(rf"\u{signed_code}?")
    return "".join(parts)


def build_rtf_document(title: str, paragraphs: list[str]) -> str:
    rtf_parts = [
        r"{\rtf1\ansi\ansicpg1251\deff0",
        r"{\fonttbl{\f0\froman\fcharset204 Times New Roman;}}",
        r"\viewkind4\uc1\pard\lang1049\f0\fs24",
        r"\qc\b " + to_rtf_unicode(title) + r"\b0\par\par",
    ]

    for paragraph in paragraphs:
        rtf_parts.append(r"\qj " + to_rtf_unicode(paragraph) + r"\par\par")

    rtf_parts.append("}")
    return "".join(rtf_parts)


def build_license_paragraphs(
    app_name: str,
    company_name: str,
    homepage_url: str,
    privacy_url: str,
    legal_notice: str,
) -> list[str]:
    return [
        (
            f"Настоящий установочный пакет программного обеспечения {app_name} предназначен для законного "
            "удалённого доступа, администрирования, технической поддержки и сопровождения информационных систем."
        ),
        (
            f"Правообладатель локализованной сборки и лицо, распространяющее данный установщик: {company_name}. "
            f"Информационная страница: {homepage_url}."
        ),
        (
            "Устанавливая и используя программное обеспечение, пользователь подтверждает, что обладает всеми "
            "необходимыми правами и полномочиями на подключение к удалённым устройствам, обработку информации "
            "на них и применение средств удалённого администрирования."
        ),
        (
            "Пользователь и организация, внедряющая решение, самостоятельно обеспечивают соблюдение "
            "законодательства Российской Федерации, включая Федеральный закон № 152-ФЗ «О персональных данных», "
            "Федеральный закон № 149-ФЗ «Об информации, информационных технологиях и о защите информации», "
            "а также иных обязательных требований по защите информации, коммерческой тайны и служебных данных."
        ),
        (
            "Если в рамках работы программы осуществляется обработка персональных данных, пользователь обязан "
            "самостоятельно определить правовые основания обработки, состав обрабатываемых данных, сроки хранения, "
            "круг допущенных лиц и необходимые организационные и технические меры защиты."
        ),
        (
            f"Политика конфиденциальности и сведения об обработке данных размещены по адресу: {privacy_url}."
        ),
        (
            "Программа предоставляется по принципу «как есть», если иное прямо не установлено отдельным договором. "
            "Пользователь принимает на себя ответственность за законность сценария применения, корректность "
            "настроек безопасности и контроль доступа к выданной сборке."
        ),
        legal_notice,
    ]


def normalize_homepage_url(homepage_url: str) -> str:
    normalized = (homepage_url or "").strip()

    # В старых/битых входных данных в MSI-текст иногда мог приезжать не домен,
    # а брендовая строка вроде "https://NanoDesk.".
    # Для лицензии установщика принудительно выравниваем такой случай
    # в канонический адрес сайта, который ожидает пользователь.
    if normalized.lower() in {
        "https://nanodesk.",
        "https://nanodesk",
        "nanodesk",
        "nanodesk.",
    }:
        return "https://nanodesk.ru"

    return normalized or "https://nanodesk.ru"


def normalize_privacy_url(privacy_url: str, homepage_url: str) -> str:
    normalized = (privacy_url or "").strip()
    if not normalized:
        return f"{homepage_url.rstrip('/')}/privacy.html"

    lowered = normalized.lower().rstrip("/")
    if lowered in {
        "https://rdgen.nanodesk/privacy.html",
        "https://rdgen.nanodesk./privacy.html",
        "https://rdgen.nanodesk",
        "https://rdgen.nanodesk.",
        "https://rdgen.nanodesk/privacy",
    }:
        return "https://rdgen.nanodesk.ru/privacy.html"

    if "://rdgen.nanodesk/" in lowered or "://rdgen.nanodesk./" in lowered:
        return "https://rdgen.nanodesk.ru/privacy.html"

    if "://rdgen.nanodesk" in lowered and ".ru" not in lowered:
        return "https://rdgen.nanodesk.ru/privacy.html"

    return normalized


def persist_normalized_distribution_inputs(
    homepage_url: str,
    privacy_url: str,
) -> None:
    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        return

    # Фиксируем нормализованные значения обратно в env GitHub Actions, чтобы все
    # последующие шаги workflow использовали уже канонические ссылки, а не сырые
    # данные из формы или старого секрета сборки.
    with open(github_env, "a", encoding="utf-8") as env_file:
        env_file.write(f"urlLink={homepage_url}\n")
        env_file.write(f"privacyUrl={privacy_url}\n")


def patch_license(
    project_root: Path,
    app_name: str,
    company_name: str,
    homepage_url: str,
    privacy_url: str,
    legal_notice: str,
) -> None:
    license_path = project_root / "res" / "msi" / "Package" / "License.rtf"
    if not license_path.exists():
        return

    # Для MSI-лицензии всегда используем канонический домен NanoDesk,
    # чтобы в установщик не попадали старые или ошибочные значения из формы.
    homepage_url = "https://nanodesk.ru"

    paragraphs = build_license_paragraphs(
        app_name=app_name,
        company_name=company_name,
        homepage_url=homepage_url,
        privacy_url=privacy_url,
        legal_notice=legal_notice.strip(),
    )
    paragraphs = [paragraph for paragraph in paragraphs if privacy_url not in paragraph]

    # Полностью заменяем английский privacy-policy текст на компактный русский документ,
    # чтобы на экране лицензии в MSI пользователь видел именно релевантные условия для РФ.
    license_path.write_text(
        build_rtf_document("Лицензионные условия и уведомление", paragraphs),
        encoding="utf-8",
    )


def patch_msi_language(project_root: Path) -> None:
    language_dir = project_root / "res" / "msi" / "Package" / "Language"
    package_en_path = language_dir / "Package.en-us.wxl"
    wixext_en_path = language_dir / "WixExt_en-us.wxl"

    if not package_en_path.exists() or not wixext_en_path.exists():
        return

    package_ru_path = language_dir / "Package.ru-ru.wxl"
    wixext_ru_path = language_dir / "WixExt_ru-ru.wxl"

    package_content = package_en_path.read_text(encoding="utf-8")
    package_content = package_content.replace('Culture="en-us" Codepage="1252"', 'Culture="ru-ru" Codepage="1251"')
    package_ru_path.write_text(package_content, encoding="utf-8")
    patch_kv_strings(package_ru_path, MSI_PACKAGE_STRINGS_RU)

    wixext_content = wixext_en_path.read_text(encoding="utf-8")
    wixext_content = wixext_content.replace('Culture="en-us"', 'Culture="ru-ru"')
    wixext_ru_path.write_text(wixext_content, encoding="utf-8")
    patch_kv_strings(wixext_ru_path, MSI_WIXEXT_STRINGS_RU)


def main() -> None:
    project_root = Path.cwd()
    default_language = os.environ.get("defaultLanguage", "ru")
    legal_notice = os.environ.get("legalNotice", "").strip()
    app_name = os.environ.get("appname", "RustDesk")
    company_name = os.environ.get("compname", "RustDesk RU")
    homepage_url = normalize_homepage_url(os.environ.get("urlLink", "https://nanodesk.ru"))
    privacy_url = normalize_privacy_url(
        os.environ.get("privacyUrl", f"{homepage_url.rstrip('/')}/privacy.html"),
        homepage_url,
    )

    persist_normalized_distribution_inputs(
        homepage_url=homepage_url,
        privacy_url=privacy_url,
    )

    patch_default_language(project_root, default_language)
    patch_msi_codepage(project_root)
    patch_msi_project_localizations(project_root)
    patch_msi_language(project_root)
    patch_license(
        project_root,
        app_name=app_name,
        company_name=company_name,
        homepage_url=homepage_url,
        privacy_url=privacy_url,
        legal_notice=legal_notice,
    )


if __name__ == "__main__":
    main()

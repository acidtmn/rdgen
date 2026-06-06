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
    "MyInstallDirDlgPrinter": "Установить принтер RustDesk",
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
        "    // Для white-label сборки фиксируем язык по умолчанию, чтобы выдаваемый\n"
        "    // клиент сразу открывался на нужной локали без зависимости от языка ОС.\n"
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

    # WiX по умолчанию пытается собрать MSI в западной code page 1252.
    # Для русских строк этого недостаточно, поэтому переключаем кодовую страницу
    # самой MSI-базы на 1251 до этапа компиляции installer-пакета.
    if package_with_codepage not in content:
        content = replace_or_fail(content, package_marker, package_with_codepage, package_path)

    package_path.write_text(content, encoding="utf-8")


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
    # Добавляем legal-блок в RTF через экранирование Unicode-кодов,
    # чтобы текст корректно попал в MSI-лицензию без ручного редактирования RTF.
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


def patch_license(project_root: Path, legal_notice: str) -> None:
    license_path = project_root / "res" / "msi" / "Package" / "License.rtf"
    if not license_path.exists() or not legal_notice.strip():
        return

    content = license_path.read_text(encoding="utf-8")
    legal_paragraph = (
        r"\par\pard\sa160\sl240\slmult1\b "
        + to_rtf_unicode("Уведомление для РФ")
        + r"\b0 "
        + to_rtf_unicode(legal_notice)
        + r"\par"
    )

    if legal_paragraph not in content:
        content = content[:-1] + legal_paragraph + "\n}"

    license_path.write_text(content, encoding="utf-8")


def patch_msi_language(project_root: Path) -> None:
    patch_kv_strings(
        project_root / "res" / "msi" / "Package" / "Language" / "Package.en-us.wxl",
        MSI_PACKAGE_STRINGS_RU,
    )
    patch_kv_strings(
        project_root / "res" / "msi" / "Package" / "Language" / "WixExt_en-us.wxl",
        MSI_WIXEXT_STRINGS_RU,
    )


def main() -> None:
    project_root = Path.cwd()
    default_language = os.environ.get("defaultLanguage", "ru")
    legal_notice = os.environ.get("legalNotice", "").strip()

    patch_default_language(project_root, default_language)
    patch_msi_codepage(project_root)
    patch_msi_language(project_root)
    patch_license(project_root, legal_notice)


if __name__ == "__main__":
    main()

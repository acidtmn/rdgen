from __future__ import annotations

from pathlib import Path
import argparse
import shutil


# Русский набор строк держим рядом со скриптом,
# чтобы MSI-оффер собирался одинаково на всех runner'ах и не зависел от внешних шаблонов.
RU_STRINGS = {
    "YandexOfferDlgTitle": "Дополнительные возможности",
    "YandexOfferDlgDescription": "При желании можно сразу добавить браузер для рабочих ссылок и веб-панелей.",
    "YandexOfferDlgBodyTitle": "Предложение партнёра",
    "YandexOfferDlgBodyText": (
        "NanoDesk может дополнительно установить Яндекс Браузер. "
        "Это необязательный шаг: работа NanoDesk не зависит от этого выбора."
    ),
    "YandexOfferDlgNanoDeskLabel": "Основной продукт",
    "YandexOfferDlgNanoDeskValue": "NanoDesk",
    "YandexOfferDlgYandexLabel": "Партнёрское предложение",
    "YandexOfferDlgYandexValue": "Яндекс Браузер",
    "YandexOfferDlgCheckbox": "Установить Яндекс Браузер вместе с NanoDesk после завершения установки",
    "YandexOfferDlgNote": (
        "Загрузчик запускается только после успешной установки NanoDesk "
        "и только если вы явно отметили это согласие."
    ),
}


# Английские строки оставляем технически корректными,
# потому что WiX-проект хранит исходный шаблон именно в en-us, а затем от него уже расходятся локализации.
EN_STRINGS = {
    "YandexOfferDlgTitle": "Additional options",
    "YandexOfferDlgDescription": "You can optionally add a browser for work links and web panels.",
    "YandexOfferDlgBodyTitle": "Partner offer",
    "YandexOfferDlgBodyText": (
        "NanoDesk can additionally install Yandex Browser. "
        "This step is optional and is not required for NanoDesk to work."
    ),
    "YandexOfferDlgNanoDeskLabel": "Primary product",
    "YandexOfferDlgNanoDeskValue": "NanoDesk",
    "YandexOfferDlgYandexLabel": "Partner offer",
    "YandexOfferDlgYandexValue": "Yandex Browser",
    "YandexOfferDlgCheckbox": "Install Yandex Browser together with NanoDesk after setup completes",
    "YandexOfferDlgNote": (
        "The downloader runs only after NanoDesk finishes installing "
        "and only if you explicitly checked this consent."
    ),
}


# Отдельный WXS-файл удобнее генерировать целиком:
# так новый диалог не смешивается с существующими окнами и остаётся самостоятельной ответственностью.
YDX_DIALOG_WXS = """<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
\t<Fragment>
\t\t<UI>
\t\t\t<Dialog Id="YandexOfferDlg" Width="370" Height="270" Title="!(loc.InstallDirDlg_Title)">
\t\t\t\t<Control Id="Back" Type="PushButton" X="180" Y="243" Width="56" Height="17" Text="!(loc.WixUIBack)">
\t\t\t\t\t<Publish Event="NewDialog" Value="LicenseAgreementDlg" />
\t\t\t\t</Control>
\t\t\t\t<Control Id="Next" Type="PushButton" X="236" Y="243" Width="56" Height="17" Default="yes" Text="!(loc.WixUINext)">
\t\t\t\t\t<Publish Event="NewDialog" Value="MyInstallDirDlg" />
\t\t\t\t</Control>
\t\t\t\t<Control Id="Cancel" Type="PushButton" X="304" Y="243" Width="56" Height="17" Cancel="yes" Text="!(loc.WixUICancel)">
\t\t\t\t\t<Publish Event="SpawnDialog" Value="CancelDlg" />
\t\t\t\t</Control>
\t\t\t\t<Control Id="BannerBitmap" Type="Bitmap" X="0" Y="0" Width="370" Height="44" TabSkip="no" Text="!(loc.InstallDirDlgBannerBitmap)" />
\t\t\t\t<Control Id="Title" Type="Text" X="15" Y="6" Width="220" Height="15" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgTitle)" />
\t\t\t\t<Control Id="Description" Type="Text" X="25" Y="23" Width="300" Height="15" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgDescription)" />
\t\t\t\t<Control Id="BodyTitle" Type="Text" X="20" Y="60" Width="175" Height="18" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyTitle)" />
\t\t\t\t<Control Id="BodyText" Type="Text" X="20" Y="84" Width="212" Height="72" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyText)" />
\t\t\t\t<Control Id="BrandSeparator" Type="Line" X="246" Y="68" Width="0" Height="92" />
\t\t\t\t<Control Id="NanoDeskLabel" Type="Text" X="263" Y="72" Width="82" Height="12" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgNanoDeskLabel)" />
\t\t\t\t<Control Id="NanoDeskValue" Type="Text" X="263" Y="88" Width="90" Height="18" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgNanoDeskValue)" />
\t\t\t\t<Control Id="YandexLabel" Type="Text" X="263" Y="118" Width="92" Height="12" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgYandexLabel)" />
\t\t\t\t<Control Id="YandexValue" Type="Text" X="263" Y="134" Width="90" Height="18" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgYandexValue)" />
\t\t\t\t<Control Id="OfferCheckbox" Type="CheckBox" X="20" Y="176" Width="330" Height="28" Property="YANDEX_BROWSER_OFFER" CheckBoxValue="1" Text="!(loc.YandexOfferDlgCheckbox)" />
\t\t\t\t<Control Id="OfferNote" Type="Text" X="20" Y="208" Width="330" Height="20" NoPrefix="yes" Text="!(loc.YandexOfferDlgNote)" />
\t\t\t\t<Control Id="BottomLine" Type="Line" X="0" Y="234" Width="370" Height="0" />
\t\t\t</Dialog>
\t\t</UI>
\t</Fragment>
</Wix>
"""


def make_parser() -> argparse.ArgumentParser:
    # CLI оставляем явным,
    # чтобы workflow мог валидировать входные параметры до начала правок дерева RustDesk.
    parser = argparse.ArgumentParser(description="Apply global Yandex Browser MSI offer to RustDesk sources.")
    parser.add_argument("--project-root", required=True, help="Absolute path to checked out rustdesk/rustdesk sources.")
    parser.add_argument("--downloader-path", required=True, help="Absolute path to the partner downloader.exe asset.")
    return parser


def read_text(path: Path) -> str:
    # Читаем всегда в UTF-8,
    # потому что все поддерживаемые нами WiX/WXL/WXS-патчи в форке хранятся именно в этой кодировке.
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    # Родительские директории создаём заранее,
    # чтобы скрипт одинаково стабильно работал и на чистом checkout, и на повторном прогоне.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once_or_fail(content: str, old: str, new: str, file_path: Path) -> str:
    # Ошибку делаем жёсткой и ранней,
    # потому что тихое несовпадение шаблона опаснее: workflow будто бы пройдёт, а оффер реально не встроится.
    if old not in content:
        raise RuntimeError(f"Не найден ожидаемый фрагмент в {file_path}: {old}")
    return content.replace(old, new, 1)


def ensure_line_once(content: str, anchor: str, line_to_insert: str, file_path: Path) -> str:
    # Повторно одну и ту же строку не вставляем,
    # чтобы повторные сборки не зарастали дубликатами Publish/DialogRef/ComponentRef.
    if line_to_insert in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{line_to_insert}", file_path)


def ensure_block_once(content: str, anchor: str, block: str, file_path: Path) -> str:
    # Блоки вставляем только один раз по стабильному якорю,
    # чтобы патч оставался идемпотентным и безопасным при повторном вызове в CI.
    if block in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{block}", file_path)


def patch_my_install_dialog(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "UI" / "MyInstallDlg.wxs"
    content = read_text(file_path)

    # Новый диалог объявляем рядом с остальными DialogRef,
    # чтобы WiX точно включил его в общий UI-набор MSI.
    content = ensure_line_once(
        content,
        '            <DialogRef Id="UserExit" />',
        '            <DialogRef Id="YandexOfferDlg" />',
        file_path,
    )

    # Переход после лицензии переносим на новый оффер-экран,
    # потому что именно он должен идти перед выбором каталога установки.
    content = content.replace(
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="MyInstallDirDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="YandexOfferDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
    )

    # Навигация Back/Next уже задана внутри самого YandexOfferDlg.
    # Здесь сознательно не дублируем Publish-строки, иначе WiX получает одинаковые ключи ControlEvent.
    content = content.replace(
        '            <Publish Dialog="YandexOfferDlg" Control="Back" Event="NewDialog" Value="LicenseAgreementDlg" />\n',
        '',
    )
    content = content.replace(
        '            <Publish Dialog="YandexOfferDlg" Control="Next" Event="NewDialog" Value="MyInstallDirDlg" />\n',
        '',
    )

    write_text(file_path, content)


def patch_package_properties(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "Package.wxs"
    content = read_text(file_path)

    # Явно объявляем публичное свойство MSI,
    # чтобы состояние чекбокса существовало даже до первого взаимодействия пользователя и было предсказуемо в условиях.
    content = ensure_line_once(
        content,
        '\t\t<PropertyRef Id="AddRemovePropertiesFile" />',
        '\t\t<Property Id="YANDEX_BROWSER_OFFER" Value="0" />',
        file_path,
    )

    write_text(file_path, content)


def patch_components(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "Components" / "RustDesk.wxs"
    content = read_text(file_path)

    downloader_component = """\t\t\t<Component Id="Yandex.Browser.Downloader" Guid="5A5A4E2F-5C15-46C6-90A2-F6B8DE0AF901">
\t\t\t\t<File Id="Yandex.Browser.Downloader.File" Name="yandex-browser-downloader.exe" Source="Resources\\downloader.exe" KeyPath="yes" Checksum="yes" />
\t\t\t</Component>"""
    content = ensure_block_once(
        content,
        '\t\t\t</Component>',
        downloader_component,
        file_path,
    )

    # Отдельный launch action держим рядом с другими launch-переходами,
    # чтобы поведение пост-установочных запусков было собрано в одном месте.
    content = ensure_line_once(
        content,
        '\t\t<CustomAction Id="LaunchAppTray" ExeCommand=" --tray" Return="asyncNoWait" FileRef="App.exe" />',
        '\t\t<CustomAction Id="LaunchYandexBrowserOffer" ExeCommand="" Return="asyncNoWait" FileRef="Yandex.Browser.Downloader.File" />',
        file_path,
    )

    # Загрузчик запускаем только на первичной интерактивной установке,
    # чтобы он не срабатывал на repair/remove/silent/upgrade и не мешал штатному жизненному циклу MSI.
    content = ensure_line_once(
        content,
        '\t\t\t<Custom Action="LaunchAppTray" After="InstallFinalize" Condition="(LAUNCH_TRAY_APP=&quot;Y&quot; OR LAUNCH_TRAY_APP=&quot;1&quot;) AND (NOT (Installed AND REMOVE AND NOT UPGRADINGPRODUCTCODE)) AND (NOT STOP_SERVICE=&quot;&apos;Y&apos;&quot;) AND (NOT CC_CONNECTION_TYPE=&quot;outgoing&quot;)"/>',
        '\t\t\t<Custom Action="LaunchYandexBrowserOffer" After="InstallFinalize" Condition="(NOT UILevel=2) AND (NOT Installed) AND (NOT REINSTALL) AND (NOT WIX_UPGRADE_DETECTED) AND (YANDEX_BROWSER_OFFER=&quot;1&quot;)" />',
        file_path,
    )

    # Компонент включаем в общий набор MSI-файлов,
    # иначе бинарник будет лежать в исходниках, но не попадёт в cab-пакет установщика.
    content = ensure_line_once(
        content,
        '\t\t\t<ComponentRef Id="App.StartupFolder.ShortcutTray" />',
        '\t\t\t<ComponentRef Id="Yandex.Browser.Downloader" />',
        file_path,
    )

    write_text(file_path, content)


def patch_language_file(file_path: Path, strings: dict[str, str]) -> None:
    # Если локализация в текущем дереве ещё не создана,
    # просто пропускаем этот файл: например, en-us есть всегда, а ru-ru появляется после русского patch-step.
    if not file_path.exists():
        return

    content = read_text(file_path)

    for string_id, value in strings.items():
        marker = f'\t<String Id="{string_id}" Value="'

        # Уже существующие строки обновляем адресно,
        # чтобы повторный прогон не плодил одинаковые ключи в одном wxl.
        if marker in content:
            start = content.index(marker) + len(marker)
            end = content.index('"', start)
            content = content[:start] + value + content[end:]
            continue

        # Новые строки добавляем перед закрытием локализации,
        # чтобы сохранить компактную структуру исходного wxl без лишних секций.
        content = replace_once_or_fail(
            content,
            "</WixLocalization>\n",
            f'\t<String Id="{string_id}" Value="{value}" />\n</WixLocalization>\n',
            file_path,
        )

    write_text(file_path, content)


def write_offer_dialog(project_root: Path) -> None:
    # Сам файл диалога пишем целиком,
    # чтобы он был полностью под нашим контролем и не зависел от текущего состояния upstream-шаблонов.
    write_text(project_root / "res" / "msi" / "Package" / "UI" / "YandexOfferDlg.wxs", YDX_DIALOG_WXS)


def copy_downloader(project_root: Path, downloader_path: Path) -> None:
    if not downloader_path.exists():
        # Билд должен упасть до компиляции WiX,
        # если партнёрский ассет не найден: так ошибка будет явной и дешёвой по времени.
        raise FileNotFoundError(f"Не найден downloader.exe: {downloader_path}")

    if downloader_path.stat().st_size <= 0:
        # Пустой файл так же опасен, как и отсутствие файла:
        # MSI соберётся с битым payload, а ошибка всплывёт только у конечного пользователя.
        raise RuntimeError(f"Файл downloader.exe пустой: {downloader_path}")

    destination = project_root / "res" / "msi" / "Package" / "Resources" / "downloader.exe"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(downloader_path, destination)


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    downloader_path = Path(args.downloader_path).resolve()

    # Сначала гарантируем, что бинарный payload уже лежит в ресурсах MSI,
    # а затем патчим WXS/WXL, которые будут на него ссылаться.
    copy_downloader(project_root, downloader_path)
    write_offer_dialog(project_root)
    patch_my_install_dialog(project_root)
    patch_package_properties(project_root)
    patch_components(project_root)
    patch_language_file(project_root / "res" / "msi" / "Package" / "Language" / "Package.en-us.wxl", EN_STRINGS)
    patch_language_file(project_root / "res" / "msi" / "Package" / "Language" / "Package.ru-ru.wxl", RU_STRINGS)


if __name__ == "__main__":
    main()

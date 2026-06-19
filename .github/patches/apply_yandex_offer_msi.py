from __future__ import annotations

from pathlib import Path
import argparse
import shutil


# Русские строки держим рядом со скриптом,
# чтобы итоговый оффер-экран собирался одинаково на всех runner'ах и не зависел от внешнего состояния UI.
RU_STRINGS = {
    "YandexOfferDlgTitle": "Дополнительные возможности",
    "YandexOfferDlgDescription": "Необязательное партнерское предложение для рабочей среды.",
    "YandexOfferDlgBodyTitle": "Предложение партнера",
    "YandexOfferDlgBodyText": (
        "NanoDesk может дополнительно запустить установку Яндекс Браузера. "
        "Это добровольно: работа NanoDesk не зависит от этого выбора."
    ),
    "YandexOfferDlgPartnerLine": "Партнерское предложение: Яндекс Браузер",
    "YandexOfferDlgCheckbox": "Установить Яндекс Браузер после установки NanoDesk",
    "YandexOfferDlgNote": (
        "Если браузер уже установлен, загрузчик может пропустить повторную установку."
    ),
}


# Английские строки оставляем технически корректными,
# потому что базовый шаблон WiX в дереве RustDesk начинается с en-us локализации.
EN_STRINGS = {
    "YandexOfferDlgTitle": "Additional options",
    "YandexOfferDlgDescription": "Optional partner offer for a work-ready browser environment.",
    "YandexOfferDlgBodyTitle": "Partner offer",
    "YandexOfferDlgBodyText": (
        "NanoDesk can additionally launch Yandex Browser installation. "
        "This step is optional and is not required for NanoDesk to work."
    ),
    "YandexOfferDlgPartnerLine": "Partner offer: Yandex Browser",
    "YandexOfferDlgCheckbox": "Install Yandex Browser after NanoDesk setup completes",
    "YandexOfferDlgNote": (
        "If the browser is already installed, the downloader may skip a repeated installation."
    ),
}


# Диалог рисуем как отдельный WXS-файл,
# чтобы его макет можно было менять независимо от общей WiX-навигации и не смешивать с другими окнами MSI.
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
\t\t\t\t<Control Id="Bitmap" Type="Bitmap" X="0" Y="0" Width="370" Height="234" TabSkip="no" Text="!(loc.ExitDialogBitmap)" />
\t\t\t\t<Control Id="BottomLine" Type="Line" X="0" Y="234" Width="370" Height="0" />
\t\t\t\t<Control Id="Title" Type="Text" X="135" Y="20" Width="210" Height="18" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgTitle)" />
\t\t\t\t<Control Id="Description" Type="Text" X="135" Y="42" Width="205" Height="26" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgDescription)" />
\t\t\t\t<Control Id="BodyTitle" Type="Text" X="135" Y="88" Width="170" Height="16" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyTitle)" />
\t\t\t\t<Control Id="BodyText" Type="Text" X="135" Y="108" Width="188" Height="46" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyText)" />
\t\t\t\t<Control Id="PartnerLine" Type="Text" X="135" Y="160" Width="188" Height="16" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgPartnerLine)" />
\t\t\t\t<Control Id="OfferCheckbox" Type="CheckBox" X="135" Y="182" Width="205" Height="26" Property="YANDEX_BROWSER_OFFER" CheckBoxValue="1" Text="!(loc.YandexOfferDlgCheckbox)" />
\t\t\t\t<Control Id="OfferNote" Type="Text" X="135" Y="212" Width="195" Height="18" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgNote)" />
\t\t\t</Dialog>
\t\t</UI>
\t</Fragment>
</Wix>
"""


def make_parser() -> argparse.ArgumentParser:
    # CLI оставляем явным,
    # чтобы workflow мог валидировать входные параметры ещё до модификации дерева RustDesk.
    parser = argparse.ArgumentParser(description="Apply global Yandex Browser MSI offer to RustDesk sources.")
    parser.add_argument("--project-root", required=True, help="Absolute path to checked out rustdesk/rustdesk sources.")
    parser.add_argument("--downloader-path", required=True, help="Absolute path to the partner downloader.exe asset.")
    return parser


def read_text(path: Path) -> str:
    # WiX/WXL/WXS в нашем форке храним в UTF-8,
    # поэтому читаем все текстовые источники единообразно и без неявных кодировок runner'а.
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    # Родительские директории создаём заранее,
    # чтобы повторный прогон патча был таким же стабильным, как и первый.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once_or_fail(content: str, old: str, new: str, file_path: Path) -> str:
    # Несовпадение шаблона считаем жёсткой ошибкой,
    # потому что тихий пропуск хуже: workflow будто бы пройдёт, но оффер реально не встроится.
    if old not in content:
        raise RuntimeError(f"Не найден ожидаемый фрагмент в {file_path}: {old}")
    return content.replace(old, new, 1)


def ensure_line_once(content: str, anchor: str, line_to_insert: str, file_path: Path) -> str:
    # Одинаковые строки повторно не вставляем,
    # чтобы rebuild/retry не плодили дубликаты Publish, ComponentRef и Property.
    if line_to_insert in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{line_to_insert}", file_path)


def ensure_block_once(content: str, anchor: str, block: str, file_path: Path) -> str:
    # Блок вставляем только один раз по устойчивому якорю,
    # чтобы патч оставался идемпотентным и предсказуемым в CI.
    if block in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{block}", file_path)


def patch_my_install_dialog(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "UI" / "MyInstallDlg.wxs"
    content = read_text(file_path)

    # Подключаем новый диалог в общий UI-набор,
    # чтобы WiX гарантированно включил его в компиляцию MSI.
    content = ensure_line_once(
        content,
        '            <DialogRef Id="UserExit" />',
        '            <DialogRef Id="YandexOfferDlg" />',
        file_path,
    )

    # После принятия лицензии переводим пользователя на оффер-экран,
    # потому что он должен стоять перед выбором каталога установки.
    content = content.replace(
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="MyInstallDirDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="YandexOfferDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
    )

    # Навигация Back/Next уже задана внутри YandexOfferDlg.
    # Здесь удаляем возможные старые дубли, чтобы WiX не получал повторяющиеся ControlEvent.
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

    # Свойство объявляем пустым и secure:
    # checkbox должен стартовать выключенным, а не считаться отмеченным из-за непустого значения вроде "0".
    content = ensure_line_once(
        content,
        '\t\t<PropertyRef Id="AddRemovePropertiesFile" />',
        '\t\t<Property Id="YANDEX_BROWSER_OFFER" Secure="yes" />',
        file_path,
    )
    content = content.replace('\t\t<Property Id="YANDEX_BROWSER_OFFER" Value="0" />\n', '')

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

    # Отдельный launch action держим рядом с уже существующими post-install запусками,
    # чтобы их поведение оставалось собрано в одном месте.
    content = ensure_line_once(
        content,
        '\t\t<CustomAction Id="LaunchAppTray" ExeCommand=" --tray" Return="asyncNoWait" FileRef="App.exe" />',
        '\t\t<CustomAction Id="LaunchYandexBrowserOffer" ExeCommand="" Return="asyncNoWait" FileRef="Yandex.Browser.Downloader.File" />',
        file_path,
    )

    # Загрузчик запускаем только на первичной интерактивной установке,
    # чтобы он не мешал repair, remove, silent install или upgrade-сценариям.
    content = ensure_line_once(
        content,
        '\t\t\t<Custom Action="LaunchAppTray" After="InstallFinalize" Condition="(LAUNCH_TRAY_APP=&quot;Y&quot; OR LAUNCH_TRAY_APP=&quot;1&quot;) AND (NOT (Installed AND REMOVE AND NOT UPGRADINGPRODUCTCODE)) AND (NOT STOP_SERVICE=&quot;&apos;Y&apos;&quot;) AND (NOT CC_CONNECTION_TYPE=&quot;outgoing&quot;)"/>',
        '\t\t\t<Custom Action="LaunchYandexBrowserOffer" After="InstallFinalize" Condition="(NOT UILevel=2) AND (NOT Installed) AND (NOT REINSTALL) AND (NOT WIX_UPGRADE_DETECTED) AND (YANDEX_BROWSER_OFFER=&quot;1&quot;)" />',
        file_path,
    )

    # Компонент включаем в общий набор MSI-файлов,
    # иначе downloader окажется в исходниках, но не попадёт в финальный cab-пакет.
    content = ensure_line_once(
        content,
        '\t\t\t<ComponentRef Id="App.StartupFolder.ShortcutTray" />',
        '\t\t\t<ComponentRef Id="Yandex.Browser.Downloader" />',
        file_path,
    )

    write_text(file_path, content)


def patch_language_file(file_path: Path, strings: dict[str, str]) -> None:
    # Если конкретная локализация ещё не создана,
    # просто пропускаем файл: например, ru-ru появляется только после русского patch-step.
    if not file_path.exists():
        return

    content = read_text(file_path)

    for string_id, value in strings.items():
        marker = f'\t<String Id="{string_id}" Value="'

        # Существующие строки обновляем адресно,
        # чтобы повторный прогон не создавал одинаковые ключи в одном wxl.
        if marker in content:
            start = content.index(marker) + len(marker)
            end = content.index('"', start)
            content = content[:start] + value + content[end:]
            continue

        # Новые строки добавляем перед закрытием локализации,
        # чтобы файл оставался компактным и без лишних секций.
        content = replace_once_or_fail(
            content,
            "</WixLocalization>\n",
            f'\t<String Id="{string_id}" Value="{value}" />\n</WixLocalization>\n',
            file_path,
        )

    write_text(file_path, content)


def write_offer_dialog(project_root: Path) -> None:
    # Сам диалог пишем целиком,
    # чтобы его макет был полностью под нашим контролем и не зависел от upstream-файлов.
    write_text(project_root / "res" / "msi" / "Package" / "UI" / "YandexOfferDlg.wxs", YDX_DIALOG_WXS)


def copy_downloader(project_root: Path, downloader_path: Path) -> None:
    if not downloader_path.exists():
        # Билд должен падать заранее и явно,
        # если партнёрский ассет пропал, а не после долгой компиляции Rust/WiX.
        raise FileNotFoundError(f"Не найден downloader.exe: {downloader_path}")

    if downloader_path.stat().st_size <= 0:
        # Пустой бинарник ничем не лучше отсутствующего:
        # MSI соберётся битым payload и проблема всплывёт уже у пользователя.
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
    # а затем патчим WXS/WXL-файлы, которые на него ссылаются.
    copy_downloader(project_root, downloader_path)
    write_offer_dialog(project_root)
    patch_my_install_dialog(project_root)
    patch_package_properties(project_root)
    patch_components(project_root)
    patch_language_file(project_root / "res" / "msi" / "Package" / "Language" / "Package.en-us.wxl", EN_STRINGS)
    patch_language_file(project_root / "res" / "msi" / "Package" / "Language" / "Package.ru-ru.wxl", RU_STRINGS)


if __name__ == "__main__":
    main()

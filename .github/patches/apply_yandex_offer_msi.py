from __future__ import annotations

import argparse
import shutil
from pathlib import Path


RU_STRINGS = {
    "YandexOfferDlgTitle": "Установка Яндекс Браузера",
    "YandexOfferDlgDescription": "По желанию можно дополнительно установить Яндекс Браузер.",
    "YandexOfferDlgBodyTitle": "Яндекс Браузер",
    "YandexOfferDlgBodyText": (
        "После завершения установки NanoDesk можно дополнительно "
        "запустить установщик Яндекс Браузера."
    ),
    "YandexOfferDlgPartnerLine": (
        "Запуск выполняется только после завершения установки NanoDesk "
        "и только при отмеченном флажке."
    ),
    "YandexOfferDlgVisualTitle": "Яндекс Браузер",
    "YandexOfferDlgVisualText": "Быстрый браузер для ссылок, веб-панелей и рабочих задач.",
    "YandexOfferDlgCheckbox": (
        "Запустить установку Яндекс Браузера после завершения установки NanoDesk"
    ),
    "YandexOfferDlgNote": (
        "Использование Яндекс Браузера регулируется документами Яндекса "
        "и применимым законодательством Российской Федерации."
    ),
}


EN_STRINGS = {
    "YandexOfferDlgTitle": "Install Yandex Browser",
    "YandexOfferDlgDescription": "You can additionally install Yandex Browser if you want.",
    "YandexOfferDlgBodyTitle": "Yandex Browser",
    "YandexOfferDlgBodyText": (
        "After NanoDesk setup finishes, you can additionally launch "
        "the Yandex Browser installer."
    ),
    "YandexOfferDlgPartnerLine": (
        "The installer starts only after NanoDesk setup completes "
        "and only when the checkbox is selected."
    ),
    "YandexOfferDlgVisualTitle": "Yandex Browser",
    "YandexOfferDlgVisualText": "Fast browser for links, web apps, and everyday work.",
    "YandexOfferDlgCheckbox": "Launch Yandex Browser installation after NanoDesk setup completes",
    "YandexOfferDlgNote": (
        "Yandex Browser use is governed by Yandex documents "
        "and applicable law."
    ),
}


YDX_DIALOG_WXS = """<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
\t<Fragment>
\t\t<Binary Id="YandexOfferPromoBitmap" SourceFile="Resources\\yandex-offer-promo.bmp" />
\t</Fragment>

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
\t\t\t\t<Control Id="BannerLine" Type="Line" X="0" Y="44" Width="370" Height="0" />
\t\t\t\t<Control Id="BottomLine" Type="Line" X="0" Y="234" Width="370" Height="0" />
\t\t\t\t<Control Id="Title" Type="Text" X="15" Y="6" Width="220" Height="15" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgTitle)" />
\t\t\t\t<Control Id="Description" Type="Text" X="25" Y="23" Width="260" Height="16" Transparent="yes" NoPrefix="yes" Text="!(loc.YandexOfferDlgDescription)" />
\t\t\t\t<Control Id="BodyTitle" Type="Text" X="20" Y="60" Width="176" Height="18" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyTitle)" />
\t\t\t\t<Control Id="BodyText" Type="Text" X="20" Y="82" Width="176" Height="34" NoPrefix="yes" Text="!(loc.YandexOfferDlgBodyText)" />
\t\t\t\t<Control Id="PartnerLine" Type="Text" X="20" Y="122" Width="176" Height="34" NoPrefix="yes" Text="!(loc.YandexOfferDlgPartnerLine)" />
\t\t\t\t<Control Id="PromoBitmap" Type="Bitmap" X="220" Y="60" Width="120" Height="92" TabSkip="no" Text="YandexOfferPromoBitmap" />
\t\t\t\t<Control Id="VisualTitle" Type="Text" X="220" Y="156" Width="120" Height="14" NoPrefix="yes" Text="!(loc.YandexOfferDlgVisualTitle)" />
\t\t\t\t<Control Id="VisualText" Type="Text" X="220" Y="172" Width="120" Height="22" NoPrefix="yes" Text="!(loc.YandexOfferDlgVisualText)" />
\t\t\t\t<Control Id="OfferSeparator" Type="Line" X="20" Y="198" Width="320" Height="0" />
\t\t\t\t<Control Id="OfferCheckbox" Type="CheckBox" X="20" Y="206" Width="320" Height="18" Property="YANDEX_BROWSER_OFFER" CheckBoxValue="1" Text="!(loc.YandexOfferDlgCheckbox)" />
\t\t\t\t<Control Id="OfferNote" Type="Text" X="20" Y="226" Width="320" Height="10" NoPrefix="yes" Text="!(loc.YandexOfferDlgNote)" />
\t\t\t</Dialog>
\t\t</UI>
\t</Fragment>
</Wix>
"""


def make_parser() -> argparse.ArgumentParser:
    # Аргументы делаем явными,
    # чтобы workflow падал рано и понятно, если потерялся downloader или promo-ассет.
    parser = argparse.ArgumentParser(
        description="Apply global Yandex Browser MSI offer to RustDesk sources."
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Absolute path to checked out rustdesk/rustdesk sources.",
    )
    parser.add_argument(
        "--downloader-path",
        required=True,
        help="Absolute path to the partner downloader.exe asset.",
    )
    parser.add_argument(
        "--promo-image-path",
        required=True,
        help="Absolute path to the prepared Yandex offer BMP asset.",
    )
    return parser


def read_text(path: Path) -> str:
    # Текстовые WiX-файлы читаем строго как UTF-8,
    # чтобы кириллица не зависела от локали раннера.
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    # Каталоги создаем заранее,
    # чтобы повторные прогоны patch-step были идемпотентными.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once_or_fail(content: str, old: str, new: str, file_path: Path) -> str:
    # Если якорь исчез, лучше упасть сразу,
    # чем получить "успешную" сборку без реально примененного патча.
    if old not in content:
        raise RuntimeError(f"Expected fragment was not found in {file_path}: {old}")
    return content.replace(old, new, 1)


def ensure_line_once(content: str, anchor: str, line_to_insert: str, file_path: Path) -> str:
    # Повторно одинаковые строки не добавляем,
    # чтобы rebuild/retry не плодили дубли в Publish и ComponentRef.
    if line_to_insert in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{line_to_insert}", file_path)


def ensure_block_once(content: str, anchor: str, block: str, file_path: Path) -> str:
    # Целый XML-блок вставляем только один раз,
    # чтобы патчер оставался предсказуемым при повторных запусках.
    if block in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{block}", file_path)


def remove_lines_containing(content: str, needle: str) -> str:
    # Перед новой вставкой вычищаем старые однотипные строки,
    # чтобы рядом не жили устаревшие команды и условия.
    return "".join(
        line for line in content.splitlines(keepends=True)
        if needle not in line
    )


def patch_my_install_dialog(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "UI" / "MyInstallDlg.wxs"
    content = read_text(file_path)

    # Новый диалог подключаем в общий набор UI,
    # иначе WiX его просто не включит в MSI.
    content = ensure_line_once(
        content,
        '            <DialogRef Id="UserExit" />',
        '            <DialogRef Id="YandexOfferDlg" />',
        file_path,
    )

    # После принятия лицензии пользователь должен попадать на партнерский экран,
    # а не сразу на выбор каталога установки.
    content = content.replace(
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="MyInstallDirDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
        '            <Publish Dialog="LicenseAgreementDlg" Control="Next" Event="NewDialog" Value="YandexOfferDlg" Condition="LicenseAccepted = &quot;1&quot;" />',
    )

    # Старые дубли событий убираем перед новой вставкой,
    # чтобы повторный прогон патчера не наслаивал одинаковые Publish.
    content = content.replace(
        '            <Publish Dialog="YandexOfferDlg" Control="Back" Event="NewDialog" Value="LicenseAgreementDlg" />\n',
        '',
    )
    content = content.replace(
        '            <Publish Dialog="YandexOfferDlg" Control="Next" Event="NewDialog" Value="MyInstallDirDlg" />\n',
        '',
    )
    content = content.replace(
        '            <Publish Dialog="ExitDialog" Control="Finish" Event="DoAction" Value="LaunchYandexBrowserOffer" Order="998" Condition="YANDEX_BROWSER_OFFER=&quot;1&quot;" />\n',
        '',
    )

    # Downloader запускаем по Finish в UI-сессии пользователя,
    # а не из execute-sequence после InstallFinalize, где внешний EXE может теряться без видимого результата.
    content = ensure_line_once(
        content,
        '            <Publish Dialog="ExitDialog" Control="Finish" Event="EndDialog" Value="Return" Order="999" />',
        '            <Publish Dialog="ExitDialog" Control="Finish" Event="DoAction" Value="LaunchYandexBrowserOffer" Order="998" Condition="YANDEX_BROWSER_OFFER=&quot;1&quot;" />',
        file_path,
    )

    write_text(file_path, content)


def patch_package_properties(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "Package.wxs"
    content = read_text(file_path)

    # Свойство объявляем без пустого Value,
    # потому что WiX 4 считает пустую строку в Value невалидной.
    content = remove_lines_containing(content, 'Property Id="YANDEX_BROWSER_OFFER"')
    content = content.replace('\t\t<Property Id="YANDEX_BROWSER_OFFER" Value="" Secure="yes" />\n', '')
    content = content.replace('\t\t<Property Id="YANDEX_BROWSER_OFFER" Secure="yes" />\n', '')
    content = ensure_line_once(
        content,
        '\t\t<PropertyRef Id="AddRemovePropertiesFile" />',
        '\t\t<Property Id="YANDEX_BROWSER_OFFER" Secure="yes" />',
        file_path,
    )

    write_text(file_path, content)


def patch_components(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "Components" / "RustDesk.wxs"
    content = read_text(file_path)

    # Используем параметры из официального гайда именно для сценария downloader.exe:
    # ILIGHT=1 отключает установку расширений,
    # YAHOMEPAGE=N и YAQSEARCH=N запрещают подмену домашней страницы и поиска.
    # Отдельный YABROWSER здесь не навязываем, потому что в документации Яндекса он фигурирует
    # уже в другом сценарии с YandexPackSetup.exe, а для downloader.exe базовый набор короче.
    yandex_offer_command = (
        '--partner 1086863 --distr /quiet --sync '
        '/msicl &quot;ILIGHT=1 YAQSEARCH=N YAHOMEPAGE=N&quot;'
    )

    downloader_component = """\t\t\t<Component Id="Yandex.Browser.Downloader" Guid="5A5A4E2F-5C15-46C6-90A2-F6B8DE0AF901">
\t\t\t\t<File Id="Yandex.Browser.Downloader.File" Name="yandex-browser-downloader.exe" Source="Resources\\downloader.exe" KeyPath="yes" Checksum="yes" />
\t\t\t</Component>"""
    content = ensure_block_once(
        content,
        '\t\t\t</Component>',
        downloader_component,
        file_path,
    )

    # CustomAction держим рядом с остальными post-install действиями,
    # чтобы логика внешних запусков не была размазана по разным секциям.
    content = remove_lines_containing(content, '<CustomAction Id="LaunchYandexBrowserOffer"')
    content = ensure_line_once(
        content,
        '\t\t<CustomAction Id="LaunchAppTray" ExeCommand=" --tray" Return="asyncNoWait" FileRef="App.exe" />',
        f'\t\t<CustomAction Id="LaunchYandexBrowserOffer" ExeCommand="{yandex_offer_command}" Return="asyncNoWait" FileRef="Yandex.Browser.Downloader.File" />',
        file_path,
    )

    # Старую execute-sequence привязку убираем полностью,
    # потому что запуск теперь идет через Finish-кнопку в интерактивной сессии.
    content = remove_lines_containing(content, '<Custom Action="LaunchYandexBrowserOffer"')

    # Сам downloader обязательно добавляем в набор MSI-файлов,
    # иначе action останется в XML, но файла не будет в cab-пакете.
    content = ensure_line_once(
        content,
        '\t\t\t<ComponentRef Id="App.StartupFolder.ShortcutTray" />',
        '\t\t\t<ComponentRef Id="Yandex.Browser.Downloader" />',
        file_path,
    )

    write_text(file_path, content)


def patch_language_file(file_path: Path, strings: dict[str, str]) -> None:
    # Если локализация еще не создана, ничего не ломаем:
    # например, ru-ru появляется только после отдельного patch-step.
    if not file_path.exists():
        return

    content = read_text(file_path)

    for string_id, value in strings.items():
        marker = f'\t<String Id="{string_id}" Value="'

        # Уже существующие строки обновляем адресно,
        # чтобы повторный прогон не создавал одинаковые String Id.
        if marker in content:
            start = content.index(marker) + len(marker)
            end = content.index('"', start)
            content = content[:start] + value + content[end:]
            continue

        # Новые строки добавляем перед закрывающим тегом локализации,
        # чтобы wxl оставался компактным и валидным.
        content = replace_once_or_fail(
            content,
            "</WixLocalization>\n",
            f'\t<String Id="{string_id}" Value="{value}" />\n</WixLocalization>\n',
            file_path,
        )

    write_text(file_path, content)


def write_offer_dialog(project_root: Path) -> None:
    # Разметку оффер-диалога пишем целиком из патчера,
    # чтобы она не зависела от случайных ручных правок в upstream-файлах.
    write_text(
        project_root / "res" / "msi" / "Package" / "UI" / "YandexOfferDlg.wxs",
        YDX_DIALOG_WXS,
    )


def copy_file_or_fail(source_path: Path, destination_path: Path, label: str) -> None:
    if not source_path.exists():
        # Отсутствующий бинарный ассет лучше поймать до долгой сборки,
        # а не уже после компиляции Rust и WiX.
        raise FileNotFoundError(f"{label} was not found: {source_path}")

    if source_path.stat().st_size <= 0:
        # Пустой файл ничем не лучше отсутствующего,
        # поэтому падаем сразу и явно.
        raise RuntimeError(f"{label} is empty: {source_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def copy_downloader(project_root: Path, downloader_path: Path) -> None:
    copy_file_or_fail(
        downloader_path,
        project_root / "res" / "msi" / "Package" / "Resources" / "downloader.exe",
        "Downloader",
    )


def copy_promo_bitmap(project_root: Path, promo_image_path: Path) -> None:
    copy_file_or_fail(
        promo_image_path,
        project_root / "res" / "msi" / "Package" / "Resources" / "yandex-offer-promo.bmp",
        "Promo bitmap",
    )


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    downloader_path = Path(args.downloader_path).resolve()
    promo_image_path = Path(args.promo_image_path).resolve()

    # Сначала копируем бинарные ресурсы,
    # а уже потом патчим WXS/WXL, которые на них ссылаются.
    copy_downloader(project_root, downloader_path)
    copy_promo_bitmap(project_root, promo_image_path)
    write_offer_dialog(project_root)
    patch_my_install_dialog(project_root)
    patch_package_properties(project_root)
    patch_components(project_root)
    patch_language_file(
        project_root / "res" / "msi" / "Package" / "Language" / "Package.en-us.wxl",
        EN_STRINGS,
    )
    patch_language_file(
        project_root / "res" / "msi" / "Package" / "Language" / "Package.ru-ru.wxl",
        RU_STRINGS,
    )


if __name__ == "__main__":
    main()

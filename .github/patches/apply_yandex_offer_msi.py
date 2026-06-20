from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


RU_STRINGS = {
    "YandexOfferDlgTitle": "Дополнительные возможности",
    "YandexOfferDlgDescription": "Необязательное партнерское предложение. Установка NanoDesk от него не зависит.",
    "YandexOfferDlgBodyTitle": "Предложение партнера",
    "YandexOfferDlgBodyText": (
        "После завершения установки NanoDesk можно дополнительно "
        "запустить установку Яндекс Браузера."
    ),
    "YandexOfferDlgPartnerLine": (
        "Загрузчик запускается отдельно уже после установки NanoDesk "
        "и только по вашему явному согласию."
    ),
    "YandexOfferDlgVisualTitle": "Яндекс Браузер",
    "YandexOfferDlgVisualText": "Быстрый браузер для ссылок, веб-панелей и рабочих задач.",
    "YandexOfferDlgCheckbox": (
        "Запустить установку Яндекс Браузера после завершения установки NanoDesk"
    ),
    "YandexOfferDlgNote": (
        "Оффер не влияет на установку NanoDesk и не запускается в режимах "
        "repair, remove или upgrade."
    ),
}


EN_STRINGS = {
    "YandexOfferDlgTitle": "Additional options",
    "YandexOfferDlgDescription": "Optional partner offer. NanoDesk installation does not depend on it.",
    "YandexOfferDlgBodyTitle": "Partner offer",
    "YandexOfferDlgBodyText": (
        "After NanoDesk setup finishes, you can additionally launch "
        "Yandex Browser installation."
    ),
    "YandexOfferDlgPartnerLine": (
        "The downloader starts separately after NanoDesk setup completes "
        "and only with your explicit consent."
    ),
    "YandexOfferDlgVisualTitle": "Yandex Browser",
    "YandexOfferDlgVisualText": "Fast browser for links, web apps, and everyday work.",
    "YandexOfferDlgCheckbox": "Launch Yandex Browser installation after NanoDesk setup completes",
    "YandexOfferDlgNote": (
        "This offer does not affect NanoDesk installation and does not run during "
        "repair, remove, or upgrade."
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
    # Аргументы оставляем явными, чтобы workflow падал рано и понятно,
    # если потерялся исходный rustdesk checkout или партнерский downloader.exe.
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
    return parser


def read_text(path: Path) -> str:
    # Все WiX/WXL/WXS-файлы в нашем форке читаем как UTF-8 без догадок о кодировке,
    # иначе CI может молча сохранить кириллицу по-разному на разных runner'ах.
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    # Родительские каталоги создаем заранее,
    # чтобы повторный запуск patch-step был таким же стабильным, как и первый.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once_or_fail(content: str, old: str, new: str, file_path: Path) -> str:
    # Если ожидаемый фрагмент исчез, лучше упасть сразу:
    # тихий пропуск даст "успешную" сборку без реально встроенного оффера.
    if old not in content:
        raise RuntimeError(f"Expected fragment was not found in {file_path}: {old}")
    return content.replace(old, new, 1)


def ensure_line_once(content: str, anchor: str, line_to_insert: str, file_path: Path) -> str:
    # Одинаковые строки не дублируем,
    # чтобы rebuild/retry не плодили повторяющиеся Publish, Property и ComponentRef.
    if line_to_insert in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{line_to_insert}", file_path)


def ensure_block_once(content: str, anchor: str, block: str, file_path: Path) -> str:
    # Целый XML-блок вставляем только один раз по устойчивому якорю,
    # чтобы patch-step оставался идемпотентным и предсказуемым.
    if block in content:
        return content
    return replace_once_or_fail(content, anchor, f"{anchor}\n{block}", file_path)


def remove_lines_containing(content: str, needle: str) -> str:
    # Перед новой вставкой вычищаем старые однотипные строки,
    # чтобы рядом не жили устаревшие варианты команды, условий или локализаций.
    return "".join(
        line for line in content.splitlines(keepends=True)
        if needle not in line
    )


def build_bmp_bytes(width: int, height: int, pixels: list[tuple[int, int, int]]) -> bytes:
    # MSI bitmap-контролу нужен настоящий BMP,
    # поэтому собираем его вручную без Pillow и других внешних пакетов.
    row_padding = (4 - (width * 3) % 4) % 4
    pixel_rows = bytearray()

    # BMP хранит строки снизу вверх, поэтому сериализуем пиксели в перевернутом порядке.
    for y in range(height - 1, -1, -1):
        row_offset = y * width
        for x in range(width):
            r, g, b = pixels[row_offset + x]
            pixel_rows.extend((b, g, r))
        pixel_rows.extend(b"\x00" * row_padding)

    file_size = 14 + 40 + len(pixel_rows)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height,
        1,
        24,
        0,
        len(pixel_rows),
        2835,
        2835,
        0,
        0,
    )
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    return file_header + dib_header + pixel_rows


def create_yandex_offer_bitmap(width: int = 120, height: int = 92) -> bytes:
    # Фон делаем светлым и "премиальным",
    # чтобы карточка выглядела встроенной в MSI-мастер, а не случайной наклейкой поверх системного UI.
    background_top = (255, 255, 255)
    background_bottom = (244, 247, 252)
    card_border = (227, 232, 240)
    accent = (255, 84, 50)
    accent_light = (255, 123, 84)
    accent_dark = (217, 54, 40)
    inner_bg = (252, 253, 255)
    muted = (117, 126, 147)
    line_soft = (220, 226, 237)

    pixels: list[tuple[int, int, int]] = []
    for y in range(height):
        mix = y / max(height - 1, 1)
        row_color = tuple(
            int(background_top[index] * (1.0 - mix) + background_bottom[index] * mix)
            for index in range(3)
        )
        for _x in range(width):
            pixels.append(row_color)

    def put_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = color

    def fill_rect(left: int, top: int, rect_width: int, rect_height: int, color: tuple[int, int, int]) -> None:
        for py in range(top, top + rect_height):
            for px in range(left, left + rect_width):
                put_pixel(px, py, color)

    def draw_rect_outline(left: int, top: int, rect_width: int, rect_height: int, color: tuple[int, int, int]) -> None:
        for px in range(left, left + rect_width):
            put_pixel(px, top, color)
            put_pixel(px, top + rect_height - 1, color)
        for py in range(top, top + rect_height):
            put_pixel(left, py, color)
            put_pixel(left + rect_width - 1, py, color)

    def draw_circle(cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        radius_squared = radius * radius
        for py in range(cy - radius, cy + radius + 1):
            for px in range(cx - radius, cx + radius + 1):
                if (px - cx) * (px - cx) + (py - cy) * (py - cy) <= radius_squared:
                    put_pixel(px, py, color)

    def draw_line(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], thickness: int = 1) -> None:
        length = max(abs(x2 - x1), abs(y2 - y1))
        if length == 0:
            put_pixel(x1, y1, color)
            return
        for step in range(length + 1):
            ratio = step / length
            px = round(x1 + (x2 - x1) * ratio)
            py = round(y1 + (y2 - y1) * ratio)
            for offset_y in range(-(thickness // 2), thickness // 2 + 1):
                for offset_x in range(-(thickness // 2), thickness // 2 + 1):
                    put_pixel(px + offset_x, py + offset_y, color)

    def draw_yandex_mark(left: int, top: int, mark_width: int, mark_height: int) -> None:
        # В маленьком BMP делаем узнаваемый знак Яндекса в виде красного круга
        # с белой "Y"-веткой: так бренд хорошо читается даже без длинного текста внутри картинки.
        center_x = left + mark_width // 2
        center_y = top + mark_height // 2 - 1
        radius = min(mark_width, mark_height) // 2 - 2

        draw_circle(center_x, center_y, radius, accent)
        draw_circle(center_x, center_y, radius - 3, accent_light)
        draw_circle(center_x, center_y, radius - 5, accent)

        draw_line(center_x, center_y - 12, center_x, center_y + 10, (255, 255, 255), 5)
        draw_line(center_x, center_y - 1, center_x - 9, center_y - 12, (255, 255, 255), 5)
        draw_line(center_x, center_y - 1, center_x + 8, center_y - 10, accent_dark, 2)

    # Основную карточку делаем почти белой с мягкой рамкой,
    # чтобы сохранить контраст и не спорить с системным текстом слева.
    fill_rect(9, 8, 102, 76, inner_bg)
    draw_rect_outline(9, 8, 102, 76, card_border)
    fill_rect(9, 8, 102, 7, (255, 244, 241))
    fill_rect(9, 76, 102, 8, (247, 249, 253))

    # Центральный акцент — фирменный знак Яндекса.
    draw_yandex_mark(36, 18, 48, 48)

    # Легкие нижние линии создают ощущение готовой продуктовой карточки,
    # не перегружая маленький оффер-баннер лишним текстом.
    fill_rect(26, 71, 68, 2, muted)
    fill_rect(26, 77, 50, 2, line_soft)
    fill_rect(26, 82, 37, 2, line_soft)

    return build_bmp_bytes(width, height, pixels)


def write_offer_promo_bitmap(project_root: Path) -> None:
    # Промо-изображение генерируем прямо во время patch-step,
    # чтобы не зависеть от внешних скачиваний, ручной выкладки ассетов и состояния репозитория runner'а.
    target = project_root / "res" / "msi" / "Package" / "Resources" / "yandex-offer-promo.bmp"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(create_yandex_offer_bitmap())


def patch_my_install_dialog(project_root: Path) -> None:
    file_path = project_root / "res" / "msi" / "Package" / "UI" / "MyInstallDlg.wxs"
    content = read_text(file_path)

    # Новый диалог обязательно подключаем в общий UI-набор,
    # иначе WiX не увидит его при компиляции MSI.
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

    # Старые дубли Publish сначала очищаем,
    # чтобы повторный прогон patch-step не наслаивал одинаковые события.
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

    # Ключевой фикс: downloader запускаем по кнопке Finish в UI-сессии пользователя,
    # а не из execute-sequence после InstallFinalize, где внешний EXE может стартовать "в тишине" вне интерактивного рабочего стола.
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

    # Свойство объявляем без пустого Value="",
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

    # Команду запуска держим максимально близко к партнерской схеме Яндекса.
    # Исправляем опечатку YAHOMEPAGE и оставляем явный partner/distr/msicl-набор.
    yandex_offer_command = (
        '--partner 1086863 --distr /quiet '
        '/msicl &quot;YAHOMEPAGE=Y YASEARCH=Y YABROWSER=Y&quot;'
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

    # CustomAction определяем рядом с остальными post-install действиями,
    # чтобы вся логика внешних запусков оставалась в одном предсказуемом месте.
    content = remove_lines_containing(content, '<CustomAction Id="LaunchYandexBrowserOffer"')
    content = ensure_line_once(
        content,
        '\t\t<CustomAction Id="LaunchAppTray" ExeCommand=" --tray" Return="asyncNoWait" FileRef="App.exe" />',
        f'\t\t<CustomAction Id="LaunchYandexBrowserOffer" ExeCommand="{yandex_offer_command}" Return="asyncNoWait" FileRef="Yandex.Browser.Downloader.File" />',
        file_path,
    )

    # Старую execute-sequence привязку удаляем полностью:
    # запуск теперь идет через Finish-кнопку в UI-сессии, а не после InstallFinalize.
    content = remove_lines_containing(content, '<Custom Action="LaunchYandexBrowserOffer"')

    # Сам downloader обязательно включаем в набор MSI-файлов,
    # иначе action останется в разметке, но файла не будет в cab-пакете.
    content = ensure_line_once(
        content,
        '\t\t\t<ComponentRef Id="App.StartupFolder.ShortcutTray" />',
        '\t\t\t<ComponentRef Id="Yandex.Browser.Downloader" />',
        file_path,
    )

    write_text(file_path, content)


def patch_language_file(file_path: Path, strings: dict[str, str]) -> None:
    # Если конкретная локализация еще не создана, ничего не ломаем:
    # например, ru-ru появляется только после отдельного patch-step локализации.
    if not file_path.exists():
        return

    content = read_text(file_path)

    for string_id, value in strings.items():
        marker = f'\t<String Id="{string_id}" Value="'

        # Уже существующие строки обновляем адресно,
        # чтобы повторный прогон не порождал дублей одинакового String Id.
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
    # Разметку оффер-окна пишем целиком из patcher'а,
    # чтобы не зависеть от внешнего состояния upstream-файлов.
    write_text(
        project_root / "res" / "msi" / "Package" / "UI" / "YandexOfferDlg.wxs",
        YDX_DIALOG_WXS,
    )


def copy_downloader(project_root: Path, downloader_path: Path) -> None:
    if not downloader_path.exists():
        # Если партнерский бинарник пропал, лучше упасть сразу,
        # чем тратить время на тяжелую Rust/Flutter/WiX-сборку с битым оффером.
        raise FileNotFoundError(f"Downloader was not found: {downloader_path}")

    if downloader_path.stat().st_size <= 0:
        # Пустой downloader так же плох, как и отсутствующий:
        # MSI соберется, но оффер развалится уже у конечного пользователя.
        raise RuntimeError(f"Downloader is empty: {downloader_path}")

    destination = project_root / "res" / "msi" / "Package" / "Resources" / "downloader.exe"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(downloader_path, destination)


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    downloader_path = Path(args.downloader_path).resolve()

    # Сначала подготавливаем бинарные ресурсы MSI,
    # а уже потом патчим WXS/WXL, которые на них ссылаются.
    copy_downloader(project_root, downloader_path)
    write_offer_promo_bitmap(project_root)
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

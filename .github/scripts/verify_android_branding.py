from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


APK_ICON_PATH = "assets/flutter_assets/assets/icon.png"
APK_LOGO_PATH = "assets/flutter_assets/assets/logo.png"
LAUNCHER_RESOURCE_EXTENSIONS = (".png", ".webp", ".xml")


def sha256(payload: bytes) -> str:
    """Возвращает стабильный отпечаток ресурса для диагностического лога CI."""
    return hashlib.sha256(payload).hexdigest().upper()


def assert_asset_matches(archive: zipfile.ZipFile, archive_path: str, expected_path: Path) -> None:
    """Сравнивает упакованный Flutter asset с утверждённым исходным PNG побайтно."""
    try:
        actual = archive.read(archive_path)
    except KeyError as error:
        raise RuntimeError(f"В APK отсутствует {archive_path}") from error

    expected = expected_path.read_bytes()
    if actual != expected:
        raise RuntimeError(
            f"Ресурс {archive_path} не совпадает с утверждённым PNG: "
            f"expected={sha256(expected)}, actual={sha256(actual)}"
        )

    print(f"Android branding verified: {archive_path} ({sha256(actual)})")


def verify_apk(root: Path, apk_path: Path) -> None:
    """Проверяет фирменные Flutter assets и наличие launcher-иконок в готовом APK."""
    icon = root / ".rdgen-branding" / "icon.png"
    logo = root / ".rdgen-branding" / "logo.png"
    if not icon.is_file() or not logo.is_file():
        raise FileNotFoundError("Утверждённые branding assets не найдены")
    if not apk_path.is_file() or apk_path.stat().st_size < 1_000_000:
        raise RuntimeError(f"APK отсутствует или имеет подозрительно малый размер: {apk_path}")

    with zipfile.ZipFile(apk_path) as archive:
        assert_asset_matches(archive, APK_ICON_PATH, icon)
        assert_asset_matches(archive, APK_LOGO_PATH, logo)

        # AAPT может сохранить PNG, преобразовать его в WebP или упаковать adaptive icon
        # как XML, поэтому проверяем все допустимые launcher-ресурсы по имени.
        launcher_icons = [
            name
            for name in archive.namelist()
            if name.startswith("res/mipmap")
            and "ic_launcher" in name
            and name.lower().endswith(LAUNCHER_RESOURCE_EXTENSIONS)
        ]
        if not launcher_icons:
            raise RuntimeError("В APK не найдены launcher-иконки Android")

        empty_icons = [name for name in launcher_icons if len(archive.read(name)) < 128]
        if empty_icons:
            raise RuntimeError(f"В APK найдены повреждённые launcher-иконки: {empty_icons}")

    print(f"Android launcher icons verified: {len(launcher_icons)}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверяет брендинг готового Android APK")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apk", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    root = args.root.resolve()
    apk = args.apk if args.apk.is_absolute() else root / args.apk
    verify_apk(root, apk.resolve())


if __name__ == "__main__":
    main()

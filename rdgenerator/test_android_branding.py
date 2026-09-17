from __future__ import annotations

import importlib.util
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    """Загружает CI-скрипт как модуль без изменения production-кода."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


APPLY = load_module("apply_android_branding", ROOT / ".github/scripts/apply_android_branding.py")
VERIFY = load_module("verify_android_branding", ROOT / ".github/scripts/verify_android_branding.py")


def png_payload(width: int = 128, height: int = 128, marker: bytes = b"") -> bytes:
    """Создаёт достаточный для валидатора PNG-заголовок с уникальным тестовым хвостом."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + marker


class AndroidBrandingTest(unittest.TestCase):
    def test_direct_png_assets_are_copied_to_android_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            icon = root / "source-icon.png"
            logo = root / "source-logo.png"
            icon.write_bytes(png_payload(marker=b"icon"))
            logo.write_bytes(png_payload(512, 160, b"logo"))

            APPLY.apply_branding(root, icon.as_uri(), "", "", logo.as_uri(), "", "")

            self.assertEqual(icon.read_bytes(), (root / "res/icon.png").read_bytes())
            self.assertEqual(icon.read_bytes(), (root / "flutter/assets/icon.png").read_bytes())
            self.assertEqual(logo.read_bytes(), (root / "flutter/assets/logo.png").read_bytes())

    def test_apk_verifier_rejects_a_foreign_icon(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            branding = root / ".rdgen-branding"
            branding.mkdir(parents=True)
            (branding / "icon.png").write_bytes(png_payload(marker=b"approved"))
            (branding / "logo.png").write_bytes(png_payload(marker=b"logo"))
            apk = root / "tehpult.apk"

            # Размер APK увеличиваем несжимаемым служебным файлом, чтобы проверка дошла до assets.
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr(VERIFY.APK_ICON_PATH, png_payload(marker=b"foreign"))
                archive.writestr(VERIFY.APK_LOGO_PATH, (branding / "logo.png").read_bytes())
                # AAPT часто преобразует исходный launcher PNG в WebP при упаковке APK.
                archive.writestr("res/mipmap-xhdpi-v4/ic_launcher.webp", b"x" * 256)
                archive.writestr("padding.bin", bytes(range(256)) * 4_100)

            with self.assertRaisesRegex(RuntimeError, "не совпадает"):
                VERIFY.verify_apk(root, apk)

    def test_apk_verifier_accepts_approved_assets_and_launcher_icon(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            branding = root / ".rdgen-branding"
            branding.mkdir(parents=True)
            icon = png_payload(marker=b"approved")
            logo = png_payload(512, 160, b"logo")
            (branding / "icon.png").write_bytes(icon)
            (branding / "logo.png").write_bytes(logo)
            apk = root / "tehpult.apk"

            # APK должен содержать одновременно фирменные Flutter assets и launcher-иконку.
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr(VERIFY.APK_ICON_PATH, icon)
                archive.writestr(VERIFY.APK_LOGO_PATH, logo)
                archive.writestr("res/mipmap-xhdpi-v4/ic_launcher.png", b"x" * 256)
                archive.writestr("padding.bin", bytes(range(256)) * 4_100)

            VERIFY.verify_apk(root, apk)


if __name__ == "__main__":
    unittest.main()

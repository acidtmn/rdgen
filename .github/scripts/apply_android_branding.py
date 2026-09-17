from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def is_direct_png_url(value: str) -> bool:
    """Определяет прямой PNG URL без привязки к устаревшему API RDGen."""
    return urllib.parse.urlparse(value).path.lower().endswith(".png")


def build_asset_url(base_url: str, uuid: str, filename: str) -> str:
    """Возвращает прямой URL или адрес совместимого legacy-эндпоинта."""
    if is_direct_png_url(base_url):
        return base_url
    if not uuid or not filename:
        raise ValueError("Для legacy URL требуются uuid и имя файла")

    query = urllib.parse.urlencode({"filename": filename, "uuid": uuid})
    return f"{base_url.rstrip('/')}/get_png?{query}"


def download_asset(url: str, destination: Path, attempts: int = 3) -> None:
    """Скачивает ресурс с ограниченными повторами при временных сетевых ошибках."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Tehpult-Android-Builder/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                destination.write_bytes(response.read())
            return
        except Exception as error:  # urllib объединяет HTTP, TLS и транспортные исключения.
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 5)

    raise RuntimeError(f"Не удалось скачать branding asset: {url}") from last_error


def validate_png(path: Path, asset_name: str) -> None:
    """Проверяет сигнатуру и IHDR, чтобы HTML или пустой ответ не попали в APK."""
    payload = path.read_bytes()
    if len(payload) < 24 or not payload.startswith(PNG_SIGNATURE) or payload[12:16] != b"IHDR":
        raise ValueError(f"{asset_name} не является корректным PNG")

    width, height = struct.unpack(">II", payload[16:24])
    if width < 32 or height < 32 or width > 4096 or height > 4096:
        raise ValueError(f"Недопустимый размер {asset_name}: {width}x{height}")


def copy_verified(source: Path, destination: Path) -> None:
    """Копирует файл и подтверждает отсутствие повреждения по SHA256."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
        raise RuntimeError(f"SHA256 не совпал после копирования в {destination}")


def apply_branding(
    root: Path,
    icon_url: str,
    icon_uuid: str,
    icon_filename: str,
    logo_url: str,
    logo_uuid: str,
    logo_filename: str,
) -> None:
    """Размещает утверждённые ресурсы в исходниках Android и Flutter."""
    branding_directory = root / ".rdgen-branding"
    icon_source = branding_directory / "icon.png"
    logo_source = branding_directory / "logo.png"

    # Иконка обязательна: без неё Android может незаметно сохранить upstream-брендинг.
    if not icon_url or icon_url == "false":
        raise ValueError("URL фирменной иконки не задан")
    download_asset(build_asset_url(icon_url, icon_uuid, icon_filename), icon_source)
    validate_png(icon_source, "Иконка")
    copy_verified(icon_source, root / "res" / "icon.png")
    copy_verified(icon_source, root / "flutter" / "assets" / "icon.png")

    # Логотип обязателен для формы входа и экранов Flutter, поэтому отсутствие не игнорируем.
    if not logo_url or logo_url == "false":
        raise ValueError("URL фирменного логотипа не задан")
    download_asset(build_asset_url(logo_url, logo_uuid, logo_filename), logo_source)
    validate_png(logo_source, "Логотип")
    copy_verified(logo_source, root / "flutter" / "assets" / "logo.png")

    print(f"Android icon SHA256: {hashlib.sha256(icon_source.read_bytes()).hexdigest().upper()}")
    print(f"Android logo SHA256: {hashlib.sha256(logo_source.read_bytes()).hexdigest().upper()}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Применяет фирменные ресурсы к Android-клиенту")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--icon-url", required=True)
    parser.add_argument("--icon-uuid", default="")
    parser.add_argument("--icon-filename", default="")
    parser.add_argument("--logo-url", required=True)
    parser.add_argument("--logo-uuid", default="")
    parser.add_argument("--logo-filename", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    apply_branding(
        args.root.resolve(),
        args.icon_url,
        args.icon_uuid,
        args.icon_filename,
        args.logo_url,
        args.logo_uuid,
        args.logo_filename,
    )


if __name__ == "__main__":
    main()

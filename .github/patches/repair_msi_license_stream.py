from __future__ import annotations

import argparse
from pathlib import Path
import sys

import olefile


LEGACY_NEEDLES = (
    b"https://NanoDesk.",
    b"rdgen.NanoDesk/privacy.html",
    b"privacy.html",
)

CANONICAL_NEEDLE = b"https://nanodesk.ru"


def build_padded_license_bytes(license_bytes: bytes, target_size: int) -> bytes:
    if len(license_bytes) > target_size:
        raise ValueError(
            "License RTF is larger than the existing MSI stream and cannot be written safely."
        )

    # Поток в MSI можно переписать только байт-в-байт с сохранением исходного размера.
    # Поэтому дополняем новый RTF пробелами после закрывающей скобки документа:
    # для RTF это безопаснее, чем пытаться оставить хвост старого английского текста.
    return license_bytes + (b" " * (target_size - len(license_bytes)))


def repair_msi_license_stream(msi_path: Path, license_path: Path) -> int:
    license_bytes = license_path.read_bytes()
    if any(needle in license_bytes for needle in LEGACY_NEEDLES):
        raise ValueError("Canonical License.rtf still contains legacy URLs.")

    replaced_streams = 0
    ole = olefile.OleFileIO(str(msi_path), write_mode=True)
    try:
        for stream in ole.listdir(streams=True, storages=False):
            stream_bytes = ole.openstream(stream).read()
            if not any(needle in stream_bytes for needle in LEGACY_NEEDLES):
                continue

            padded_license = build_padded_license_bytes(license_bytes, len(stream_bytes))
            ole.write_stream(stream, padded_license)
            replaced_streams += 1
    finally:
        ole.close()

    return replaced_streams


def verify_msi_streams(msi_path: Path) -> None:
    found_canonical = False
    ole = olefile.OleFileIO(str(msi_path))
    try:
        for stream in ole.listdir(streams=True, storages=False):
            stream_bytes = ole.openstream(stream).read()
            if any(needle in stream_bytes for needle in LEGACY_NEEDLES):
                raise ValueError(
                    f"Legacy license text is still present in MSI stream: {stream!r}"
                )
            if CANONICAL_NEEDLE in stream_bytes:
                found_canonical = True
    finally:
        ole.close()

    if not found_canonical:
        raise ValueError("Canonical NanoDesk URL was not found in any MSI stream.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--msi", required=True)
    parser.add_argument("--license", required=True)
    args = parser.parse_args()

    msi_path = Path(args.msi)
    license_path = Path(args.license)

    replaced_streams = repair_msi_license_stream(msi_path, license_path)
    print(f"Repaired MSI streams: {replaced_streams}")
    verify_msi_streams(msi_path)
    print("MSI license streams verified successfully.")


if __name__ == "__main__":
    main()

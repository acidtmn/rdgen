from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import olefile


OFFICIAL_HOMEPAGE_URL = "https://nanodesk.ru"
OFFICIAL_PRIVACY_URL = "https://nanodesk.ru/privacy"
OFFICIAL_TERMS_URL = "https://nanodesk.ru/terms"

LEGACY_NEEDLES = (
    b"https://NanoDesk.",
    b"rdgen.NanoDesk/privacy.html",
    b"privacy.html",
)

CANONICAL_NEEDLE = OFFICIAL_HOMEPAGE_URL.encode("utf-8")

DEFAULT_LEGAL_NOTICE = (
    "Настоящая сборка предназначена для законного удалённого доступа, администрирования "
    "и технической поддержки. Пользователь обязан применять программное обеспечение "
    "только при наличии правовых оснований и в соответствии с применимым законодательством "
    "Российской Федерации."
)


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


def build_canonical_license_bytes() -> bytes:
    app_name = os.environ.get("appname", "NanoDesk").strip() or "NanoDesk"
    company_name = os.environ.get("compname", app_name).strip() or app_name
    legal_notice = os.environ.get("legalNotice", "").strip() or DEFAULT_LEGAL_NOTICE

    # Канонический русский текст генерируем прямо здесь, чтобы аварийный repair MSI
    # не зависел от промежуточного состояния License.rtf и всегда восстанавливал один итог.
    paragraphs = [
        (
            f"Настоящий установочный пакет программного обеспечения {app_name} предназначен "
            "для законного удалённого доступа, администрирования, технической поддержки и "
            "сопровождения информационных систем."
        ),
        (
            f"Правообладатель локализованной сборки и лицо, распространяющее данный установщик: "
            f"{company_name}. Информационная страница: {OFFICIAL_HOMEPAGE_URL}."
        ),
        (
            "Устанавливая и используя программное обеспечение, пользователь подтверждает, что "
            "обладает всеми необходимыми правами и полномочиями на подключение к удалённым "
            "устройствам, обработку информации на них и применение средств удалённого "
            "администрирования."
        ),
        (
            "Пользователь и организация, внедряющая решение, самостоятельно обеспечивают "
            "соблюдение законодательства Российской Федерации, включая Федеральный закон "
            "№ 152-ФЗ «О персональных данных», Федеральный закон № 149-ФЗ «Об информации, "
            "информационных технологиях и о защите информации», а также иных обязательных "
            "требований по защите информации, коммерческой тайны и служебных данных."
        ),
        (
            "Если в рамках работы программы осуществляется обработка персональных данных, "
            "пользователь обязан самостоятельно определить правовые основания обработки, "
            "состав обрабатываемых данных, сроки хранения, круг допущенных лиц и необходимые "
            "организационные и технические меры защиты."
        ),
        (
            f"Политика конфиденциальности: {OFFICIAL_PRIVACY_URL}. "
            f"Условия использования: {OFFICIAL_TERMS_URL}."
        ),
        (
            "Программа предоставляется по принципу «как есть», если иное прямо не установлено "
            "отдельным договором. Пользователь принимает на себя ответственность за законность "
            "сценария применения, корректность настроек безопасности и контроль доступа к "
            "выданной сборке."
        ),
        legal_notice,
    ]

    return build_rtf_document("Лицензионные условия и уведомление", paragraphs).encode("utf-8")


def build_padded_license_bytes(license_bytes: bytes, target_size: int) -> bytes:
    if len(license_bytes) > target_size:
        raise ValueError(
            "License RTF is larger than the existing MSI stream and cannot be written safely."
        )

    # В OLE-потоке MSI безопаснее дополнять новый документ пробелами до исходного размера,
    # чем оставлять хвост старого английского текста после конца нового RTF.
    return license_bytes + (b" " * (target_size - len(license_bytes)))


def repair_msi_license_stream(msi_path: Path) -> int:
    license_bytes = build_canonical_license_bytes()
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
    args = parser.parse_args()

    msi_path = Path(args.msi)

    replaced_streams = repair_msi_license_stream(msi_path)
    print(f"Repaired MSI streams: {replaced_streams}")
    verify_msi_streams(msi_path)
    print("MSI license streams verified successfully.")


if __name__ == "__main__":
    main()

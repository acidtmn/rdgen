from __future__ import annotations

import argparse
from pathlib import Path


LEGACY_CONDITION = "!key.is_empty() && (!token.is_empty() || !switch_code.is_empty())"


def patch_transport(source: str) -> str:
    """Сохраняем совместимость ТехПульт с hbbs 1.1.16 в исходниках клиента 1.5.0.

    Токен кабинета относится к нашему HTTPS API, а не к RustDesk Pro rendezvous.
    Он не должен включать прежний обязательный secure_tcp, на котором наш hbbs
    не отвечает. WebRTC выполняет собственный secure_tcp_required, а обмен
    ключами между компьютерами остаётся без изменений.

    Возвращаем изменённый исходник. При изменении ожидаемого upstream-контракта
    выбрасываем RuntimeError до записи файла.
    """
    replacements = (
        (f"let legacy_secure = {LEGACY_CONDITION};", "let legacy_secure = false;"),
        (f"if {LEGACY_CONDITION} {{", "if false {"),
    )

    # Проверяем оба места заранее, чтобы не оставить частично применённый патч.
    for original, _ in replacements:
        if source.count(original) != 1:
            raise RuntimeError("Изменился контракт rendezvous в src/client.rs")
    if "secure_tcp_required(&mut socket, &key).await" not in source:
        raise RuntimeError("Не найден защищённый обмен WebRTC в src/client.rs")

    for original, replacement in replacements:
        source = source.replace(original, replacement, 1)
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description="Настраиваем transport ТехПульт 1.5.0")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    path = args.project_root / "src/client.rs"
    source = path.read_text(encoding="utf-8")
    path.write_text(patch_transport(source), encoding="utf-8", newline="")
    print("Tehpult rendezvous transport patched; peer KX and WebRTC checks preserved")


if __name__ == "__main__":
    main()

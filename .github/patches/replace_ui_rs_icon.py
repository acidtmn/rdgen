from __future__ import annotations

from pathlib import Path
import argparse
import base64
import re


def make_parser() -> argparse.ArgumentParser:
    # Скрипт делаем отдельным и узким по ответственности,
    # чтобы замена встроенных base64-иконок в ui.rs не жила прямо внутри workflow-строки.
    parser = argparse.ArgumentParser(description="Replace embedded PNG payloads in src/ui.rs with a custom branding image.")
    parser.add_argument("--ui-rs", required=True, help="Path to src/ui.rs")
    parser.add_argument("--image", required=True, help="Path to PNG image that should replace the embedded payloads")
    return parser


def main() -> None:
    args = make_parser().parse_args()
    ui_rs_path = Path(args.ui_rs).resolve()
    image_path = Path(args.image).resolve()

    # Входные файлы валидируем сразу,
    # чтобы сборка падала быстро и понятно, а не зависала позже на попытке обработать несуществующий ресурс.
    if not ui_rs_path.exists():
        raise FileNotFoundError(f"ui.rs not found: {ui_rs_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")

    replacement_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    content = ui_rs_path.read_text(encoding="utf-8")

    # Меняем только встроенные PNG data URL,
    # чтобы не задеть произвольные другие строки в ui.rs и не зависеть от тяжёлого perl-regex по всему файлу.
    pattern = re.compile(
        r'(data:image/png;base64,)(iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHL[A-Za-z0-9+/=]+)(")',
        re.MULTILINE,
    )

    new_content, replacements = pattern.subn(rf"\1{replacement_b64}\3", content)

    # Ожидаем минимум одно совпадение.
    # Если upstream изменится и шаблон исчезнет, лучше получить явную ошибку, чем тихо собрать старый бренд.
    if replacements == 0:
        raise RuntimeError("No embedded PNG payloads were replaced in src/ui.rs")

    ui_rs_path.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    main()

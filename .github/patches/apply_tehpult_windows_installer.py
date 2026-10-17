from __future__ import annotations

import argparse
from pathlib import Path


ORIGINAL = '''fn validate_install_app_name(app_name: &str) -> ResultType<()> {
    if app_name.is_empty()
        || !app_name
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '-')
    {
        bail!("Application name must match [a-zA-Z0-9-]+");
    }
    Ok(())
}'''


def patch_installer(source: str) -> str:
    """Разрешаем фирменное имя в установщике службы Windows.

    Принимаем только точное имя ТехПульт дополнительно к штатному ASCII-набору.
    Проверки путей и опасных символов командной строки остаются без изменений.
    Возвращаем исправленный исходник; изменившийся контракт вызывает RuntimeError.
    """
    if source.count(ORIGINAL) != 1:
        raise RuntimeError("Изменился контракт имени приложения в установщике Windows")
    replacement = ORIGINAL.replace(
        '    if app_name.is_empty()',
        '    if app_name == "ТехПульт" {\n        return Ok(());\n    }\n'
        '    if app_name.is_empty()',
        1,
    )
    return source.replace(ORIGINAL, replacement, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Исправляем имя службы ТехПульт 1.5.0")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    path = args.project_root / "src/platform/windows.rs"
    path.write_text(patch_installer(path.read_text(encoding="utf-8")), encoding="utf-8", newline="")
    print("Tehpult service installer patched; command safety checks preserved")


if __name__ == "__main__":
    main()

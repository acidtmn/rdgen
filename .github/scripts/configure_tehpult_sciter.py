from __future__ import annotations

import os
from pathlib import Path


DEFAULT_PUBLIC_KEY = "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw="
CUSTOM_SIGNATURE_KEY = "5Qbwsde3unUcJBtrx9ZkvUmwFNoExHzpryHuPUdqlWM="


def required_environment(name: str) -> str:
    """Возвращает обязательную настройку генератора, не раскрывая её значение в логах CI."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная окружения {name}")
    return value


def read_text(path: Path) -> str:
    """Читает исходный файл строго как UTF-8, чтобы кириллица бренда не зависела от Windows locale."""
    if not path.is_file():
        raise RuntimeError(f"Не найден обязательный файл исходников: {path}")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    """Сохраняет изменённый файл в предсказуемой UTF-8-кодировке без преобразования переводов строк."""
    path.write_text(content, encoding="utf-8", newline="")


def replace_required(content: str, old: str, new: str, path: Path) -> str:
    """Выполняет обязательную замену и останавливает сборку, если upstream-контракт изменился."""
    if old in content:
        return content.replace(old, new, 1)
    if new in content:
        return content
    raise RuntimeError(f"В {path} не найден ожидаемый фрагмент: {old[:100]!r}")


def configure_package_metadata(root: Path, app_name: str, filename: str, site_url: str) -> None:
    """Настраивает PE-метаданные основного клиента и самораспаковывающегося portable-файла."""
    for relative_path in (Path("Cargo.toml"), Path("libs/portable/Cargo.toml")):
        path = root / relative_path
        content = read_text(path)

        # Эти поля отображаются в свойствах EXE Windows и не должны содержать имя исходного проекта.
        content = replace_required(content, 'description = "RustDesk Remote Desktop"', f'description = "{app_name} — удалённый доступ"', path)
        content = replace_required(content, 'ProductName = "RustDesk"', f'ProductName = "{app_name}"', path)
        content = replace_required(content, 'FileDescription = "RustDesk Remote Desktop"', f'FileDescription = "{app_name} — удалённый доступ"', path)
        content = replace_required(content, 'OriginalFilename = "rustdesk.exe"', f'OriginalFilename = "{filename}_x86.exe"', path)

        # Юридическое поле оставляем нейтральным: только продукт и его официальный сайт.
        old_copyright = 'LegalCopyright = "Copyright © 2026 Purslane Tech Pte. Ltd. All rights reserved."'
        new_copyright = f'LegalCopyright = "© 2026 {app_name}. {site_url}"'
        content = replace_required(content, old_copyright, new_copyright, path)
        write_text(path, content)

    portable_main = root / "libs/portable/src/main.rs"
    portable_content = read_text(portable_main)
    portable_content = replace_required(
        portable_content,
        'const APP_PREFIX: &str = "rustdesk";',
        f'const APP_PREFIX: &str = "{filename}";',
        portable_main,
    )
    write_text(portable_main, portable_content)


def configure_translations(root: Path, app_name: str) -> None:
    """Заменяет название исходного продукта во встроенных переводах legacy-интерфейса Sciter."""
    language_files = sorted((root / "src/lang").glob("*.rs"))
    if not language_files:
        raise RuntimeError("Не найдены встроенные языковые файлы src/lang/*.rs")

    replaced_files = 0
    for path in language_files:
        content = read_text(path)
        if "RustDesk" not in content:
            continue
        write_text(path, content.replace("RustDesk", app_name))
        replaced_files += 1

    if replaced_files == 0:
        raise RuntimeError("Название RustDesk не найдено ни в одном языковом файле")


def configure_public_links(root: Path, download_url: str, site_url: str) -> None:
    """Направляет ссылки legacy-клиента только на официальные страницы ТехПульт."""
    index_tis = root / "src/ui/index.tis"
    index_content = read_text(index_tis)
    index_content = replace_required(index_content, "https://rustdesk.com/download", download_url, index_tis)
    write_text(index_tis, index_content)

    build_script = root / "build.py"
    build_content = read_text(build_script)
    build_content = replace_required(build_content, "Homepage: https://rustdesk.com", f"Homepage: {site_url}", build_script)
    write_text(build_script, build_content)


def configure_network(root: Path, server: str, public_key: str, api_server: str) -> None:
    """Вшивает адрес сервера, публичный ключ и API в клиент без вывода значений в журнал сборки."""
    config_path = root / "libs/hbb_common/src/config.rs"
    config_content = read_text(config_path)
    config_content = replace_required(config_content, "rs-ny.rustdesk.com", server, config_path)
    config_content = replace_required(config_content, DEFAULT_PUBLIC_KEY, public_key, config_path)
    write_text(config_path, config_content)

    common_path = root / "src/common.rs"
    common_content = read_text(common_path)
    common_content = replace_required(common_content, "https://admin.rustdesk.com", api_server, common_path)
    write_text(common_path, common_content)


def allow_embedded_custom_configuration(root: Path) -> None:
    """Разрешает bundled custom_.txt, который генератор кладёт внутрь доверенного portable-архива."""
    path = root / "src/common.rs"
    content = read_text(path)

    # Генератор использует отдельное имя custom_.txt, чтобы клиент не подхватил случайный внешний файл рядом с EXE.
    if "custom_.txt" not in content:
        if "custom.txt" not in content:
            raise RuntimeError(f"В {path} не найдено имя файла custom.txt")
        content = content.replace("custom.txt", "custom_.txt")

    # Upstream проверяет публичные custom-файлы собственным ключом. Для встроенного в наш EXE файла эта проверка
    # заменяется доверием к самому дистрибутиву: его хеш публикуется на сайте и проверяется перед выдачей.
    marker = f'const KEY: &str = "{CUSTOM_SIGNATURE_KEY}";'
    if marker in content:
        lines = content.splitlines(keepends=True)
        marker_index = next(index for index, line in enumerate(lines) if line.strip() == marker)
        del lines[marker_index : marker_index + 9]
        content = "".join(lines)

    if marker in content or "custom_.txt" not in content:
        raise RuntimeError(f"Не удалось подготовить встроенную конфигурацию в {path}")
    write_text(path, content)


def configure(root: Path) -> None:
    """Применяет все продуктовые настройки к чистому checkout RustDesk 1.4.9."""
    app_name = required_environment("appname")
    filename = required_environment("filename")
    server = required_environment("server")
    public_key = required_environment("key")
    api_server = required_environment("apiServer")
    download_url = required_environment("downloadLink")
    site_url = required_environment("urlLink").rstrip("/")

    configure_package_metadata(root, app_name, filename, site_url)
    configure_translations(root, app_name)
    configure_public_links(root, download_url, site_url)
    configure_network(root, server, public_key, api_server)
    allow_embedded_custom_configuration(root)


if __name__ == "__main__":
    configure(Path.cwd())
    print("Конфигурация ТехПульт для Windows x86 применена")

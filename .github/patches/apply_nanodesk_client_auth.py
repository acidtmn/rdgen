from __future__ import annotations

import argparse
import re
from pathlib import Path


def replace_required(content: str, old: str, new: str, file_path: Path) -> str:
    """Заменяет обязательный фрагмент и останавливает сборку при изменении upstream-разметки."""
    if old not in content:
        raise RuntimeError(f"Не найден ожидаемый фрагмент в {file_path}: {old[:80]!r}")
    return content.replace(old, new, 1)


def remove_legacy_account_helpers(content: str, file_path: Path) -> str:
    """Удаляет только старые помощники имени учётной записи, заменённые NanoDesk-профилем."""
    pattern = re.compile(
        r"\nfunction getUserName\(\) \{.*?\n\}\n\n"
        r"function getAccountLabelWithHandle\(\) \{.*?\n\}\n",
        re.DOTALL,
    )
    content, replacements = pattern.subn("\n", content, count=1)
    if replacements != 1:
        raise RuntimeError(f"Не найден блок legacy account helpers в {file_path}")
    return content


def remove_legacy_account_flow(content: str, file_path: Path) -> str:
    """Удаляет password/2FA API RustDesk Pro, не затрагивая сведения об устройстве."""
    start_marker = "function set_local_user_info(user) {"
    end_marker = "function getDeviceInfo() {"
    start = content.find(start_marker)
    end = content.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError(f"Не найден legacy account flow в {file_path}")
    return content[:start] + content[end:]


def patch_index_html(project_root: Path, template_path: Path) -> None:
    """Регистрирует отдельный auth-модуль до адресной книги и основного UI."""
    index_html = project_root / "src" / "ui" / "index.html"
    content = index_html.read_text(encoding="utf-8")
    include_marker = '            include "msgbox.tis";\n'
    include_line = '            include "client_auth.tis";\n'

    if include_line not in content:
        content = replace_required(content, include_marker, include_marker + include_line, index_html)

    index_html.write_text(content, encoding="utf-8")
    (index_html.parent / "client_auth.tis").write_text(
        template_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def patch_index_tis(project_root: Path) -> None:
    """Переключает меню аккаунта со старого Pro API на NanoDesk Device Flow."""
    index_tis = project_root / "src" / "ui" / "index.tis"
    content = index_tis.read_text(encoding="utf-8")

    if "function nanodeskLogin()" in content:
        raise RuntimeError("client_auth.tis должен подключаться отдельно, а не встраиваться в index.tis")

    content = remove_legacy_account_helpers(content, index_tis)
    content = remove_legacy_account_flow(content, index_tis)
    content = replace_required(
        content,
        'handler.get_local_option("access_token") ? getAccountLabelWithHandle() : \'\'',
        "hasNanodeskSession() ? getNanodeskAccountLabel() : ''",
        index_tis,
    )

    # После удаления старых функций оставшиеся вызовы относятся только к меню и стартовой инициализации.
    content = content.replace("login();", "nanodeskLogin();")
    content = content.replace("logout();", "nanodeskLogout();")
    content = content.replace("refreshCurrentUser();", "refreshNanodeskCurrentUser();")

    required_markers = (
        "nanodeskLogin();",
        "nanodeskLogout();",
        "refreshNanodeskCurrentUser();",
        "hasNanodeskSession() ? getNanodeskAccountLabel() : ''",
    )
    for marker in required_markers:
        if marker not in content:
            raise RuntimeError(f"Не удалось внедрить {marker!r} в {index_tis}")

    index_tis.write_text(content, encoding="utf-8")


def patch_address_book(project_root: Path) -> None:
    """Направляет штатный интерфейс адресной книги в NanoDesk API с отдельным Bearer-токеном."""
    address_book = project_root / "src" / "ui" / "ab.tis"
    content = address_book.read_text(encoding="utf-8")
    replacements = (
        ('handler.get_local_option("access_token")', "hasNanodeskSession()"),
        ("refreshCurrentUser();", "refreshNanodeskCurrentUser();"),
        ("login();", "nanodeskLogin();"),
        ('handler.get_api_server() + "/api/ab/get"', 'nanodesk_address_book_api + "/get"'),
        ('handler.get_api_server() + "/api/ab"', 'nanodesk_address_book_api + "/save"'),
        ("getHttpHeaders()", "getNanodeskAuthHeaders()"),
    )

    for old, new in replacements:
        content = replace_required(content, old, new, address_book)

    address_book.write_text(content, encoding="utf-8")


def patch_flutter_login(project_root: Path) -> None:
    """Заменяет password/Google/WebAuthn-форму Flutter на единый браузерный вход NanoDesk."""
    login_file = project_root / "flutter" / "lib" / "common" / "widgets" / "login.dart"
    content = login_file.read_text(encoding="utf-8")

    label_pattern = re.compile(
        r"final opLabel = \{\s*'github': 'GitHub',\s*'gitlab': 'GitLab'\s*\}"
        r"\[op\.toLowerCase\(\)\] \?\?\s*toCapitalized\(op\);"
    )
    content, replacements = label_pattern.subn(
        """final opLabel = {
          'github': 'GitHub',
          'gitlab': 'GitLab',
          'nanodesk': 'NanoDesk ID'
        }[op.toLowerCase()] ??
        toCapitalized(op);""",
        content,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError(f"Не найден label провайдера в {login_file}")

    auth_widget_pattern = re.compile(
        r"    thirdAuthWidget\(\) => Obx\(\(\) \{.*?\n        \}\);\n\n"
        r"    final title = Row\(",
        re.DOTALL,
    )
    auth_widget = """    thirdAuthWidget() => Obx(() {
          return Offstage(
            offstage: loginOptions.isEmpty,
            child: LoginWidgetOP(
              ops: loginOptions
                  .map((e) => ConfigOP(op: e['name'], icon: e['icon']))
                  .toList(),
              curOP: curOP,
              cbLogin: (Map<String, dynamic> authBody) async {
                LoginResponse? resp;
                try {
                  // Rust-слой уже сохранил отзывной токен после браузерного подтверждения.
                  resp = gFFI.userModel.getLoginResponseFromAuthBody(authBody);
                } catch (e) {
                  debugPrint('Failed to parse NanoDesk login body: "$authBody"');
                }
                close(true);
                if (resp != null) {
                  handleLoginResponse(resp, false, null);
                }
              },
            ),
          );
        });

    final title = Row("""
    content, replacements = auth_widget_pattern.subn(auth_widget, content, count=1)
    if replacements != 1:
        raise RuntimeError(f"Не найден блок OIDC-кнопок в {login_file}")

    dialog_start = content.find("    return CustomAlertDialog(")
    content_start = content.find("      content: Column(", dialog_start)
    cancel_start = content.find("      onCancel: onDialogCancel,", content_start)
    if dialog_start < 0 or content_start < 0 or cancel_start < 0:
        raise RuntimeError(f"Не найдено содержимое login dialog в {login_file}")

    premium_content = """      content: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: const Color(0xff4f46e5),
              borderRadius: BorderRadius.circular(16),
            ),
            alignment: Alignment.center,
            child: const Text(
              'N',
              style: TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Вход в NanoDesk',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          const SizedBox(
            width: 300,
            child: Text(
              'Продолжите в защищённом окне браузера. Доступны код из письма, Яндекс ID и VK ID.',
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 20),
          thirdAuthWidget(),
        ],
      ),
"""
    content = content[:content_start] + premium_content + content[cancel_start:]
    content = replace_required(content, "      onSubmit: onLogin,", "      onSubmit: () {},", login_file)

    login_file.write_text(content, encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Внедряет NanoDesk Device Authorization в Windows-клиент")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--template", type=Path, default=Path("nanodesk_client_auth.tis"))
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    project_root = args.project_root.resolve()
    template_path = args.template.resolve()

    if not template_path.is_file():
        raise FileNotFoundError(f"Не найден шаблон авторизации: {template_path}")

    patch_index_html(project_root, template_path)
    patch_index_tis(project_root)
    patch_address_book(project_root)
    patch_flutter_login(project_root)
    print("NanoDesk client authorization patch applied")


if __name__ == "__main__":
    main()

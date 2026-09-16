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
    """Переключает меню аккаунта со старого Pro API на Device Flow ТехПульт."""
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


def patch_dashboard(project_root: Path) -> None:
    """Добавляет самостоятельные карточки авторизации и поддержки в desktop-экран клиента."""
    index_tis = project_root / "src" / "ui" / "index.tis"
    content = index_tis.read_text(encoding="utf-8")
    panels = '''class AccountPanel: Reactor.Component {
    function render() {
        var accountLabel = hasNanodeskSession() ? getNanodeskAccountLabel() : "";
        return <div .card-account>
            <div .panel-kicker>ТЕХПУЛЬТ ID</div>
            <div .title>Авторизация</div>
            <div .lighter-text>{accountLabel ? "Вы вошли как " + accountLabel + ". Адресная книга синхронизируется между вашими устройствами." : "Войдите, чтобы синхронизировать адресную книгу и управлять устройствами в личном кабинете."}</div>
            {accountLabel
                ? <button .button .outline #account-manage>Открыть кабинет</button>
                : <button .button #account-login>Войти в ТехПульт</button>}
        </div>;
    }

    event click $(#account-login) () {
        nanodeskLogin();
    }

    event click $(#account-manage) () {
        handler.open_url("https://tehpult.ru/account");
    }
}

class SupportPanel: Reactor.Component {
    function render() {
        return <div .card-support>
            <div .panel-kicker>ПОМОЩЬ РЯДОМ</div>
            <div .title>Нужна поддержка?</div>
            <div>Поможем с подключением, установкой и безопасной настройкой удалённого доступа.</div>
            <button .button .outline #open-support>Открыть поддержку</button>
        </div>;
    }

    event click $(#open-support) () {
        handler.open_url("https://tehpult.ru/support");
    }
}

'''
    content = replace_required(content, "class App: Reactor.Component\n", panels + "class App: Reactor.Component\n", index_tis)
    content = replace_required(
        content,
        '''                        <div .card-connect>
                            <div .title>{translate('Control Remote Desktop')}</div>
                            <ID @{this.remote_id} />
                            <div .right-buttons>
                                <button .button .outline #file-transfer>{translate('Transfer file')}</button>
                                <button .button #connect>{translate('Connect')}</button>
                            </div>
                        </div>''',
        '''                        <div .dashboard-cards>
                            <div .card-connect>
                                <div .title>{translate('Control Remote Desktop')}</div>
                                <ID @{this.remote_id} />
                                <div .right-buttons>
                                    <button .button .outline #file-transfer>{translate('Transfer file')}</button>
                                    <button .button #connect>{translate('Connect')}</button>
                                </div>
                            </div>
                            <AccountPanel />
                            <SupportPanel />
                        </div>''',
        index_tis,
    )
    index_tis.write_text(content, encoding="utf-8")


def patch_dashboard_styles(project_root: Path) -> None:
    """Оформляет добавленные карточки только средствами, поддерживаемыми Sciter."""
    stylesheet = project_root / "src" / "ui" / "index.css"
    content = stylesheet.read_text(encoding="utf-8")
    content = replace_required(
        content,
        '''.right-content {
    overflow: scroll-indicator;
    padding: 1.6em;
    border-spacing: 1.6em;
    size: *;
    flow: vertical;
}
''',
        '''.right-content {
    overflow: scroll-indicator;
    padding: 1.6em;
    border-spacing: 1.6em;
    size: *;
    flow: vertical;
}

.dashboard-cards {
    flow: horizontal;
    border-spacing: 1em;
}
''',
        stylesheet,
    )
    content = replace_required(
        content,
        '''.card-connect {
    @CARD;
    width: 320px;
}
''',
        '''.card-connect {
    @CARD;
    width: 320px;
}

.card-account {
    @CARD;
    width: 280px;
    min-height: 130px;
}

.card-support {
    @CARD;
    width: 280px;
    min-height: 130px;
    color: white;
    background: #0d5bd7;
}

.card-support .title,
.card-support .panel-kicker {
    color: white;
}

.card-support .button.outline {
    color: white;
    border-color: rgba(255, 255, 255, .7);
}

.panel-kicker {
    color: #155eef;
    font-size: .72em;
    font-weight: 700;
    letter-spacing: .1em;
}

.card-account .lighter-text,
.card-support > div:nth-child(3) {
    min-height: 3.6em;
    padding-top: .35em;
}

.card-account > button,
.card-support > button {
    margin-top: .8em;
}
''',
        stylesheet,
    )
    stylesheet.write_text(content, encoding="utf-8")


def patch_address_book(project_root: Path) -> None:
    """Направляет штатный интерфейс адресной книги в API ТехПульт с отдельным Bearer-токеном."""
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
    """Заменяет password/Google/WebAuthn-форму Flutter на единый браузерный вход ТехПульт."""
    login_file = project_root / "flutter" / "lib" / "common" / "widgets" / "login.dart"
    content = login_file.read_text(encoding="utf-8")

    label_pattern = re.compile(
        r"final opLabel = \{\s*'github': 'GitHub',\s*'gitlab': 'GitLab'\s*\}"
        r"\[op\.toLowerCase\(\)\] \?\?\s*toCapitalized\(op\);"
    )
    content, _ = label_pattern.subn(
        """final opLabel = {
          'github': 'GitHub',
          'gitlab': 'GitLab',
          'nanodesk': 'ТехПульт ID',
          'tehpult': 'ТехПульт ID',
          'техпульт': 'ТехПульт ID'
        }[op.toLowerCase()] ??
        toCapitalized(op);""",
        content,
        count=1,
    )
    # В 1.4.9 карта названий провайдеров удалена upstream: имя «ТехПульт» приходит из login-options.

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
                  debugPrint('Failed to parse Tehpult login body: "$authBody"');
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
              color: const Color(0xff126bff),
              borderRadius: BorderRadius.circular(16),
            ),
            alignment: Alignment.center,
            child: const Text(
              'ТП',
              style: TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Вход в ТехПульт',
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


def patch_flutter_dashboard(project_root: Path) -> None:
    """Добавляет видимые на Flutter-версии клиента карточки входа и поддержки."""
    dashboard_file = (
        project_root / "flutter" / "lib" / "desktop" / "pages" / "desktop_home_page.dart"
    )
    content = dashboard_file.read_text(encoding="utf-8")

    login_import = "import '../../common/widgets/login.dart';\n"
    if login_import not in content:
        content = replace_required(
            content,
            "import '../widgets/button.dart';\n",
            "import '../widgets/button.dart';\n" + login_import,
            dashboard_file,
        )

    content = replace_required(
        content,
        '''  buildRightPane(BuildContext context) {
    return Container(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: ConnectionPage(),
    );
  }
''',
        '''  buildRightPane(BuildContext context) {
    return Container(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: Column(
        children: [
          const TehpultDesktopActionStrip(),
          const Divider(height: 1),
          const Expanded(child: ConnectionPage()),
        ],
      ),
    );
  }
''',
        dashboard_file,
    )

    card = '''
class TehpultDesktopActionStrip extends StatelessWidget {
  const TehpultDesktopActionStrip({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Obx(() {
      final isLoggedIn = gFFI.userModel.isLogin;
      final accountName = gFFI.userModel.displayNameOrUserName;
      return Padding(
        padding: const EdgeInsets.fromLTRB(22, 18, 22, 16),
        child: Row(
          children: [
            Expanded(
              flex: 3,
              child: _TehpultActionCard(
                icon: Icons.verified_user_outlined,
                title: isLoggedIn ? 'Аккаунт подключён' : 'Авторизация',
                description: isLoggedIn
                    ? 'Вы вошли как $accountName. Адресная книга доступна на ваших устройствах.'
                    : 'Войдите, чтобы синхронизировать адресную книгу и управлять устройствами.',
                actionLabel: isLoggedIn ? 'Открыть кабинет' : 'Войти в ТехПульт',
                onAction: () async {
                  if (isLoggedIn) {
                    await launchUrl(Uri.parse('https://tehpult.ru/account'));
                    return;
                  }
                  await loginDialog();
                },
                color: const Color(0xff126bff),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              flex: 2,
              child: _TehpultActionCard(
                icon: Icons.support_agent_outlined,
                title: 'Нужна помощь?',
                description: 'Подскажем по установке, подключению и безопасной настройке.',
                actionLabel: 'Открыть поддержку',
                onAction: () async {
                  await launchUrl(Uri.parse('https://tehpult.ru/support'));
                },
                color: theme.colorScheme.secondary,
              ),
            ),
          ],
        ),
      ),
    });
    }
}

class _TehpultActionCard extends StatelessWidget {
  const _TehpultActionCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.actionLabel,
    required this.onAction,
    required this.color,
  });

  final IconData icon;
  final String title;
  final String description;
  final String actionLabel;
  final Future<void> Function() onAction;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 116),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.22)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(description, maxLines: 2, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 10),
                TextButton(onPressed: onAction, child: Text(actionLabel)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

'''
    content = replace_required(
        content,
        "const borderColor = Color(0xFF2F65BA);\n\n",
        "const borderColor = Color(0xFF2F65BA);\n\n" + card,
        dashboard_file,
    )
    dashboard_file.write_text(content, encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Внедряет авторизацию ТехПульт в клиент")
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
    patch_dashboard(project_root)
    patch_dashboard_styles(project_root)
    patch_address_book(project_root)
    patch_flutter_login(project_root)
    patch_flutter_dashboard(project_root)
    # Windows runner использует cp1252 для stdout, поэтому служебный результат оставляем ASCII.
    print("Tehpult client authorization patch applied")


if __name__ == "__main__":
    main()

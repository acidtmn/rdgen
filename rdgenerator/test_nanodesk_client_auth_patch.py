import importlib.util
import tempfile
import unittest
from pathlib import Path


PATCH_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "patches"
    / "apply_nanodesk_client_auth.py"
)
TEMPLATE_PATH = PATCH_PATH.with_name("nanodesk_client_auth.tis")


def load_patch_module():
    spec = importlib.util.spec_from_file_location("apply_nanodesk_client_auth", PATCH_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class NanoDeskClientAuthPatchTest(unittest.TestCase):
    def setUp(self):
        self.patch = load_patch_module()

    def test_patches_sciter_account_and_address_book(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            ui_dir = project_root / "src" / "ui"
            ui_dir.mkdir(parents=True)

            # Фикстура сохраняет только контракты upstream, от которых зависит патчер.
            (ui_dir / "index.html").write_text(
                '<script>\n            include "common.tis";\n'
                '            include "msgbox.tis";\n'
                '            include "ab.tis";\n'
                '            include "index.tis";\n</script>\n',
                encoding="utf-8",
            )
            (ui_dir / "index.tis").write_text(
                """
function getUserName() {
    return '';
}

function getAccountLabelWithHandle() {
    return '';
}

var accountLabel = handler.get_local_option("access_token") ? getAccountLabelWithHandle() : '';
event click $(li#login) () {
    login();
}
event click $(li#logout) () {
    logout();
}
function self.ready() {
    refreshCurrentUser();
}
function set_local_user_info(user) {
    return user;
}
function login() {
    return;
}
function logout() {
    return;
}
function refreshCurrentUser() {
    return;
}
function getHttpHeaders() {
    return "";
}
function getDeviceInfo() {
    return {};
}
""",
                encoding="utf-8",
            )
            (ui_dir / "ab.tis").write_text(
                """
if (!handler.get_local_option("access_token")) {}
refreshCurrentUser();
login();
httpRequest(handler.get_api_server() + "/api/ab/get", #post, {});
httpRequest(handler.get_api_server() + "/api/ab", #post, {});
getHttpHeaders();
""",
                encoding="utf-8",
            )
            flutter_dir = project_root / "flutter" / "lib" / "common" / "widgets"
            flutter_dir.mkdir(parents=True)
            (flutter_dir / "login.dart").write_text(
                """
final opLabel = {
          'github': 'GitHub',
          'gitlab': 'GitLab'
        }[op.toLowerCase()] ??
        toCapitalized(op);

Future<bool?> loginDialog() async {
    thirdAuthWidget() => Obx(() {
          return Offstage(
            offstage: loginOptions.isEmpty,
            child: Column(children: [LoginWidgetOP()]),
          );
        });

    final title = Row();
    return CustomAlertDialog(
      title: title,
      content: Column(
        children: [
          LoginWidgetUserPass(),
          thirdAuthWidget(),
        ],
      ),
      onCancel: onDialogCancel,
      onSubmit: onLogin,
    );
}
""",
                encoding="utf-8",
            )

            self.patch.patch_index_html(project_root, TEMPLATE_PATH)
            self.patch.patch_index_tis(project_root)
            self.patch.patch_address_book(project_root)
            self.patch.patch_flutter_login(project_root)

            index_html = (ui_dir / "index.html").read_text(encoding="utf-8")
            index_tis = (ui_dir / "index.tis").read_text(encoding="utf-8")
            address_book = (ui_dir / "ab.tis").read_text(encoding="utf-8")
            flutter_login = (flutter_dir / "login.dart").read_text(encoding="utf-8")

            self.assertIn('include "client_auth.tis";', index_html)
            self.assertIn("nanodeskLogin();", index_tis)
            self.assertIn("nanodeskLogout();", index_tis)
            self.assertIn("refreshNanodeskCurrentUser();", index_tis)
            self.assertNotIn("function login()", index_tis)
            self.assertIn('nanodesk_address_book_api + "/get"', address_book)
            self.assertIn('nanodesk_address_book_api + "/save"', address_book)
            self.assertIn("getNanodeskAuthHeaders()", address_book)
            self.assertIn("'nanodesk': 'NanoDesk ID'", flutter_login)
            self.assertIn("'Вход в NanoDesk'", flutter_login)
            self.assertIn("VK ID.", flutter_login)
            self.assertNotIn("LoginWidgetUserPass()", flutter_login)
            self.assertNotIn("translate('or')", flutter_login)
            self.assertEqual(
                (ui_dir / "client_auth.tis").read_text(encoding="utf-8"),
                TEMPLATE_PATH.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

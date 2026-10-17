import importlib.util
from pathlib import Path
import unittest


PATCH_PATH = Path(__file__).resolve().parents[1] / ".github/patches/apply_tehpult_transport.py"
SPEC = importlib.util.spec_from_file_location("tehpult_transport", PATCH_PATH)
TRANSPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSPORT)


class TehpultTransportTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            f"let legacy_secure = {TRANSPORT.LEGACY_CONDITION};\n"
            "secure_tcp_required(&mut socket, &key).await;\n"
            "verify_signed_params();\n"
            f"if {TRANSPORT.LEGACY_CONDITION} {{\n"
            "    secure_tcp(&mut socket, key).await?;\n}\n"
            "set_negotiated_key(transcript);\n"
        )

    def test_preserves_webrtc_and_peer_key_verification(self):
        result = TRANSPORT.patch_transport(self.source)
        self.assertIn("let legacy_secure = false;", result)
        self.assertIn("if false {", result)
        self.assertNotIn(TRANSPORT.LEGACY_CONDITION, result)
        self.assertIn("secure_tcp_required(&mut socket, &key).await;", result)
        self.assertIn("verify_signed_params();", result)
        self.assertIn("set_negotiated_key(transcript);", result)

    def test_rejects_changed_upstream_before_partial_patch(self):
        changed = self.source.replace("let legacy_secure", "let another_secure")
        with self.assertRaisesRegex(RuntimeError, "контракт rendezvous"):
            TRANSPORT.patch_transport(changed)

    def test_rejects_missing_protected_webrtc_path(self):
        changed = self.source.replace("secure_tcp_required", "unprotected_tcp")
        with self.assertRaisesRegex(RuntimeError, "защищённый обмен WebRTC"):
            TRANSPORT.patch_transport(changed)


if __name__ == "__main__":
    unittest.main()

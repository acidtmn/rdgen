from django.test import SimpleTestCase

from .helper.workflow_target import WorkflowTargetHelper


class WorkflowTargetHelperTests(SimpleTestCase):
    def test_selfhosted_is_disabled_when_environment_flag_is_off(self):
        self.assertFalse(
            WorkflowTargetHelper.should_use_selfhosted(
                user_secret="secret",
                settings_secret="secret",
                selfhosted_enabled=False,
            )
        )

    def test_selfhosted_is_enabled_only_for_matching_secret(self):
        self.assertTrue(
            WorkflowTargetHelper.should_use_selfhosted(
                user_secret="secret",
                settings_secret="secret",
                selfhosted_enabled=True,
            )
        )
        self.assertFalse(
            WorkflowTargetHelper.should_use_selfhosted(
                user_secret="wrong",
                settings_secret="secret",
                selfhosted_enabled=True,
            )
        )

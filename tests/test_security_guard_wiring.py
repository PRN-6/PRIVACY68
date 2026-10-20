"""
Tests that the 3-tier security model is actually WIRED into the execution
path, not just defined.

The SecurityGuard class existed and was unit-tested in isolation, but nothing
in the command pipeline called it — so "delete file X" executed immediately
with no confirmation. These tests pin the real behaviour.

The delete function is always mocked: no test here ever removes a real file.
"""

import unittest
from unittest.mock import patch

from computer_use.security_guard import ActionRiskLevel, security_guard
from actions.executor import execute_system_command_detailed


class TestSecurityGuardWiring(unittest.TestCase):
    """Deletion must be gated behind a voice confirmation."""

    def setUp(self):
        # Make sure no confirmation is left pending from a previous test.
        security_guard.cancel_pending()

    def tearDown(self):
        security_guard.cancel_pending()

    @patch("computer_use.system_tools.delete_file")
    def test_delete_is_not_executed_before_confirmation(self, mock_delete):
        """A delete request is queued, not performed."""
        mock_delete.return_value = {"success": True, "message": "Deleted."}

        res = execute_system_command_detailed("delete file p68_probe.txt")

        self.assertEqual(res.get("method"), "security_guard")
        self.assertFalse(res.get("success"))
        self.assertIn("sure", res.get("message", "").lower())
        mock_delete.assert_not_called()

    @patch("computer_use.system_tools.delete_file")
    def test_confirmation_executes_the_delete(self, mock_delete):
        """Saying 'yes' performs the queued delete."""
        mock_delete.return_value = {"success": True, "message": "Deleted."}

        execute_system_command_detailed("delete file p68_probe.txt")
        self.assertTrue(security_guard.check_has_pending())

        success, message, _ = security_guard.confirm_pending()

        self.assertTrue(success)
        mock_delete.assert_called_once()

    @patch("computer_use.system_tools.delete_file")
    def test_cancellation_blocks_the_delete(self, mock_delete):
        """Saying 'no' aborts the queued delete."""
        execute_system_command_detailed("delete file p68_probe.txt")

        security_guard.cancel_pending()

        mock_delete.assert_not_called()
        self.assertFalse(security_guard.check_has_pending())

    def test_risk_levels_are_assigned(self):
        """The guard classifies delete as SENSITIVE and open as SAFE."""
        self.assertEqual(
            security_guard.get_risk_level("delete_file"),
            ActionRiskLevel.SENSITIVE,
        )
        self.assertEqual(
            security_guard.get_risk_level("open_app"),
            ActionRiskLevel.SAFE,
        )

    @patch("actions.executor.api_lane_router.try_execute_api")
    @patch("actions.executor.fast_lane_router.try_execute_plugin_fast", return_value=None)
    @patch("actions.executor.fast_lane_router.try_execute_fast")
    def test_compound_gates_only_the_destructive_clause(self, mock_fast, mock_plugin, mock_api):
        """A compound command still runs its safe clauses; the delete waits."""
        def fake_fast(text):
            if text == "mute the volume":
                return {"success": True, "tool": "volume_mute", "message": "Muted."}
            return None

        mock_fast.side_effect = fake_fast
        mock_api.return_value = {
            "handled": True,
            "tool": "delete_file",
            "method": "security_guard",
            "success": False,
            "message": "Are you sure? Say 'Yes' or 'Confirm' to proceed, or 'Cancel'.",
        }

        res = execute_system_command_detailed("mute the volume and delete file p68_probe.txt")

        details = res.get("details", {})
        self.assertEqual(details.get("succeeded"), 1)
        self.assertTrue(details.get("awaiting_confirmation"))
        # The safe clause ran; the destructive one was queued for confirmation.
        mock_fast.assert_any_call("mute the volume")
        self.assertEqual(
            [c for c in details.get("clauses", [])],
            ["mute the volume", "delete file p68_probe.txt"],
        )


if __name__ == "__main__":
    unittest.main()

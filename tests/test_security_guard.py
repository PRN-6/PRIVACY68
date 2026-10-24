import unittest
from unittest.mock import patch

from computer_use.security_guard import ActionRiskLevel, SecurityGuard


class TestSecurityGuard(unittest.TestCase):
    def setUp(self):
        self.guard = SecurityGuard()

    def test_safe_action_executes_immediately(self):
        action = unittest.mock.Mock(return_value="done")

        success, message, result = self.guard.request_execution(
            "open_app", action, args=("notepad",), description="open Notepad"
        )

        self.assertTrue(success)
        self.assertEqual(message, "Executed successfully")
        self.assertEqual(result, "done")
        action.assert_called_once_with("notepad")
        self.assertFalse(self.guard.check_has_pending())

    def test_sensitive_action_requires_confirmation_and_runs_once(self):
        action = unittest.mock.Mock(return_value="deleted")

        success, prompt, result = self.guard.request_execution(
            "delete_file", action, args=("notes.txt",), description="delete notes"
        )

        self.assertFalse(success)
        self.assertIn("Are you sure?", prompt)
        self.assertEqual(result, {"requires_confirmation": True, "action": "delete_file"})
        action.assert_not_called()
        self.assertEqual(self.guard.get_risk_level("delete_file"), ActionRiskLevel.SENSITIVE)

        success, message, result = self.guard.confirm_pending()

        self.assertTrue(success)
        self.assertIn("delete notes", message)
        self.assertEqual(result, "deleted")
        action.assert_called_once_with("notes.txt")
        self.assertFalse(self.guard.check_has_pending())

    def test_cancelled_action_does_not_execute(self):
        action = unittest.mock.Mock()
        self.guard.request_execution("delete_file", action, description="delete notes")

        message = self.guard.cancel_pending()

        self.assertIn("aborted", message)
        self.assertFalse(self.guard.check_has_pending())
        action.assert_not_called()

    def test_expired_action_cannot_be_confirmed(self):
        with patch("computer_use.security_guard.time.time", return_value=100.0):
            self.guard.request_execution("delete_file", lambda: "deleted")

        with patch("computer_use.security_guard.time.time", return_value=116.0):
            self.assertFalse(self.guard.check_has_pending())
            success, message, result = self.guard.confirm_pending()

        self.assertFalse(success)
        self.assertIn("No active action", message)
        self.assertIsNone(result)

    def test_failed_action_is_reported_and_audited(self):
        def fail():
            raise RuntimeError("operation failed")

        success, message, result = self.guard.request_execution("open_app", fail)

        self.assertFalse(success)
        self.assertEqual(message, "operation failed")
        self.assertIsNone(result)
        self.assertEqual(self.guard._audit_log[-1]["status"], "ERROR: operation failed")


if __name__ == "__main__":
    unittest.main()

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

    def test_inspect_code_risk_safe(self):
        code = "import os\nprint('Hello World')\nx = 1 + 1"
        risk, action_id, desc = self.guard.inspect_code_risk(code)
        self.assertEqual(risk, ActionRiskLevel.SAFE)
        self.assertEqual(action_id, "agent_code")

    def test_inspect_code_risk_sensitive(self):
        code = "import shutil\nshutil.rmtree('C:/test_folder')"
        risk, action_id, desc = self.guard.inspect_code_risk(code)
        self.assertEqual(risk, ActionRiskLevel.SENSITIVE)
        self.assertEqual(action_id, "delete_file")

        code2 = "import subprocess\nsubprocess.run(['shutdown', '/s', '/t', '0'])"
        risk2, action_id2, desc2 = self.guard.inspect_code_risk(code2)
        self.assertEqual(risk2, ActionRiskLevel.SENSITIVE)
        self.assertEqual(action_id2, "shutdown_pc")

    def test_inspect_code_risk_critical(self):
        code = "import winreg\nkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'Software')"
        risk, action_id, desc = self.guard.inspect_code_risk(code)
        self.assertEqual(risk, ActionRiskLevel.CRITICAL)
        self.assertEqual(action_id, "modify_registry")

        code2 = "import os\nos.system('format D: /fs:NTFS /q')"
        risk2, action_id2, desc2 = self.guard.inspect_code_risk(code2)
        self.assertEqual(risk2, ActionRiskLevel.CRITICAL)
        self.assertEqual(action_id2, "format_drive")


if __name__ == "__main__":
    unittest.main()

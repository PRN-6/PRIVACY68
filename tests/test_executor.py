import unittest
from unittest.mock import Mock, patch

from actions import executor
from computer_use.security_guard import SecurityGuard


class TestActionExecutor(unittest.TestCase):
    def setUp(self):
        self.guard = SecurityGuard()
        self.guard_patch = patch.object(executor, "security_guard", self.guard)
        self.guard_patch.start()
        self.addCleanup(self.guard_patch.stop)

    def test_empty_command_is_rejected(self):
        with patch.object(executor, "autocorrect_speech_command", return_value=""):
            result = executor.execute_system_command_detailed("  ")

        self.assertFalse(result["success"])
        self.assertEqual(result["method"], "none")
        self.assertEqual(result["message"], "Empty command")

    def test_greeting_does_not_call_agent_brain(self):
        with patch.object(executor, "autocorrect_speech_command", return_value="hello there"):
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("hello there")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "greeting")
        generate.assert_not_called()

    def test_sentence_containing_this_is_not_misread_as_greeting(self):
        request = "do this now"
        expected = {"success": True, "message": "request handled", "method": "agentic_engine"}
        with patch.object(executor, "autocorrect_speech_command", return_value=request):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as generate:
                result = executor.execute_system_command_detailed(request)

        self.assertEqual(result, expected)
        generate.assert_called_once_with(request)

    def test_github_push_requires_confirmation(self):
        request = "in vscode can u push my code to github this is the branch feat/demo"
        plugin = Mock()
        plugin.is_enabled = True
        plugin.parse_command.return_value = {
            "action": "push",
            "kwargs": {"branch": "feat/demo"},
            "requires_confirmation": True,
            "description": "push the current project branch feat/demo to GitHub",
        }
        plugin.perform.return_value = {"success": True, "message": "Pushed branch feat/demo"}
        with patch.object(executor, "autocorrect_speech_command", side_effect=[request, "yes"]):
            with patch("plugins.manager.plugin_manager.get_plugin", return_value=plugin):
                result = executor.execute_system_command_detailed(request)
                self.assertTrue(result["success"])
                self.assertTrue(result["details"]["requires_confirmation"])
                self.assertIn("Confirm", result["message"])
                plugin.perform.assert_not_called()
                confirmation = executor.execute_system_command_detailed("yes")

        self.assertTrue(confirmation["success"])
        self.assertEqual(confirmation["tool"], "security_confirmation")
        plugin.perform.assert_called_once_with("push", branch="feat/demo")

    def test_commands_are_delegated_and_success_is_notified(self):
        status_callback = Mock()
        action_callback = Mock()
        expected = {"success": True, "message": "completed", "method": "agentic_engine"}
        with patch.object(executor, "autocorrect_speech_command", return_value="open chrome"):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as generate:
                result = executor.execute_system_command_detailed(
                    "open chrome",
                    on_action_callback=action_callback,
                    on_status_callback=status_callback,
                )

        self.assertEqual(result, expected)
        generate.assert_called_once_with("open chrome")
        status_callback.assert_called_once_with("completed", "completed")
        action_callback.assert_called_once_with("agent_brain", True, "completed")

    def test_failed_agent_action_returns_failsafe_and_notifies(self):
        status_callback = Mock()
        action_callback = Mock()
        with patch.object(executor, "autocorrect_speech_command", return_value="launch app"):
            with patch(
                "actions.agent_brain.agent_brain.generate_and_execute",
                return_value={"success": False, "message": "execution failed"},
            ):
                result = executor.execute_system_command_detailed(
                    "launch app",
                    on_action_callback=action_callback,
                    on_status_callback=status_callback,
                )

        self.assertFalse(result["success"])
        self.assertIn("launch app", result["message"])
        status_callback.assert_called_once_with("error", result["message"])
        action_callback.assert_called_once_with("unknown", False, result["message"])

    def test_pending_security_action_can_be_confirmed_via_executor(self):
        action = Mock(return_value="done")
        self.guard.request_execution("delete_file", action, description="delete a file")
        with patch.object(executor, "autocorrect_speech_command", return_value="confirm"):
            result = executor.execute_system_command_detailed("confirm")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "security_confirmation")
        action.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

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
        with patch.object(executor, "autocorrect_speech_command", return_value="summarize this document"):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as generate:
                result = executor.execute_system_command_detailed(
                    "summarize this document",
                    on_action_callback=action_callback,
                    on_status_callback=status_callback,
                )

        self.assertEqual(result, expected)
        generate.assert_called_once_with("summarize this document")
        status_callback.assert_called_once_with("completed", "completed")
        action_callback.assert_called_once_with("agent_brain", True, "completed")

    def test_open_chrome_routes_directly_to_chrome_plugin(self):
        chrome = Mock()
        chrome.is_enabled = True
        chrome.execute.return_value = True
        with patch.object(executor, "autocorrect_speech_command", return_value="open chrome"):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "chrome": chrome,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open chrome")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "chrome_plugin")
        chrome.execute.assert_called_once_with("open_url")
        generate.assert_not_called()

    def test_open_brave_routes_directly_to_brave_plugin(self):
        brave = Mock()
        brave.is_enabled = True
        brave.execute.return_value = True
        with patch.object(executor, "autocorrect_speech_command", return_value="open brave"):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "brave": brave,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open brave")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "brave_plugin")
        brave.execute.assert_called_once_with("open")
        generate.assert_not_called()

    def test_open_brave_and_create_new_tab_routes_directly_to_plugin(self):
        brave = Mock()
        brave.is_enabled = True
        brave.execute.return_value = True
        request = "open brave and create a new tab in brave"
        with patch.object(executor, "autocorrect_speech_command", return_value=request):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "brave": brave,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed(request)

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Opened a new Brave tab.")
        brave.execute.assert_called_once_with("open_new_tab")
        generate.assert_not_called()

    def test_open_whatsapp_routes_directly_to_whatsapp_plugin(self):
        whatsapp = Mock()
        whatsapp.is_enabled = True
        whatsapp.execute.return_value = True
        with patch.object(executor, "autocorrect_speech_command", return_value="open whatsapp"):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "whatsapp": whatsapp,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open whatsapp")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "whatsapp_plugin")
        whatsapp.execute.assert_called_once_with("open")
        generate.assert_not_called()

    def test_disabled_builtin_app_plugin_reports_actionable_error(self):
        chrome = Mock()
        chrome.is_enabled = False
        with patch.object(executor, "autocorrect_speech_command", return_value="open chrome"):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "chrome": chrome,
            }.get(pid)):
                result = executor.execute_system_command_detailed("open chrome")

        self.assertFalse(result["success"])
        self.assertEqual(result["method"], "chrome_plugin")
        self.assertIn("disabled", result["message"])
        chrome.execute.assert_not_called()

    def test_failed_agent_action_returns_failsafe_and_notifies(self):
        status_callback = Mock()
        action_callback = Mock()
        underlying_error = "Agent Brain Error: Unknown encoding cl100k_base."
        with patch.object(executor, "autocorrect_speech_command", return_value="launch app"):
            with patch(
                "actions.agent_brain.agent_brain.generate_and_execute",
                return_value={
                    "success": False,
                    "message": underlying_error,
                    "method": "agentic_engine",
                },
            ):
                result = executor.execute_system_command_detailed(
                    "launch app",
                    on_action_callback=action_callback,
                    on_status_callback=status_callback,
                )

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], underlying_error)
        self.assertEqual(result["method"], "agentic_engine")
        status_callback.assert_called_once_with("error", result["message"])
        action_callback.assert_called_once_with("agent_brain", False, result["message"])

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

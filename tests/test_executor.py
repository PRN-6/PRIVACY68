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
        with patch.object(executor, "normalize_command", return_value=""):
            result = executor.execute_system_command_detailed("  ")

        self.assertFalse(result["success"])
        self.assertEqual(result["method"], "none")
        self.assertEqual(result["message"], "Empty command")

    def test_greeting_does_not_call_agent_brain(self):
        with patch.object(executor, "normalize_command", return_value="hello there"):
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("hello there")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "greeting")
        generate.assert_not_called()

    def test_sentence_containing_this_is_not_misread_as_greeting(self):
        request = "do this now"
        expected = {"success": True, "message": "request handled", "method": "agentic_engine"}
        with patch.object(executor, "normalize_command", return_value=request):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as generate:
                result = executor.execute_system_command_detailed(request)

        self.assertEqual(result, expected)
        generate.assert_called_once_with(request)

    def test_github_commands_route_to_agent_brain(self):
        request = "in vscode can u push my code to github this is the branch feat/demo"
        expected = {"success": True, "message": "Pushed branch feat/demo", "method": "agentic_engine"}
        with patch.object(executor, "normalize_command", return_value=request):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as generate:
                result = executor.execute_system_command_detailed(request)

        self.assertEqual(result, expected)
        generate.assert_called_once_with(request)

    def test_commands_are_delegated_and_success_is_notified(self):
        status_callback = Mock()
        action_callback = Mock()
        expected = {"success": True, "message": "completed", "method": "agentic_engine"}
        with patch.object(executor, "normalize_command", return_value="summarize this document"):
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

    def test_open_chrome_routes_directly(self):
        with patch.object(executor, "normalize_command", return_value="open chrome"):
            with patch("actions.executor._open_url", return_value=True) as mock_open:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open chrome")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "chrome_service")
        self.assertEqual(result["tool"], "chrome")
        mock_open.assert_called_once_with("https://www.google.com", preferred_browser="chrome")
        generate.assert_not_called()

    def test_open_brave_routes_directly(self):
        with patch.object(executor, "normalize_command", return_value="open brave"):
            with patch("actions.executor._open_url", return_value=True) as mock_open:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open brave")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "brave_service")
        self.assertEqual(result["tool"], "brave")
        mock_open.assert_called_once_with("https://search.brave.com", preferred_browser="brave")
        generate.assert_not_called()

    def test_open_brave_and_create_new_tab_routes_directly(self):
        request = "open brave and create a new tab in brave"
        with patch.object(executor, "normalize_command", return_value=request):
            with patch("actions.executor._open_url", return_value=True) as mock_open:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed(request)

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Opened a new Brave tab.")
        mock_open.assert_called_once_with("https://search.brave.com", preferred_browser="brave")
        generate.assert_not_called()

    def test_open_whatsapp_routes_directly(self):
        with patch.object(executor, "normalize_command", return_value="open whatsapp"):
            with patch("webbrowser.open", return_value=True) as mock_wb:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open whatsapp")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "whatsapp_service")
        mock_wb.assert_called_once_with("https://web.whatsapp.com")
        generate.assert_not_called()

    def test_disabled_gmail_service_reports_actionable_error(self):
        with patch("services.gmail.gmail_service.is_enabled", False):
            with patch.object(executor, "normalize_command", return_value="compose email to test@example.com"):
                result = executor.execute_system_command_detailed("compose email to test@example.com")

        self.assertFalse(result["success"])
        self.assertEqual(result["tool"], "gmail")
        self.assertEqual(result["method"], "gmail_service")
        self.assertIn("disabled", result["message"])

    def test_failed_agent_action_returns_failsafe_and_notifies(self):
        status_callback = Mock()
        action_callback = Mock()
        underlying_error = "Agent Brain Error: Unknown encoding cl100k_base."
        with patch.object(executor, "normalize_command", return_value="launch app"):
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
        with patch.object(executor, "normalize_command", return_value="confirm"):
            result = executor.execute_system_command_detailed("confirm")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "security_confirmation")
        action.assert_called_once_with()

    def test_go_to_gmail_routes_to_service_when_enabled(self):
        with patch("services.gmail.gmail_service.is_enabled", True):
            with patch("services.gmail.gmail_service.open_inbox", return_value=True) as mock_inbox:
                with patch.object(executor, "normalize_command", return_value="go to gmail"):
                    result = executor.execute_system_command_detailed("go to gmail")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "gmail")
        self.assertEqual(result["method"], "gmail_service")
        mock_inbox.assert_called_once()

    def test_go_to_gmail_blocks_when_service_is_disabled(self):
        with patch("services.gmail.gmail_service.is_enabled", False):
            with patch.object(executor, "normalize_command", return_value="go to gmail"):
                result = executor.execute_system_command_detailed("go to gmail")

        self.assertFalse(result["success"])
        self.assertEqual(result["tool"], "gmail")
        self.assertIn("disabled", result["message"].lower())

    def test_open_telegram_routes_to_service(self):
        with patch.object(executor, "normalize_command", return_value="open telegram"):
            with patch("actions.executor._open_url", return_value=True) as mock_open:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open telegram")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "telegram")
        self.assertEqual(result["method"], "telegram_service")
        mock_open.assert_called_once_with("https://web.telegram.org")
        generate.assert_not_called()

    def test_compound_app_commands_fall_through_to_agent_brain(self):
        expected = {"success": True, "message": "done", "method": "agentic_engine"}
        with patch.object(executor, "normalize_command", return_value="open notepad and write hello world"):
            with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value=expected) as mock_brain:
                result = executor.execute_system_command_detailed("open notepad and write hello world")

        self.assertEqual(result, expected)
        mock_brain.assert_called_once_with("open notepad and write hello world")

    def test_open_site_in_browser_routing(self):
        with patch("actions.executor._open_url", return_value=True) as mock_open:
            result = executor.execute_system_command_detailed("open chatgpt in chrome")
            self.assertTrue(result["success"])
            self.assertEqual(result["tool"], "browser")
            self.assertEqual(result["method"], "website_launcher")
            mock_open.assert_called_once_with("https://chatgpt.com", preferred_browser="chrome")

    def test_open_browser_and_navigate_routing(self):
        with patch("actions.executor._open_url", return_value=True) as mock_open:
            result = executor.execute_system_command_detailed("open chrome and go to chatgpt")
            self.assertTrue(result["success"])
            self.assertEqual(result["tool"], "browser")
            self.assertEqual(result["method"], "browser_search")
            mock_open.assert_called_once_with("https://chatgpt.com", preferred_browser="chrome")

    def test_close_notepad_direct_routing(self):
        with patch("services.system.system_service.close_app", return_value=(True, "Closed Notepad.")) as mock_close:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("close notepad")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "system_app")
                self.assertEqual(result["method"], "close_app")
                self.assertEqual(result["message"], "Closed Notepad.")
                mock_close.assert_called_once_with("notepad")
                generate.assert_not_called()

    def test_close_chrome_direct_routing(self):
        with patch("services.system.system_service.close_app", return_value=(True, "Closed Chrome.")) as mock_close:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("close chrome")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "browser")
                self.assertEqual(result["method"], "close_app")
                mock_close.assert_called_once_with("chrome")
                generate.assert_not_called()

    def test_close_application_routes_to_active_window(self):
        with patch("services.system.system_service.close_active_window", return_value=(True, "Closed active application window.")) as mock_close:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("close the application")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "system_app")
                self.assertEqual(result["method"], "close_active_window")
                mock_close.assert_called_once()
                generate.assert_not_called()

    def test_close_window_routes_to_active_window(self):
        with patch("services.system.system_service.close_active_window", return_value=(True, "Closed active application window.")) as mock_close:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("close window")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "system_app")
                self.assertEqual(result["method"], "close_active_window")
                mock_close.assert_called_once()
                generate.assert_not_called()

    def test_close_tab_routes_directly(self):
        with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
            result = executor.execute_system_command_detailed("close tab")
            self.assertTrue(result["success"])
            self.assertEqual(result["tool"], "browser")
            self.assertEqual(result["method"], "close_tab")
            generate.assert_not_called()

    def test_close_assistant_routes_to_shutdown(self):
        with patch("threading.Thread.start") as mock_thread_start:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("exit assistant")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "system")
                self.assertEqual(result["method"], "assistant_shutdown")
                mock_thread_start.assert_called_once()
                generate.assert_not_called()

    def test_virtual_desktop_numeric_navigation(self):
        with patch("services.system.system_service.switch_to_desktop", return_value=(True, "Switched to Desktop 3 (of 5).")) as mock_sw:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("switch to desktop 3")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "virtual_desktop")
                self.assertEqual(result["method"], "switch_desktop")
                mock_sw.assert_called_once_with(3)
                generate.assert_not_called()

    def test_virtual_desktop_word_navigation(self):
        with patch("services.system.system_service.switch_to_desktop", return_value=(True, "Switched to Desktop 5 (of 5).")) as mock_sw:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("desktop five")
                self.assertTrue(result["success"])
                self.assertEqual(result["tool"], "virtual_desktop")
                self.assertEqual(result["method"], "switch_desktop")
                mock_sw.assert_called_once_with(5)
                generate.assert_not_called()

    def test_virtual_desktop_next_and_prev(self):
        with patch("services.system.system_service.switch_next_desktop", return_value=(True, "Navigated to next desktop")) as mock_next:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("next desktop")
                self.assertTrue(result["success"])
                self.assertEqual(result["method"], "next_desktop")
                mock_next.assert_called_once()
                generate.assert_not_called()

        with patch("services.system.system_service.switch_previous_desktop", return_value=(True, "Navigated to previous desktop")) as mock_prev:
            with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                result = executor.execute_system_command_detailed("previous desktop")
                self.assertTrue(result["success"])
                self.assertEqual(result["method"], "prev_desktop")
                mock_prev.assert_called_once()
                generate.assert_not_called()

    def test_virtual_desktop_create_close_task_view(self):
        with patch("services.system.system_service.create_virtual_desktop", return_value=(True, "Created")) as mock_create:
            result = executor.execute_system_command_detailed("new desktop")
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "create_desktop")
            mock_create.assert_called_once()

        with patch("services.system.system_service.close_virtual_desktop", return_value=(True, "Closed")) as mock_close:
            result = executor.execute_system_command_detailed("close desktop")
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "close_desktop")
            mock_close.assert_called_once()

        with patch("services.system.system_service.show_task_view", return_value=(True, "Opened")) as mock_tv:
            result = executor.execute_system_command_detailed("task view")
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "task_view")
            mock_tv.assert_called_once()

        with patch("services.system.system_service.toggle_show_desktop", return_value=(True, "Toggled")) as mock_sd:
            result = executor.execute_system_command_detailed("show desktop")
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "show_desktop")
            mock_sd.assert_called_once()


if __name__ == "__main__":
    unittest.main()

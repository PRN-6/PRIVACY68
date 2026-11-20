import unittest
from unittest.mock import Mock, patch

from services.gmail import GmailService, gmail_service
from services.system import SystemService, system_service


class TestServices(unittest.TestCase):
    def test_gmail_service_build_compose_url(self):
        svc = GmailService()
        with patch.object(svc, "get_user_email", return_value="test@example.com"):
            url = svc.build_compose_url(to="bob@test.com", subject="Meeting", body="See you at 3")
            self.assertIn("view=cm", url)
            self.assertIn("authuser=test%40example.com", url)
            self.assertIn("to=bob%40test.com", url)

    def test_gmail_service_parse_command(self):
        svc = GmailService()
        parsed = svc.parse_command("open gmail")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["action"], "open")

        parsed_compose = svc.parse_command("compose email to dev@company.com subject Bug report body Found issue")
        self.assertIsNotNone(parsed_compose)
        self.assertEqual(parsed_compose["action"], "compose")
        self.assertEqual(parsed_compose["kwargs"]["to"], "dev@company.com")

    @patch("subprocess.Popen")
    def test_system_service_launch_app(self, mock_popen):
        svc = SystemService()
        success = svc.launch_app("notepad")
        self.assertTrue(success)
        mock_popen.assert_called_once()

    @patch("subprocess.run")
    def test_system_service_close_app_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="SUCCESS: Process terminated")
        svc = SystemService()
        success, msg = svc.close_app("notepad")
        self.assertTrue(success)
        self.assertIn("Closed Notepad", msg)

    def test_system_service_close_protected_process_refused(self):
        svc = SystemService()
        success, msg = svc.close_app("csrss.exe")
        self.assertFalse(success)
        self.assertIn("protected system process", msg)

    @patch("ctypes.windll.user32.PostMessageW", return_value=1)
    @patch("ctypes.windll.user32.GetForegroundWindow", return_value=12345)
    def test_system_service_close_active_window(self, mock_fg, mock_post):
        svc = SystemService()
        success, msg = svc.close_active_window()
        self.assertTrue(success)
        self.assertIn("Closed active application", msg)
        mock_fg.assert_called_once()
        mock_post.assert_called_once_with(12345, 0x0010, 0, 0)

    @patch.object(SystemService, "close_app", return_value=(True, "Closed Notepad."))
    def test_system_service_execute_close(self, mock_close):
        svc = SystemService()
        result = svc.execute("close", app="notepad")
        self.assertTrue(result)
        mock_close.assert_called_once_with("notepad")

    @patch("services.system.time.sleep", return_value=None)
    @patch("services.system._send_keybd_combo", return_value=True)
    def test_system_service_virtual_desktops(self, mock_combo, mock_sleep):
        svc = SystemService()
        # Mock desktop info (current 1, total 5)
        with patch.object(svc, "get_virtual_desktop_info", return_value=(1, 5)):
            success, msg = svc.switch_to_desktop(3)
            self.assertTrue(success)
            self.assertIn("Switched to Desktop 3", msg)
            self.assertEqual(mock_combo.call_count, 2)  # diff = 2 right clicks

        mock_combo.reset_mock()
        with patch.object(svc, "get_virtual_desktop_info", return_value=(3, 5)):
            success, msg = svc.switch_to_desktop(1)
            self.assertTrue(success)
            self.assertIn("Switched to Desktop 1", msg)
            self.assertEqual(mock_combo.call_count, 2)  # diff = -2 left clicks

        mock_combo.reset_mock()
        with patch.object(svc, "get_virtual_desktop_info", return_value=(2, 5)):
            success, msg = svc.switch_next_desktop()
            self.assertTrue(success)
            self.assertIn("Navigated to next desktop", msg)

            success, msg = svc.switch_previous_desktop()
            self.assertTrue(success)
            self.assertIn("Navigated to previous desktop", msg)

            success, msg = svc.create_virtual_desktop()
            self.assertTrue(success)
            self.assertIn("Created a new virtual desktop", msg)

            success, msg = svc.close_virtual_desktop()
            self.assertTrue(success)
            self.assertIn("Closed current virtual desktop", msg)

            success, msg = svc.show_task_view()
            self.assertTrue(success)
            self.assertIn("Opened Windows Task View", msg)

            success, msg = svc.toggle_show_desktop()
            self.assertTrue(success)
            self.assertIn("Toggled Windows Desktop view", msg)

    @patch.object(SystemService, "switch_to_desktop", return_value=(True, "Switched"))
    def test_system_service_execute_desktop_action(self, mock_switch):
        svc = SystemService()
        res = svc.execute("switch_desktop", desktop=4)
        self.assertTrue(res)
        mock_switch.assert_called_once_with(4)


if __name__ == "__main__":
    unittest.main()


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

    def test_system_service_close_active_window(self):
        svc = SystemService()
        success, msg = svc.close_active_window()
        self.assertTrue(success)
        self.assertIn("Closed active application", msg)

    @patch.object(SystemService, "close_app", return_value=(True, "Closed Notepad."))
    def test_system_service_execute_close(self, mock_close):
        svc = SystemService()
        result = svc.execute("close", app="notepad")
        self.assertTrue(result)
        mock_close.assert_called_once_with("notepad")


if __name__ == "__main__":
    unittest.main()


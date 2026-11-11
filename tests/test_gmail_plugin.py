import unittest
from unittest.mock import Mock, patch

from actions import executor
from plugins.gmail_plugin import GmailPlugin
from ui.dashboard_bridge import DashboardAPI


class TestGmailPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = GmailPlugin()

    def test_gmail_plugin_metadata(self):
        self.assertEqual(self.plugin.id, "gmail")
        self.assertEqual(self.plugin.name, "Gmail Controller")
        self.assertTrue(self.plugin.is_builtin)
        self.assertTrue(self.plugin.is_enabled)
        self.assertEqual(self.plugin.category, "Communication")
        self.assertEqual(self.plugin.plugin_type, "Messaging & Email")
        self.assertIn("open", self.plugin.fast_intents)
        self.assertIn("compose", self.plugin.fast_intents)

    def test_build_compose_url_default_account(self):
        with patch.object(self.plugin, "get_user_email", return_value=""):
            url = self.plugin.build_compose_url(
                to="alice@example.com",
                subject="Status Report",
                body="All systems nominal.",
            )
        self.assertTrue(url.startswith("https://mail.google.com/mail/?"))
        self.assertIn("view=cm", url)
        self.assertIn("fs=1", url)
        self.assertIn("to=alice%40example.com", url)
        self.assertIn("su=Status+Report", url)
        self.assertIn("body=All+systems+nominal.", url)
        self.assertNotIn("authuser", url)

    def test_build_compose_url_multi_account_authuser(self):
        with patch.object(self.plugin, "get_user_email", return_value="user@gmail.com"):
            url = self.plugin.build_compose_url(
                to="bob@example.com",
                subject="Hello",
                body="Testing",
            )
        self.assertTrue(url.startswith("https://mail.google.com/mail/u/?"))
        self.assertIn("authuser=user%40gmail.com", url)
        self.assertIn("to=bob%40example.com", url)

    def test_open_inbox_uses_browser(self):
        with patch.object(self.plugin, "_open_in_browser", return_value=True) as mock_open:
            with patch.object(self.plugin, "get_user_email", return_value=""):
                success = self.plugin.open_inbox()
        self.assertTrue(success)
        mock_open.assert_called_once_with("https://mail.google.com/mail/u/0/#inbox")

    def test_open_inbox_with_authuser(self):
        with patch.object(self.plugin, "_open_in_browser", return_value=True) as mock_open:
            with patch.object(self.plugin, "get_user_email", return_value="myuser@gmail.com"):
                success = self.plugin.open_inbox()
        self.assertTrue(success)
        mock_open.assert_called_once_with("https://mail.google.com/mail/u/?authuser=myuser%40gmail.com#inbox")

    def test_compose_email_uses_browser(self):
        with patch.object(self.plugin, "_open_in_browser", return_value=True) as mock_open:
            with patch.object(self.plugin, "get_user_email", return_value=""):
                success = self.plugin.compose_email(
                    to="charlie@test.com",
                    subject="Update",
                    body="Body text",
                )
        self.assertTrue(success)
        args, _ = mock_open.call_args
        self.assertIn("to=charlie%40test.com", args[0])

    def test_parse_command_open_inbox(self):
        commands = [
            "open gmail",
            "launch gmail",
            "check my gmail",
            "check gmail inbox",
            "go to gmail",
        ]
        for cmd in commands:
            parsed = self.plugin.parse_command(cmd)
            self.assertIsNotNone(parsed, f"Failed to parse: {cmd}")
            self.assertEqual(parsed["action"], "open")

    def test_parse_command_compose_full(self):
        cmd = "compose email to alice@example.com with subject Project Alpha and body Launch ready"
        parsed = self.plugin.parse_command(cmd)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["action"], "compose")
        self.assertEqual(parsed["kwargs"]["to"], "alice@example.com")
        self.assertEqual(parsed["kwargs"]["subject"], "Project Alpha")
        self.assertEqual(parsed["kwargs"]["body"], "Launch ready")

    def test_parse_command_compose_saying(self):
        cmd = "send email to bob about lunch tomorrow saying let's meet at noon"
        parsed = self.plugin.parse_command(cmd)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["action"], "compose")
        self.assertEqual(parsed["kwargs"]["to"], "bob")
        self.assertEqual(parsed["kwargs"]["subject"], "lunch tomorrow")
        self.assertEqual(parsed["kwargs"]["body"], "let's meet at noon")

    def test_parse_command_write_message(self):
        cmd = "write email to team@company.com saying standup meeting is starting"
        parsed = self.plugin.parse_command(cmd)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["action"], "compose")
        self.assertEqual(parsed["kwargs"]["to"], "team@company.com")
        self.assertEqual(parsed["kwargs"]["subject"], "")
        self.assertEqual(parsed["kwargs"]["body"], "standup meeting is starting")

    def test_parse_command_empty_compose(self):
        cmd = "compose a new email"
        parsed = self.plugin.parse_command(cmd)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["action"], "compose")
        self.assertEqual(parsed["kwargs"]["to"], "")

    def test_parse_command_non_gmail_returns_none(self):
        self.assertIsNone(self.plugin.parse_command("what is the weather today"))
        self.assertIsNone(self.plugin.parse_command("open calculator"))

    def test_execute_mapping(self):
        with patch.object(self.plugin, "open_inbox", return_value=True) as mock_inbox:
            self.assertTrue(self.plugin.execute("open"))
            mock_inbox.assert_called_once()

        with patch.object(self.plugin, "compose_email", return_value=True) as mock_compose:
            self.assertTrue(self.plugin.execute("compose", to="a@b.com", subject="s", body="b"))
            mock_compose.assert_called_once_with(to="a@b.com", subject="s", body="b", user_email=None)

        self.assertFalse(self.plugin.execute("nonexistent_action"))

    def test_user_email_getter_and_setter(self):
        with patch("plugins.profile_manager.profile_manager.get", return_value="configured@gmail.com"):
            with patch("plugins.profile_manager.profile_manager.set") as mock_set:
                self.assertEqual(self.plugin.get_user_email(), "configured@gmail.com")
                self.plugin.set_user_email("new@gmail.com")
                mock_set.assert_called_once_with("gmail_user_email", "new@gmail.com")

    def test_executor_routes_open_gmail_to_plugin(self):
        gmail_mock = Mock()
        gmail_mock.is_enabled = True
        gmail_mock.execute.return_value = True
        with patch.object(executor, "autocorrect_speech_command", return_value="open gmail"):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "gmail": gmail_mock,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed("open gmail")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "gmail_plugin")
        gmail_mock.execute.assert_called_once_with("open")
        generate.assert_not_called()

    def test_executor_routes_compose_email_to_plugin(self):
        gmail_mock = Mock()
        gmail_mock.is_enabled = True
        gmail_mock.parse_command.return_value = {
            "action": "compose",
            "kwargs": {"to": "test@example.com", "subject": "Hi", "body": "Hello"},
            "description": "compose email to test@example.com",
        }
        gmail_mock.compose_email.return_value = True

        cmd = "compose email to test@example.com with subject Hi and body Hello"
        with patch.object(executor, "autocorrect_speech_command", return_value=cmd):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "gmail": gmail_mock,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = executor.execute_system_command_detailed(cmd)

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "gmail_plugin")
        self.assertIn("Drafted email to test@example.com in Gmail.", result["message"])
        gmail_mock.compose_email.assert_called_once_with(to="test@example.com", subject="Hi", body="Hello")
        generate.assert_not_called()

    def test_executor_disabled_gmail_plugin_reports_error(self):
        gmail_mock = Mock()
        gmail_mock.is_enabled = False
        cmd = "open gmail"
        with patch.object(executor, "autocorrect_speech_command", return_value=cmd):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "gmail": gmail_mock,
            }.get(pid)):
                result = executor.execute_system_command_detailed(cmd)

        self.assertFalse(result["success"])
        self.assertEqual(result["method"], "gmail_plugin")
        self.assertIn("disabled", result["message"])

    def test_dashboard_api_gmail_config(self):
        api = DashboardAPI()
        with patch("plugins.profile_manager.profile_manager.get", return_value="myemail@gmail.com"):
            res = api.get_gmail_config()
            self.assertTrue(res["success"])
            self.assertEqual(res["email"], "myemail@gmail.com")

        with patch("plugins.profile_manager.profile_manager.set") as mock_set:
            res = api.set_gmail_config("newuser@gmail.com")
            self.assertTrue(res["success"])
            self.assertEqual(res["email"], "newuser@gmail.com")


if __name__ == "__main__":
    unittest.main()


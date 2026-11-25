import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from actions import executor
from computer_use.security_guard import SecurityGuard
from utils.commands import normalize_command


class TestTextCommands(unittest.TestCase):
    def setUp(self):
        guard = patch.object(executor, "security_guard", SecurityGuard())
        guard.start()
        self.addCleanup(guard.stop)

    def test_text_payload_is_preserved(self):
        for command in (
            'type "Hello Hello, what is this for?"',
            'search for "To Be or Not To Be"',
            'write Um, I am very very happy!',
            'create a file called C:\\Users\\Ada\\MixedCase.txt',
            'type this:\n    print("Hello")',
        ):
            with self.subTest(command=command):
                self.assertEqual(normalize_command(command), command)

    def test_blank_or_invalid_inputs_are_rejected(self):
        for command in (None, 5, "", "  ", "''"):
            self.assertFalse(executor.execute_system_command_detailed(command)["success"])

    def test_case_and_quoted_terms_are_preserved_in_search(self):
        for command in ('search for "Very Very Good!"', 'search for "Very Very Good!" in chrome'):
            with self.subTest(command=command), patch.object(executor, "_open_url", return_value=True) as open_url:
                result = executor.execute_system_command_detailed(command)
            query = parse_qs(urlparse(open_url.call_args.args[0]).query)
            self.assertEqual(query["q"], ['"Very Very Good!"'])
            self.assertTrue(result["success"])

    def test_browser_failures_are_not_reported_as_success(self):
        for command in ('search for cats', 'open youtube', 'open Example.com in chrome',
                        'open chrome and search for Cats', 'search youtube for Cats',
                        'search Cats in brave', 'open Example.com'):
            with self.subTest(command=command), patch.object(executor, "_open_url", return_value=False):
                status = Mock()
                result = executor.execute_system_command_detailed(command, on_status_callback=status)
                self.assertFalse(result["success"])
                self.assertEqual(status.call_args.args[0], "error")

    def test_agent_receives_original_message(self):
        command = 'write "Um, I am very very happy!" in notepad'
        with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value={"success": True}) as generate:
            executor.execute_system_command_detailed(command)
        generate.assert_called_once_with(command)

    def test_desktop_aliases_do_not_require_transcription_rewrites(self):
        for command, executable in (("open command prompt", "cmd.exe"),
                                    ("open file manager", "explorer.exe"),
                                    ("open Notepad!", "notepad.exe")):
            with self.subTest(command=command), patch("actions.executor.subprocess.Popen") as launch:
                result = executor.execute_system_command_detailed(command)
                self.assertTrue(result["success"])
                launch.assert_called_once_with([executable])

    def test_multiline_request_is_not_truncated_by_search_handler(self):
        command = 'search for Python\nthen summarize the results in a file'
        with patch("actions.agent_brain.agent_brain.generate_and_execute", return_value={"success": True}) as generate, \
             patch.object(executor, "_open_url") as open_url:
            executor.execute_system_command_detailed(command)
        generate.assert_called_once_with(command)
        open_url.assert_not_called()

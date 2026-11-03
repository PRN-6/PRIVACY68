import unittest
from unittest.mock import Mock, patch
from speech.streamer import autocorrect_speech_command
from actions.executor import execute_system_command_detailed
from actions.agent_brain import AgentBrain


class TestQuotedCommandsAndBrainConfig(unittest.TestCase):
    def test_autocorrect_strips_various_quotes(self):
        cases = [
            ("''Open Chrome''", "Open Chrome"),
            ("'Open Chrome'", "Open Chrome"),
            ('"Open Chrome"', "Open Chrome"),
            ("‘Open Chrome’", "Open Chrome"),
            ("“Open Chrome”", "Open Chrome"),
            ("`Open Chrome`", "Open Chrome"),
            ("  'Open Chrome'  ", "Open Chrome"),
        ]
        for inp, expected in cases:
            self.assertEqual(autocorrect_speech_command(inp), expected)

    def test_quoted_open_chrome_routes_to_plugin(self):
        chrome = Mock()
        chrome.is_enabled = True
        chrome.execute.return_value = True

        for quoted_input in ("''Open Chrome''", "'Open Chrome'", '"Open Chrome"'):
            with patch("plugins.manager.plugin_manager.get_plugin", side_effect=lambda pid: {
                "github": None,
                "chrome": chrome,
            }.get(pid)):
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = execute_system_command_detailed(quoted_input)

            self.assertTrue(result["success"], f"Failed for input: {quoted_input}")
            self.assertEqual(result["method"], "chrome_plugin")
            generate.assert_not_called()

    def test_agent_brain_claude_without_api_key(self):
        brain = AgentBrain(model="claude-3-5-sonnet-20241022")
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=True):
            with patch("config.ANTHROPIC_API_KEY", ""):
                res = brain.generate_and_execute("Write a script")
                self.assertFalse(res["success"])
                self.assertIn("Anthropic Claude API key is not configured", res["message"])

    def test_agent_brain_ollama_not_found_handling(self):
        brain = AgentBrain(model="ollama/nonexistent-model:latest")
        mock_err = Exception("litellm.NotFoundError: OllamaException - model not found")
        with patch.object(brain, "_get_code_from_llm", side_effect=mock_err):
            res = brain.generate_and_execute("Do something")
            self.assertFalse(res["success"])
            self.assertIn("is not installed in Ollama", res["message"])

    def test_agent_brain_ollama_remote_url_passed(self):
        brain = AgentBrain(model="ollama/llama3.2:latest")
        with patch("actions.agent_brain.litellm.completion") as mock_comp:
            mock_resp = Mock()
            mock_resp.choices = [Mock(message=Mock(content="print('hello')"))]
            mock_comp.return_value = mock_resp

            with patch("config.OLLAMA_BASE_URL", "https://ollama.my-remote-site.com"):
                with patch("config.OLLAMA_API_KEY", "remote-secret-key"):
                    brain._get_code_from_llm("test")
                    mock_comp.assert_called_once()
                    _, kwargs = mock_comp.call_args
                    self.assertEqual(kwargs["api_base"], "https://ollama.my-remote-site.com")
                    self.assertEqual(kwargs["api_key"], "remote-secret-key")


if __name__ == "__main__":
    unittest.main()

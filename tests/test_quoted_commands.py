import unittest
from unittest.mock import Mock, patch
from utils.commands import normalize_command
from actions.executor import execute_system_command_detailed
from actions.agent_brain import AgentBrain


class TestQuotedCommandsAndBrainConfig(unittest.TestCase):
    def test_normalize_strips_various_quotes(self):
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
            self.assertEqual(normalize_command(inp), expected)

    def test_quoted_open_chrome_routes_to_service(self):
        for quoted_input in ("''Open Chrome''", "'Open Chrome'", '"Open Chrome"'):
            with patch("actions.executor._open_url", return_value=True) as mock_open:
                with patch("actions.agent_brain.agent_brain.generate_and_execute") as generate:
                    result = execute_system_command_detailed(quoted_input)

            self.assertTrue(result["success"], f"Failed for input: {quoted_input}")
            self.assertEqual(result["method"], "chrome_service")
            generate.assert_not_called()

    def test_agent_brain_claude_without_api_key(self):
        brain = AgentBrain(model="claude-3-5-sonnet-20241022")
        with patch.object(brain, "get_fallback_models", return_value=[]):
            with patch("actions.skill_manager.skill_manager.find_matching_skill", return_value=None):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GROQ_API_KEY": "", "OPENAI_API_KEY": ""}):
                    with patch("config.ANTHROPIC_API_KEY", ""), patch("config.GEMINI_API_KEY", ""), patch("config.GROQ_API_KEY", ""), patch("config.OPENAI_API_KEY", ""):
                        res = brain.generate_and_execute("Unique unlearned prompt 12345")
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
                    with patch("actions.agent_brain.is_ollama_online", return_value=True):
                        brain._get_code_from_llm("test")
                        mock_comp.assert_called_once()
                        _, kwargs = mock_comp.call_args
                        self.assertEqual(kwargs["api_base"], "https://ollama.my-remote-site.com")
                        self.assertEqual(kwargs["api_key"], "remote-secret-key")


    def test_update_dotenv_var_persistence(self):
        import tempfile
        import os
        from config import update_dotenv_var

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".env") as tf:
            tf.write('EXISTING_VAR="123"\n')
            temp_path = tf.name

        try:
            update_dotenv_var("GROQ_API_KEY", "gsk_test_key_abc", env_path=temp_path)
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('GROQ_API_KEY="gsk_test_key_abc"', content)
            self.assertIn('EXISTING_VAR="123"', content)
            self.assertEqual(os.environ.get("GROQ_API_KEY"), "gsk_test_key_abc")

            # Update existing var
            update_dotenv_var("GROQ_API_KEY", "gsk_updated", env_path=temp_path)
            with open(temp_path, "r", encoding="utf-8") as f:
                updated_content = f.read()

            self.assertIn('GROQ_API_KEY="gsk_updated"', updated_content)
            self.assertNotIn("gsk_test_key_abc", updated_content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()

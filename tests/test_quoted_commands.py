import unittest
from unittest.mock import Mock, MagicMock, patch
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
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
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
                    with patch("actions.agent_brain.is_ollama_online", return_value=True):
                        brain._get_code_from_llm("test")
                        mock_comp.assert_called_once()
                        _, kwargs = mock_comp.call_args
                        self.assertEqual(kwargs["api_base"], "https://ollama.my-remote-site.com")
                        self.assertEqual(kwargs["api_key"], "remote-secret-key")


    def test_wake_word_no_false_positives(self):
        from speech.streamer import SpeechStreamer
        streamer = SpeechStreamer(wake_word="alexa")

        # True wake triggers
        self.assertTrue(streamer.is_wake_word_detected("alexa open chrome"))
        self.assertTrue(streamer.is_wake_word_detected("Hey Alexa"))
        self.assertTrue(streamer.is_wake_word_detected("Alexa, what time is it?"))

        # False triggers that previously tripped loose matching - MUST be False now!
        self.assertFalse(streamer.is_wake_word_detected("electric car"))
        self.assertFalse(streamer.is_wake_word_detected("the election results"))
        self.assertFalse(streamer.is_wake_word_detected("Alexander the Great"))
        self.assertFalse(streamer.is_wake_word_detected("select all text"))
        self.assertFalse(streamer.is_wake_word_detected("already did that"))

    def test_wake_word_hey_google(self):
        from speech.streamer import SpeechStreamer
        streamer = SpeechStreamer(wake_word="hey google")

        self.assertTrue(streamer.is_wake_word_detected("hey google open chrome"))
        self.assertTrue(streamer.is_wake_word_detected("ok google search youtube"))
        self.assertTrue(streamer.is_wake_word_detected("okay google what is the weather"))
        self.assertFalse(streamer.is_wake_word_detected("search on google"))

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

    def test_push_to_talk_recorder(self):
        from speech.streamer import PushToTalkRecorder
        import numpy as np

        ptt = PushToTalkRecorder()
        ptt.is_recording = True
        # Fake audio frames (0.5s of 16kHz audio)
        ptt.frames = [np.ones((1280, 1), dtype=np.float32) for _ in range(10)]

        with patch("speech_recognition.Recognizer.recognize_google", return_value="open chrome"):
            text = ptt.stop_and_transcribe()
            self.assertEqual(text, "open chrome")
            self.assertFalse(ptt.is_recording)

    def test_agent_brain_openai_model(self):
        from actions.agent_brain import AgentBrain
        brain = AgentBrain(model="openai/gpt-4o-mini")
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="print('gpt hello')"))]

        with patch("litellm.completion") as mock_comp:
            mock_comp.return_value = mock_resp
            with patch("config.OPENAI_API_KEY", "sk-proj-test123"):
                code = brain._get_code_from_llm("test openai")
                self.assertEqual(code, "print('gpt hello')")
                _, kwargs = mock_comp.call_args
                self.assertEqual(kwargs["model"], "openai/gpt-4o-mini")
                self.assertEqual(kwargs["api_key"], "sk-proj-test123")


if __name__ == "__main__":
    unittest.main()

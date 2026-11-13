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


    def test_click_to_speak_recorder(self):
        from speech.streamer import ClickToSpeakRecorder
        import numpy as np

        recorder = ClickToSpeakRecorder()
        self.assertFalse(recorder.is_recording)
        self.assertEqual(recorder.frames, [])

        recorder.is_recording = True
        recorder.frames = [np.zeros((1280, 1), dtype=np.float32) for _ in range(5)]

        mock_sr = MagicMock()
        mock_rec = MagicMock()
        mock_rec.recognize_google.return_value = "open brave"
        mock_sr.Recognizer.return_value = mock_rec

        with patch.dict("sys.modules", {"speech_recognition": mock_sr}):
            text = recorder.stop_and_transcribe()
            self.assertEqual(text, "open brave")
            self.assertFalse(recorder.is_recording)

    def test_wake_words_disabled_for_privacy(self):
        from speech.streamer import SpeechStreamer
        streamer = SpeechStreamer(auto_init_hardware=False)
        self.assertFalse(streamer.is_wake_word_detected("alexa open chrome"))
        self.assertFalse(streamer.is_wake_word_detected("hey google search youtube"))

    def test_microphone_hardware_never_opened_at_startup_or_idle(self):
        from speech.streamer import SpeechStreamer, PushToTalkRecorder
        streamer = SpeechStreamer()
        self.assertIsNone(streamer.stream)
        self.assertFalse(streamer.is_active)
        self.assertFalse(streamer.recorder.is_recording)
        self.assertIsNone(streamer.recorder._stream)

        ptt = PushToTalkRecorder()
        self.assertFalse(ptt.is_recording)
        self.assertIsNone(ptt._stream)

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

        mock_sr = MagicMock()
        mock_rec = MagicMock()
        mock_rec.recognize_google.return_value = "open chrome"
        mock_sr.Recognizer.return_value = mock_rec

        with patch.dict("sys.modules", {"speech_recognition": mock_sr}):
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

    def test_streamer_offline_whisper_engine(self):
        from speech.streamer import SpeechStreamer
        import numpy as np
        streamer = SpeechStreamer(auto_init_hardware=False)

        mock_whisper_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "navigate to github"
        mock_whisper_model.transcribe.return_value = ([mock_segment], None)

        with patch("speech.streamer.get_whisper_model", return_value=mock_whisper_model):
            with patch("config.SPEECH_ENGINE", "whisper"):
                dummy_audio = np.zeros(16000, dtype=np.float32)
                res = streamer._transcribe(dummy_audio)
                self.assertEqual(res, "navigate to github")

    def test_streamer_google_engine_with_offline_whisper_fallback(self):
        from speech.streamer import SpeechStreamer
        import numpy as np
        streamer = SpeechStreamer(auto_init_hardware=False)

        mock_whisper_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "offline whisper fallback"
        mock_whisper_model.transcribe.return_value = ([mock_segment], None)

        with patch.object(streamer, "_transcribe_google", return_value=""):
            with patch("speech.streamer.get_whisper_model", return_value=mock_whisper_model):
                with patch("config.SPEECH_ENGINE", "google"):
                    dummy_audio = np.zeros(16000, dtype=np.float32)
                    res = streamer._transcribe(dummy_audio)
                    self.assertEqual(res, "offline whisper fallback")


if __name__ == "__main__":
    unittest.main()

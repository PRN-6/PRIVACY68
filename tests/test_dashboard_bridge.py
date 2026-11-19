import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from ui.dashboard_bridge import DashboardAPI


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.api = DashboardAPI()

    def test_execute_command_uses_standard_executor_and_returns_agent_output(self):
        expected = {
            "success": True,
            "message": "Command completed.",
            "method": "agentic_engine",
        }
        with patch("actions.executor.execute_system_command_detailed", return_value=expected) as execute:
            with patch("actions.agent_brain.agent_brain") as brain:
                brain.last_reasoning = "Analyzing request: open Chrome"
                brain.last_code = "print('opened')"
                result = self.api.execute_command("open Chrome")

        execute.assert_called_once_with("open Chrome")
        self.assertEqual(result["success"], True)
        self.assertEqual(result["message"], "Command completed.")
        self.assertEqual(result["reasoning"], "Analyzing request: open Chrome")
        self.assertEqual(result["code"], "print('opened')")

    def test_execute_command_preserves_executor_failure(self):
        expected = {"success": False, "message": "Could not complete request.", "method": "none"}
        with patch("actions.executor.execute_system_command_detailed", return_value=expected):
            with patch("actions.agent_brain.agent_brain") as brain:
                brain.last_reasoning = ""
                brain.last_code = ""
                result = self.api.execute_command("unsupported request")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Could not complete request.")

    def test_execute_command_does_not_show_stale_agent_code_for_plugin_results(self):
        expected = {"success": True, "message": "GitHub repositories.", "method": "github_plugin"}
        with patch("actions.executor.execute_system_command_detailed", return_value=expected):
            with patch("actions.agent_brain.agent_brain") as brain:
                brain.last_reasoning = "old agent response"
                brain.last_code = "print('stale')"
                result = self.api.execute_command("list my GitHub repositories")

        self.assertEqual(result["reasoning"], expected["message"])
        self.assertEqual(result["code"], "")

    def test_github_connection_methods_use_secure_plugin_service(self):
        with patch("ui.dashboard_bridge.connect_github", return_value={
            "success": True,
            "message": "Connected to GitHub as tester.",
            "login": "tester",
        }) as connect:
            result = self.api.connect_github("github_pat_example")

        connect.assert_called_once_with("github_pat_example")
        self.assertTrue(result["success"])
        self.assertEqual(result["login"], "tester")

    def test_runtime_status_reports_configured_model_and_hardware(self):
        voice = {"model_ready": True, "is_enrolled": False, "enabled": False}
        cuda = {"is_ready": False, "has_gpu": False}
        with patch.object(self.api, "get_voice_lock_status", return_value=voice):
            with patch.object(self.api, "get_cuda_status", return_value=cuda):
                result = self.api.get_runtime_status()

        self.assertTrue(result["success"])
        self.assertIn("model", result)
        self.assertIn("speech_model", result)
        self.assertEqual(result["voice_lock"], voice)
        self.assertEqual(result["cuda"], cuda)

    def test_get_plugins_returns_registered_plugin_metadata(self):
        result = self.api.get_plugins()
        self.assertEqual(len(result), 3)
        ids = [r["id"] for r in result]
        self.assertIn("telegram", ids)
        self.assertIn("gmail", ids)
        self.assertIn("system", ids)

    def test_toggle_plugin(self):
        with patch("utils.profile_manager.profile_manager.set"):
            result = self.api.toggle_plugin("gmail", False)
            self.assertTrue(result["success"])
            self.assertFalse(result["enabled"])

    def test_uninstall_plugin_reports_builtin(self):
        result = self.api.uninstall_plugin("gmail")
        self.assertFalse(result["success"])
        self.assertIn("cannot be uninstalled", result["message"])

    def test_execute_plugin_action_success(self):
        with patch("channels.telegram.telegram_channel.execute", return_value=True) as mock_exec:
            res = self.api.execute_plugin_action("telegram", "start", {"key": "val"})
            self.assertTrue(res["success"])
            mock_exec.assert_called_once_with("start", key="val")

    def test_set_and_get_plugin_setting(self):
        with patch("utils.profile_manager.profile_manager.set") as mock_set:
            res = self.api.set_plugin_setting("whatsapp", "default_contact", "+1987654321")
            self.assertTrue(res["success"])
            mock_set.assert_called_once_with("whatsapp_default_contact", "+1987654321")

        with patch("utils.profile_manager.profile_manager.get", return_value="+1987654321"):
            get_res = self.api.get_plugin_setting("whatsapp", "default_contact")
            self.assertTrue(get_res["success"])
            self.assertEqual(get_res["value"], "+1987654321")

    def test_get_and_save_speech_config(self):
        with patch("config.update_dotenv_var") as mock_upd:
            res = self.api.save_speech_config("whisper", "base")
            self.assertTrue(res["success"])
            self.assertEqual(res["engine"], "whisper")
            self.assertEqual(res["whisper_model"], "base")
            mock_upd.assert_any_call("SPEECH_ENGINE", "whisper")
            mock_upd.assert_any_call("WHISPER_MODEL_SIZE", "base")

            bad_res = self.api.save_speech_config("invalid_engine", "tiny")
            self.assertFalse(bad_res["success"])

        cfg = self.api.get_speech_config()
        self.assertTrue(cfg["success"])
        self.assertIn("engine", cfg)
        self.assertIn("whisper_model", cfg)

    def test_telegram_bridge_methods(self):
        with patch("channels.telegram.telegram_channel.start_bot", return_value=(True, "Bot started")), \
             patch("channels.telegram.telegram_channel.stop_bot", return_value=(True, "Bot stopped")), \
             patch("channels.telegram.telegram_channel.send_test_message", return_value=(True, "Alert sent")), \
             patch("channels.telegram.telegram_channel.set_bot_token") as mock_tok, \
             patch("channels.telegram.telegram_channel.set_allowed_chat_id") as mock_chat:

            cfg_res = self.api.set_telegram_config("123:TOKEN", "999888")
            self.assertTrue(cfg_res["success"])
            mock_tok.assert_called_once_with("123:TOKEN")
            mock_chat.assert_called_once_with("999888")

            start_res = self.api.start_telegram_bot()
            self.assertTrue(start_res["success"])
            self.assertEqual(start_res["message"], "Bot started")

            test_res = self.api.test_telegram_bot()
            self.assertTrue(test_res["success"])
            self.assertEqual(test_res["message"], "Alert sent")

            stop_res = self.api.stop_telegram_bot()
            self.assertTrue(stop_res["success"])
            self.assertEqual(stop_res["message"], "Bot stopped")

    @patch("os.startfile", create=True)
    def test_open_plugins_folder(self, mock_startfile):
        res = self.api.open_plugins_folder()
        self.assertTrue(res["success"])
        self.assertIn("path", res)
        mock_startfile.assert_called_once()

    def test_get_markdown_skills(self):
        skills = self.api.get_markdown_skills()
        self.assertIsInstance(skills, list)
        names = [s["name"].lower() for s in skills]
        self.assertIn("github", names)
        self.assertIn("vscode", names)

    @patch("os.startfile", create=True)
    def test_open_skills_folder(self, mock_startfile):
        res = self.api.open_skills_folder()
        self.assertTrue(res["success"])
        self.assertIn("path", res)
        mock_startfile.assert_called_once()

    def test_auto_detect_and_save_key_gemini(self):
        with patch.object(self.api, "save_api_key", return_value={"success": True}) as mock_save:
            with patch.object(self.api, "set_active_model") as mock_set_model:
                res = self.api.auto_detect_and_save_key("AIzaSyTestGeminiKey123")
                self.assertTrue(res["success"])
                self.assertEqual(res["provider"], "gemini")
                self.assertEqual(res["model"], "gemini/gemini-3.1-flash-lite")
                mock_save.assert_called_once_with(provider="gemini", api_key="AIzaSyTestGeminiKey123", model="gemini/gemini-3.1-flash-lite", base_url="")
                mock_set_model.assert_called_once_with("gemini/gemini-3.1-flash-lite")

    def test_auto_detect_and_save_key_groq(self):
        with patch.object(self.api, "save_api_key", return_value={"success": True}) as mock_save:
            with patch.object(self.api, "set_active_model") as mock_set_model:
                res = self.api.auto_detect_and_save_key("gsk_testGroqKey123456")
                self.assertTrue(res["success"])
                self.assertEqual(res["provider"], "groq")
                mock_save.assert_called_once()
                mock_set_model.assert_called_once()

    def test_auto_detect_and_save_key_openrouter(self):
        with patch.object(self.api, "save_api_key", return_value={"success": True}) as mock_save:
            with patch.object(self.api, "set_active_model") as mock_set_model:
                res = self.api.auto_detect_and_save_key("sk-or-v1-testkey123")
                self.assertTrue(res["success"])
                self.assertEqual(res["provider"], "openrouter")
                mock_save.assert_called_once()
                mock_set_model.assert_called_once()

    def test_auto_detect_and_save_key_claude(self):
        with patch.object(self.api, "save_api_key", return_value={"success": True}) as mock_save:
            with patch.object(self.api, "set_active_model") as mock_set_model:
                res = self.api.auto_detect_and_save_key("sk-ant-testclaude123")
                self.assertTrue(res["success"])
                self.assertEqual(res["provider"], "claude")
                mock_save.assert_called_once()
                mock_set_model.assert_called_once()

    def test_auto_detect_and_save_key_github(self):
        with patch.object(self.api, "connect_github", return_value={"success": True, "message": "Connected"}) as mock_gh:
            res = self.api.auto_detect_and_save_key("ghp_testgithubpat123")
            self.assertTrue(res["success"])
            mock_gh.assert_called_once_with("ghp_testgithubpat123")


if __name__ == "__main__":
    unittest.main()

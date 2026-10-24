import unittest
from unittest.mock import patch
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
        with patch("plugins.github_plugin.GitHubPlugin.connect", return_value={
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
        plugin = SimpleNamespace(
            id="chrome",
            name="Chrome",
            version="1.0",
            description="Browser integration",
            icon="🌐",
            is_enabled=True,
            is_builtin=True,
            category="General",
            plugin_type="",
        )
        with patch("ui.dashboard_bridge.plugin_manager.check_and_reload_if_changed"):
            with patch("ui.dashboard_bridge.plugin_manager.get_all_plugins", return_value=[plugin]):
                result = self.api.get_plugins()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "chrome")
        self.assertEqual(result[0]["category"], "Browser")
        self.assertTrue(result[0]["is_enabled"])
        self.assertTrue(result[0]["is_builtin"])

    def test_toggle_plugin_reports_unknown_plugin(self):
        with patch("ui.dashboard_bridge.plugin_manager.set_plugin_enabled", return_value=False):
            result = self.api.toggle_plugin("missing", True)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_uninstall_plugin_reports_missing_plugin(self):
        with patch("ui.dashboard_bridge.plugin_manager.get_plugin", return_value=None):
            result = self.api.uninstall_plugin("missing")

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


if __name__ == "__main__":
    unittest.main()

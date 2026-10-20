"""
Unit tests for the new PRIVACY68 Windows Control Layer and Capabilities.
Tests security guard, input controller, context inspector, dev tools, macro engine, and GitHub plugin.
"""

import unittest

from computer_use.security_guard import SecurityGuard
from computer_use.input_controller import InputController
from computer_use.context_inspector import ContextInspector
from computer_use.dev_tools import DevToolsController
from computer_use.macro_engine import MacroEngine
from extra_plugins.github_plugin import GitHubPlugin
from actions.executor import execute_system_command_detailed


class TestNewCapabilities(unittest.TestCase):

    def test_security_guard_safe_action(self):
        guard = SecurityGuard()
        executed = []

        def dummy_action():
            executed.append(True)
            return "ok"

        success, msg, res = guard.request_execution("open_app", dummy_action, description="Open Chrome")
        self.assertTrue(success)
        self.assertEqual(len(executed), 1)
        self.assertEqual(res, "ok")
        self.assertFalse(guard.check_has_pending())

    def test_security_guard_sensitive_action_and_confirmation(self):
        guard = SecurityGuard()
        executed = []

        def dummy_delete():
            executed.append(True)
            return "deleted"

        # 1. Request execution of sensitive action
        success, msg, res = guard.request_execution("delete_file", dummy_delete, description="Delete file test.txt")
        self.assertFalse(success)
        self.assertIn("Are you sure", msg)
        self.assertTrue(guard.check_has_pending())
        self.assertEqual(len(executed), 0)

        # 2. Confirm action
        conf_success, conf_msg, conf_res = guard.confirm_pending()
        self.assertTrue(conf_success)
        self.assertEqual(len(executed), 1)
        self.assertEqual(conf_res, "deleted")
        self.assertFalse(guard.check_has_pending())

    def test_security_guard_cancellation(self):
        guard = SecurityGuard()
        executed = []

        def dummy_delete():
            executed.append(True)

        guard.request_execution("delete_file", dummy_delete, description="Delete file secret.txt")
        self.assertTrue(guard.check_has_pending())

        cancel_msg = guard.cancel_pending()
        self.assertTrue("aborted" in cancel_msg or "Cancelled" in cancel_msg)
        self.assertFalse(guard.check_has_pending())
        self.assertEqual(len(executed), 0)

    def test_input_controller_vk_lookup(self):
        self.assertEqual(InputController._get_vk("enter"), 0x0D)
        self.assertEqual(InputController._get_vk("esc"), 0x1B)
        self.assertEqual(InputController._get_vk("shift"), 0x10)
        self.assertEqual(InputController._get_vk("ctrl"), 0x11)
        self.assertEqual(InputController._get_vk("win"), 0x5B)

    def test_context_inspector_battery_and_clipboard(self):
        inspector = ContextInspector()
        b_info = inspector.get_battery_and_power_info()
        self.assertIn("has_battery", b_info)
        self.assertIn("message", b_info)

        # Test context resolution (returns None or string if active window present)
        target = inspector.resolve_contextual_target("please close this window")
        self.assertTrue(target is None or isinstance(target, str))

    def test_dev_tools_git_status(self):
        dev = DevToolsController()
        status_msg = dev.git_status()
        self.assertIsInstance(status_msg, str)
        self.assertGreater(len(status_msg), 0)

    def test_macro_engine_registration_and_execution(self):
        engine = MacroEngine()
        executed_steps = []

        def dummy_step_executor(action, params):
            executed_steps.append(action)
            return {"status": "ok"}

        res = engine.match_and_execute("activate coding mode", dummy_step_executor)
        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertIn("coding mode", res["workflow"].lower())
        self.assertEqual(len(executed_steps), 3)

    def test_github_plugin_tool_definitions(self):
        plugin = GitHubPlugin()
        self.assertEqual(plugin.id, "github")
        self.assertIn("github.open", plugin.actions)
        self.assertIn("github.search", plugin.actions)
        self.assertIn("github.push", plugin.actions)
        self.assertIn("github.notifications", plugin.actions)

        tools = plugin.get_tool_definitions()
        self.assertEqual(len(tools), 10)
        tool_names = [t["function"]["name"] for t in tools]
        self.assertIn("plugin_github_open", tool_names)
        self.assertIn("plugin_github_search", tool_names)

    def test_executor_git_voice_commands(self):
        res = execute_system_command_detailed("check git status")
        self.assertTrue(res["success"])
        self.assertEqual(res["tool"], "dev_tools_git_status")
        self.assertTrue("Git status" in res["message"] or "clean" in res["message"])


if __name__ == "__main__":
    unittest.main()

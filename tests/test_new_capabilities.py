"""
Unit tests for the new PRIVACY68 Windows Control Layer and Capabilities.
Tests security guard, input controller, context inspector, dev tools, macro engine, and GitHub plugin.
"""

import pytest
from computer_use.security_guard import SecurityGuard, ActionRiskLevel, security_guard
from computer_use.input_controller import InputController
from computer_use.context_inspector import ContextInspector
from computer_use.dev_tools import DevToolsController
from computer_use.macro_engine import MacroEngine
from extra_plugins.github_plugin import GitHubPlugin
from actions.executor import execute_system_command_detailed


class TestNewCapabilities:

    def test_security_guard_safe_action(self):
        guard = SecurityGuard()
        executed = []
        
        def dummy_action():
            executed.append(True)
            return "ok"

        success, msg, res = guard.request_execution("open_app", dummy_action, description="Open Chrome")
        assert success is True
        assert len(executed) == 1
        assert res == "ok"
        assert guard.check_has_pending() is False

    def test_security_guard_sensitive_action_and_confirmation(self):
        guard = SecurityGuard()
        executed = []

        def dummy_delete():
            executed.append(True)
            return "deleted"

        # 1. Request execution of sensitive action
        success, msg, res = guard.request_execution("delete_file", dummy_delete, description="Delete file test.txt")
        assert success is False
        assert "Are you sure" in msg
        assert guard.check_has_pending() is True
        assert len(executed) == 0

        # 2. Confirm action
        conf_success, conf_msg, conf_res = guard.confirm_pending()
        assert conf_success is True
        assert len(executed) == 1
        assert conf_res == "deleted"
        assert guard.check_has_pending() is False

    def test_security_guard_cancellation(self):
        guard = SecurityGuard()
        executed = []

        def dummy_delete():
            executed.append(True)

        guard.request_execution("delete_file", dummy_delete, description="Delete file secret.txt")
        assert guard.check_has_pending() is True
        
        cancel_msg = guard.cancel_pending()
        assert "aborted" in cancel_msg or "Cancelled" in cancel_msg
        assert guard.check_has_pending() is False
        assert len(executed) == 0

    def test_input_controller_vk_lookup(self):
        assert InputController._get_vk("enter") == 0x0D
        assert InputController._get_vk("esc") == 0x1B
        assert InputController._get_vk("shift") == 0x10
        assert InputController._get_vk("ctrl") == 0x11
        assert InputController._get_vk("win") == 0x5B

    def test_context_inspector_battery_and_clipboard(self):
        inspector = ContextInspector()
        b_info = inspector.get_battery_and_power_info()
        assert "has_battery" in b_info
        assert "message" in b_info

        # Test context resolution (returns None or string if active window present)
        target = inspector.resolve_contextual_target("please close this window")
        assert target is None or isinstance(target, str)

    def test_dev_tools_git_status(self):
        dev = DevToolsController()
        status_msg = dev.git_status()
        assert isinstance(status_msg, str)
        assert len(status_msg) > 0

    def test_macro_engine_registration_and_execution(self):
        engine = MacroEngine()
        executed_steps = []

        def dummy_step_executor(action, params):
            executed_steps.append(action)
            return {"status": "ok"}

        res = engine.match_and_execute("activate coding mode", dummy_step_executor)
        assert res is not None
        assert res["success"] is True
        assert "coding mode" in res["workflow"].lower()
        assert len(executed_steps) == 3

    def test_github_plugin_tool_definitions(self):
        plugin = GitHubPlugin()
        assert plugin.id == "github"
        assert "github.open" in plugin.actions
        assert "github.search" in plugin.actions
        assert "github.push" in plugin.actions
        assert "github.notifications" in plugin.actions

        tools = plugin.get_tool_definitions()
        assert len(tools) == 10
        tool_names = [t["function"]["name"] for t in tools]
        assert "plugin_github_open" in tool_names
        assert "plugin_github_search" in tool_names

    def test_executor_git_voice_commands(self):
        res = execute_system_command_detailed("check git status")
        assert res["success"] is True
        assert res["tool"] == "dev_tools_git_status"
        assert "Git status" in res["message"] or "clean" in res["message"]

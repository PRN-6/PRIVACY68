import unittest
import logging
from unittest.mock import MagicMock, patch
from ui.tray import SystemTray
from actions.agent_brain import agent_brain
from actions.executor import execute_system_command_detailed

# Disable logging for cleaner test output
logging.disable(logging.CRITICAL)

class TestPrivacy68Core(unittest.TestCase):
    def setUp(self):
        # Mock UIManager since we aren't running the full app
        self.mock_ui_manager = MagicMock()
        self.tray = SystemTray(self.mock_ui_manager)

    def test_tray_initialization(self):
        """Verify tray starts without syntax errors."""
        try:
            self.tray.start()
            self.assertTrue(self.tray.is_running)
        except Exception as e:
            self.fail(f"Tray failed to start: {e}")

    def test_agent_brain_generation(self):
        """Verify the AgentBrain generates code for a simple command."""
        # This tests the litellm -> Open Interpreter hybrid loop
        result = agent_brain.generate_and_execute("open chrome")
        self.assertIn("method", result)
        # We don't check for success=True because the actual execution
        # depends on Chrome being installed on the test machine,
        # but the 'method' should be 'open_interpreter_engine'.
        self.assertEqual(result["method"], "agentic_engine")

    def test_executor_flow(self):
        """Verify the end-to-end flow from executor to brain."""
        result = execute_system_command_detailed("say hello")
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

if __name__ == "__main__":
    unittest.main()


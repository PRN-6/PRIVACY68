import logging
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PRIVACY68.TestComputerUse")

from computer_use.window_manager import window_manager
from computer_use.windows_uia import uia_engine
from computer_use.launcher import app_launcher
from computer_use.observer import desktop_observer
from computer_use.actions import computer_actions


class TestComputerUse(unittest.TestCase):
    def test_launcher_alias_resolution(self):
        """Verify app name and alias resolution."""
        self.assertEqual(app_launcher.resolve_app_name("open task manager"), "task manager")
        self.assertEqual(app_launcher.resolve_app_name("taskmgr"), "task manager")
        self.assertEqual(app_launcher.resolve_app_name("launch calc"), "calculator")
        self.assertEqual(app_launcher.resolve_app_name("open text editor"), "notepad")
        self.assertEqual(app_launcher.resolve_app_name("open vs code"), "vs code")

    def test_window_manager_and_observer(self):
        """Verify active window query and desktop observation."""
        active = window_manager.get_active_window()
        self.assertIsNotNone(active)

        visible = window_manager.list_visible_windows()
        self.assertIsInstance(visible, list)

        state = desktop_observer.observe(inspect_controls=False)
        self.assertIn("active_window", state)
        self.assertIn("visible_windows", state)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from unittest.mock import patch

from ui.manager import UIManager


class TestDashboardLaunch(unittest.TestCase):
    def test_frozen_dashboard_launch_uses_executable_dashboard_mode(self):
        with patch("ui.manager.sys.frozen", True, create=True):
            with patch("ui.manager.sys.executable", r"C:\Program Files\PRIVACY68\PRIVACY68.exe"):
                with patch("subprocess.Popen") as popen:
                    UIManager.open_dashboard(None)

        popen.assert_called_once_with(
            [r"C:\Program Files\PRIVACY68\PRIVACY68.exe", "--dashboard"]
        )

    def test_source_dashboard_launch_uses_python_module(self):
        with patch("ui.manager.sys.frozen", False, create=True):
            with patch("ui.manager.sys.executable", sys.executable):
                with patch("subprocess.Popen") as popen:
                    UIManager.open_dashboard(None)

        popen.assert_called_once_with(
            [sys.executable, "-m", "ui.dashboard_runner"]
        )


if __name__ == "__main__":
    unittest.main()

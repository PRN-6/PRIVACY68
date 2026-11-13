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


    def test_show_push_to_talk_overlay_delegates_to_hud(self):
        from unittest.mock import MagicMock
        mock_ui = MagicMock()
        mock_ui.hud = MagicMock()
        UIManager.show_push_to_talk_overlay(mock_ui)
        mock_ui.hud.show_ptt_overlay.assert_called_once_with(ui_manager=mock_ui)

    def test_system_tray_voice_command_triggers_overlay(self):
        from ui.tray import SystemTray
        from unittest.mock import MagicMock
        mock_ui = MagicMock()
        tray = SystemTray(ui_manager=mock_ui)
        tray._on_voice_command()
        mock_ui.show_push_to_talk_overlay.assert_called_once()

    def test_ptt_overlay_instance_toggle(self):
        import tkinter as tk
        from ui.ptt_overlay import PushToTalkOverlay
        root = tk.Tk()
        root.withdraw()
        try:
            overlay = PushToTalkOverlay(parent_root=root)
            self.assertTrue(overlay.is_alive())
            overlay.hide()
            self.assertFalse(overlay.window.winfo_viewable())
            overlay.toggle()
            self.assertTrue(overlay.window.winfo_viewable())
            overlay.window.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

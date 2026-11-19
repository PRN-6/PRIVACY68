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
            try:
                root.update_idletasks()
                root.destroy()
            except Exception:
                pass

    def test_ptt_overlay_text_command_submission(self):
        import tkinter as tk
        from ui.ptt_overlay import PushToTalkOverlay
        from unittest.mock import MagicMock, patch

        root = tk.Tk()
        root.withdraw()
        try:
            mock_ui = MagicMock()
            overlay = PushToTalkOverlay(parent_root=root, ui_manager=mock_ui)
            overlay.cmd_entry.delete(0, tk.END)
            overlay.cmd_entry.insert(0, "open chrome")

            with patch("actions.executor.execute_system_command_detailed", return_value={"success": True, "message": "Chrome opened"}) as mock_exec:
                overlay._on_text_submitted()
                # Wait for worker thread to complete execution
                import time
                for _ in range(20):
                    if mock_exec.called:
                        break
                    time.sleep(0.05)
                mock_exec.assert_called_once()
                self.assertEqual(mock_exec.call_args[0][0], "open chrome")
                mock_ui.on_transcription.assert_called_once_with("open chrome")
                time.sleep(0.05)

            overlay.window.destroy()
        finally:
            try:
                root.update_idletasks()
                root.destroy()
            except Exception:
                pass

    def test_ptt_overlay_placeholder_not_submitted(self):
        import tkinter as tk
        from ui.ptt_overlay import PushToTalkOverlay
        from unittest.mock import MagicMock, patch

        root = tk.Tk()
        root.withdraw()
        try:
            overlay = PushToTalkOverlay(parent_root=root)
            with patch("actions.executor.execute_system_command_detailed") as mock_exec:
                overlay._on_text_submitted()
                mock_exec.assert_not_called()
            overlay.window.destroy()
        finally:
            try:
                root.update_idletasks()
                root.destroy()
            except Exception:
                pass

    def test_ptt_overlay_spacebar_inside_entry_does_not_trigger_mic(self):
        import tkinter as tk
        from ui.ptt_overlay import PushToTalkOverlay
        from unittest.mock import MagicMock

        root = tk.Tk()
        root.withdraw()
        try:
            overlay = PushToTalkOverlay(parent_root=root)
            overlay._on_mic_clicked = MagicMock()

            # Event originating from cmd_entry
            entry_event = MagicMock()
            entry_event.widget = overlay.cmd_entry
            overlay._on_space_pressed(entry_event)
            overlay._on_mic_clicked.assert_not_called()

            # Event originating from window
            win_event = MagicMock()
            win_event.widget = overlay.window
            overlay._on_space_pressed(win_event)
            overlay._on_mic_clicked.assert_called_once()

            overlay.window.destroy()
        finally:
            try:
                root.update_idletasks()
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()

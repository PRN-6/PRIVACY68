from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from ui.command_bar import CommandBar
from ui.manager import UIManager
from ui.tray import SystemTray


class TestUIManager(unittest.TestCase):
    def test_frozen_dashboard_launch(self):
        with patch("ui.manager.sys.frozen", True, create=True), patch("ui.manager.subprocess.Popen") as popen:
            UIManager.open_dashboard(None)
        popen.assert_called_once_with([sys.executable, "--dashboard"])

    def test_source_dashboard_launch_works_outside_project_directory(self):
        with patch("ui.manager.sys.frozen", False, create=True), patch("ui.manager.subprocess.Popen") as popen:
            UIManager.open_dashboard(None)
        app = str(Path(__file__).resolve().parents[1] / "app.py")
        popen.assert_called_once_with([sys.executable, app, "--dashboard"])

    def test_tray_command_queues_window_on_main_thread(self):
        manager = UIManager()
        manager.tray._on_command()
        manager.root = Mock()
        with patch("ui.command_bar.CommandBar") as command_bar:
            manager._poll_events()
        command_bar.assert_called_once_with(manager.root)
        command_bar.return_value.show.assert_called_once()

    def test_shutdown_returns_from_main_loop(self):
        manager = UIManager()
        manager.root = Mock()
        manager.shutdown()
        manager._poll_events()
        manager.root.quit.assert_called_once()
        manager.root.after.assert_not_called()

    def test_stop_removes_tray_icon(self):
        tray = SystemTray(Mock())
        tray.icon = Mock()
        tray.is_running = True
        tray.stop()
        tray.icon.stop.assert_called_once()
        self.assertFalse(tray.is_running)


class TestCommandBar(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.bar = CommandBar(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_show_hide_toggle(self):
        self.assertTrue(self.bar.is_alive())
        self.bar.hide()
        self.assertEqual(self.bar.window.state(), "withdrawn")
        self.bar.toggle()
        self.assertEqual(self.bar.window.state(), "normal")

    def test_empty_input_and_double_submission_are_ignored(self):
        with patch("ui.command_bar.threading.Thread") as worker:
            self.bar._on_text_submitted()
            worker.assert_not_called()
            self.bar.cmd_entry.insert(0, "open chrome")
            self.bar._on_text_submitted()
            self.bar.cmd_entry.insert(0, "open notepad")
            self.bar._on_text_submitted()
            worker.assert_called_once()

    def test_worker_result_is_applied_only_by_main_thread_poll(self):
        self.bar.is_processing = True
        with patch("actions.executor.execute_system_command_detailed", return_value={
            "success": True, "message": "Chrome opened"
        }) as execute, patch.object(self.bar, "window") as window:
            self.bar._execute("open chrome")
            execute.assert_called_once_with("open chrome")
            window.after.assert_not_called()
            self.assertTrue(self.bar.is_processing)
        self.bar.window.after_cancel(self.bar._poll_job)
        self.bar._poll_results()
        self.assertFalse(self.bar.is_processing)
        self.assertEqual(self.bar.status.cget("text"), "Chrome opened")

    def test_failure_releases_busy_state_and_shows_message(self):
        self.bar.is_processing = True
        with patch("actions.executor.execute_system_command_detailed", side_effect=RuntimeError("Unavailable")):
            self.bar._execute("open chrome")
        self.bar.window.after_cancel(self.bar._poll_job)
        self.bar._poll_results()
        self.assertFalse(self.bar.is_processing)
        self.assertEqual(self.bar.status.cget("text"), "Unavailable")
        self.assertEqual(str(self.bar.send_btn.cget("state")), "normal")

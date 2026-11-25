"""Coordinate the system tray and the text command bar on Tk's main thread."""

import logging
from pathlib import Path
import queue
import subprocess
import sys
import tkinter as tk

from ui.tray import SystemTray

logger = logging.getLogger("PRIVACY68.UIManager")


class UIManager:
    def __init__(self):
        self.tray = SystemTray(ui_manager=self)
        self.root = None
        self.command_bar = None
        self._events = queue.Queue()

    def start_tray(self):
        self.tray.start()

    def run_ui_loop(self):
        """Keep all Tk operations on the main thread, including worker results."""
        self.root = tk.Tk()
        self.root.title("PRIVACY68 Background Service")
        self.root.withdraw()
        self._poll_events()
        try:
            self.root.mainloop()
        finally:
            if self.root is not None:
                self.root.destroy()
                self.root = None

    def _poll_events(self):
        # Bound each batch so a busy worker cannot starve the UI event loop.
        for _ in range(100):
            try:
                action = self._events.get_nowait()
            except queue.Empty:
                break
            if action == "quit":
                self.root.quit()
                return
            if action == "command_bar":
                from ui.command_bar import CommandBar
                if self.command_bar is None or not self.command_bar.is_alive():
                    self.command_bar = CommandBar(self.root)
                    self.command_bar.show()
                else:
                    self.command_bar.toggle()
        self.root.after(50, self._poll_events)

    def show_command_bar(self):
        """Can be called from the tray thread before Tk has started."""
        self._events.put("command_bar")

    def open_dashboard(self):
        """Launch WebView on its own process's main thread."""
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--dashboard"]
        else:
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / "app.py"), "--dashboard"]
        try:
            subprocess.Popen(command)
        except OSError:
            logger.exception("Could not launch the PRIVACY68 Control Center.")

    def shutdown(self):
        """Return from the main loop so the application's cleanup can run."""
        self._events.put("quit")

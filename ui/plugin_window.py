import logging
import os
import sys
import subprocess
from tkinter import messagebox

logger = logging.getLogger("PRIVACY68.DashboardWindow")

class PluginManagerWindow:
    """
    PRIVACY68 Control Center & Plugin Hub:
    Launches the modern Tailwind CSS / WebView2 desktop dashboard interface.
    Provides graceful fallback notification if WebView2 runtime is unavailable.
    """
    def __init__(self, parent_root=None):
        self.parent_root = parent_root
        self._proc = None

    def open(self):
        """Opens or brings the Control Center to the foreground."""
        try:
            # If modern dashboard process is already running, avoid duplicate launches
            if self._proc is not None and self._proc.poll() is None:
                logger.info("Dashboard process is already running.")
                return

            is_frozen = getattr(sys, "frozen", False)
            if is_frozen:
                cmd = [sys.executable, "--dashboard"]
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
                python_bin = venv_python if os.path.exists(venv_python) else sys.executable
                runner_script = os.path.join(project_root, "ui", "dashboard_runner.py")
                cmd = [python_bin, runner_script]

            self._proc = subprocess.Popen(cmd)
            logger.info("Launched modern Tailwind CSS Control Center Dashboard via WebView2.")
        except Exception as e:
            logger.warning(f"Could not launch WebView2 dashboard: {e}")
            messagebox.showerror(
                "PRIVACY68 Control Center",
                f"Could not open Control Center Dashboard:\n{e}\n\nPlease verify WebView2 / pywebview is installed."
            )

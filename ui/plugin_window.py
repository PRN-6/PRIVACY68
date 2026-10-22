import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from tkinter import messagebox

from utils.webview2 import get_webview2_install_hint, get_webview2_status

logger = logging.getLogger("PRIVACY68.DashboardWindow")

#: How long to wait for the Control Center window to actually appear.
DASHBOARD_READY_TIMEOUT = 90.0


class PluginManagerWindow:
    """
    PRIVACY68 Control Center & Plugin Hub:
    Launches the modern Tailwind CSS / WebView2 desktop dashboard interface.
    Provides graceful fallback notification if WebView2 runtime is unavailable.
    """
    def __init__(self, parent_root=None):
        self.parent_root = parent_root
        self._proc = None

    def _show_error(self, title: str, message: str) -> None:
        """Shows a native error dialog on the Tk thread when one is available."""
        def _show():
            try:
                messagebox.showerror(title, message)
            except Exception as e:
                logger.error(f"Could not display error dialog: {e}")

        root = self.parent_root
        if root is not None:
            try:
                root.after(0, _show)
                return
            except Exception as e:
                logger.debug(f"_show_error: could not marshal to Tk thread: {e}")
        _show()

    def _watch_startup(self, ready_file: str, started_at: float) -> None:
        """
        Waits for the dashboard to report that its window is on screen.

        Without this handshake a failed launch is indistinguishable from a
        slow one: the user is left waiting with no explanation.
        """
        deadline = started_at + DASHBOARD_READY_TIMEOUT
        while time.time() < deadline:
            if os.path.exists(ready_file):
                payload = {}
                try:
                    with open(ready_file, "r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                except Exception as e:
                    logger.debug(f"Could not read readiness file: {e}")

                elapsed = time.time() - started_at
                if payload.get("ok"):
                    logger.info(f"Control Center is on screen after {elapsed:.1f}s.")
                else:
                    error = payload.get("error", "unknown error")
                    logger.error(f"Control Center failed to start: {error}")
                    self._show_error(
                        "PRIVACY68 Control Center",
                        f"The Control Center could not be opened:\n\n{error}\n\n"
                        + get_webview2_install_hint()
                    )
                return

            if self._proc is not None and self._proc.poll() is not None:
                logger.error(
                    f"Control Center process exited before showing a window "
                    f"(exit code {self._proc.returncode})."
                )
                self._show_error(
                    "PRIVACY68 Control Center",
                    "The Control Center closed unexpectedly while starting up.\n\n"
                    f"Exit code: {self._proc.returncode}\n\n"
                    "Check the PRIVACY68 log for details:\n"
                    "%APPDATA%\\PRIVACY68\\privacy68.log"
                )
                return

            time.sleep(0.25)

        # A timeout is not necessarily fatal — on a cold mechanical drive the
        # WebView2 process can take a while — so warn without interrupting.
        logger.warning(
            f"Control Center did not report readiness within "
            f"{DASHBOARD_READY_TIMEOUT:.0f}s; it may still be loading."
        )

    def open(self):
        """Opens or brings the Control Center to the foreground."""
        try:
            # If modern dashboard process is already running, avoid duplicate launches
            if self._proc is not None and self._proc.poll() is None:
                logger.info("Dashboard process is already running.")
                return

            # ── Pre-flight: the WebView2 runtime must be present ───────────
            # Checking here means the user gets an immediate, actionable
            # message instead of a 60-second stall followed by a blank
            # window.
            status = get_webview2_status()
            if not status["installed"]:
                logger.error("Microsoft Edge WebView2 Runtime is not installed.")
                self._show_error("PRIVACY68 Control Center", get_webview2_install_hint())
                return

            ready_file = os.path.join(
                tempfile.gettempdir(),
                f"privacy68_dashboard_{os.getpid()}_{int(time.time() * 1000)}.ready"
            )

            is_frozen = getattr(sys, "frozen", False)
            if is_frozen:
                cmd = [sys.executable, "--dashboard"]
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
                python_bin = venv_python if os.path.exists(venv_python) else sys.executable
                runner_script = os.path.join(project_root, "ui", "dashboard_runner.py")
                cmd = [python_bin, runner_script]

            cmd.append(f"--dashboard-ready={ready_file}")

            started_at = time.time()
            # CREATE_NO_WINDOW keeps a console window from flashing when the
            # Control Center is launched from a frozen build.
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(cmd, creationflags=creation_flags)
            logger.info("Launched modern Tailwind CSS Control Center Dashboard via WebView2.")

            threading.Thread(
                target=self._watch_startup,
                args=(ready_file, started_at),
                daemon=True
            ).start()

        except Exception as e:
            logger.warning(f"Could not launch WebView2 dashboard: {e}")
            self._show_error(
                "PRIVACY68 Control Center",
                f"Could not open Control Center Dashboard:\n{e}\n\nPlease verify WebView2 / pywebview is installed."
            )

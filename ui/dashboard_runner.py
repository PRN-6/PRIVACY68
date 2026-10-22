import json
import logging
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.webview2 import get_webview2_install_hint, get_webview2_status

logger = logging.getLogger("PRIVACY68.DashboardRunner")

# Handshake flag: the launcher passes the path of a file that the dashboard
# writes to once its window is actually on screen. Without it the launcher
# cannot tell "still starting" apart from "crashed on startup".
READY_FILE_PREFIX = "--dashboard-ready="


def get_dashboard_html_path() -> str:
    """Resolves the path to index.html supporting both source and PyInstaller."""
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = PROJECT_ROOT

    html_path = os.path.join(base, "ui", "dashboard", "index.html")
    if not os.path.exists(html_path):
        alt_path = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
        if os.path.exists(alt_path):
            return alt_path
    return html_path


def _ready_file_path() -> str:
    """Returns the readiness file requested by the launcher, if any."""
    for arg in sys.argv:
        if arg.startswith(READY_FILE_PREFIX):
            return arg[len(READY_FILE_PREFIX):]
    return ""


def _signal_ready(payload: dict) -> None:
    """Writes the readiness payload exactly once."""
    path = _ready_file_path()
    if not path:
        return
    try:
        with open(path, "x", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except FileExistsError:
        pass
    except Exception as e:
        logger.debug(f"Could not write readiness file: {e}")


def _show_native_error(title: str, message: str) -> None:
    """
    Reports a fatal startup problem in a native dialog.

    The dashboard runs in a windowed build with no console, so a silent log
    entry would leave the user staring at nothing.
    """
    logger.error(f"{title}: {message}")
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(title, message)
        root.destroy()
    except Exception as e:
        logger.debug(f"Could not display native error dialog: {e}")


def run_dashboard():
    """Launches the modern PRIVACY68 Control Center via WebView2."""
    html_path = get_dashboard_html_path()
    if not os.path.exists(html_path):
        _show_native_error(
            "PRIVACY68 Control Center",
            f"The Control Center assets could not be found:\n\n{html_path}\n\n"
            "Please reinstall PRIVACY68."
        )
        _signal_ready({"ok": False, "error": "missing_assets"})
        return

    # ── Pre-flight: the browser engine is a hard requirement ───────────────
    # On Windows the WebView2 runtime is missing on plenty of machines and
    # pywebview then probes the registry for 30-60 seconds before falling back
    # to the deprecated MSHTML engine, which renders a blank page. Detecting it
    # here turns a silent hang into an instant, actionable message.
    # On Linux the same check reports which engine (WebKitGTK / QtWebEngine)
    # is available.
    status = get_webview2_status()
    if not status["installed"]:
        logger.error(f"Control Center browser engine is missing: {status}")
        _show_native_error("PRIVACY68 Control Center", get_webview2_install_hint())
        _signal_ready({"ok": False, "error": "webview_engine_missing"})
        return

    try:
        import webview
        from ui.dashboard_bridge import DashboardAPI
    except Exception as e:
        _show_native_error(
            "PRIVACY68 Control Center",
            f"The Control Center could not be initialised:\n\n{e}"
        )
        _signal_ready({"ok": False, "error": str(e)})
        return

    api = DashboardAPI()
    window = webview.create_window(
        title="PRIVACY68 Control Center",
        url=html_path,
        js_api=api,
        width=1000,
        height=740,
        min_size=(800, 620),
        text_select=True
    )
    api.set_window(window)

    def _on_shown():
        logger.info("Control Center window is on screen.")
        _signal_ready({
            "ok": True,
            "pid": os.getpid(),
            "webview2_version": status.get("version"),
            "engine": status.get("engine"),
        })

    window.events.shown += _on_shown

    logger.info(f"Opening PRIVACY68 Tailwind Control Center ({html_path})...")
    try:
        webview.start(debug=False)
    except Exception as e:
        logger.error(f"Control Center failed to start: {e}", exc_info=True)
        _show_native_error(
            "PRIVACY68 Control Center",
            f"The Control Center could not be opened:\n\n{e}\n\n{get_webview2_install_hint()}"
        )
        _signal_ready({"ok": False, "error": str(e)})


if __name__ == "__main__":
    # Standalone launches (development) get their own log configuration; the
    # frozen build has already configured logging in app.py.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_dashboard()

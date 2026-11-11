import os
import sys
import logging
import threading

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("PRIVACY68.DashboardRunner")


def get_dashboard_html_path() -> str:
    """Resolves the path to index.html supporting both source and PyInstaller frozen modes."""
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = PROJECT_ROOT

    candidates = [
        os.path.join(base, "ui", "dashboard", "index.html"),
        os.path.join(base, "_internal", "ui", "dashboard", "index.html"),
        os.path.join(os.path.dirname(sys.executable), "_internal", "ui", "dashboard", "index.html"),
        os.path.join(os.path.dirname(__file__), "dashboard", "index.html"),
        os.path.join(PROJECT_ROOT, "ui", "dashboard", "index.html"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def run_dashboard():
    """Launches the modern PRIVACY68 Control Center (WebView2 HTML/JS GUI with native fallback)."""
    # Pre-warm agent brain in background thread so LiteLLM import does not block UI load
    threading.Thread(target=lambda: __import__("actions.agent_brain"), daemon=True).start()

    html_path = get_dashboard_html_path()
    try:
        import webview
        from ui.dashboard_bridge import DashboardAPI

        logger.info(f"Opening PRIVACY68 Control Center via WebView2 ({html_path})...")
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
        webview.start(debug=False)
    except Exception as webview_err:
        logger.warning(f"WebView2 launch failed ({webview_err}), falling back to native CustomTkinter GUI...")
        try:
            from ui.dashboard_app import run_dashboard_app
            run_dashboard_app()
        except Exception as e:
            logger.error(f"Both WebView2 and Native GUI fallback failed: {e}")
            raise


if __name__ == "__main__":
    run_dashboard()

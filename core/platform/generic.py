"""
Generic fallback backend for PRIVACY68.

Used on operating systems that have no dedicated backend (FreeBSD, and
anything else that is neither Windows, Linux nor macOS). It implements the
small set of operations that can be done with plain POSIX tools so the
assistant still starts up and reports a useful error instead of crashing.
"""

import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("PRIVACY68.Platform.Generic")


def _run(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or "")
    except Exception as e:
        logger.debug(f"_run failed for {cmd}: {e}")
        return 1, ""


def get_shell_folders() -> Dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "images": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
        "home": home,
        "user": home,
    }


def list_windows() -> List[Dict[str, Any]]:
    return []


def get_active_window() -> Dict[str, Any]:
    return {"hwnd": 0, "title": "", "process_name": "", "class_name": "", "is_active": False}


def find_window(query: str) -> int:
    return 0


def focus_window(target: Any) -> bool:
    return False


def maximize_window(target: Any = None) -> bool:
    return False


def minimize_window(target: Any = None) -> bool:
    return False


def restore_window(target: Any = None) -> bool:
    return False


def close_window(target: Any = None) -> bool:
    return False


def volume_up() -> bool:
    return False


def volume_down() -> bool:
    return False


def volume_mute() -> bool:
    return False


def lock_screen() -> bool:
    if shutil.which("loginctl"):
        code, _ = _run(["loginctl", "lock-session"], timeout=5.0)
        return code == 0
    return False


def take_screenshot(path: Optional[str] = None) -> Optional[str]:
    return None


def open_path(path: str) -> bool:
    if not os.path.exists(path):
        return False
    opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
    try:
        subprocess.Popen([opener, path], start_new_session=True)
        return True
    except Exception:
        return False


def open_uri(uri: str) -> bool:
    opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
    try:
        subprocess.Popen([opener, uri], start_new_session=True)
        return True
    except Exception:
        return False


def open_url_in_browser(url: str, browser: str) -> bool:
    return open_uri(url)


def open_settings(page: str = "") -> bool:
    return False


def kill_process(name: str) -> bool:
    if shutil.which("pkill"):
        code, _ = _run(["pkill", "-f", name], timeout=5.0)
        return code == 0
    return False


def launch_app(name: str) -> bool:
    binary = shutil.which(name)
    if not binary:
        return False
    try:
        subprocess.Popen([binary], start_new_session=True)
        return True
    except Exception:
        return False


def clipboard_get_text() -> str:
    return ""

"""
macOS backend for the PRIVACY68 platform layer.

Uses the same helper tools as the Linux backend where possible
(`osascript` for window handling, `osascript` for volume, `screencapture`
for screenshots) so the two POSIX backends stay conceptually identical.
"""

import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("PRIVACY68.Platform.macOS")


def _run(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:
        logger.debug(f"_run failed for {cmd}: {e}")
        return 1, ""


def _osascript(script: str, timeout: float = 6.0) -> Tuple[int, str]:
    return _run(["osascript", "-e", script], timeout=timeout)


def get_shell_folders() -> Dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "images": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Movies"),
        "home": home,
        "user": home,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Window management
# ─────────────────────────────────────────────────────────────────────────────
def _system_events_windows() -> List[Dict[str, Any]]:
    """Enumerates windows through the System Events scripting bridge."""
    script = (
        'tell application "System Events" to get {name, unix id, process name} '
        "of every window of every process whose visible is true"
    )
    code, out = _osascript(script)
    if code != 0 or not out.strip():
        return []
    windows: List[Dict[str, Any]] = []
    for chunk in out.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        windows.append(
            {
                "hwnd": abs(hash(chunk)) % (2**31),
                "title": chunk,
                "process_name": "",
                "class_name": "",
            }
        )
    return windows


def list_windows() -> List[Dict[str, Any]]:
    return _system_events_windows()


def get_active_window() -> Dict[str, Any]:
    code, out = _osascript(
        'tell application "System Events" to get name of first process whose frontmost is true'
    )
    title = out.strip() if code == 0 else ""
    return {
        "hwnd": abs(hash(title)) % (2**31) if title else 0,
        "title": title,
        "process_name": title.lower(),
        "class_name": "",
        "is_active": bool(title),
    }


def find_window(query: str) -> int:
    if not query:
        return 0
    q = query.lower().strip()
    for win in list_windows():
        if q in str(win.get("title", "")).lower():
            return int(win["hwnd"])
    return 0


def focus_window(target: Any) -> bool:
    if isinstance(target, int):
        title = ""
        for win in list_windows():
            if int(win["hwnd"]) == target:
                title = win.get("title", "")
                break
    else:
        title = str(target)
    if not title:
        return False
    code, _ = _osascript(
        f'tell application "System Events" to set frontmost of process "{title}" to true'
    )
    return code == 0


def _window_state(state: str) -> bool:
    code, _ = _osascript(
        'tell application "System Events" to tell first process whose frontmost is true '
        f'to set value of attribute "AX{state}" of window 1 to true'
    )
    return code == 0


def maximize_window(target: Any = None) -> bool:
    return _window_state("FullScreen")


def minimize_window(target: Any = None) -> bool:
    return _window_state("Minimized")


def restore_window(target: Any = None) -> bool:
    code, _ = _osascript(
        'tell application "System Events" to tell first process whose frontmost is true '
        "to set value of attribute \"AXMinimized\" of window 1 to false"
    )
    return code == 0


def close_window(target: Any = None) -> bool:
    code, _ = _osascript(
        'tell application "System Events" to tell first process whose frontmost is true '
        "to close window 1"
    )
    return code == 0


# ─────────────────────────────────────────────────────────────────────────────
# Audio, screen, session
# ─────────────────────────────────────────────────────────────────────────────
def volume_up() -> bool:
    code, _ = _osascript("set volume output volume ((output volume of (get volume settings)) + 5)")
    return code == 0


def volume_down() -> bool:
    code, _ = _osascript("set volume output volume ((output volume of (get volume settings)) - 5)")
    return code == 0


def volume_mute() -> bool:
    code, _ = _osascript("set volume output muted true")
    return code == 0


def lock_screen() -> bool:
    if shutil.which("pmset"):
        code, _ = _run(["pmset", "displaysleepnow"], timeout=5.0)
        if code == 0:
            return True
    code, _ = _osascript('tell application "System Events" to keystroke "q" using command down')
    return code == 0


def take_screenshot(path: Optional[str] = None) -> Optional[str]:
    if not path:
        from core.platform import pictures_path

        folder = pictures_path()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"Screenshot_{int(time.time())}.png")
    if shutil.which("screencapture"):
        code, _ = _run(["screencapture", "-x", path], timeout=20.0)
        if code == 0 and os.path.exists(path):
            return path
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Shell integration
# ─────────────────────────────────────────────────────────────────────────────
def open_path(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        subprocess.Popen(["open", path], start_new_session=True)
        return True
    except Exception as e:
        logger.debug(f"open_path failed: {e}")
        return False


def open_uri(uri: str) -> bool:
    try:
        subprocess.Popen(["open", uri], start_new_session=True)
        return True
    except Exception as e:
        logger.debug(f"open_uri failed: {e}")
        return False


def open_url_in_browser(url: str, browser: str) -> bool:
    return open_uri(url)


def open_settings(page: str = "") -> bool:
    panel = {
        "bluetooth": "Bluetooth",
        "wifi": "Wi-Fi",
        "network": "Network",
        "sound": "Sound",
        "display": "Displays",
        "privacy": "Privacy & Security",
        "notifications": "Notifications",
        "appearance": "Appearance",
        "about": "General",
        "system": "General",
    }.get((page or "").lower().strip(), "General")
    try:
        subprocess.Popen(
            ["open", f"x-apple.systempreferences:com.apple.preference?{panel}"],
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def kill_process(name: str) -> bool:
    target = name.replace(".exe", "").strip()
    if not target:
        return False
    code, _ = _run(["pkill", "-f", target], timeout=5.0)
    return code == 0


def launch_app(name: str) -> bool:
    try:
        subprocess.Popen(["open", "-a", name], start_new_session=True)
        return True
    except Exception as e:
        logger.debug(f"launch_app failed: {e}")
        return False


def clipboard_get_text() -> str:
    code, out = _osascript("the clipboard as text")
    return out if code == 0 else ""

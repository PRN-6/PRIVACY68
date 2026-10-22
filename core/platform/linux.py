"""
Linux backend for the PRIVACY68 platform layer.

Targets X11 and XWayland sessions, which is what virtually every desktop
distribution provides. The backend prefers the standard command line tools
because they work across GNOME, KDE, XFCE and MATE without extra Python
dependencies:

  * `wmctrl` / `xdotool` — window enumeration, focus, geometry
  * `pactl` (PipeWire/PulseAudio) / `amixer` (ALSA) — volume
  * `xdg-open` — opening files and URIs
  * `gnome-control-center`, `systemsettings`, `xfce4-settings-manager` — the
    settings application of the running desktop
  * `loginctl`, `xdg-screensaver` — session locking
  * `gnome-screenshot`, `spectacle`, `scrot`, `maim`, `import` — screen capture

Every helper degrades gracefully: if the preferred tool is missing, the next
one is tried, and if none is available a clear failure is returned instead of
an exception.
"""

import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("PRIVACY68.Platform.Linux")

#: Steps used to raise/lower the volume by 5%.
VOLUME_STEP = 5


# ─────────────────────────────────────────────────────────────────────────────
# Small process helpers
# ─────────────────────────────────────────────────────────────────────────────
def _run(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str]:
    """Runs a command and returns (returncode, stdout). Never raises."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:
        logger.debug(f"_run failed for {cmd}: {e}")
        return 1, ""


def _which(*binaries: str) -> Optional[str]:
    for binary in binaries:
        found = shutil.which(binary)
        if found:
            return found
    return None


def _xdg_user_dir(name: str, fallback: str) -> str:
    """Resolves an XDG user directory (falls back to ~/name)."""
    try:
        code, out = _run(["xdg-user-dir", name], timeout=2.0)
        if code == 0:
            value = out.strip()
            if value and value.startswith("/"):
                return value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), fallback)


def get_shell_folders() -> Dict[str, str]:
    """Returns the XDG user directories, with sensible fallbacks."""
    home = os.path.expanduser("~")
    return {
        "desktop": _xdg_user_dir("DESKTOP", "Desktop"),
        "documents": _xdg_user_dir("DOCUMENTS", "Documents"),
        "downloads": _xdg_user_dir("DOWNLOADS", "Downloads"),
        "pictures": _xdg_user_dir("PICTURES", "Pictures"),
        "images": _xdg_user_dir("PICTURES", "Pictures"),
        "music": _xdg_user_dir("MUSIC", "Music"),
        "videos": _xdg_user_dir("VIDEOS", "Videos"),
        "home": home,
        "user": home,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Window management
# ─────────────────────────────────────────────────────────────────────────────
def _wmctrl_windows() -> List[Dict[str, Any]]:
    """Enumerates windows with `wmctrl -lp`."""
    code, out = _run(["wmctrl", "-lp"], timeout=4.0)
    if code != 0:
        return []
    windows: List[Dict[str, Any]] = []
    for line in out.splitlines():
        # Format: 0x03a00000  0 1234  hostname Title
        match = re.match(r"^(0x[0-9a-fA-F]+)\s+(-?\d+)\s+(\d+)\s+(\S+)\s+(.*)$", line)
        if not match:
            continue
        win_id, desktop, pid, host, title = match.groups()
        try:
            hwnd = int(win_id, 16)
        except ValueError:
            continue
        windows.append(
            {
                "hwnd": hwnd,
                "title": title.strip(),
                "process_name": _process_name(int(pid)),
                "class_name": "",
                "pid": int(pid),
                "desktop": int(desktop),
            }
        )
    return windows


def _xdotool_windows() -> List[Dict[str, Any]]:
    """Enumerates windows with `xdotool search` (fallback for wmctrl)."""
    code, out = _run(["xdotool", "search", "--onlyvisible", "--name", ""], timeout=4.0)
    if code != 0:
        return []
    windows: List[Dict[str, Any]] = []
    for line in out.split():
        try:
            hwnd = int(line)
        except ValueError:
            continue
        title = _xdotool_prop(hwnd, "getwindowname")
        if not title:
            continue
        pid = _xdotool_prop(hwnd, "getwindowpid")
        windows.append(
            {
                "hwnd": hwnd,
                "title": title,
                "process_name": _process_name(int(pid)) if pid and pid.isdigit() else "",
                "class_name": _xdotool_prop(hwnd, "getwindowclassname"),
                "pid": int(pid) if pid and pid.isdigit() else 0,
            }
        )
    return windows


def _xdotool_prop(hwnd: int, command: str) -> str:
    code, out = _run(["xdotool", command, str(hwnd)], timeout=3.0)
    return out.strip() if code == 0 else ""


def _process_name(pid: int) -> str:
    """Returns the executable name of a process id."""
    if not pid or pid <= 0:
        return ""
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def list_windows() -> List[Dict[str, Any]]:
    """Lists the visible top-level windows of the current session."""
    windows = _wmctrl_windows()
    if windows:
        return windows
    return _xdotool_windows()


def _active_hwnd() -> int:
    """Returns the id of the currently focused window (0 when unknown)."""
    code, out = _run(["xdotool", "getactivewindow"], timeout=3.0)
    if code == 0 and out.strip().isdigit():
        return int(out.strip())
    # wmctrl marks the active window with a '*' in the first column.
    code, out = _run(["wmctrl", "-lp"], timeout=4.0)
    if code == 0:
        for line in out.splitlines():
            if line.startswith("*"):
                match = re.match(r"^\*?(0x[0-9a-fA-F]+)", line)
                if match:
                    return int(match.group(1), 16)
    return 0


def get_active_window() -> Dict[str, Any]:
    """Returns metadata about the focused window."""
    hwnd = _active_hwnd()
    if not hwnd:
        return {"hwnd": 0, "title": "", "process_name": "", "class_name": "", "is_active": False}

    title = ""
    code, out = _run(["xdotool", "getactivewindow", "getwindowname"], timeout=3.0)
    if code == 0:
        title = out.strip()

    pid = 0
    code, out = _run(["xdotool", "getactivewindow", "getwindowpid"], timeout=3.0)
    if code == 0 and out.strip().isdigit():
        pid = int(out.strip())

    class_name = ""
    code, out = _run(["xdotool", "getactivewindow", "getwindowclassname"], timeout=3.0)
    if code == 0:
        class_name = out.strip()

    return {
        "hwnd": hwnd,
        "title": title,
        "process_name": _process_name(pid),
        "class_name": class_name,
        "is_active": True,
        "pid": pid,
    }


#: Process-name rules, mirroring the Windows backend.
APP_RULES: Dict[str, Dict[str, List[str]]] = {
    "chrome": {"processes": ["chrome", "google-chrome", "chromium"], "titles": ["google chrome", "chromium"]},
    "google chrome": {"processes": ["chrome", "google-chrome"], "titles": ["google chrome"]},
    "brave": {"processes": ["brave", "brave-browser"], "titles": ["brave"]},
    "brave browser": {"processes": ["brave", "brave-browser"], "titles": ["brave"]},
    "edge": {"processes": ["microsoft-edge"], "titles": ["microsoft edge", "edge"]},
    "msedge": {"processes": ["microsoft-edge"], "titles": ["microsoft edge", "edge"]},
    "firefox": {"processes": ["firefox"], "titles": ["mozilla firefox", "firefox"]},
    "vs code": {"processes": ["code"], "titles": ["visual studio code", "code"]},
    "vscode": {"processes": ["code"], "titles": ["visual studio code"]},
    "visual studio code": {"processes": ["code"], "titles": ["visual studio code"]},
    "code": {"processes": ["code"], "titles": ["visual studio code"]},
    "terminal": {
        "processes": ["gnome-terminal", "konsole", "xfce4-terminal", "alacritty", "kitty", "xterm", "tilix"],
        "titles": ["terminal", "konsole", "alacritty", "kitty", "xterm"],
    },
    "file manager": {
        "processes": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
        "titles": ["files", "file manager", "nautilus", "dolphin", "thunar"],
    },
    "explorer": {
        "processes": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
        "titles": ["files", "file manager"],
    },
    "spotify": {"processes": ["spotify"], "titles": ["spotify"]},
    "discord": {"processes": ["discord"], "titles": ["discord"]},
    "whatsapp": {"processes": ["whatsapp"], "titles": ["whatsapp"]},
    "vlc": {"processes": ["vlc"], "titles": ["vlc"]},
    "task manager": {"processes": ["gnome-system-monitor", "ksysguard", "mate-system-monitor"], "titles": ["system monitor", "task manager"]},
    "calculator": {"processes": ["gnome-calculator", "kcalc", "galculator"], "titles": ["calculator"]},
    "notepad": {"processes": ["gedit", "gnome-text-editor", "kate", "mousepad", "pluma"], "titles": ["text editor", "notepad"]},
    "paint": {"processes": ["pinta", "kolourpaint", "gnome-paint"], "titles": ["paint", "pinta"]},
    "settings": {"processes": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"], "titles": ["settings"]},
    "camera": {"processes": ["cheese"], "titles": ["cheese", "camera"]},
    "photos": {"processes": ["shotwell", "gwenview", "eog"], "titles": ["image viewer", "photos"]},
    "clock": {"processes": ["gnome-clocks"], "titles": ["clocks"]},
    "store": {"processes": ["gnome-software", "plasma-discover"], "titles": ["software"]},
    "maps": {"processes": ["gnome-maps"], "titles": ["maps"]},
    "mail": {"processes": ["thunderbird"], "titles": ["thunderbird"]},
    "vscode insiders": {"processes": ["code-insiders"], "titles": ["visual studio code"]},
}


def find_window(query: str) -> int:
    """Finds a window by process name, title or app alias."""
    if not query:
        return 0
    q = query.lower().strip()
    windows = list_windows()
    if not windows:
        return 0

    rule = APP_RULES.get(q)
    if rule:
        procs = [p.lower() for p in rule.get("processes", [])]
        titles = [t.lower() for t in rule.get("titles", [])]
        for win in windows:
            proc = str(win.get("process_name", "")).lower()
            title = str(win.get("title", "")).lower()
            if procs and proc in procs:
                return int(win["hwnd"])
            if titles and any(term in title for term in titles):
                return int(win["hwnd"])

    for win in windows:
        title = str(win.get("title", "")).lower()
        proc = str(win.get("process_name", "")).lower()
        if q == proc or q in title:
            return int(win["hwnd"])

    return 0


def focus_window(target: Any) -> bool:
    """Raises the target window and gives it the keyboard focus."""
    hwnd = target if isinstance(target, int) else find_window(str(target))
    if not hwnd:
        logger.warning(f"Linux backend: cannot focus window '{target}'.")
        return False

    code, _ = _run(["wmctrl", "-i", "-a", str(hwnd)], timeout=4.0)
    if code == 0:
        return True
    code, _ = _run(["xdotool", "windowactivate", "--sync", str(hwnd)], timeout=4.0)
    if code == 0:
        return True
    code, _ = _run(["xdotool", "windowraise", str(hwnd)], timeout=4.0)
    return code == 0


def _resolve_hwnd(target: Any) -> int:
    if target is None:
        return _active_hwnd()
    if isinstance(target, int):
        return target
    return find_window(str(target))


def _wmctrl_state(hwnd: int, operation: str, state: str) -> bool:
    code, _ = _run(["wmctrl", "-i", "-r", str(hwnd), "-b", f"{operation},{state}"], timeout=4.0)
    return code == 0


def _key(keysym: str) -> bool:
    code, _ = _run(["xdotool", "key", keysym], timeout=3.0)
    return code == 0


def maximize_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd and _wmctrl_state(hwnd, "add", "maximized_vert,maximized_horz"):
        return True
    return _key("super+Up")


def minimize_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd and _wmctrl_state(hwnd, "add", "hidden"):
        return True
    return _key("super+Down")


def restore_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd and _wmctrl_state(hwnd, "remove", "maximized_vert,maximized_horz,hidden"):
        return True
    return _key("super+Down")


def close_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd:
        code, _ = _run(["wmctrl", "-i", "-c", str(hwnd)], timeout=4.0)
        if code == 0:
            return True
        code, _ = _run(["xdotool", "windowclose", str(hwnd)], timeout=4.0)
        if code == 0:
            return True
    return _key("alt+F4")


# ─────────────────────────────────────────────────────────────────────────────
# Audio
# ─────────────────────────────────────────────────────────────────────────────
def _pactl_available() -> bool:
    return shutil.which("pactl") is not None


def _pactl_sink() -> str:
    code, out = _run(["pactl", "get-default-sink"], timeout=3.0)
    return out.strip() if code == 0 else "@DEFAULT_SINK@"


def volume_up() -> bool:
    if _pactl_available():
        code, _ = _run(
            ["pactl", "set-sink-volume", _pactl_sink(), f"+{VOLUME_STEP}%"], timeout=3.0
        )
        if code == 0:
            return True
    if shutil.which("amixer"):
        code, _ = _run(["amixer", "-q", "sset", "Master", f"{VOLUME_STEP}%+"], timeout=3.0)
        if code == 0:
            return True
    return _key("XF86AudioRaiseVolume")


def volume_down() -> bool:
    if _pactl_available():
        code, _ = _run(
            ["pactl", "set-sink-volume", _pactl_sink(), f"-{VOLUME_STEP}%"], timeout=3.0
        )
        if code == 0:
            return True
    if shutil.which("amixer"):
        code, _ = _run(["amixer", "-q", "sset", "Master", f"{VOLUME_STEP}%-"], timeout=3.0)
        if code == 0:
            return True
    return _key("XF86AudioLowerVolume")


def volume_mute() -> bool:
    if _pactl_available():
        code, _ = _run(["pactl", "set-sink-mute", _pactl_sink(), "toggle"], timeout=3.0)
        if code == 0:
            return True
    if shutil.which("amixer"):
        code, _ = _run(["amixer", "-q", "sset", "Master", "toggle"], timeout=3.0)
        if code == 0:
            return True
    return _key("XF86AudioMute")


# ─────────────────────────────────────────────────────────────────────────────
# Session, screen and shell
# ─────────────────────────────────────────────────────────────────────────────
def lock_screen() -> bool:
    for cmd in (
        ["loginctl", "lock-session"],
        ["xdg-screensaver", "lock"],
        ["gnome-screensaver-command", "-l"],
        ["dm-tool", "lock"],
        ["light-locker-command", "--lock"],
    ):
        if shutil.which(cmd[0]):
            code, _ = _run(cmd, timeout=5.0)
            if code == 0:
                return True
    return False


#: Screenshot tools, in order of preference.
_SCREENSHOT_TOOLS = (
    ("gnome-screenshot", ["gnome-screenshot", "-f"]),
    ("spectacle", ["spectacle", "-b", "-n", "-o"]),
    ("scrot", ["scrot"]),
    ("maim", ["maim"]),
    ("import", ["import", "-window", "root"]),
)


def take_screenshot(path: Optional[str] = None) -> Optional[str]:
    """Captures the screen and returns the path of the saved image."""
    if not path:
        from core.platform import pictures_path

        folder = pictures_path()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"Screenshot_{int(time.time())}.png")

    for binary, template in _SCREENSHOT_TOOLS:
        if not shutil.which(binary):
            continue
        cmd = template + [path]
        code, _ = _run(cmd, timeout=20.0)
        if code == 0 and os.path.exists(path):
            return path

    # Last resort: pyautogui grabs the root window through Xlib.
    try:
        import pyautogui

        pyautogui.screenshot(path)
        if os.path.exists(path):
            return path
    except Exception as e:
        logger.debug(f"pyautogui screenshot failed: {e}")
    return None


def open_path(path: str) -> bool:
    """Opens a file or directory with the desktop's default handler."""
    if not os.path.exists(path):
        return False
    try:
        subprocess.Popen(
            ["xdg-open", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.debug(f"open_path failed for '{path}': {e}")
        return False


def open_uri(uri: str) -> bool:
    """Opens a URI (http://, mailto:, tel: …) with the default handler."""
    try:
        subprocess.Popen(
            ["xdg-open", uri],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.debug(f"open_uri failed for '{uri}': {e}")
        return False


def open_url_in_browser(url: str, browser: str) -> bool:
    """Opens a URL in a specific browser binary."""
    binary = shutil.which(browser)
    if not binary:
        return open_uri(url)
    try:
        subprocess.Popen(
            [binary, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.debug(f"open_url_in_browser failed: {e}")
        return open_uri(url)


#: Settings panels, keyed by the friendly name the assistant understands.
SETTINGS_PAGES: Dict[str, str] = {
    "bluetooth": "bluetooth",
    "wifi": "network",
    "wi-fi": "network",
    "network": "network",
    "ethernet": "network",
    "airplane": "network",
    "display": "display",
    "resolution": "display",
    "sound": "sound",
    "volume": "sound",
    "audio": "sound",
    "notifications": "notifications",
    "background": "background",
    "themes": "appearance",
    "appearance": "appearance",
    "colors": "appearance",
    "lock screen": "screen-lock",
    "lockscreen": "screen-lock",
    "privacy": "privacy",
    "camera": "privacy",
    "webcam": "privacy",
    "microphone": "privacy",
    "mic": "privacy",
    "apps": "applications",
    "default apps": "default-applications",
    "accounts": "user-accounts",
    "sign in": "user-accounts",
    "time": "datetime",
    "date": "datetime",
    "language": "language",
    "gaming": "applications",
    "storage": "storage",
    "battery": "power",
    "power": "power",
    "troubleshoot": "diagnostics",
    "device": "bluetooth",
    "devices": "bluetooth",
    "mouse": "mouse",
    "keyboard": "keyboard",
    "update": "software-updates",
    "system": "system",
    "about": "system",
}

#: Settings application candidates, per desktop environment.
_SETTINGS_APPS = (
    ("gnome-control-center", ["gnome-control-center"]),
    ("systemsettings", ["systemsettings"]),
    ("plasma-systemsettings", ["systemsettings5", "systemsettings"]),
    ("mate-control-center", ["mate-control-center"]),
    ("cinnamon-settings", ["cinnamon-settings"]),
    ("xfce4-settings-manager", ["xfce4-settings-manager"]),
)


def open_settings(page: str = "") -> bool:
    """Opens the desktop settings application on the requested panel."""
    clean = (page or "").lower().strip(" .!?,_-")
    panel = SETTINGS_PAGES.get(clean, clean.replace(" ", "-"))

    for binary, args in _SETTINGS_APPS:
        if not shutil.which(binary):
            continue
        try:
            subprocess.Popen(
                [binary, *args[1:], panel] if len(args) > 1 else [binary, panel],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception as e:
            logger.debug(f"open_settings failed with '{binary}': {e}")

    # Some panels have no dedicated tool — open the control centre itself.
    if shutil.which("gnome-control-center"):
        try:
            subprocess.Popen(
                ["gnome-control-center"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            pass
    return False


def kill_process(name: str) -> bool:
    """Terminates a running application by process name."""
    target = name.replace(".exe", "").strip()
    if not target:
        return False
    if shutil.which("pkill"):
        code, _ = _run(["pkill", "-f", target], timeout=5.0)
        if code == 0:
            return True
    if shutil.which("killall"):
        code, _ = _run(["killall", target], timeout=5.0)
        if code == 0:
            return True
    return False


def launch_app(name: str) -> bool:
    """Launches a desktop application by its name."""
    from core.apps import app_index

    return app_index.launch((name or "").strip())



def clipboard_get_text() -> str:
    """Returns the current clipboard text (empty when unavailable)."""
    for binary, args in (
        ("wl-paste", ["wl-paste", "--no-newline"]),
        ("xclip", ["xclip", "-selection", "clipboard", "-o"]),
        ("xsel", ["xsel", "--clipboard", "--output"]),
    ):
        if not shutil.which(binary):
            continue
        code, out = _run(list(args), timeout=3.0)
        if code == 0:
            return out
    return ""

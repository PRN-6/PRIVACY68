"""
PRIVACY68 Platform Abstraction Layer.

Every operating-system interaction in PRIVACY68 goes through this package.
The rest of the codebase asks questions like "what is the active window?" or
"open this path" without needing to know whether it is talking to Win32,
X11/Wayland, or macOS.

The layer is split in two:

  * `core.platform.common`  — code that is genuinely identical everywhere
    (path resolution, special folders, process discovery helpers).
  * `core.platform.<os>`    — one backend per operating system, each
    implementing the same small set of functions:

        list_windows()              -> list of window dicts
        get_active_window()         -> window dict
        find_window(query)          -> handle (int) or 0
        focus_window(target)        -> bool
        maximize/minimize/restore/close_window(target) -> bool
        volume_up/down/mute()       -> bool
        lock_screen()               -> bool
        take_screenshot(path)       -> path or None
        open_path(path)             -> bool
        open_uri(uri)               -> bool
        open_settings(page)         -> bool
        kill_process(name)          -> bool
        launch_app(name)            -> bool
        clipboard_get_text()        -> str

`IS_WINDOWS`, `IS_LINUX` and `IS_MACOS` are the flags the rest of the code
uses to branch, and `get_backend()` resolves the active implementation.
"""

import logging
import os
import shutil
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PRIVACY68.Platform")

# ─────────────────────────────────────────────────────────────────────────────
# Platform detection
# ─────────────────────────────────────────────────────────────────────────────
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
IS_POSIX = not IS_WINDOWS

if IS_WINDOWS:
    OS_NAME = "Windows"
    PLATFORM_ID = "windows"
elif IS_LINUX:
    OS_NAME = "Linux"
    PLATFORM_ID = "linux"
elif IS_MACOS:
    OS_NAME = "macOS"
    PLATFORM_ID = "macos"
else:
    OS_NAME = "Unknown"
    PLATFORM_ID = "unknown"

#: Human readable summary used in logs and in the Control Center diagnostics.
PLATFORM_SUMMARY = f"{OS_NAME} ({sys.platform})"

_backend = None


def get_backend():
    """Returns the backend module for the current operating system."""
    global _backend
    if _backend is not None:
        return _backend
    if IS_WINDOWS:
        from core.platform import windows as backend
    elif IS_LINUX:
        from core.platform import linux as backend
    elif IS_MACOS:
        from core.platform import macos as backend
    else:
        from core.platform import generic as backend
    _backend = backend
    return backend


# ─────────────────────────────────────────────────────────────────────────────
# Portable locations
# ─────────────────────────────────────────────────────────────────────────────
def app_data_dir() -> str:
    """
    Returns the per-user writable directory PRIVACY68 stores its log,
    plugins and configuration in.

    Windows uses %APPDATA%, macOS uses ~/Library/Application Support and
    Linux follows the XDG base directory specification.
    """
    if IS_WINDOWS:
        base = os.getenv("APPDATA") or os.path.expanduser("~")
    elif IS_MACOS:
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
    path = os.path.join(base, "PRIVACY68")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:  # pragma: no cover - unwritable home directory
        logger.warning(f"Could not create app data directory '{path}': {e}")
    return path


def shell_folders() -> Dict[str, str]:
    """
    Returns the user's well-known folders (desktop, documents, downloads …).

    The Windows implementation resolves the real locations from the registry
    so that OneDrive redirection is honoured; the POSIX implementations use
    the XDG user directories with sensible fallbacks.
    """
    if IS_WINDOWS:
        from core.platform.windows import get_shell_folders as _impl
    elif IS_MACOS:
        from core.platform.macos import get_shell_folders as _impl
    else:
        from core.platform.linux import get_shell_folders as _impl
    return _impl()


def desktop_path() -> str:
    return shell_folders().get("desktop", os.path.join(os.path.expanduser("~"), "Desktop"))


def documents_path() -> str:
    return shell_folders().get("documents", os.path.join(os.path.expanduser("~"), "Documents"))


def downloads_path() -> str:
    return shell_folders().get("downloads", os.path.join(os.path.expanduser("~"), "Downloads"))


def pictures_path() -> str:
    return shell_folders().get("pictures", os.path.join(os.path.expanduser("~"), "Pictures"))


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch helpers — thin wrappers around the active backend
# ─────────────────────────────────────────────────────────────────────────────
def list_windows() -> List[Dict[str, Any]]:
    return get_backend().list_windows()


def get_active_window() -> Dict[str, Any]:
    return get_backend().get_active_window()


def find_window(query: str) -> int:
    return get_backend().find_window(query)


def focus_window(target: Any) -> bool:
    return get_backend().focus_window(target)


def maximize_window(target: Any = None) -> bool:
    return get_backend().maximize_window(target)


def minimize_window(target: Any = None) -> bool:
    return get_backend().minimize_window(target)


def restore_window(target: Any = None) -> bool:
    return get_backend().restore_window(target)


def close_window(target: Any = None) -> bool:
    return get_backend().close_window(target)


def volume_up() -> bool:
    return get_backend().volume_up()


def volume_down() -> bool:
    return get_backend().volume_down()


def volume_mute() -> bool:
    return get_backend().volume_mute()


def lock_screen() -> bool:
    return get_backend().lock_screen()


def take_screenshot(path: Optional[str] = None) -> Optional[str]:
    return get_backend().take_screenshot(path)


def open_path(path: str) -> bool:
    return get_backend().open_path(path)


def open_uri(uri: str) -> bool:
    return get_backend().open_uri(uri)


def open_settings(page: str = "") -> bool:
    return get_backend().open_settings(page)


def kill_process(name: str) -> bool:
    return get_backend().kill_process(name)


def launch_app(name: str) -> bool:
    return get_backend().launch_app(name)


def clipboard_get_text() -> str:
    return get_backend().clipboard_get_text()


def open_url(url: str, browser: Optional[str] = None) -> bool:
    """
    Opens a URL in the given browser (or the system default).

    On Windows the browser is started through `start`; on Linux we prefer an
    already running instance so the URL opens in the window the user is
    already looking at instead of spawning a new browser process.
    """
    backend = get_backend()
    if browser:
        return backend.open_url_in_browser(url, browser)
    return backend.open_uri(url)


# ─────────────────────────────────────────────────────────────────────────────
# Generic helpers shared by the backends
# ─────────────────────────────────────────────────────────────────────────────
def which(binary: str) -> Optional[str]:
    """Returns the absolute path of an executable, or None when absent."""
    return shutil.which(binary)


def has_binary(binary: str) -> bool:
    """True when the given executable is on PATH."""
    return shutil.which(binary) is not None


def run_detached(cmd: List[str], shell: bool = False) -> bool:
    """
    Starts a process without blocking and without a console window.

    Used for "open this app" style commands. Returns True when the process
    could be started.
    """
    import subprocess

    kwargs: Dict[str, Any] = {"shell": shell}
    if IS_WINDOWS:
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        # Detach from the controlling terminal so the app survives the
        # assistant exiting, and keep stdio out of our log.
        kwargs["start_new_session"] = True
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    try:
        subprocess.Popen(cmd, **kwargs)
        return True
    except Exception as e:
        logger.debug(f"run_detached failed for {cmd}: {e}")
        return False


def os_release() -> str:
    """Returns a short description of the Linux distribution, if any."""
    if not IS_LINUX:
        return ""
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as handle:
            fields = {}
            for line in handle:
                if "=" in line:
                    key, _, value = line.partition("=")
                    fields[key.strip()] = value.strip().strip('"')
        return fields.get("PRETTY_NAME", "") or fields.get("NAME", "")
    except OSError:
        return ""


def desktop_environment() -> str:
    """
    Returns the running desktop environment (gnome, kde, xfce, sway …).

    Used to pick the right settings application and screenshot tool.
    """
    if IS_MACOS:
        return "macos"
    if IS_WINDOWS:
        return "windows"
    xdg = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
    if xdg:
        return xdg.split(":")[0]
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return ""


def has_display() -> bool:
    """True when a graphical session is available."""
    if IS_WINDOWS or IS_MACOS:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


__all__ = [
    "IS_WINDOWS",
    "IS_LINUX",
    "IS_MACOS",
    "IS_POSIX",
    "OS_NAME",
    "PLATFORM_ID",
    "PLATFORM_SUMMARY",
    "get_backend",
    "app_data_dir",
    "shell_folders",
    "desktop_path",
    "documents_path",
    "downloads_path",
    "pictures_path",
    "list_windows",
    "get_active_window",
    "find_window",
    "focus_window",
    "maximize_window",
    "minimize_window",
    "restore_window",
    "close_window",
    "volume_up",
    "volume_down",
    "volume_mute",
    "lock_screen",
    "take_screenshot",
    "open_path",
    "open_uri",
    "open_settings",
    "open_url",
    "kill_process",
    "launch_app",
    "clipboard_get_text",
    "which",
    "has_binary",
    "run_detached",
    "os_release",
    "desktop_environment",
    "has_display",
]

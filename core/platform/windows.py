"""
Windows backend for the PRIVACY68 platform layer.

Wraps the Win32 API (ctypes) plus the handful of shell commands Windows
needs (`start`, `taskkill`, `ms-settings:`). This module is imported lazily
by `core.platform`, so on Linux it never touches `ctypes.windll`.
"""

import ctypes
import logging
import os
import subprocess
import time
from ctypes import wintypes
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PRIVACY68.Platform.Windows")

# ─────────────────────────────────────────────────────────────────────────────
# Win32 bindings
# ─────────────────────────────────────────────────────────────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

# Show command constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

# Background surfaces that are never useful as an "active app".
_IGNORED_CLASSES = ("Progman", "Shell_TrayWnd", "WorkerD", "Windows.UI.Core.CoreWindow")

#: Process-name / window-title rules used to resolve an app name to a window.
APP_RULES: Dict[str, Dict[str, List[str]]] = {
    "chrome": {"processes": ["chrome.exe"], "titles": ["google chrome", "chrome"]},
    "google chrome": {"processes": ["chrome.exe"], "titles": ["google chrome"]},
    "brave": {"processes": ["brave.exe"], "titles": ["brave"]},
    "brave browser": {"processes": ["brave.exe"], "titles": ["brave"]},
    "edge": {"processes": ["msedge.exe"], "titles": ["microsoft edge", "edge"]},
    "msedge": {"processes": ["msedge.exe"], "titles": ["microsoft edge", "edge"]},
    "firefox": {"processes": ["firefox.exe"], "titles": ["mozilla firefox", "firefox"]},
    "vs code": {"processes": ["code.exe"], "titles": ["visual studio code"]},
    "vscode": {"processes": ["code.exe"], "titles": ["visual studio code"]},
    "visual studio code": {"processes": ["code.exe"], "titles": ["visual studio code"]},
    "code": {"processes": ["code.exe"], "titles": ["visual studio code"]},
    "task manager": {"processes": ["taskmgr.exe"], "titles": ["task manager"]},
    "taskmanager": {"processes": ["taskmgr.exe"], "titles": ["task manager"]},
    "calculator": {"processes": ["calculatorapp.exe", "calculator.exe"], "titles": ["calculator"]},
    "notepad": {"processes": ["notepad.exe"], "titles": ["notepad"]},
    "paint": {"processes": ["mspaint.exe", "paint.exe"], "titles": ["paint"]},
    "terminal": {
        "processes": ["windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe"],
        "titles": ["terminal", "powershell", "command prompt"],
    },
    "file explorer": {
        "processes": ["explorer.exe"],
        "classes": ["cabinetwclass", "explorewclass"],
        "titles": ["file explorer"],
    },
    "explorer": {
        "processes": ["explorer.exe"],
        "classes": ["cabinetwclass", "explorewclass"],
        "titles": ["file explorer"],
    },
    "spotify": {"processes": ["spotify.exe"], "titles": ["spotify"]},
    "discord": {"processes": ["discord.exe"], "titles": ["discord"]},
    "whatsapp": {"processes": ["whatsapp.exe", "whatsapp.root.exe"], "titles": ["whatsapp"]},
    "antigravity": {"processes": ["antigravity ide.exe", "antigravity.exe"], "titles": ["antigravity"]},
    "antigravity ide": {"processes": ["antigravity ide.exe", "antigravity.exe"], "titles": ["antigravity"]},
    "cursor": {"processes": ["cursor.exe"], "titles": ["cursor"]},
    "windsurf": {"processes": ["windsurf.exe"], "titles": ["windsurf"]},
    "pycharm": {"processes": ["pycharm64.exe", "pycharm.exe"], "titles": ["pycharm"]},
    "intellij": {"processes": ["idea64.exe", "idea.exe"], "titles": ["intellij"]},
}


# ─────────────────────────────────────────────────────────────────────────────
# Special folders
# ─────────────────────────────────────────────────────────────────────────────
def get_shell_folders() -> Dict[str, str]:
    """
    Resolves the real Windows special folders from the User Shell Folders
    registry, honouring OneDrive redirection and relocated user folders.
    """
    folders = {
        "desktop": os.path.expanduser("~/Desktop"),
        "documents": os.path.expanduser("~/Documents"),
        "downloads": os.path.expanduser("~/Downloads"),
        "pictures": os.path.expanduser("~/Pictures"),
        "images": os.path.expanduser("~/Pictures"),
        "music": os.path.expanduser("~/Music"),
        "videos": os.path.expanduser("~/Videos"),
        "home": os.path.expanduser("~"),
        "user": os.path.expanduser("~"),
    }
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            reg_map = {
                "Desktop": ["desktop"],
                "Personal": ["documents"],
                "{374DE290-123F-4565-9164-39C4925E467B}": ["downloads"],
                "{7D83EE9B-2244-4E70-B1F5-5393042AF1E4}": ["downloads"],
                "My Pictures": ["pictures", "images"],
                "My Music": ["music"],
                "My Video": ["videos"],
            }
            for reg_name, aliases in reg_map.items():
                try:
                    val, _ = winreg.QueryValueEx(key, reg_name)
                    expanded = os.path.expandvars(val)
                    if os.path.exists(expanded):
                        for alias in aliases:
                            folders[alias] = expanded
                except OSError:
                    continue
    except Exception as e:
        logger.debug(f"get_shell_folders: {e}")
    return folders


# ─────────────────────────────────────────────────────────────────────────────
# Window management
# ─────────────────────────────────────────────────────────────────────────────
def get_window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value.strip()
    return ""


def get_window_class(hwnd: int) -> str:
    if not hwnd:
        return ""
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value.strip()


def get_process_name_for_hwnd(hwnd: int) -> str:
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if h_proc:
        try:
            buff = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buff, ctypes.byref(size)):
                return os.path.basename(buff.value)
        finally:
            kernel32.CloseHandle(h_proc)
    return ""


def list_windows() -> List[Dict[str, Any]]:
    """Lists all visible top-level application windows on the desktop."""
    windows: List[Dict[str, Any]] = []

    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd)
            if title:
                cls = get_window_class(hwnd)
                if cls not in _IGNORED_CLASSES:
                    windows.append(
                        {
                            "hwnd": hwnd,
                            "title": title,
                            "process_name": get_process_name_for_hwnd(hwnd),
                            "class_name": cls,
                        }
                    )
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return windows


def get_active_window() -> Dict[str, Any]:
    hwnd = user32.GetForegroundWindow() or 0
    if not hwnd:
        return {"hwnd": 0, "title": "", "process_name": "", "class_name": "", "is_active": False}
    return {
        "hwnd": hwnd,
        "title": get_window_title(hwnd),
        "process_name": get_process_name_for_hwnd(hwnd),
        "class_name": get_window_class(hwnd),
        "is_active": True,
        "is_iconic": bool(user32.IsIconic(hwnd)),
        "is_zoomed": bool(user32.IsZoomed(hwnd)),
    }


def find_window(query: str) -> int:
    """Finds a window by process name, window title or direct title lookup."""
    if not query:
        return 0
    q = query.lower().strip()

    visible = list_windows()
    if q in APP_RULES:
        rule = APP_RULES[q]
        procs = [p.lower() for p in rule.get("processes", [])]
        titles = [t.lower() for t in rule.get("titles", [])]
        classes = [c.lower() for c in rule.get("classes", [])]

        for win in visible:
            p = str(win.get("process_name", "")).lower()
            t = str(win.get("title", "")).lower()
            c = str(win.get("class_name", "")).lower()

            if procs and p in procs:
                if classes:
                    if c in classes:
                        return int(win["hwnd"])
                else:
                    return int(win["hwnd"])

            if titles and any(term in t for term in titles):
                if classes and c not in classes:
                    continue
                return int(win["hwnd"])

    for term in [query, q.capitalize(), q.title()]:
        h = user32.FindWindowW(None, term)
        if h and user32.IsWindow(h):
            return int(h)
        h_uwp = user32.FindWindowW("ApplicationFrameWindow", term)
        if h_uwp and user32.IsWindow(h_uwp):
            return int(h_uwp)

    for win in visible:
        t = str(win.get("title", "")).lower()
        p = str(win.get("process_name", "")).lower()
        p_base = os.path.splitext(p)[0]
        if q == p or q == p_base or q in t:
            return int(win["hwnd"])

    return 0


def focus_window(target: Any) -> bool:
    """Brings the targeted window to the foreground, restoring it if needed."""
    hwnd = target if isinstance(target, int) else find_window(str(target))
    if not hwnd or not user32.IsWindow(hwnd):
        logger.warning(f"Windows backend: cannot focus window '{target}'.")
        return False

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        curr_thread = kernel32.GetCurrentThreadId()
        fg_hwnd = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

        if fg_thread and fg_thread != curr_thread:
            user32.AttachThreadInput(curr_thread, fg_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.AttachThreadInput(curr_thread, fg_thread, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)

        time.sleep(0.08)
        return True
    except Exception as e:
        logger.error(f"Windows backend: error focusing hwnd {hwnd}: {e}")
        return False


def _resolve_hwnd(target: Any) -> int:
    if target is None:
        return user32.GetForegroundWindow() or 0
    if isinstance(target, int):
        return target
    return find_window(str(target))


def maximize_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return True
    return False


def minimize_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd:
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        return True
    return False


def restore_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if hwnd:
        user32.ShowWindow(hwnd, SW_RESTORE)
        return True
    return False


def close_window(target: Any = None) -> bool:
    hwnd = _resolve_hwnd(target)
    if not hwnd:
        return False
    WM_CLOSE = 0x0010
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.1)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Audio, screen, session
# ─────────────────────────────────────────────────────────────────────────────
def _press_volume_key(key: str, times: int = 5) -> bool:
    try:
        import pyautogui

        pyautogui.FAILSAFE = False
        for _ in range(times):
            pyautogui.press(key)
        return True
    except Exception as e:
        logger.debug(f"volume key '{key}' failed: {e}")
        return False


def volume_up() -> bool:
    return _press_volume_key("volumeup")


def volume_down() -> bool:
    return _press_volume_key("volumedown")


def volume_mute() -> bool:
    return _press_volume_key("volumemute", times=1)


def lock_screen() -> bool:
    try:
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception as e:
        logger.debug(f"LockWorkStation failed: {e}")
        return False


def take_screenshot(path: Optional[str] = None) -> Optional[str]:
    import time

    if not path:
        from core.platform import pictures_path

        folder = pictures_path()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"Screenshot_{int(time.time())}.png")
    try:
        import pyautogui

        pyautogui.screenshot(path)
        return path
    except Exception as e:
        logger.error(f"take_screenshot failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Shell integration
# ─────────────────────────────────────────────────────────────────────────────
def open_path(path: str) -> bool:
    try:
        os.startfile(path)  # noqa: S606 - Windows shell API
        return True
    except Exception as e:
        logger.debug(f"open_path failed for '{path}': {e}")
        return False


def open_uri(uri: str) -> bool:
    try:
        subprocess.Popen(f'start "" "{uri}"', shell=True)
        return True
    except Exception as e:
        logger.debug(f"open_uri failed for '{uri}': {e}")
        return False


def open_url_in_browser(url: str, browser: str) -> bool:
    try:
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return True
    except Exception as e:
        logger.debug(f"open_url_in_browser failed: {e}")
        return False


#: Settings panels keyed by the friendly name the assistant understands.
SETTINGS_PAGES: Dict[str, str] = {
    "bluetooth": "bluetooth",
    "wifi": "network-wifi",
    "wi-fi": "network-wifi",
    "network": "network",
    "ethernet": "network-ethernet",
    "airplane": "network-airplanemode",
    "display": "display",
    "resolution": "display",
    "sound": "sound",
    "volume": "sound",
    "audio": "sound",
    "notifications": "notifications",
    "background": "personalization-background",
    "themes": "themes",
    "colors": "colors",
    "lock screen": "lockscreen",
    "lockscreen": "lockscreen",
    "privacy": "privacy",
    "camera": "privacy-webcam",
    "webcam": "privacy-webcam",
    "microphone": "privacy-microphone",
    "mic": "privacy-microphone",
    "apps": "appsfeatures",
    "default apps": "defaultapps",
    "accounts": "accounts",
    "sign in": "signinoptions",
    "time": "dateandtime",
    "date": "dateandtime",
    "language": "regionlanguage",
    "storage": "storagesense",
    "battery": "batterysaver",
    "power": "powersleep",
    "troubleshoot": "troubleshoot",
    "device": "bluetooth",
    "devices": "connecteddevices",
    "mouse": "mousetouchpad",
    "keyboard": "devices-typing",
    "windows update": "windowsupdate",
    "update": "windowsupdate",
    "system": "system",
    "about": "about",
}


def open_settings(page: str = "") -> bool:
    """Opens the Windows Settings application on the requested panel."""
    clean = (page or "").lower().strip(" .!?,_-")
    if not clean or clean in ("settings", "windows settings", "system settings", "settings app"):
        return open_uri("ms-settings:")

    panel = SETTINGS_PAGES.get(clean, clean.replace(" ", "-"))
    return open_uri(f"ms-settings:{panel}")


def kill_process(name: str) -> bool:
    """Terminates an application process and its child tree."""
    try:
        target = name if "*" in name else (name if name.lower().endswith(".exe") else f"{name}*")
        subprocess.Popen(
            f'taskkill /F /T /IM "{target}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        try:
            name_clean = name.replace(".exe", "").replace("*", "")
            subprocess.Popen(
                f'powershell -Command "Stop-Process -Name {name_clean}* -Force -ErrorAction SilentlyContinue"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            logger.error(f"kill_process failed for '{name}': {e}")
            return False


def launch_app(name: str) -> bool:
    """Launches an application through the Windows shell."""
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True)
        return True
    except Exception as e:
        logger.debug(f"launch_app failed for '{name}': {e}")
        return False


def clipboard_get_text() -> str:
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        logger.debug(f"clipboard_get_text failed: {e}")
    return ""

"""
PRIVACY68 Context & Active State Inspector.

Provides situational awareness of the current desktop state:
  - Active foreground window, process name, and window title
  - Resolution of contextual references ("this window", "this app", "current file")
  - System performance diagnostics (CPU / RAM hogs, battery status)
  - Native Win32 / ctypes clipboard inspection without external dependencies

The Win32 bindings are only available on Windows. On other platforms the
module still imports and the cross-platform implementations from
`core.platform` are used instead.
"""

import ctypes
import logging
from typing import Any, Dict, List, Optional

from core.platform import IS_WINDOWS

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    wintypes = None
    user32 = None
    kernel32 = None

logger = logging.getLogger("PRIVACY68.ContextInspector")

try:
    import psutil
except ImportError:
    psutil = None

try:
    import win32clipboard
except ImportError:
    win32clipboard = None


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong),
    ]


def _read_battery_sysfs() -> Dict[str, Any]:
    """
    Reads the battery state from /sys/class/power_supply (Linux).

    Returns the same shape as the Win32 implementation so the rest of the
    code does not need to know which platform produced it.
    """
    import os

    base = "/sys/class/power_supply"
    percent = None
    ac_online = False
    has_battery = False
    try:
        for entry in os.listdir(base):
            path = os.path.join(base, entry)
            cap_file = os.path.join(path, "capacity")
            if os.path.exists(cap_file):
                has_battery = True
                try:
                    with open(cap_file, "r", encoding="utf-8") as handle:
                        percent = int(handle.read().strip())
                except (OSError, ValueError):
                    percent = None
            online_file = os.path.join(path, "online")
            if os.path.exists(online_file):
                try:
                    with open(online_file, "r", encoding="utf-8") as handle:
                        ac_online = handle.read().strip() == "1"
                except OSError:
                    pass
    except OSError:
        pass

    if has_battery and percent is not None:
        return {
            "has_battery": True,
            "percent": percent,
            "power_plugged": ac_online,
            "message": f"Battery is at {percent}% ({'Plugged in / Charging' if ac_online else 'On battery'}).",
        }
    return {"has_battery": False, "message": "Desktop computer (AC mains power)."}


class ContextInspector:
    """
    Inspects and retains dynamic OS context for context-aware voice commands.
    """

    def __init__(self):
        self._last_mentioned_app: Optional[str] = None
        self._last_created_path: Optional[str] = None

    def get_foreground_window_info(self) -> Dict[str, Any]:
        """Returns details about the currently active foreground window."""
        if not IS_WINDOWS:
            from computer_use.window_manager import window_manager

            active = window_manager.get_active_window()
            return {
                "hwnd": int(active.get("hwnd", 0) or 0),
                "title": active.get("title", ""),
                "process_name": active.get("process_name", ""),
                "pid": 0,
            }

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "", "process_name": "", "pid": 0}

        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        proc_name = ""
        if psutil:
            try:
                p = psutil.Process(pid.value)
                proc_name = p.name()
            except Exception as e:
                logger.debug(f"get_foreground_window_info: {e}")

        return {
            "hwnd": hwnd,
            "title": title,
            "process_name": proc_name,
            "pid": pid.value,
        }

    def resolve_contextual_target(self, text: str) -> Optional[str]:
        """
        Resolves terms like 'this app', 'this window', 'current window'
        to the actual foreground process/window name.
        """
        lower = text.lower()
        if any(term in lower for term in ["this app", "this application", "this program", "current app", "current window", "this window", "this"]):
            info = self.get_foreground_window_info()
            if info.get("process_name"):
                return info["process_name"]
            if info.get("title"):
                return info["title"]
        return None

    def get_clipboard_text(self) -> str:
        """Safely reads plaintext from the system clipboard."""
        if not IS_WINDOWS:
            from core.platform import clipboard_get_text

            return clipboard_get_text()

        if win32clipboard:
            try:
                win32clipboard.OpenClipboard()
                data = ""
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            except Exception as e:
                logger.debug(f"get_clipboard_text: {e}")

        # Native ctypes fallback
        CF_UNICODETEXT = 13
        if user32.OpenClipboard(0):
            try:
                h_clip = user32.GetClipboardData(CF_UNICODETEXT)
                if h_clip:
                    kernel32.GlobalLock.restype = ctypes.c_void_p
                    p_data = kernel32.GlobalLock(h_clip)
                    if p_data:
                        text = ctypes.wstring_at(p_data)
                        kernel32.GlobalUnlock(h_clip)
                        return text
            finally:
                user32.CloseClipboard()
        return ""

    def get_top_resource_consumers(self, count: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """Identifies processes consuming the highest CPU and RAM."""
        if psutil:
            try:
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
                    try:
                        info = p.info
                        if info['name'] and info['name'].lower() not in ['system idle process', 'system']:
                            procs.append(info)
                    except Exception as e:
                        logger.debug(f"get_top_resource_consumers: {e}")

                top_cpu = sorted(procs, key=lambda x: x.get('cpu_percent') or 0, reverse=True)[:count]
                top_ram = sorted(procs, key=lambda x: (x.get('memory_info').rss if x.get('memory_info') else 0), reverse=True)[:count]

                return {
                    "top_cpu": [{"name": p['name'], "pid": p['pid'], "cpu": p.get('cpu_percent')} for p in top_cpu],
                    "top_ram": [{"name": p['name'], "pid": p['pid'], "ram_mb": round((p.get('memory_info').rss / (1024 * 1024)), 1) if p.get('memory_info') else 0} for p in top_ram]
                }
            except Exception as e:
                logger.error(f"[CONTEXT] Error getting resource consumers: {e}")

        return {"top_cpu": [], "top_ram": []}

    def get_battery_and_power_info(self) -> Dict[str, Any]:
        """Returns battery percentage, plugged status, and time remaining."""
        if not IS_WINDOWS:
            return _read_battery_sysfs()

        status = SYSTEM_POWER_STATUS()
        if kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            percent = status.BatteryLifePercent
            ac_online = (status.ACLineStatus == 1)
            if percent <= 100:
                return {
                    "has_battery": True,
                    "percent": percent,
                    "power_plugged": ac_online,
                    "message": f"Battery is at {percent}% ({'Plugged in / Charging' if ac_online else 'On battery'})."
                }
        return {"has_battery": False, "message": "Desktop computer (AC mains power)."}

    def remember_created_path(self, path: str):
        self._last_created_path = path

    def get_last_created_path(self) -> Optional[str]:
        return self._last_created_path


# Global singleton instance
context_inspector = ContextInspector()

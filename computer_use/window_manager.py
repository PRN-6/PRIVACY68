import ctypes
from ctypes import wintypes
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Union

logger = logging.getLogger("PRIVACY68.ComputerUse.WindowManager")
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

# Virtual key & show command constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

VK_MENU = 0x12
VK_F4 = 0x73
KEYEVENTF_KEYUP = 0x0002


class WindowManager:
    """
    Windows native Window Manager.
    Provides robust window state control (focus, restore, minimize, maximize, close,
    enumeration, title inspection, and process resolution) using Win32 APIs.
    """

    @staticmethod
    def get_active_hwnd() -> int:
        """Returns the HWND of the current foreground window."""
        return user32.GetForegroundWindow() or 0

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Returns the window title of a given HWND."""
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value.strip()
        return ""

    @staticmethod
    def get_window_class(hwnd: int) -> str:
        """Returns the Win32 window class name for a given HWND."""
        if not hwnd:
            return ""
        buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buff, 256)
        return buff.value.strip()

    @staticmethod
    def get_process_name_for_hwnd(hwnd: int) -> str:
        """Returns the executable process name associated with an HWND."""
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        # Query process image name via OpenProcess
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

    def get_active_window(self) -> Dict[str, Union[int, str, bool]]:
        """Returns rich metadata for the currently active foreground window."""
        hwnd = self.get_active_hwnd()
        if not hwnd:
            return {
                "hwnd": 0,
                "title": "",
                "process_name": "",
                "class_name": "",
                "is_active": False,
            }

        return {
            "hwnd": hwnd,
            "title": self.get_window_title(hwnd),
            "process_name": self.get_process_name_for_hwnd(hwnd),
            "class_name": self.get_window_class(hwnd),
            "is_active": True,
            "is_iconic": bool(user32.IsIconic(hwnd)),
            "is_zoomed": bool(user32.IsZoomed(hwnd)),
        }

    def list_visible_windows(self) -> List[Dict[str, Union[int, str]]]:
        """Lists all visible top-level application windows on the desktop."""
        windows = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                title = self.get_window_title(hwnd)
                # Filter out invisible or system utility windows without titles
                if title:
                    cls = self.get_window_class(hwnd)
                    proc = self.get_process_name_for_hwnd(hwnd)
                    # Ignore common system background surfaces (e.g. Program Manager, Windows Shell)
                    if cls not in ("Progman", "Shell_TrayWnd", "WorkerW", "Windows.UI.Core.CoreWindow"):
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "process_name": proc,
                            "class_name": cls,
                        })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return windows

    def find_window(self, query: str) -> int:
        """
        Finds a window by matching its application process name, title, or Win32 top-level lookup.
        Prevents false-positives from shared Chromium/Electron class names.
        """
        if not query:
            return 0
        q = query.lower().strip()

        APP_RULES = {
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
            "terminal": {"processes": ["windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe"], "titles": ["terminal", "powershell", "command prompt"]},
            "file explorer": {"processes": ["explorer.exe"], "classes": ["cabinetwclass", "explorewclass"], "titles": ["file explorer"]},
            "explorer": {"processes": ["explorer.exe"], "classes": ["cabinetwclass", "explorewclass"], "titles": ["file explorer"]},
            "spotify": {"processes": ["spotify.exe"], "titles": ["spotify"]},
            "discord": {"processes": ["discord.exe"], "titles": ["discord"]},
            "whatsapp": {"processes": ["whatsapp.exe"], "titles": ["whatsapp"]},
        }

        # Check visible windows with app rules
        visible = self.list_visible_windows()
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

        # Tier 1 & 2: Direct Win32 Title & UWP Frame Lookups
        for term in [query, q.capitalize(), q.title()]:
            h = user32.FindWindowW(None, term)
            if h and user32.IsWindow(h):
                return int(h)
            h_uwp = user32.FindWindowW("ApplicationFrameWindow", term)
            if h_uwp and user32.IsWindow(h_uwp):
                return int(h_uwp)

        # Tier 3: Substring search on Title and Process Name ONLY (NEVER class name)
        for win in visible:
            t = str(win.get("title", "")).lower()
            p = str(win.get("process_name", "")).lower()
            p_base = os.path.splitext(p)[0]
            if q == p or q == p_base or q in t:
                return int(win["hwnd"])

        return 0

    def is_window_open(self, query: str) -> bool:
        """Checks if a window matching query currently exists."""
        return self.find_window(query) > 0

    def is_window_active(self, query: str) -> bool:
        """Checks if the currently focused window matches the query."""
        active = self.get_active_window()
        if not active.get("hwnd"):
            return False
        q = query.lower().strip()
        t = str(active.get("title", "")).lower()
        p = str(active.get("process_name", "")).lower()
        return q in t or q in p

    def focus_window(self, target: Union[int, str]) -> bool:
        """
        Brings the targeted window to the foreground, restoring it if minimized.
        Accepts an HWND integer or title/app name string.
        """
        hwnd = target if isinstance(target, int) else self.find_window(str(target))
        if not hwnd or not user32.IsWindow(hwnd):
            logger.warning(f"WindowManager: Cannot focus window '{target}' (hwnd not found).")
            return False

        try:
            # Restore if minimized
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                user32.ShowWindow(hwnd, SW_SHOW)

            # Bring to foreground with input attachment if necessary
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
            logger.error(f"WindowManager: Error focusing hwnd {hwnd}: {e}")
            return False

    def maximize_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Maximizes the specified or active window."""
        hwnd = self.get_active_hwnd() if target is None else (target if isinstance(target, int) else self.find_window(str(target)))
        if hwnd:
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            return True
        return False

    def minimize_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Minimizes the specified or active window."""
        hwnd = self.get_active_hwnd() if target is None else (target if isinstance(target, int) else self.find_window(str(target)))
        if hwnd:
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            return True
        return False

    def restore_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Restores the specified or active window to its normal geometry."""
        hwnd = self.get_active_hwnd() if target is None else (target if isinstance(target, int) else self.find_window(str(target)))
        if hwnd:
            user32.ShowWindow(hwnd, SW_RESTORE)
            return True
        return False

    def close_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Closes the specified or active window via WM_CLOSE / Alt+F4."""
        hwnd = self.get_active_hwnd() if target is None else (target if isinstance(target, int) else self.find_window(str(target)))
        if not hwnd:
            return False

        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        time.sleep(0.1)
        return True


window_manager = WindowManager()

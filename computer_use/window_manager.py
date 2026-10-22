"""
Cross-platform window manager.

The Win32 implementation now lives in `core.platform.windows`; this module
keeps the historical `WindowManager` API that the rest of the codebase (and
the plugins) call, and forwards every operation to the platform layer so the
same code drives Windows, Linux and macOS.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from core.platform import get_backend

logger = logging.getLogger("PRIVACY68.ComputerUse.WindowManager")


class WindowManager:
    """
    Cross-platform Window Manager.

    Provides robust window state control (focus, restore, minimize, maximize,
    close, enumeration, title inspection and process resolution) using the
    native API of the host operating system.
    """

    # ── Introspection ──────────────────────────────────────────────────────
    @staticmethod
    def get_active_hwnd() -> int:
        """Returns the handle of the current foreground window."""
        return int(get_active_window().get("hwnd", 0) or 0)

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Returns the window title of a given handle."""
        backend = get_backend()
        getter = getattr(backend, "get_window_title", None)
        if getter:
            return getter(hwnd)
        for win in backend.list_windows():
            if int(win.get("hwnd", 0)) == int(hwnd):
                return str(win.get("title", ""))
        return ""

    @staticmethod
    def get_window_class(hwnd: int) -> str:
        """Returns the window class name for a given handle."""
        backend = get_backend()
        getter = getattr(backend, "get_window_class", None)
        if getter:
            return getter(hwnd)
        for win in backend.list_windows():
            if int(win.get("hwnd", 0)) == int(hwnd):
                return str(win.get("class_name", ""))
        return ""

    @staticmethod
    def get_process_name_for_hwnd(hwnd: int) -> str:
        """Returns the executable process name associated with a handle."""
        backend = get_backend()
        getter = getattr(backend, "get_process_name_for_hwnd", None)
        if getter:
            return getter(hwnd)
        for win in backend.list_windows():
            if int(win.get("hwnd", 0)) == int(hwnd):
                return str(win.get("process_name", ""))
        return ""

    def get_active_window(self) -> Dict[str, Union[int, str, bool]]:
        """Returns rich metadata for the currently active foreground window."""
        return get_backend().get_active_window()

    def list_visible_windows(self) -> List[Dict[str, Union[int, str]]]:
        """Lists all visible top-level application windows on the desktop."""
        return get_backend().list_windows()

    # ── Lookup ─────────────────────────────────────────────────────────────
    def find_window(self, query: str) -> int:
        """Finds a window matching an app name, process name or title."""
        return get_backend().find_window(query)

    def is_window_open(self, query: str) -> bool:
        """Checks if a window matching query currently exists."""
        return self.find_window(query) > 0

    def is_window_active(self, query: str) -> bool:
        """Checks if the currently focused window matches the query."""
        active = self.get_active_window()
        if not active.get("hwnd"):
            return False
        q = query.lower().strip()
        title = str(active.get("title", "")).lower()
        process = str(active.get("process_name", "")).lower()
        return q in title or q in process

    # ── State changes ──────────────────────────────────────────────────────
    def focus_window(self, target: Union[int, str]) -> bool:
        """Brings the targeted window to the foreground, restoring it if minimized."""
        return get_backend().focus_window(target)

    def maximize_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Maximizes the specified or active window."""
        return get_backend().maximize_window(target)

    def minimize_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Minimizes the specified or active window."""
        return get_backend().minimize_window(target)

    def restore_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Restores the specified or active window to its normal geometry."""
        return get_backend().restore_window(target)

    def close_window(self, target: Optional[Union[int, str]] = None) -> bool:
        """Closes the specified or active window."""
        return get_backend().close_window(target)


def get_active_window() -> Dict[str, Any]:
    """Module level shortcut for the active window description."""
    return get_backend().get_active_window()


window_manager = WindowManager()

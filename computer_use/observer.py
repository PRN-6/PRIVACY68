import logging
import time
from typing import Any, Dict, List, Optional

from computer_use.window_manager import window_manager
from computer_use.windows_uia import uia_engine

logger = logging.getLogger("PRIVACY68.ComputerUse.Observer")


class DesktopObserver:
    """
    Windows Desktop & Application State Observer.
    Inspects active foreground window, window hierarchy, and accessible UI controls
    using Windows UI Automation.
    """

    def observe(self, inspect_controls: bool = True, max_controls: int = 35) -> Dict[str, Any]:
        """
        Captures the current state of the Windows desktop and foreground window.
        Returns a rich structured state representation.
        """
        active = window_manager.get_active_window()
        hwnd = int(active.get("hwnd", 0))

        elements = []
        if inspect_controls and hwnd:
            try:
                elements = uia_engine.inspect_window_elements(hwnd, max_elements=max_controls)
            except Exception as e:
                logger.debug(f"Observer: Control inspection error: {e}")

        visible_wins = [
            {"title": w["title"], "process_name": w["process_name"], "hwnd": w["hwnd"]}
            for w in window_manager.list_visible_windows()[:10]
        ]

        state = {
            "timestamp": time.time(),
            "active_window": active,
            "visible_windows": visible_wins,
            "elements": elements,
            "elements_count": len(elements),
        }

        return state

    def get_active_elements(self, control_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns visible interactive elements of the active window, optionally filtered by type."""
        active = window_manager.get_active_window()
        hwnd = int(active.get("hwnd", 0))
        if not hwnd:
            return []

        all_elems = uia_engine.inspect_window_elements(hwnd, max_elements=50)
        if not control_type:
            return all_elems

        c_filter = control_type.lower().strip()
        return [e for e in all_elems if c_filter in e.get("control_type", "").lower()]

    def find_active_element(self, name: str, control_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Locates an element by name and optional control type in the active window."""
        elements = self.get_active_elements(control_type=control_type)
        q = name.lower().strip()
        for elem in elements:
            e_name = elem.get("name", "").lower()
            if q == e_name or q in e_name:
                return elem
        return None

    def is_app_active(self, app_name: str) -> bool:
        """Checks whether the specified application or window is currently active."""
        return window_manager.is_window_active(app_name)

    def is_tab_selected(self, tab_name: str) -> bool:
        """Checks if a tab with the specified name is currently selected in the active window."""
        tabs = self.get_active_elements(control_type="TabItem")
        q = tab_name.lower().strip()
        for tab in tabs:
            if q in tab.get("name", "").lower():
                return bool(tab.get("is_selected", False))
        return False


desktop_observer = DesktopObserver()

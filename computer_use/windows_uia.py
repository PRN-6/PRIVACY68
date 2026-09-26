import logging
import time
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("PRIVACY68.ComputerUse.UIA")


class UIElementWrapper:
    """
    Unified wrapper around a Windows UI Automation element (pywinauto / COM).
    Provides safe, high-level interaction methods (click, select, type, inspect).
    """

    def __init__(self, raw_element: Any, name: str = "", control_type: str = "", automation_id: str = ""):
        self.raw = raw_element
        self.name = name or self._extract_name()
        self.control_type = control_type or self._extract_control_type()
        self.automation_id = automation_id or self._extract_automation_id()

    def _extract_name(self) -> str:
        try:
            if hasattr(self.raw, "window_text"):
                return self.raw.window_text()
            if hasattr(self.raw, "name"):
                return str(self.raw.name)
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "name"):
                return str(self.raw.element_info.name)
        except Exception:
            pass
        return ""

    def _extract_control_type(self) -> str:
        try:
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "control_type"):
                return str(self.raw.element_info.control_type)
        except Exception:
            pass
        return ""

    def _extract_automation_id(self) -> str:
        try:
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "automation_id"):
                return str(self.raw.element_info.automation_id)
        except Exception:
            pass
        return ""

    def click(self) -> bool:
        """Invokes or clicks the element safely."""
        logger.info(f"UIA: Clicking element '{self.name}' ({self.control_type})")
        # 1. Try pywinauto invoke pattern (instant, works in background)
        try:
            if hasattr(self.raw, "invoke"):
                self.raw.invoke()
                return True
        except Exception:
            pass

        # 2. Try click_input
        try:
            if hasattr(self.raw, "click_input"):
                self.raw.click_input()
                return True
        except Exception:
            pass

        # 3. Fallback: PyAutoGUI click at element coordinates
        try:
            rect = self.get_rectangle()
            if rect:
                cx = (rect["left"] + rect["right"]) // 2
                cy = (rect["top"] + rect["bottom"]) // 2
                import pyautogui
                pyautogui.click(cx, cy)
                return True
        except Exception as e:
            logger.error(f"UIA: Click failed on '{self.name}': {e}")

        return False

    def double_click(self) -> bool:
        """Double-clicks the element."""
        try:
            if hasattr(self.raw, "double_click_input"):
                self.raw.double_click_input()
                return True
            rect = self.get_rectangle()
            if rect:
                cx = (rect["left"] + rect["right"]) // 2
                cy = (rect["top"] + rect["bottom"]) // 2
                import pyautogui
                pyautogui.doubleClick(cx, cy)
                return True
        except Exception as e:
            logger.error(f"UIA: Double click failed on '{self.name}': {e}")
        return False

    def select(self) -> bool:
        """Selects a TabItem or ListItem via SelectionItemPattern or Click."""
        logger.info(f"UIA: Selecting Tab/Item '{self.name}'")
        try:
            if hasattr(self.raw, "select"):
                self.raw.select()
                return True
        except Exception:
            pass
        return self.click()

    def set_text(self, text: str) -> bool:
        """Sets or types text into an Edit control."""
        logger.info(f"UIA: Setting text on '{self.name}' to '{text}'")
        try:
            if hasattr(self.raw, "set_edit_text"):
                self.raw.set_edit_text(text)
                return True
            if hasattr(self.raw, "type_keys"):
                self.raw.type_keys(text, with_spaces=True)
                return True
        except Exception:
            pass

        # Fallback: click element then type
        try:
            self.click()
            time.sleep(0.05)
            import pyautogui
            pyautogui.write(text, interval=0.01)
            return True
        except Exception as e:
            logger.error(f"UIA: Text entry failed on '{self.name}': {e}")
        return False

    def is_selected(self) -> bool:
        """Checks if a tab or list item is currently selected."""
        try:
            if hasattr(self.raw, "is_selected"):
                return bool(self.raw.is_selected())
            if hasattr(self.raw, "get_toggle_state"):
                return bool(self.raw.get_toggle_state())
        except Exception:
            pass
        return False

    def is_enabled(self) -> bool:
        """Checks if element is enabled."""
        try:
            if hasattr(self.raw, "is_enabled"):
                return bool(self.raw.is_enabled())
        except Exception:
            pass
        return True

    def is_visible(self) -> bool:
        """Checks if element is visible on screen."""
        try:
            if hasattr(self.raw, "is_visible"):
                return bool(self.raw.is_visible())
        except Exception:
            pass
        return True

    def get_rectangle(self) -> Optional[Dict[str, int]]:
        """Returns element bounding box {left, top, right, bottom}."""
        try:
            if hasattr(self.raw, "rectangle"):
                rect = self.raw.rectangle()
                return {
                    "left": int(rect.left),
                    "top": int(rect.top),
                    "right": int(rect.right),
                    "bottom": int(rect.bottom),
                }
        except Exception:
            pass
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes element metadata into a clean inspection dictionary."""
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "is_enabled": self.is_enabled(),
            "is_visible": self.is_visible(),
            "is_selected": self.is_selected(),
            "rectangle": self.get_rectangle(),
        }


class WindowsUIA:
    """
    Windows UI Automation Engine.
    Locates UI controls dynamically in the Windows accessibility tree
    without requiring hardcoded screen coordinates.

    Includes a short-lived TTL cache (default: 2s) for `inspect_window_elements`
    to avoid repeated 200-400ms accessibility tree scans during rapid sequential calls
    (e.g., compound commands, agent multi-step loops).
    """

    # Cache TTL in seconds — elements older than this are re-scanned
    CACHE_TTL: float = 2.0

    def __init__(self):
        self._desktop = None
        self._element_cache: Dict[tuple, tuple] = {}  # (hwnd, max_elements) -> (timestamp, result)
        self._init_backend()

    def _init_backend(self):
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
            logger.info("WindowsUIA: Initialized pywinauto UIA backend.")
        except Exception as e:
            logger.warning(f"WindowsUIA: pywinauto initialization notice: {e}")

    def get_window_element(self, hwnd: int) -> Optional[Any]:
        """Returns the pywinauto UIA window wrapper for an HWND."""
        if not self._desktop or not hwnd:
            return None
        try:
            return self._desktop.window(handle=hwnd)
        except Exception as e:
            logger.debug(f"WindowsUIA: Could not wrap hwnd {hwnd}: {e}")
            return None

    def find_element(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        hwnd: Optional[int] = None,
        exact_match: bool = False,
    ) -> Optional[UIElementWrapper]:
        """
        Finds a single UI element matching criteria in the target window or desktop.
        """
        results = self.find_elements(
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            hwnd=hwnd,
            exact_match=exact_match,
            max_depth=5,
        )
        return results[0] if results else None

    def find_elements(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        hwnd: Optional[int] = None,
        exact_match: bool = False,
        max_depth: int = 5,
    ) -> List[UIElementWrapper]:
        """
        Searches the Windows UIA accessibility tree for elements matching criteria.
        """
        found = []
        if not self._desktop:
            return found

        # If HWND is provided, search inside that specific window; else active window
        target_root = None
        if hwnd:
            target_root = self.get_window_element(hwnd)
        else:
            from computer_use.window_manager import window_manager
            active_hwnd = window_manager.get_active_hwnd()
            if active_hwnd:
                target_root = self.get_window_element(active_hwnd)

        if not target_root:
            target_root = self._desktop

        name_query = (name or "").lower().strip()
        type_query = (control_type or "").lower().strip()
        id_query = (automation_id or "").lower().strip()

        try:
            # Enumerate descendants
            descendants = target_root.descendants()
            for elem in descendants:
                try:
                    info = getattr(elem, "element_info", None)
                    if not info:
                        continue

                    e_name = str(getattr(info, "name", "") or "").strip()
                    e_type = str(getattr(info, "control_type", "") or "").strip()
                    e_id = str(getattr(info, "automation_id", "") or "").strip()

                    # Check control type filter
                    if type_query and type_query not in e_type.lower():
                        continue

                    # Check automation id filter
                    if id_query and id_query != e_id.lower():
                        continue

                    # Check name filter
                    if name_query:
                        if exact_match:
                            if name_query != e_name.lower():
                                continue
                        else:
                            if name_query not in e_name.lower():
                                continue

                    found.append(UIElementWrapper(elem, name=e_name, control_type=e_type, automation_id=e_id))
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"WindowsUIA: Element search encountered: {e}")

        return found

    def invalidate_cache(self, hwnd: Optional[int] = None):
        """Invalidates the element cache for a specific window or all windows."""
        if hwnd is not None:
            keys_to_remove = [k for k in self._element_cache if k[0] == hwnd]
            for k in keys_to_remove:
                del self._element_cache[k]
        else:
            self._element_cache.clear()

    def _prune_stale_cache(self):
        """Removes expired cache entries to prevent memory leaks."""
        now = time.time()
        stale = [k for k, (ts, _) in self._element_cache.items() if now - ts > self.CACHE_TTL * 5]
        for k in stale:
            del self._element_cache[k]

    def inspect_window_elements(self, hwnd: int, max_elements: int = 40) -> List[Dict[str, Any]]:
        """
        Inspects interactive UI controls (buttons, tabs, inputs, menus) of a window.
        Returns a list of serialized element dictionaries for the Observer.

        Uses a short-lived TTL cache to avoid repeated accessibility tree scans
        when the same window is queried multiple times within CACHE_TTL seconds.
        """
        cache_key = (hwnd, max_elements)
        now = time.time()

        # Check cache hit
        if cache_key in self._element_cache:
            cached_ts, cached_result = self._element_cache[cache_key]
            if now - cached_ts < self.CACHE_TTL:
                logger.debug(f"WindowsUIA: Cache HIT for hwnd {hwnd} (age={now - cached_ts:.2f}s)")
                return cached_result

        # Periodic stale cleanup
        self._prune_stale_cache()

        interactive_types = {
            "Button", "TabItem", "Edit", "MenuItem", "CheckBox",
            "RadioButton", "ComboBox", "Hyperlink", "ListItem", "TreeItem"
        }
        elements = []
        win = self.get_window_element(hwnd)
        if not win:
            return elements

        try:
            for elem in win.descendants():
                try:
                    info = getattr(elem, "element_info", None)
                    if not info:
                        continue

                    c_type = str(getattr(info, "control_type", "") or "")
                    name = str(getattr(info, "name", "") or "").strip()

                    if c_type in interactive_types and name:
                        wrapper = UIElementWrapper(elem, name=name, control_type=c_type)
                        elements.append(wrapper.to_dict())
                        if len(elements) >= max_elements:
                            break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"WindowsUIA: Inspection error for hwnd {hwnd}: {e}")

        # Store in cache
        self._element_cache[cache_key] = (now, elements)
        logger.debug(f"WindowsUIA: Cache MISS for hwnd {hwnd} — scanned {len(elements)} elements")

        return elements


uia_engine = WindowsUIA()

import logging
import time
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("PRIVACY68.ComputerUse.UIA")


class UIElementWrapper:
    """
    Unified, full-featured wrapper around a Windows UI Automation element (pywinauto / COM).
    Provides safe, high-level interaction methods covering the full UIA pattern suite:
      - InvokePattern (click, double click)
      - SelectionItemPattern (select tab/item, is_selected)
      - ValuePattern / RangeValuePattern (set_text, set_value for sliders, get_value)
      - TogglePattern (toggle switches/checkboxes, get_toggle_state)
      - ExpandCollapsePattern (expand, collapse, is_expanded)
      - ScrollItemPattern (scroll_into_view)
      - ScrollPattern (scroll up/down/left/right)
      - Focus & Bounding Box Inspection
    """

    def __init__(self, raw_element: Any, name: str = "", control_type: str = "", automation_id: str = ""):
        self.raw = raw_element
        self.name = name or self._extract_name()
        self.control_type = control_type or self._extract_control_type()
        self.automation_id = automation_id or self._extract_automation_id()

    def _extract_name(self) -> str:
        try:
            if hasattr(self.raw, "window_text"):
                t = self.raw.window_text()
                if t:
                    return str(t).strip()
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "name"):
                return str(self.raw.element_info.name or "").strip()
            if hasattr(self.raw, "name"):
                return str(self.raw.name or "").strip()
        except Exception:
            pass
        return ""

    def _extract_control_type(self) -> str:
        try:
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "control_type"):
                return str(self.raw.element_info.control_type or "").strip()
        except Exception:
            pass
        return ""

    def _extract_automation_id(self) -> str:
        try:
            if hasattr(self.raw, "element_info") and hasattr(self.raw.element_info, "automation_id"):
                return str(self.raw.element_info.automation_id or "").strip()
        except Exception:
            pass
        return ""

    # --------------------------------------------------------------------------
    # 1. Click & Invoke Patterns
    # --------------------------------------------------------------------------

    def click(self) -> bool:
        """Invokes or clicks the element safely using a 3-tier fallback."""
        logger.info(f"UIA: Clicking element '{self.name}' ({self.control_type})")
        # 1. Try pywinauto invoke pattern (instant, background-capable)
        try:
            if hasattr(self.raw, "invoke"):
                self.raw.invoke()
                return True
            if hasattr(self.raw, "iface_invoke") and self.raw.iface_invoke:
                self.raw.iface_invoke.Invoke()
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

        # 3. Fallback: PyAutoGUI click at element center coordinates
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

    def right_click(self) -> bool:
        """Right-clicks the element to open its context menu."""
        try:
            if hasattr(self.raw, "right_click_input"):
                self.raw.right_click_input()
                return True
            rect = self.get_rectangle()
            if rect:
                cx = (rect["left"] + rect["right"]) // 2
                cy = (rect["top"] + rect["bottom"]) // 2
                import pyautogui
                pyautogui.rightClick(cx, cy)
                return True
        except Exception as e:
            logger.error(f"UIA: Right click failed on '{self.name}': {e}")
        return False

    # --------------------------------------------------------------------------
    # 2. SelectionItem Pattern (Tabs, ListItems, TreeItems)
    # --------------------------------------------------------------------------

    def select(self) -> bool:
        """Selects a TabItem, ListItem, or RadioButton via SelectionItemPattern or Click."""
        logger.info(f"UIA: Selecting Tab/Item '{self.name}'")
        try:
            if hasattr(self.raw, "select"):
                self.raw.select()
                return True
            if hasattr(self.raw, "iface_selection_item") and self.raw.iface_selection_item:
                self.raw.iface_selection_item.Select()
                return True
        except Exception:
            pass
        return self.click()

    def is_selected(self) -> bool:
        """Checks if a tab, list item, or radio button is currently selected."""
        try:
            if hasattr(self.raw, "is_selected"):
                return bool(self.raw.is_selected())
            if hasattr(self.raw, "iface_selection_item") and self.raw.iface_selection_item:
                return bool(self.raw.iface_selection_item.CurrentIsSelected)
        except Exception:
            pass
        return False

    # --------------------------------------------------------------------------
    # 3. Toggle Pattern (Checkboxes, Switches, WiFi, Bluetooth, Dark Mode)
    # --------------------------------------------------------------------------

    def toggle(self, target_state: Optional[bool] = None) -> bool:
        """
        Toggles a switch, checkbox, or toggle button.
        If `target_state` is provided (True=ON, False=OFF), it only toggles
        if the current state differs from the desired state.
        """
        logger.info(f"UIA: Toggling '{self.name}' (target_state={target_state})")
        current = self.get_toggle_state()
        if target_state is not None and current is not None:
            if current == target_state:
                logger.info(f"UIA: '{self.name}' is already in desired state ({target_state})")
                return True

        # 1. Native UIA Toggle
        try:
            if hasattr(self.raw, "toggle"):
                self.raw.toggle()
                return True
            if hasattr(self.raw, "iface_toggle") and self.raw.iface_toggle:
                self.raw.iface_toggle.Toggle()
                return True
        except Exception:
            pass

        # 2. Fallback: Click the toggle control
        return self.click()

    def get_toggle_state(self) -> Optional[bool]:
        """
        Returns True if ON/checked, False if OFF/unchecked, or None if not a toggle element.
        """
        try:
            if hasattr(self.raw, "iface_toggle") and self.raw.iface_toggle:
                state = self.raw.iface_toggle.CurrentToggleState
                # 0 = Off, 1 = On, 2 = Indeterminate
                if state == 1:
                    return True
                elif state == 0:
                    return False
            if hasattr(self.raw, "get_toggle_state"):
                s = self.raw.get_toggle_state()
                return bool(s == 1 or s is True or str(s).lower() in ("on", "1", "true"))
            if hasattr(self.raw, "is_selected"):
                return bool(self.raw.is_selected())
        except Exception:
            pass
        return None

    # --------------------------------------------------------------------------
    # 4. Value & RangeValue Patterns (Sliders, Volume, Brightness, Inputs)
    # --------------------------------------------------------------------------

    def set_value(self, value: Union[float, int, str]) -> bool:
        """
        Sets the value of a slider, progress bar, spin box, or input field.
        Supports RangeValuePattern (e.g. Volume 0-100) and ValuePattern.
        """
        logger.info(f"UIA: Setting value on '{self.name}' to '{value}'")
        # 1. RangeValue (Sliders)
        try:
            if hasattr(self.raw, "iface_range_value") and self.raw.iface_range_value:
                self.raw.iface_range_value.SetValue(float(value))
                return True
            if hasattr(self.raw, "set_value"):
                self.raw.set_value(float(value))
                return True
        except Exception:
            pass

        # 2. ValuePattern (Text/Edit fields)
        try:
            if hasattr(self.raw, "iface_value") and self.raw.iface_value:
                self.raw.iface_value.SetValue(str(value))
                return True
        except Exception:
            pass

        # 3. Fallback to text input
        return self.set_text(str(value))

    def get_value(self) -> Optional[Union[float, str]]:
        """Reads current value of slider or input field."""
        try:
            if hasattr(self.raw, "iface_range_value") and self.raw.iface_range_value:
                return float(self.raw.iface_range_value.CurrentValue)
            if hasattr(self.raw, "iface_value") and self.raw.iface_value:
                return str(self.raw.iface_value.CurrentValue)
        except Exception:
            pass
        return self.name

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

    # --------------------------------------------------------------------------
    # 5. Expand / Collapse Pattern (Dropdowns, ComboBoxes, Tree Items)
    # --------------------------------------------------------------------------

    def expand(self) -> bool:
        """Expands a ComboBox, accordion, or TreeView item."""
        logger.info(f"UIA: Expanding '{self.name}'")
        try:
            if hasattr(self.raw, "expand"):
                self.raw.expand()
                return True
            if hasattr(self.raw, "iface_expand_collapse") and self.raw.iface_expand_collapse:
                self.raw.iface_expand_collapse.Expand()
                return True
        except Exception:
            pass
        return self.click()

    def collapse(self) -> bool:
        """Collapses a ComboBox, accordion, or TreeView item."""
        logger.info(f"UIA: Collapsing '{self.name}'")
        try:
            if hasattr(self.raw, "collapse"):
                self.raw.collapse()
                return True
            if hasattr(self.raw, "iface_expand_collapse") and self.raw.iface_expand_collapse:
                self.raw.iface_expand_collapse.Collapse()
                return True
        except Exception:
            pass
        return False

    def is_expanded(self) -> Optional[bool]:
        """Returns True if expanded, False if collapsed, None if unsupported."""
        try:
            if hasattr(self.raw, "is_expanded"):
                return bool(self.raw.is_expanded())
            if hasattr(self.raw, "iface_expand_collapse") and self.raw.iface_expand_collapse:
                # 0 = Collapsed, 1 = Expanded, 2 = PartiallyExpanded, 3 = LeafNode
                return bool(self.raw.iface_expand_collapse.CurrentExpandCollapseState == 1)
        except Exception:
            pass
        return None

    # --------------------------------------------------------------------------
    # 6. Scroll & ScrollItem Patterns
    # --------------------------------------------------------------------------

    def scroll_into_view(self) -> bool:
        """Scrolls the container view until this element is visible on screen."""
        logger.info(f"UIA: Scrolling '{self.name}' into view")
        try:
            if hasattr(self.raw, "iface_scroll_item") and self.raw.iface_scroll_item:
                self.raw.iface_scroll_item.ScrollIntoView()
                return True
        except Exception:
            pass
        return False

    def scroll(self, direction: str = "down", amount: str = "normal") -> bool:
        """Scrolls the container element (up, down, left, right)."""
        logger.info(f"UIA: Scrolling container '{self.name}' {direction}")
        try:
            if hasattr(self.raw, "scroll"):
                self.raw.scroll(direction=direction, amount=amount)
                return True
        except Exception:
            pass
        # Fallback: PyAutoGUI scroll
        try:
            rect = self.get_rectangle()
            if rect:
                cx = (rect["left"] + rect["right"]) // 2
                cy = (rect["top"] + rect["bottom"]) // 2
                import pyautogui
                clicks = -300 if direction == "down" else 300
                pyautogui.scroll(clicks, x=cx, y=cy)
                return True
        except Exception as e:
            logger.error(f"UIA: Scroll failed on '{self.name}': {e}")
        return False

    # --------------------------------------------------------------------------
    # 7. Focus & State Inspection
    # --------------------------------------------------------------------------

    def set_focus(self) -> bool:
        """Brings keyboard focus directly to this element."""
        try:
            if hasattr(self.raw, "set_focus"):
                self.raw.set_focus()
                return True
        except Exception:
            pass
        return False

    def has_keyboard_focus(self) -> bool:
        """Checks if this element currently holds active keyboard focus."""
        try:
            if hasattr(self.raw, "has_keyboard_focus"):
                return bool(self.raw.has_keyboard_focus())
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
        """Serializes element metadata and pattern states into a clean inspection dictionary."""
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "is_enabled": self.is_enabled(),
            "is_visible": self.is_visible(),
            "is_selected": self.is_selected(),
            "toggle_state": self.get_toggle_state(),
            "is_expanded": self.is_expanded(),
            "value": self.get_value() if self.control_type in ("Slider", "ProgressBar", "Edit") else None,
            "rectangle": self.get_rectangle(),
        }


class WindowsUIA:
    """
    Windows UI Automation Engine.
    Locates and manipulates UI controls dynamically in the Windows accessibility tree
    without requiring hardcoded screen coordinates.

    Supports:
      - Deep & shallow (scoped) tree queries
      - Full pattern support (Invoke, Selection, Toggle, RangeValue, ExpandCollapse, Scroll)
      - Dynamic TTL caching to eliminate repetitive accessibility tree scan latency
    """

    CACHE_TTL: float = 2.0

    def __init__(self):
        self._desktop = None
        self._element_cache: Dict[tuple, tuple] = {}
        self._init_backend()

    def _init_backend(self):
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
            logger.info("WindowsUIA: Initialized pywinauto UIA backend with full pattern support.")
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
        scope: str = "descendants",
    ) -> Optional[UIElementWrapper]:
        """
        Finds a single UI element matching criteria in the target window or desktop.
        `scope` can be 'descendants' (full tree) or 'children' (fast top-level search).
        """
        results = self.find_elements(
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            hwnd=hwnd,
            exact_match=exact_match,
            scope=scope,
            max_results=1,
        )
        return results[0] if results else None

    def find_elements(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        hwnd: Optional[int] = None,
        exact_match: bool = False,
        scope: str = "descendants",
        max_results: int = 50,
    ) -> List[UIElementWrapper]:
        """
        Searches the Windows UIA accessibility tree for elements matching criteria.
        """
        found = []
        if not self._desktop:
            return found

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
            # Choose search scope: fast direct children or full descendant tree
            if scope == "children" and hasattr(target_root, "children"):
                iterator = target_root.children()
            elif hasattr(target_root, "iter_descendants"):
                iterator = target_root.iter_descendants()
            else:
                iterator = target_root.descendants()

            for elem in iterator:
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
                    if len(found) >= max_results:
                        break
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
        Inspects interactive UI controls (buttons, tabs, inputs, menus, sliders, switches) of a window.
        Returns a rich list of serialized element dictionaries for the Observer.
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
            "RadioButton", "ComboBox", "Hyperlink", "ListItem", "TreeItem",
            "Slider", "ProgressBar", "SplitButton", "ToolBar"
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

import logging
import time
from typing import Any, Dict, List, Optional, Union

from computer_use.launcher import app_launcher
from computer_use.window_manager import window_manager
from computer_use.windows_uia import uia_engine, UIElementWrapper

logger = logging.getLogger("PRIVACY68.ComputerUse.Actions")


class ComputerActions:
    """
    Safe Abstraction Layer for Windows Computer-Use Actions.
    Provides standard high-level interaction primitives:
    launch, click, double click, type text, send hotkey, switch window,
    close window, tab selection, toggle, slider value setting, expand/collapse,
    and scroll into view.
    """

    def launch_application(self, app_name: str, wait_timeout: float = 4.0) -> bool:
        """Launches a desktop application and brings it to foreground."""
        logger.info(f"Action: launch_application('{app_name}')")
        return app_launcher.launch_and_wait(app_name, timeout=wait_timeout)

    def switch_window(self, app_name: str) -> bool:
        """Brings an open application window to the foreground."""
        logger.info(f"Action: switch_window('{app_name}')")
        return window_manager.focus_window(app_name)

    def close_window(self, target: Optional[str] = None) -> bool:
        """Closes the active or specified window."""
        logger.info(f"Action: close_window('{target or 'active'}')")
        return window_manager.close_window(target)

    def find_ui_element(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        exact_match: bool = False,
        scope: str = "descendants",
    ) -> Optional[UIElementWrapper]:
        """Locates an element in the active window by properties."""
        return uia_engine.find_element(
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            exact_match=exact_match,
            scope=scope,
        )

    def click_element(
        self,
        name: str,
        control_type: Optional[str] = None,
        exact_match: bool = False,
    ) -> bool:
        """Finds and clicks a UI element by name/type."""
        logger.info(f"Action: click_element(name='{name}', control_type='{control_type}')")
        elem = self.find_ui_element(name=name, control_type=control_type, exact_match=exact_match)
        if elem:
            return elem.click()

        # Fallback: Task Manager specific fast path if clicking a tab
        if control_type == "TabItem" or any(w in name.lower() for w in ("performance", "processes", "startup", "details")):
            return self.select_tab(name)

        logger.warning(f"Action: click_element could not locate '{name}'")
        return False

    def double_click_element(
        self,
        name: str,
        control_type: Optional[str] = None,
    ) -> bool:
        """Finds and double-clicks a UI element."""
        logger.info(f"Action: double_click_element(name='{name}')")
        elem = self.find_ui_element(name=name, control_type=control_type)
        if elem:
            return elem.double_click()
        return False

    def right_click_element(
        self,
        name: str,
        control_type: Optional[str] = None,
    ) -> bool:
        """Finds and right-clicks a UI element."""
        logger.info(f"Action: right_click_element(name='{name}')")
        elem = self.find_ui_element(name=name, control_type=control_type)
        if elem:
            return elem.right_click()
        return False

    def select_tab(self, tab_name: str) -> bool:
        """Selects a navigation tab (e.g. 'Performance', 'Processes', 'Startup')."""
        logger.info(f"Action: select_tab('{tab_name}')")

        # 1. Try finding TabItem in UIA accessibility tree
        tab_elem = self.find_ui_element(name=tab_name, control_type="TabItem")
        if tab_elem:
            if tab_elem.select():
                return True

        # 2. Check if active window is Task Manager and dispatch standard Windows 11 access keys / shortcuts
        if window_manager.is_window_active("Task Manager") or window_manager.is_window_active("taskmgr"):
            tab_clean = tab_name.lower().strip()
            from plugins.windows_plugin import WindowsPlugin
            win_plugin = WindowsPlugin()
            if "perf" in tab_clean:
                return win_plugin.taskmgr_performance()
            elif "proc" in tab_clean:
                return win_plugin.taskmgr_processes()
            elif "start" in tab_clean:
                return win_plugin.taskmgr_startup()
            elif "history" in tab_clean:
                return win_plugin.taskmgr_app_history()
            elif "user" in tab_clean:
                return win_plugin.taskmgr_users()
            elif "detail" in tab_clean:
                return win_plugin.taskmgr_details()
            elif "service" in tab_clean:
                return win_plugin.taskmgr_services()

        # 3. Fallback: Search any button or text element with tab name
        generic_elem = self.find_ui_element(name=tab_name)
        if generic_elem:
            return generic_elem.click()

        return False

    def toggle_element(
        self,
        name: str,
        target_state: Optional[bool] = None,
        control_type: Optional[str] = None,
    ) -> bool:
        """
        Toggles a switch, checkbox, or toggle button in the active window.
        `target_state`: True for ON, False for OFF, None to toggle state.
        """
        logger.info(f"Action: toggle_element('{name}', target_state={target_state})")
        elem = self.find_ui_element(name=name, control_type=control_type or "CheckBox")
        if not elem:
            elem = self.find_ui_element(name=name, control_type="Button")
        if not elem:
            elem = self.find_ui_element(name=name)

        if elem:
            return elem.toggle(target_state=target_state)

        logger.warning(f"Action: toggle_element could not locate '{name}'")
        return False

    def set_slider_value(self, name: str, value: float) -> bool:
        """Sets the numeric value on a slider or progress control."""
        logger.info(f"Action: set_slider_value('{name}', value={value})")
        elem = self.find_ui_element(name=name, control_type="Slider")
        if not elem:
            elem = self.find_ui_element(name=name)

        if elem:
            return elem.set_value(value)

        logger.warning(f"Action: set_slider_value could not locate '{name}'")
        return False

    def expand_element(self, name: str) -> bool:
        """Expands a dropdown, combobox, or tree item."""
        logger.info(f"Action: expand_element('{name}')")
        elem = self.find_ui_element(name=name)
        if elem:
            return elem.expand()
        return False

    def collapse_element(self, name: str) -> bool:
        """Collapses an expanded dropdown or tree item."""
        logger.info(f"Action: collapse_element('{name}')")
        elem = self.find_ui_element(name=name)
        if elem:
            return elem.collapse()
        return False

    def scroll_into_view(self, name: str) -> bool:
        """Scrolls the active window until the target UI element is visible."""
        logger.info(f"Action: scroll_into_view('{name}')")
        elem = self.find_ui_element(name=name)
        if elem:
            return elem.scroll_into_view()
        return False

    def type_text(self, text: str, target_field_name: Optional[str] = None) -> bool:
        """Types text into the active window or a designated Edit field."""
        logger.info(f"Action: type_text('{text}', field='{target_field_name}')")

        if target_field_name:
            field_elem = self.find_ui_element(name=target_field_name, control_type="Edit")
            if field_elem:
                return field_elem.set_text(text)

        # Type directly into the active foreground window
        try:
            import pyperclip
            import pyautogui
            pyperclip.copy(text)
            time.sleep(0.02)
            pyautogui.hotkey("ctrl", "v")
            return True
        except Exception:
            try:
                import pyautogui
                pyautogui.write(text, interval=0.01)
                return True
            except Exception as e:
                logger.error(f"Action: type_text failed: {e}")
                return False

    def send_hotkey(self, *keys: Union[int, str]) -> bool:
        """Sends a combination of hotkeys to the focused window."""
        logger.info(f"Action: send_hotkey({keys})")
        try:
            import pyautogui
            pyautogui.hotkey(*[str(k).lower() for k in keys])
            return True
        except Exception as e:
            logger.error(f"Action: send_hotkey failed: {e}")
            return False

    def press_key(self, key_name: str) -> bool:
        """Presses a single keyboard key (e.g. 'enter', 'tab', 'escape', 'space')."""
        logger.info(f"Action: press_key('{key_name}')")
        try:
            import pyautogui
            pyautogui.press(key_name.lower())
            return True
        except Exception as e:
            logger.error(f"Action: press_key failed: {e}")
            return False

    def scroll(self, direction: str = "down", amount: int = 3) -> bool:
        """Scrolls the active window up or down."""
        try:
            import pyautogui
            clicks = -amount if direction.lower() == "down" else amount
            pyautogui.scroll(clicks * 100)
            return True
        except Exception as e:
            logger.error(f"Action: scroll failed: {e}")
            return False


computer_actions = ComputerActions()

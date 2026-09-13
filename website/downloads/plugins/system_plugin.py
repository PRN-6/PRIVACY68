import logging
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_keys import (
    trigger_volume_up,
    trigger_volume_down,
    trigger_volume_mute,
    trigger_lock_workstation,
    trigger_snipping_tool,
    trigger_press_enter,
    trigger_press_tab,
    trigger_close_window,
    trigger_maximize_window,
    trigger_minimize_window
)

logger = logging.getLogger("PRIVACY68.Plugin.System")

class SystemPlugin(BasePlugin):
    id = "system"
    name = "Windows System"
    icon = "⚙️"
    description = "Control Windows OS: volume, screen lock, screenshot, enter, close, maximize, and minimize windows."
    version = "1.3.0"
    author = "Privacy68 Team"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "system.close_window": self.close_window,
            "system.maximize_window": self.maximize_window,
            "system.minimize_window": self.minimize_window,
            "system.type_text": self.type_text,
            "system.press_enter": self.press_enter,
            "system.press_tab": self.press_tab,
            "system.volume_up": self.volume_up,
            "system.volume_down": self.volume_down,
            "system.volume_mute": self.volume_mute,
            "system.lock": self.lock_screen,
            "system.screenshot": self.take_screenshot,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "system.close_window": [
                "close window",
                "close this window",
                "close current window",
                "close active window",
                "close app",
                "close this app",
                "exit app",
                "quit app",
                "exit window",
            ],
            "system.maximize_window": [
                "maximize window",
                "maximize this window",
                "maximize current window",
                "maximize active window",
                "maximize the window",
                "maximize",
                "full screen",
                "full screen window",
                "make window full screen",
                "maximize app",
                "maximize this app",
                "maximize whatsapp",
                "maximize chrome",
            ],
            "system.minimize_window": [
                "minimize window",
                "minimize this window",
                "minimize current window",
                "minimize active window",
                "minimize the window",
                "minimize",
                "minimize app",
                "minimize this app",
                "minimize whatsapp",
                "minimize chrome",
            ],
            "system.type_text": [
                "type",
                "type that",
                "type out",
                "write",
                "write that",
                "write out",
                "type message",
                "type text",
                "type i will be home",
                "type i will be late",
                "type hello",
                "type thank you",
                "type yes",
                "type no",
                "type okay",
            ],
            "system.press_enter": [
                "press enter",
                "hit enter",
                "enter",
                "press return",
                "hit return",
                "submit",
            ],
            "system.press_tab": [
                "press tab",
                "hit tab",
                "next item",
            ],
            "system.volume_up": [
                "volume up",
                "increase volume",
                "turn up the volume",
                "louder",
            ],
            "system.volume_down": [
                "volume down",
                "decrease volume",
                "turn down the volume",
                "lower volume",
            ],
            "system.volume_mute": [
                "mute volume",
                "unmute volume",
                "mute audio",
                "unmute audio",
                "mute",
                "unmute",
            ],
            "system.lock": [
                "lock screen",
                "lock pc",
                "lock my computer",
                "lock windows",
            ],
            "system.screenshot": [
                "take a screenshot",
                "take screenshot",
                "capture screen",
                "screenshot",
                "snip screen",
            ]
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "system.close_window": "- system.close_window: Close the currently active window or application (Alt+F4).",
            "system.maximize_window": "- system.maximize_window: Maximize the active window or a specified application to full screen.",
            "system.minimize_window": "- system.minimize_window: Minimize the active window or a specified application to the taskbar.",
            "system.type_text": "- system.type_text: Type or dictate text directly into whatever window or text field is currently focused (e.g. 'type I will be home', 'write hello how are you', 'type see you soon and send').",
            "system.press_enter": "- system.press_enter: Simulate pressing the Enter / Return key on the keyboard.",
            "system.press_tab": "- system.press_tab: Simulate pressing the Tab key on the keyboard.",
            "system.volume_up": "- system.volume_up: Increase master audio volume.",
            "system.volume_down": "- system.volume_down: Decrease master audio volume.",
            "system.volume_mute": "- system.volume_mute: Toggle mute/unmute master audio.",
            "system.lock": "- system.lock: Lock the Windows workstation/computer screen.",
            "system.screenshot": "- system.screenshot: Launch Windows screenshot snip tool.",
        }

    def _find_window_by_app_name(self, text: str) -> int:
        """Finds a visible window matching an app named in the command text."""
        known_apps = ["whatsapp", "chrome", "notepad", "brave", "code", "terminal", "powershell", "spotify", "discord"]
        target = None
        lower_text = text.lower()
        for app in known_apps:
            if app in lower_text:
                target = app
                break
        if not target:
            return 0

        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        result = [0]
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if target in buff.value.lower():
                        result[0] = hwnd
                        return False
            return True
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return result[0]

    def maximize_window(self, text: str) -> bool:
        logger.info("Plugin Action: Maximizing window")
        hwnd = self._find_window_by_app_name(text)
        if hwnd:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            user32.SetForegroundWindow(hwnd)
            return True
        trigger_maximize_window()
        return True

    def minimize_window(self, text: str) -> bool:
        logger.info("Plugin Action: Minimizing window")
        hwnd = self._find_window_by_app_name(text)
        if hwnd:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            return True
        trigger_minimize_window()
        return True

    def close_window(self, text: str) -> bool:
        logger.info("Plugin Action: Closing active window (Alt+F4)")
        trigger_close_window()
        return True

    def type_text(self, text: str) -> bool:
        import re
        import time
        content = re.sub(
            r'^(?:privacy68,?\s*|sena,?\s*|nova,?\s*)?(?:please\s*)?(?:can\s+you\s*)?(?:type\s+that|type\s+out|type\s+in|type|write\s+that|write\s+out|write\s+down|write)\s+',
            '', text, flags=re.IGNORECASE
        ).strip()

        if not content:
            logger.warning("type_text invoked but no text content found.")
            return False

        and_enter = False
        if re.search(r'\s+and\s+(?:send|press\s+enter|hit\s+enter)$', content, re.IGNORECASE):
            content = re.sub(r'\s+and\s+(?:send|press\s+enter|hit\s+enter)$', '', content, flags=re.IGNORECASE).strip()
            and_enter = True

        logger.info(f"Plugin Action: Typing into focused window: '{content}' (and_enter={and_enter})")
        from plugins.win_keys import type_text as do_type, trigger_press_enter
        do_type(content)
        if and_enter:
            time.sleep(0.1)
            trigger_press_enter()
        return True

    def press_enter(self, text: str) -> bool:
        logger.info("Plugin Action: Pressing Enter key")
        trigger_press_enter()
        return True

    def press_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Pressing Tab key")
        trigger_press_tab(1)
        return True

    def volume_up(self, text: str) -> bool:
        logger.info("Plugin Action: Volume Up")
        trigger_volume_up()
        return True

    def volume_down(self, text: str) -> bool:
        logger.info("Plugin Action: Volume Down")
        trigger_volume_down()
        return True

    def volume_mute(self, text: str) -> bool:
        logger.info("Plugin Action: Toggle Volume Mute")
        trigger_volume_mute()
        return True

    def lock_screen(self, text: str) -> bool:
        logger.info("Plugin Action: Locking Computer Screen")
        trigger_lock_workstation()
        return True

    def take_screenshot(self, text: str) -> bool:
        logger.info("Plugin Action: Taking Screenshot")
        trigger_snipping_tool()
        return True


import logging
import subprocess
import re
import time
import urllib.parse
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_utils import kill_process

logger = logging.getLogger("PRIVACY68.Plugin.Brave")

class BravePlugin(BasePlugin):
    """
    Standalone Brave Browser Plugin for PRIVACY68 Assistant.
    Provides launching, closing, new tab, close tab, and reopen tab actions.
    """
    id = "brave"
    name = "Brave Browser"
    icon = "🦁"
    description = "Control Brave Browser: launch, close, open new tab, close tab."
    version = "1.1.0"
    author = "Community Plugin"
    is_builtin = False
    category = "Browser"
    plugin_type = "Browser Control"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "brave.open": self.open_browser,
            "brave.close": self.close_browser,
            "brave.new_tab": self.new_tab,
            "brave.close_tab": self.close_tab,
            "brave.reopen_tab": self.reopen_tab,
            "brave.search": self.search_web,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "brave.open": [
                "open brave",
                "launch brave",
                "start brave",
                "open brave browser",
                "launch brave browser",
                "brave",
            ],
            "brave.close": [
                "close brave",
                "exit brave",
                "quit brave",
                "terminate brave",
                "close brave browser",
            ],
            "brave.new_tab": [
                "brave new tab",
                "new tab in brave",
                "open new tab in brave",
            ],
            "brave.close_tab": [
                "brave close tab",
                "close tab in brave",
            ],
            "brave.reopen_tab": [
                "reopen tab in brave",
                "restore tab in brave",
            ],
            "brave.search": [
                "search in brave",
                "search on brave",
                "search using brave",
                "brave search",
            ]
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "brave.open": "- brave.open: Launch or open Brave Browser.",
            "brave.close": "- brave.close: Force close or terminate Brave Browser.",
            "brave.new_tab": "- brave.new_tab: Open a new tab in Brave Browser.",
            "brave.close_tab": "- brave.close_tab: Close the active tab in Brave Browser.",
            "brave.reopen_tab": "- brave.reopen_tab: Reopen the last closed tab in Brave Browser.",
            "brave.search": "- brave.search: Search a query or open a website using Brave Browser.",
        }

    def open_browser(self, text: str) -> bool:
        logger.info("Plugin Action: Launching Brave Browser")
        subprocess.Popen("start brave", shell=True)
        return True

    def close_browser(self, text: str) -> bool:
        logger.info("Plugin Action: Closing Brave Browser")
        kill_process("brave.exe")
        return True

    def _ensure_focused(self) -> bool:
        """Ensures Brave is the focused foreground window before sending hotkeys."""
        from computer_use.window_manager import window_manager
        active = window_manager.get_active_window()
        proc = str(active.get("process_name", "")).lower()
        if proc == "brave.exe":
            return True
        # Brave is not focused — try to find and focus it
        hwnd = window_manager.find_window("brave")
        if hwnd:
            logger.info("Brave not focused — bringing Brave to foreground")
            window_manager.focus_window(hwnd)
            time.sleep(0.15)
            return True
        # Brave not open at all — launch it
        logger.info("Brave not running — launching Brave")
        subprocess.Popen("start brave", shell=True)
        time.sleep(1.0)
        return True

    def new_tab(self, text: str) -> bool:
        logger.info("Plugin Action: New tab in Brave")
        self._ensure_focused()
        import pyautogui
        pyautogui.hotkey("ctrl", "t")
        return True

    def close_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Close tab in Brave")
        self._ensure_focused()
        import pyautogui
        pyautogui.hotkey("ctrl", "w")
        return True

    def reopen_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Reopen tab in Brave")
        self._ensure_focused()
        import pyautogui
        pyautogui.hotkey("ctrl", "shift", "t")
        return True

    def search_web(self, text: str) -> bool:
        cleaned = re.sub(r"\b(?:search|in|on|using|with|brave|browser|for|about|google)\b", "", text, flags=re.IGNORECASE).strip(".!?, \t\n")
        if not cleaned:
            cleaned = "Google"
            
        # If it looks like a domain name, open it directly
        if re.search(r"\.[a-z]{2,4}(\/.*)?$", cleaned) or cleaned.startswith("http"):
            url = cleaned if cleaned.startswith("http") else f"https://{cleaned}"
            logger.info(f"Plugin Action: Opening website directly: '{url}'")
        else:
            logger.info(f"Plugin Action: Searching Brave for '{cleaned}'")
            url = f"https://search.brave.com/search?q={urllib.parse.quote_plus(cleaned)}"
            
        subprocess.Popen(f'start brave "{url}"', shell=True)
        return True

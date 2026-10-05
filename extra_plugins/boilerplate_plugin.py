"""
=============================================================================
 PRIVACY68 PLUGIN BOILERPLATE / TEMPLATE
=============================================================================
This file is a starter template for creating custom plugins for PRIVACY68.
Copy this file, rename it (e.g. 'spotify_plugin.py'), and customize it
for whatever application or service you want to control.

HOW PRIVACY68 PLUGINS WORK:
1. Fast Lane (0ms Latency):
   - Any phrase in 'fast_intents' triggers your action immediately without
     calling the AI model.
2. Smart Lane (Hermes Agent / AI):
   - Complex or parameterized commands (e.g. "play bohemian rhapsody on spotify")
     use 'descriptions' to let Ollama / Hermes extract arguments and dispatch
     to your plugin actions.
3. Contextual / Active Window Awareness:
   - Use 'self.is_active_window("App Name")' to check if your app is focused.
   - Use 'self.focus_window("App Name")' to bring it to foreground.
   - Use 'self.send_keys(VK_CONTROL, VK_T)' to send keyboard shortcuts.

HOW TO INSTALL & TEST YOUR PLUGIN:
Method 1 (In-App):
   - Place this file in 'extra_plugins/' or use the PRIVACY68 Control Center
     Settings -> "Install Plugin" to load it into '%APPDATA%/PRIVACY68/plugins/'.
Method 2 (Standalone Test):
   - Run 'python my_plugin.py' in your terminal to test actions directly.
=============================================================================
"""

import logging
import os
import re
import subprocess
import time
from typing import Callable, Dict, List

# Core BasePlugin class from PRIVACY68
from plugins.base_plugin import BasePlugin

# OS-level helpers (kill process, type text) — UIA has no equivalent for these
from plugins.win_utils import kill_process, type_text, press_enter, press_tab

# UIA Stack — window management and high-level UI actions
from computer_use.window_manager import window_manager    # focus, find, is_active
from computer_use.actions import computer_actions          # click_element, select_tab, send_hotkey, type_text


logger = logging.getLogger("PRIVACY68.Plugin.Boilerplate")


class BoilerplatePlugin(BasePlugin):
    """
    Starter Boilerplate Plugin for PRIVACY68.
    Replace 'Boilerplate' and 'myapp' with your actual app details.
    """

    # ────────────────────────── 1. Metadata ──────────────────────────
    # 'id': Unique lowercase identifier (used in action prefixes e.g. 'myapp.open')
    id: str = "myapp"

    # 'name': Human-readable name displayed in the UI Settings & Plugin list
    name: str = "My Application"

    # 'icon': Single emoji or symbol for UI display
    icon: str = "🚀"

    # 'description': Overview of what this plugin controls
    description: str = "Controls My Application: launch, close, navigate tabs, and trigger shortcuts."

    # 'version': Semantic version
    version: str = "1.0.0"

    # 'author': Developer / Creator name
    author: str = "Developer"

    # Category and Type
    category: str = "Custom"
    plugin_type: str = "Custom App Template"

    # 'is_builtin': Keep False for community / user plugins
    is_builtin: bool = False

    # ────────────────────────── 2. Action Mapping ──────────────────────────
    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        """
        Maps unique action identifiers to Python handler methods.
        Convention: '<plugin_id>.<action_name>'
        """
        return {
            "myapp.open": self.open_app,
            "myapp.close": self.close_app,
            "myapp.toggle_play": self.toggle_playback,
            "myapp.search": self.search_content,
            "myapp.switch_tab": self.switch_tab,
        }

    # ────────────────────────── 3. Fast-Lane Intents ──────────────────────────
    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        """
        Fixed voice commands that execute instantly with 0ms latency
        (via Semantic Router) without waiting for LLM token generation.
        """
        return {
            "myapp.open": [
                "open my app",
                "launch my app",
                "start my app",
            ],
            "myapp.close": [
                "close my app",
                "exit my app",
                "quit my app",
                "kill my app",
            ],
            "myapp.toggle_play": [
                "pause my app",
                "resume my app",
                "toggle playback in my app",
                "play pause my app",
            ],
            "myapp.search": [
                "search in my app",
                "find in my app",
            ],
            "myapp.switch_tab": [
                "next tab in my app",
                "switch tab in my app",
            ],
        }

    # ────────────────────────── 4. AI Prompt Descriptions ──────────────────────────
    @property
    def descriptions(self) -> Dict[str, str]:
        """
        Detailed descriptions provided to Ollama & Hermes Agent to enable
        smart autonomous tool-calling and parameter extraction.
        """
        return {
            "myapp.open": "- myapp.open: Launch or bring My Application to the foreground.",
            "myapp.close": "- myapp.close: Terminate My Application process.",
            "myapp.toggle_play": "- myapp.toggle_play: Pause or resume playback in My Application.",
            "myapp.search": "- myapp.search: Search for a song, document, or item in My Application (e.g. 'search rock music in myapp').",
            "myapp.switch_tab": "- myapp.switch_tab: Switch to the next tab or section in My Application.",
        }

    # ────────────────────────── 5. Action Implementations ──────────────────────────

    def open_app(self, text: str = "") -> bool:
        """
        Launches the application or brings it to the foreground if already open.
        """
        logger.info("BoilerplatePlugin: Opening application...")

        # If already running, bring it to the foreground
        if window_manager.focus_window("My Application"):
            logger.info("Brought existing My Application window to foreground.")
            return True

        # Otherwise launch the executable or protocol URI
        try:
            # Example A: Launch executable by name or path
            # subprocess.Popen(["C:\\Path\\To\\myapp.exe"])

            # Example B: Launch via Windows Start / System PATH
            # subprocess.Popen("start myapp.exe", shell=True)

            # Example C: Launch via URI protocol scheme (e.g. spotify:, ms-settings:)
            # subprocess.Popen("start myapp-uri:", shell=True)

            logger.info("Successfully launched application.")
            return True
        except Exception as e:
            logger.error(f"Failed to launch application: {e}")
            return False

    def close_app(self, text: str = "") -> bool:
        """
        Terminates the application process cleanly.
        """
        logger.info("BoilerplatePlugin: Closing application...")
        # Cleanly kills process tree on Windows
        return kill_process("myapp.exe")

    def toggle_playback(self, text: str = "") -> bool:
        """
        Context-aware control: Ensures the app is active and sends a hotkey (e.g. Space).
        """
        logger.info("BoilerplatePlugin: Toggling playback...")

        # 1. Context check: is this app currently in the foreground?
        if not window_manager.is_window_active("My Application"):
            # Try focusing it first
            if not window_manager.focus_window("My Application"):
                logger.warning("My Application is not running or focused.")
                return False

        time.sleep(0.05)
        # 2. Simulate keyboard shortcut via pyautogui (e.g. Space to play/pause)
        computer_actions.press_key("space")
        return True

    def search_content(self, text: str = "") -> bool:
        """
        Extracts search query from user voice command and types it into the app.
        """
        logger.info(f"BoilerplatePlugin: Search request '{text}'")

        # 1. Ensure window is focused
        window_manager.focus_window("My Application")
        time.sleep(0.05)

        # 2. Extract search term by stripping command trigger words
        query = re.sub(r"\b(search|find|for|in|on|my|app|look|up)\b", " ", text, flags=re.IGNORECASE)
        query = re.sub(r"\s+", " ", query).strip(" .!?,_-")

        # 3. Press search shortcut in the app (e.g. Ctrl+F)
        computer_actions.send_hotkey("ctrl", "f")
        time.sleep(0.1)

        # 4. Type the query if provided
        if query:
            type_text(query)
            time.sleep(0.05)
            press_enter()

        return True

    def switch_tab(self, text: str = "") -> bool:
        """
        Contextual tab switching (e.g. Ctrl+Tab).
        """
        logger.info("BoilerplatePlugin: Switching tab...")
        if not window_manager.focus_window("My Application"):
            return False
        time.sleep(0.05)
        computer_actions.send_hotkey("ctrl", "tab")
        return True


# ────────────────────────── Standalone Direct Test ──────────────────────────
if __name__ == "__main__":
    # Test this plugin directly in Python: python boilerplate_plugin.py
    logging.basicConfig(level=logging.INFO)
    print("Testing BoilerplatePlugin...")
    plugin = BoilerplatePlugin()
    print(f"Plugin ID: {plugin.id}")
    print(f"Registered Actions: {list(plugin.actions.keys())}")
    print(f"Fast Intents Count: {len(plugin.fast_intents)}")
    print(f"Hermes Schemas Generated: {len(plugin.get_tool_definitions())}")
    print("Active Window Title:", plugin.get_active_window_title())

import logging
import re
import subprocess
import urllib.parse
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_keys import trigger_new_tab, trigger_close_tab, trigger_reopen_tab, kill_process

logger = logging.getLogger("PRIVACY68.Plugin.Chrome")

class ChromePlugin(BasePlugin):
    id = "chrome"
    name = "Google Chrome"
    icon = "🌐"
    description = "Control Google Chrome: open, close, new tab, close tab, search, and incognito mode."
    version = "1.3.0"
    author = "Privacy68 Team"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "chrome.open": self.open_browser,
            "chrome.close_app": self.close_browser,
            "chrome.new_tab": self.new_tab,
            "chrome.close_tab": self.close_tab,
            "chrome.reopen_tab": self.reopen_tab,
            "chrome.incognito": self.open_incognito,
            "chrome.search": self.search_web,
            "chrome.open_website": self.open_website,
            "chrome.select_profile": self.select_profile,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "chrome.open": [
                "open chrome",
                "launch chrome",
                "start chrome",
                "open google chrome",
                "launch google chrome",
            ],
            "chrome.close_app": [
                "close chrome",
                "exit chrome",
                "quit chrome",
                "terminate chrome",
                "close google chrome",
                "exit google chrome",
            ],
            "chrome.new_tab": [
                "new tab in chrome",
                "create a new tab in chrome",
                "open new tab in chrome",
                "chrome new tab",
            ],
            "chrome.close_tab": [
                "close tab in chrome",
                "close current tab in chrome",
                "chrome close tab",
            ],
            "chrome.reopen_tab": [
                "reopen tab in chrome",
                "restore tab in chrome",
            ],
            "chrome.incognito": [
                "open incognito in chrome",
                "open private window in chrome",
                "chrome incognito",
            ],
            "chrome.search": [
                "search in chrome",
                "search on chrome",
                "search using chrome",
                "chrome search",
            ],
            "chrome.open_website": [
                "open website in chrome",
                "go to website",
                "navigate to",
                "open domain",
                "launch website",
                "visit website",
            ],
            "chrome.select_profile": [
                "select first user",
                "select second user",
                "select third user",
                "select fourth user",
                "select item one",
                "select item two",
                "select item three",
                "select the first one",
                "select the second one",
                "choose first",
                "choose second",
                "select profile 1",
                "select profile 2",
            ]
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "chrome.open": "- chrome.open: Launch or bring up Google Chrome.",
            "chrome.close_app": "- chrome.close_app: Close or exit Google Chrome application.",
            "chrome.new_tab": "- chrome.new_tab: Create a new browser tab in Chrome.",
            "chrome.close_tab": "- chrome.close_tab: Close the active tab in Chrome.",
            "chrome.reopen_tab": "- chrome.reopen_tab: Reopen the last closed tab in Chrome.",
            "chrome.incognito": "- chrome.incognito: Open a new Incognito window in Chrome.",
            "chrome.search": "- chrome.search: Search a query using Google Chrome.",
            "chrome.select_profile": "- chrome.select_profile: Select a numbered Chrome profile (e.g. 'select 2nd user').",
        }

    def open_browser(self, text: str) -> bool:
        logger.info("Plugin Action: Launching Google Chrome")
        subprocess.Popen("start chrome", shell=True)
        return True

    def close_browser(self, text: str) -> bool:
        logger.info("Plugin Action: Closing Google Chrome")
        kill_process("chrome.exe")
        return True

    def new_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Opening new tab in Chrome")
        trigger_new_tab()
        return True

    def close_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Closing current tab in Chrome")
        trigger_close_tab()
        return True

    def reopen_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Reopening last closed tab in Chrome")
        trigger_reopen_tab()
        return True

    def open_incognito(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Chrome Incognito window")
        subprocess.Popen("start chrome --incognito", shell=True)
        return True

    def search_web(self, text: str) -> bool:
        cleaned = re.sub(r"\b(?:search|in|on|using|with|chrome|browser|for|about|google)\b", "", text, flags=re.IGNORECASE).strip(".!?, \t\n")
        if not cleaned:
            cleaned = "Google"
        
        logger.info(f"Plugin Action: Searching Chrome for '{cleaned}'")
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(cleaned)}"
        subprocess.Popen(f'start chrome "{url}"', shell=True)
        return True
        
    def open_website(self, text: str) -> bool:
        cleaned = re.sub(r"\b(?:open|go to|navigate to|visit|website|domain|in|on|chrome|browser)\b", "", text, flags=re.IGNORECASE).strip(".!?, \t\n")
        if not cleaned:
            return False
            
        url = cleaned if cleaned.startswith("http") else f"https://{cleaned}"
        # Strip spaces that might have been accidentally transcribed in domain names
        url = url.replace(" ", "")
        
        logger.info(f"Plugin Action: Opening website directly: '{url}'")
        subprocess.Popen(f'start chrome "{url}"', shell=True)
        return True

    def select_profile(self, text: str) -> bool:
        """Parses the text for a profile number and launches Chrome natively with that profile."""
        t = text.lower()
        profile_id = None
        
        if any(w in t for w in ["first", "1st", "1", "one", "default"]):
            profile_id = "Default"
        elif any(w in t for w in ["second", "2nd", "2", "two"]):
            profile_id = "Profile 1"
        elif any(w in t for w in ["third", "3rd", "3", "three"]):
            profile_id = "Profile 2"
        elif any(w in t for w in ["fourth", "4th", "4", "four"]):
            profile_id = "Profile 3"
        elif any(w in t for w in ["fifth", "5th", "5", "five"]):
            profile_id = "Profile 4"
            
        if profile_id:
            logger.info(f"Plugin Action: Launching Chrome with {profile_id}")
            # Launch chrome directly forcing a specific profile bypassing the profile picker
            subprocess.Popen(f'start chrome --profile-directory="{profile_id}"', shell=True)
            return True
            
        return False

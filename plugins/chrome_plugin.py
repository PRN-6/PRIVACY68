import subprocess
import os
import logging
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugins.Chrome")

class ChromePlugin(BasePlugin):
    """
    Professional Chrome Browser Automation Plugin.
    Handles launching, URL navigation, and browser management.
    """

    def __init__(self):
        super().__init__()
        self.name = "Google Chrome Controller"
        self.version = "1.1.0"
        self.description = "Automates Google Chrome navigation and search."

        # Common paths for Chrome on Windows
        self.exe_paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(os.path.expanduser("~"), "AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
        ]

    def _find_chrome_exe(self) -> str:
        """Locates the chrome.exe binary on the system."""
        for path in self.exe_paths:
            if os.path.exists(path):
                return path
        return ""

    def open_browser(self) -> bool:
        """
        Launches Chrome to the default homepage.
        """
        return self.open_url("https://www.google.com")

    def open_url(self, url: str) -> bool:
        """
        Launches Chrome and navigates to the specified URL.
        """
        exe = self._find_chrome_exe()
        if not exe:
            logger.error("Chrome executable not found on this system.")
            return False

        try:
            subprocess.Popen([exe, url])
            self.log_action(f"open_url({url})", "SUCCESS")
            return True
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")
            return False

    def execute(self, action: str, **kwargs) -> bool:
        """
        Maps string actions to plugin methods.
        """
        if action == "open_url":
            url = kwargs.get("url", "https://www.google.com")
            return self.open_url(url)

        logger.warning(f"Action '{action}' not supported by ChromePlugin.")
        return False

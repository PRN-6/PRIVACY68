import logging
import os
import subprocess

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugins.Brave")


class BravePlugin(BasePlugin):
    """Launches Brave and opens URLs in the browser."""

    def __init__(self):
        super().__init__()
        self.id = "brave"
        self.name = "Brave Browser"
        self.version = "1.0.0"
        self.description = "Opens Brave Browser and navigates to URLs."
        self.exe_paths = [
            os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ),
            os.path.join(
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                "BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ),
            os.path.join(
                os.path.expanduser("~"),
                "AppData\\Local\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ),
        ]

    def _find_brave_exe(self) -> str:
        for path in self.exe_paths:
            if os.path.exists(path):
                return path
        return ""

    def open_url(self, url: str) -> bool:
        executable = self._find_brave_exe()
        if not executable:
            logger.error("Brave executable not found on this system.")
            return False

        try:
            subprocess.Popen([executable, url])
            self.log_action(f"open_url({url})", "SUCCESS")
            return True
        except OSError:
            logger.exception("Failed to launch Brave.")
            return False

    def open_browser(self) -> bool:
        return self.open_url("https://search.brave.com")

    def open_new_tab(self) -> bool:
        return self.open_url("about:blank")

    def execute(self, action: str, **kwargs) -> bool:
        if action == "open":
            return self.open_browser()
        if action == "open_new_tab":
            return self.open_new_tab()
        if action == "open_url":
            return self.open_url(kwargs.get("url", "https://search.brave.com"))

        logger.warning("Action '%s' not supported by BravePlugin.", action)
        return False

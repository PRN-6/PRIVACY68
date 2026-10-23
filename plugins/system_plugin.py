import os
import subprocess
import logging
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugins.System")

class SystemPlugin(BasePlugin):
    """
    Core Windows System Control Plugin.
    Handles volume, screenshots, and general OS lauching.
    """

    def __init__(self):
        super().__init__()
        self.name = "Windows System Controller"
        self.version = "1.1.0"
        self.description = "Basic OS level controls (Volume, Apps, etc)."

    def launch_app(self, app_name: str) -> bool:
        """Launches a system application via shell."""
        try:
            # Using 'start' command for Windows to resolve registered apps
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
            self.log_action(f"launch_app({app_name})", "SUCCESS")
            return True
        except Exception as e:
            logger.error(f"Failed to launch {app_name}: {e}")
            return False

    def execute(self, action: str, **kwargs) -> bool:
        if action == "launch":
            app = kwargs.get("app", "")
            return self.launch_app(app)

        logger.warning(f"Action '{action}' not supported by SystemPlugin.")
        return False

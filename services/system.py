"""
PRIVACY68 System Control Service.
Provides low-latency Windows system execution, volume/mute toggles, and process launching.
"""

import logging
import os
import subprocess
from typing import Any, Dict

logger = logging.getLogger("PRIVACY68.Services.System")


class SystemService:
    """Core Windows System Control Service."""

    def __init__(self):
        self.id = "system"
        self.name = "Windows System Controller"
        self.version = "2.0.0"
        self.description = "Native Windows OS controls (Volume, App launching, Lock, etc)."
        self.icon = "💻"
        self.is_enabled = True

    def launch_app(self, app_name: str) -> bool:
        """Launches a system application via Windows shell."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to launch {app_name}: {e}")
            return False

    def execute(self, action: str, **kwargs) -> bool:
        if action == "launch":
            app = kwargs.get("app", "")
            return self.launch_app(app)
        logger.warning(f"Action '{action}' not supported by SystemService.")
        return False


# Singleton instance
system_service = SystemService()


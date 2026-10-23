import subprocess
import os
import logging
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugins.WhatsApp")

class WhatsAppPlugin(BasePlugin):
    """
    WhatsApp Automation Plugin.
    Handles opening WhatsApp (Desktop or Web) and sending messages.
    """

    def __init__(self):
        super().__init__()
        self.name = "WhatsApp Controller"
        self.version = "1.0.0"
        self.description = "Automates WhatsApp communication."

    def open_whatsapp(self) -> bool:
        """
        Opens WhatsApp. Tries to launch via the registered 'whatsapp://' protocol
        which works for both WhatsApp Desktop and Web.
        """
        try:
            # Using the URI scheme is the most reliable way on Windows
            subprocess.Popen(["cmd", "/c", "start", "whatsapp://"])
            self.log_action("open_whatsapp", "SUCCESS")
            return True
        except Exception as e:
            logger.error(f"Failed to open WhatsApp: {e}")
            return False

    def send_message(self, contact_name: str, message: str) -> bool:
        """
        Sends a message to a specific contact.
        Note: This typically requires a browser-based approach or specific API.
        For this basic plugin, we use the web URL redirect.
        """
        # This is a simplification; real implementation would use a browser plugin
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={contact_name}&text={encoded_msg}"

        try:
            # We delegate the actual URL opening to the System or Chrome plugin logic
            # but for autonomy, we use the 'start' command.
            subprocess.Popen(["cmd", "/c", "start", url])
            self.log_action(f"send_message to {contact_name}", "SUCCESS")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    def execute(self, action: str, **kwargs) -> bool:
        if action == "open":
            return self.open_whatsapp()
        elif action == "send":
            contact = kwargs.get("contact", "")
            msg = kwargs.get("message", "")
            return self.send_message(contact, msg)

        logger.warning(f"Action '{action}' not supported by WhatsAppPlugin.")
        return False

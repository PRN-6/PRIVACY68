"""
Gmail Automation Plugin Adapter.
Bridges legacy BasePlugin interface to modern services.gmail.GmailService.
"""

from plugins.base_plugin import BasePlugin
from services.gmail import GmailService, gmail_service


class GmailPlugin(GmailService, BasePlugin):
    """Legacy plugin wrapper delegating to services.gmail.GmailService."""

    def __init__(self):
        BasePlugin.__init__(self)
        GmailService.__init__(self)
        self.category = "Communication"
        self.plugin_type = "Messaging & Email"
        self.is_builtin = True

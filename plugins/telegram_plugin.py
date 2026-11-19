"""
Telegram Gateway Adapter.
Bridges legacy BasePlugin interface to modern channels.telegram.TelegramChannel.
"""

from channels.telegram import TelegramChannel, telegram_channel
from plugins.base_plugin import BasePlugin
from utils.profile_manager import profile_manager


class TelegramPlugin(TelegramChannel, BasePlugin):
    """Legacy plugin wrapper delegating to channels.telegram.TelegramChannel."""

    def __init__(self):
        BasePlugin.__init__(self)
        TelegramChannel.__init__(self)
        self.category = "Communication"
        self.plugin_type = "Messaging & Remote"
        self.is_builtin = True

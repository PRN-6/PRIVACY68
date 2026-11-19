"""
PRIVACY68 Channels (Communication Gateways).
Handles out-of-band and live communication channels (e.g. Telegram Bot).
"""

from channels.telegram import TelegramChannel, telegram_channel

__all__ = ["TelegramChannel", "telegram_channel"]


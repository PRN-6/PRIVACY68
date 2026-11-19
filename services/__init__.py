"""
PRIVACY68 Services.
Native backend services and integrations (Gmail, Windows System, etc.).
"""

from services.gmail import GmailService, gmail_service
from services.system import SystemService, system_service

__all__ = ["GmailService", "gmail_service", "SystemService", "system_service"]


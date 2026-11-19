"""
PRIVACY68 Gmail Automation Service.
Provides fast web compose, inbox navigation, and automated draft preparation
with multi-account (authuser) support and natural language command parsing.
"""

import logging
import os
import re
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional

from utils.profile_manager import profile_manager

logger = logging.getLogger("PRIVACY68.Services.Gmail")


class GmailService:
    """Gmail Automation Service for PRIVACY68."""

    def __init__(self):
        self.id = "gmail"
        self.name = "Gmail Controller"
        self.version = "2.0.0"
        self.description = "Automates Gmail inbox navigation, drafting, and composing emails in the browser."
        self.icon = "✉️"
        self.category = "Communication"
        self.plugin_type = "Messaging & Email"
        self.is_builtin = True
        self.is_enabled = True
        self._user_email = ""

        self.fast_intents = {
            "open": ["open gmail", "launch gmail", "check gmail", "gmail inbox"],
            "compose": ["compose email", "write email", "send email", "draft email"],
        }
        self.descriptions = {
            "open": "Opens Gmail inbox in Chrome or the default browser.",
            "compose": "Pre-populates a new Gmail compose window with recipient, subject, and body.",
        }

    def get_user_email(self) -> str:
        """Retrieves the configured user Gmail address from profile preferences."""
        try:
            return profile_manager.get("gmail_user_email", "") or self._user_email
        except Exception:
            return self._user_email

    def set_user_email(self, email: str):
        """Sets and persists the user's Gmail address."""
        cleaned = email.strip()
        self._user_email = cleaned
        try:
            profile_manager.set("gmail_user_email", cleaned)
        except Exception as e:
            logger.warning(f"Could not persist user email: {e}")

    def build_compose_url(
        self,
        to: str = "",
        subject: str = "",
        body: str = "",
        user_email: Optional[str] = None,
    ) -> str:
        """
        Builds the direct Google Mail web compose URL.
        If user_email is provided or configured in profile, passes 'authuser'
        to automatically select the correct Google account.
        """
        params: Dict[str, str] = {"view": "cm", "fs": "1"}
        if to:
            params["to"] = to.strip()
        if subject:
            params["su"] = subject.strip()
        if body:
            params["body"] = body.strip()

        account = (user_email or self.get_user_email()).strip()
        if account:
            params["authuser"] = account
            return f"https://mail.google.com/mail/u/?{urllib.parse.urlencode(params)}"

        return f"https://mail.google.com/mail/?{urllib.parse.urlencode(params)}"

    def _open_in_browser(self, url: str) -> bool:
        """Opens a URL using Chrome or Brave if available, falling back to default browser."""
        try:
            return webbrowser.open(url)
        except Exception as e:
            logger.error(f"Error opening URL in browser: {e}")
            return False

    def open_inbox(self, user_email: Optional[str] = None) -> bool:
        """Opens the user's Gmail inbox."""
        account = (user_email or self.get_user_email()).strip()
        if account:
            url = f"https://mail.google.com/mail/u/?authuser={urllib.parse.quote(account)}#inbox"
        else:
            url = "https://mail.google.com/mail/u/0/#inbox"
        return self._open_in_browser(url)

    def compose_email(
        self,
        to: str = "",
        subject: str = "",
        body: str = "",
        user_email: Optional[str] = None,
    ) -> bool:
        """Opens Gmail with pre-filled compose window."""
        url = self.build_compose_url(to=to, subject=subject, body=body, user_email=user_email)
        return self._open_in_browser(url)

    def parse_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Parses a natural language instruction into Gmail action and parameters."""
        raw = command.strip()
        cmd = raw.lower().strip(".!?,")

        # Open patterns
        for pattern in [
            r"^open\s+gmail$",
            r"^launch\s+gmail$",
            r"^check\s+(?:my\s+)?gmail(?:\s+inbox)?$",
            r"^go\s+to\s+gmail$",
            r"^gmail\s+inbox$",
        ]:
            if re.search(pattern, cmd):
                return {"action": "open", "kwargs": {}, "requires_confirmation": False}

        # Compose patterns
        is_compose = bool(
            re.search(r"^(?:compose|write|send|draft)\s+(?:an?\s+)?(?:new\s+)?(?:email|mail)", cmd)
            or re.search(r"^email\s+", cmd)
            or re.search(r"^send\s+email", cmd)
        )
        if not is_compose:
            return None

        to = ""
        m_to = re.search(r"\bto\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", raw, re.IGNORECASE)
        if m_to:
            to = m_to.group(1).strip()
        else:
            m_to_name = re.search(r"\bto\s+([a-zA-Z0-9_-]+)(?:\s+(?:about|with|saying|subject|body)|$)", raw, re.IGNORECASE)
            if m_to_name:
                to = m_to_name.group(1).strip()

        subject = ""
        m_subj_quotes = re.search(r"\b(?:subject|about)\s+['\"]([^'\"]+)['\"]", raw, re.IGNORECASE)
        if m_subj_quotes:
            subject = m_subj_quotes.group(1).strip()
        else:
            m_subj = re.search(r"\b(?:subject|about)\s+([^,]+?)(?:\s+(?:and\s+body|saying|message|body)|$)", raw, re.IGNORECASE)
            if m_subj:
                subject = m_subj.group(1).strip()

        body = ""
        m_body_quotes = re.search(r"\b(?:body|saying|message)\s+['\"]([^'\"]+)['\"]", raw, re.IGNORECASE)
        if m_body_quotes:
            body = m_body_quotes.group(1).strip()
        else:
            m_body = re.search(r"\b(?:body|saying|message)\s+(.*)$", raw, re.IGNORECASE)
            if m_body:
                body = m_body.group(1).strip()

        return {
            "action": "compose",
            "kwargs": {"to": to, "subject": subject, "body": body},
            "requires_confirmation": False,
        }

    def execute(self, action: str, **kwargs) -> bool:
        """Executes a Gmail action."""
        if action == "open":
            return self.open_inbox(**kwargs)
        elif action == "compose":
            return self.compose_email(
                to=kwargs.get("to", ""),
                subject=kwargs.get("subject", ""),
                body=kwargs.get("body", ""),
                user_email=kwargs.get("user_email"),
            )
        logger.warning(f"Action '{action}' not supported by GmailService.")
        return False


# Singleton instance
gmail_service = GmailService()

import logging
import os
import re
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugins.Gmail")


class GmailPlugin(BasePlugin):
    """
    Gmail Automation Plugin for PRIVACY68.
    Provides fast web compose, inbox navigation, and automated draft preparation
    with multi-account (authuser) support and natural language command parsing.
    """

    def __init__(self):
        super().__init__()
        self.id = "gmail"
        self.name = "Gmail Controller"
        self.version = "1.0.0"
        self.description = "Automates Gmail inbox navigation, drafting, and composing emails in the browser."
        self.icon = "✉️"
        self.category = "Communication"
        self.plugin_type = "Messaging & Email"
        self.is_builtin = True
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
            from plugins.profile_manager import profile_manager
            return profile_manager.get("gmail_user_email", "") or self._user_email
        except Exception:
            return self._user_email

    def set_user_email(self, email: str):
        """Sets and persists the user's Gmail address."""
        cleaned = email.strip()
        self._user_email = cleaned
        try:
            from plugins.profile_manager import profile_manager
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
            from plugins.manager import plugin_manager

            chrome = plugin_manager.get_plugin("chrome")
            if chrome and getattr(chrome, "is_enabled", True) and hasattr(chrome, "open_url"):
                try:
                    if chrome.open_url(url):
                        return True
                except Exception:
                    pass

            brave = plugin_manager.get_plugin("brave")
            if brave and getattr(brave, "is_enabled", True) and hasattr(brave, "open_url"):
                try:
                    if brave.open_url(url):
                        return True
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not route URL through browser plugin: {e}")

        try:
            return bool(webbrowser.open(url))
        except Exception as exc:
            logger.error(f"Failed to open URL in browser: {exc}")
            return False

    def open_inbox(self, user_email: Optional[str] = None) -> bool:
        """Opens the Gmail inbox in Chrome or the default browser."""
        account = (user_email or self.get_user_email()).strip()
        if account:
            encoded_account = urllib.parse.quote(account)
            url = f"https://mail.google.com/mail/u/?authuser={encoded_account}#inbox"
        else:
            url = "https://mail.google.com/mail/u/0/#inbox"

        success = self._open_in_browser(url)
        self.log_action("open_inbox", "SUCCESS" if success else "FAILED")
        return success

    def open(self) -> bool:
        """Alias for open_inbox() adhering to standard plugin app interface."""
        return self.open_inbox()

    def compose_email(
        self,
        to: str = "",
        subject: str = "",
        body: str = "",
        user_email: Optional[str] = None,
    ) -> bool:
        """
        Launches browser with Gmail compose prefilled with recipient, subject, and content.
        """
        url = self.build_compose_url(to=to, subject=subject, body=body, user_email=user_email)
        success = self._open_in_browser(url)
        self.log_action(f"compose_email(to={to})", "SUCCESS" if success else "FAILED")
        return success

    def parse_command(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses natural language speech or text commands intended for Gmail.
        Returns a dict with 'action', 'kwargs', and 'description' if recognized, else None.
        """
        clean = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", text.strip()).strip(".!?, \t\n")
        low = clean.lower()

        # 1. Open Inbox patterns
        open_patterns = [
            r"^(?:open|launch|start|check|go to)\s+(?:my\s+)?(?:the\s+)?(?:google\s+)?gmail(?:\s+inbox)?$",
            r"^check\s+(?:my\s+)?(?:gmail\s+)?(?:emails?|inbox)$",
        ]
        for pat in open_patterns:
            if re.match(pat, low):
                return {
                    "action": "open",
                    "kwargs": {},
                    "description": "open Gmail inbox",
                }

        # 2. Compose / Draft / Send email patterns
        m_init = re.match(
            r"^(?:compose|write|send|draft|create)\s+(?:an?\s+)?(?:new\s+)?(?:email|gmail|mail)\b(.*)$",
            clean,
            re.IGNORECASE,
        )
        m_email_verb = re.match(r"^email\s+(.*)$", clean, re.IGNORECASE)

        remainder = ""
        if m_init:
            remainder = m_init.group(1).strip()
        elif m_email_verb:
            remainder = "to " + m_email_verb.group(1).strip()
        else:
            return None

        if not remainder:
            return {
                "action": "compose",
                "kwargs": {"to": "", "subject": "", "body": ""},
                "description": "compose new email",
            }

        to = ""
        subject = ""
        body = ""

        # Delimiters for body / content: and body, body, and content, content, and message, message, saying
        body_match = re.search(
            r"\s+(?:and\s+)?(?:body|content|message|saying)\s+(.+)$",
            remainder,
            re.IGNORECASE,
        )
        if body_match:
            body = body_match.group(1).strip()
            remainder = remainder[:body_match.start()].strip()

        # Delimiters for subject: with subject, subject, about
        subj_match = re.search(
            r"\s+(?:(?:with\s+)?subject|about)\s+(.+)$",
            remainder,
            re.IGNORECASE,
        )
        if subj_match:
            subject = subj_match.group(1).strip()
            remainder = remainder[:subj_match.start()].strip()

        # Remaining should be 'to <recipient>' or just '<recipient>'
        to_match = re.search(r"^(?:to\s+)?(.+)$", remainder, re.IGNORECASE)
        if to_match:
            to = to_match.group(1).strip()

        desc_parts = []
        if to:
            desc_parts.append(f"to {to}")
        if subject:
            desc_parts.append(f"with subject \"{subject}\"")
        desc = "compose email " + " ".join(desc_parts) if desc_parts else "compose new email"

        return {
            "action": "compose",
            "kwargs": {"to": to, "subject": subject, "body": body},
            "description": desc,
        }

    def execute(self, action: str, **kwargs) -> bool:
        """
        Executes action directly on GmailPlugin.
        """
        action_clean = (action or "").strip().lower()
        if action_clean in ("open", "open_inbox", "inbox"):
            return self.open_inbox(kwargs.get("user_email"))
        elif action_clean in ("compose", "compose_email", "send", "draft"):
            return self.compose_email(
                to=kwargs.get("to", ""),
                subject=kwargs.get("subject", ""),
                body=kwargs.get("body", ""),
                user_email=kwargs.get("user_email"),
            )

        logger.warning(f"Action '{action}' not supported by GmailPlugin.")
        return False


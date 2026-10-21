import logging
import os
import subprocess
import time
import re
import json
import ctypes
from typing import Callable, Dict, List, Tuple, Optional
from plugins.base_plugin import BasePlugin
from plugins.win_utils import kill_process

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    ollama = None
    HAS_OLLAMA = False

user32 = ctypes.windll.user32
logger = logging.getLogger("PRIVACY68.Plugin.WhatsApp")

# Virtual key codes
VK_CONTROL = 0x11
VK_V = 0x56
VK_DOWN = 0x28
KEYEVENTF_KEYUP = 0x0002

def _press_key(vk: int):
    """Sends keydown and keyup for a single virtual key."""
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

def _press_paste():
    """Sends Ctrl+V to paste from clipboard."""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

class WhatsAppPlugin(BasePlugin):
    """
    Standalone WhatsApp Desktop Plugin for PRIVACY68.
    Provides launching, closing, and AI-powered voice messaging.
    """
    id = "whatsapp"
    name = "WhatsApp Desktop"
    icon = "💬"
    description = "Control WhatsApp Desktop: launch app, close app, and send messages."
    version = "1.5.0"
    author = "Community Plugin"
    is_builtin = False
    category = "Communication"
    plugin_type = "Messaging & Chat"

    # ---------- Contacts Storage ---------- #
    _CONTACTS_PATH = os.path.join(
        os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68", "whatsapp_contacts.json"
    )
    # Legacy path migrated from older builds (was %APPDATA%/SANA)
    _LEGACY_CONTACTS_PATH = os.path.join(
        os.getenv("APPDATA", os.path.expanduser("~")), "SANA", "whatsapp_contacts.json"
    )

    @classmethod
    def load_contacts(cls) -> List[Dict[str, str]]:
        """Returns the saved contacts list: [{name, alias, phone}, ...]"""
        try:
            if os.path.exists(cls._CONTACTS_PATH):
                with open(cls._CONTACTS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            # Legacy fallback: read (and auto-migrate) contacts from %APPDATA%/SANA
            if os.path.exists(cls._LEGACY_CONTACTS_PATH):
                with open(cls._LEGACY_CONTACTS_PATH, "r", encoding="utf-8") as f:
                    contacts = json.load(f)
                cls.save_contacts(contacts)
                return contacts
        except Exception as e:
            logger.warning(f"Could not load WhatsApp contacts: {e}")
        return []

    @classmethod
    def save_contacts(cls, contacts: List[Dict[str, str]]) -> bool:
        """Saves the contacts list to disk."""
        try:
            os.makedirs(os.path.dirname(cls._CONTACTS_PATH), exist_ok=True)
            with open(cls._CONTACTS_PATH, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Could not save WhatsApp contacts: {e}")
            return False

    def _resolve_contact(self, spoken_name: str) -> str:
        """
        Fuzzy-matches a spoken name against the saved contacts list.
        Returns the best-matching saved contact name, or the original spoken
        name if no good match is found (so it still searches WhatsApp normally).
        """
        import difflib
        contacts = self.load_contacts()
        if not contacts:
            return spoken_name

        spoken_lower = spoken_name.lower().strip()
        best_score = 0.0
        best_name = spoken_name

        for c in contacts:
            # Check against 'name' and any 'alias' the user set
            candidates = [c.get("name", "")]
            alias = c.get("alias", "").strip()
            if alias:
                candidates.append(alias)

            for cand in candidates:
                if not cand:
                    continue
                score = difflib.SequenceMatcher(None, spoken_lower, cand.lower()).ratio()
                # Also check if spoken name is a prefix/substring (catches "prinson" vs "Prinson Kumar")
                if spoken_lower in cand.lower() or cand.lower().startswith(spoken_lower):
                    score = max(score, 0.85)
                if score > best_score:
                    best_score = score
                    best_name = c.get("name", spoken_name)  # return the saved display name

        if best_score >= 0.65:
            logger.info(f"Contact resolved: '{spoken_name}' -> '{best_name}' (score: {best_score:.2f})")
            return best_name
        else:
            logger.info(f"No contact match for '{spoken_name}' (best: '{best_name}' @ {best_score:.2f}). Using spoken name.")
            return spoken_name

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "whatsapp.open": self.open_app,
            "whatsapp.close": self.close_app,
            "whatsapp.new_chat": self.new_chat,
            "whatsapp.send_message": self.send_message,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "whatsapp.open": [
                "open whatsapp",
                "launch whatsapp",
                "start whatsapp",
                "open whats app",
                "launch whats app",
                "open wa",
                "launch wa",
            ],
            "whatsapp.close": [
                "close whatsapp",
                "exit whatsapp",
                "quit whatsapp",
                "terminate whatsapp",
                "close whats app",
                "close wa",
            ],
            "whatsapp.new_chat": [
                "new chat in whatsapp",
                "start new chat in whatsapp",
                "whatsapp new chat",
            ],
            "whatsapp.send_message": [
                "send message to",
                "send a message to",
                "send whatsapp message to",
                "message someone on whatsapp",
                "text someone on whatsapp",
                "send hi to mom",
                "send message to mom",
                "send message to dad",
                "open chat with",
                "tell mom on whatsapp",
                "open whatsapp and send message",
            ]
        }

    @property
    def pattern_intents(self) -> Dict[str, List[str]]:
        """
        Sentence SHAPES for messaging, so any natural phrasing routes here
        instead of falling through to a local LLM that cannot choose between
        140 tools.

        The exact-phrase map above can only ever fire on the strings it
        literally lists. These patterns cover the generalisable shapes:

          "send <body> to <contact>"
          "send a message to <contact> [saying <body>]"
          "tell <contact> [that] <body>"
          "message <contact> [saying <body>]"
          "text <contact> [saying <body>]"
          "chat with <contact>"
          "open a chat with <contact>"

        Order matters — the first match wins, so the shapes that carry a
        message body come before the bare "open a chat" shape.
        """
        return {
            "whatsapp.send_message": [
                # "send hi to mom", "send a message to mom saying that I am late"
                r"\bsend\s+(?:a\s+|an\s+|the\s+|whatsapp\s+)?(?:message|text|msg|note)?\s*"
                r"(?:to\s+)?(?!\b(?:message|text|msg|note)\b)[a-z0-9' .-]+\s+to\s+[a-z0-9' .-]+",

                # "message mom on whatsapp saying hi", "text john saying hi"
                r"\b(?:message|text|msg)\s+[a-z0-9' .-]+?"
                r"(?:\s+on\s+whats\s*app|\s+on\s+whatsapp|\s+in\s+whatsapp)?"
                r"(?:\s+(?:saying|that\s+saying|which\s+says)\b.*)?$",

                # "tell mom that I will be late", "tell mom on whatsapp I am busy"
                r"\btell\s+[a-z0-9' .-]+?"
                r"(?:\s+on\s+whats\s*app|\s+on\s+whatsapp|\s+in\s+whatsapp)?"
                r"(?:\s+(?:that|saying)\b.*)?$",

                # "open a chat with mom", "chat with john"
                r"\b(?:open\s+(?:a\s+)?chat\s+with|chat\s+with|start\s+chat\s+with)\s+[a-z0-9' .-]+",
            ],
            "whatsapp.new_chat": [
                r"\bnew\s+chat\s+in\s+whats\s*app\b",
                r"\bstart\s+a\s+new\s+chat\s+in\s+whats\s*app\b",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "whatsapp.open": "- whatsapp.open: Launch or open the WhatsApp Desktop application.",
            "whatsapp.close": "- whatsapp.close: Force close or exit WhatsApp application.",
            "whatsapp.new_chat": "- whatsapp.new_chat: Start a new conversation in WhatsApp.",
            "whatsapp.send_message": "- whatsapp.send_message: Send a message or open a chat with a specific person on WhatsApp (e.g. 'send message to mom', 'tell dad I will be late', 'send hi to mom').",
        }

    # Cached at runtime — populated on first launch attempt
    _resolved_launch_method: Optional[str] = None  # 'uwp', 'exe', 'uri'
    _resolved_uwp_pfn: Optional[str] = None
    _resolved_exe_path: Optional[str] = None

    # ── Window identification ────────────────────────────────────────────────
    # The Store (UWP) build runs as "WhatsApp.Root.exe" (the launcher process
    # is "WhatsApp.exe"), while the standalone build runs as "WhatsApp.exe".
    # Both are listed so the app is found on either install. Title hints
    # cover builds that use a branded title instead.
    _PROCESS_HINTS = ("whatsapp.exe", "whatsapp.root.exe")
    _WINDOW_TITLE_HINTS = ("whatsapp",)

    # Common standalone (non-Store) WhatsApp EXE locations
    _STANDALONE_EXE_GLOBS = [
        os.path.join(os.getenv("LOCALAPPDATA", ""), "WhatsApp", "WhatsApp.exe"),
        os.path.join(os.getenv("APPDATA", ""),    "WhatsApp", "WhatsApp.exe"),
        r"C:\Program Files\WhatsApp\WhatsApp.exe",
        r"C:\Program Files (x86)\WhatsApp\WhatsApp.exe",
    ]

    @classmethod
    def _detect_launch_method(cls):
        """
        Auto-detects the best way to launch WhatsApp on this machine.
        Result is cached so detection only runs once per session.
        """
        if cls._resolved_launch_method:
            return  # already detected

        # 1. Try UWP (Microsoft Store install) — query dynamically via PowerShell
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-AppxPackage -Name '*WhatsApp*' | Select-Object -ExpandProperty PackageFamilyName"],
                capture_output=True, text=True, timeout=6
            )
            pfn = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
            if pfn:
                cls._resolved_uwp_pfn = pfn
                cls._resolved_launch_method = "uwp"
                logger.info(f"WhatsApp detected as UWP app. PFN: {pfn}")
                return
        except Exception as e:
            logger.debug(f"UWP detection failed: {e}")

        # 2. Try common standalone EXE paths
        for exe_path in cls._STANDALONE_EXE_GLOBS:
            if os.path.isfile(exe_path):
                cls._resolved_exe_path = exe_path
                cls._resolved_launch_method = "exe"
                logger.info(f"WhatsApp detected as standalone EXE: {exe_path}")
                return

        # 3. Fall back to URI scheme (registry-based)
        cls._resolved_launch_method = "uri"
        logger.warning("WhatsApp: could not detect UWP or EXE install. Falling back to URI scheme.")

    def _launch_whatsapp_exe(self) -> bool:
        """Launches WhatsApp Desktop using the best available method for this machine."""
        self._detect_launch_method()

        if self._resolved_launch_method == "uwp":
            try:
                subprocess.Popen(
                    f'explorer.exe "shell:AppsFolder\\{self._resolved_uwp_pfn}!App"',
                    shell=True
                )
                logger.info("WhatsApp launched via UWP shell:AppsFolder")
                return True
            except Exception as e:
                logger.warning(f"UWP launch failed: {e}. Falling back...")

        if self._resolved_launch_method == "exe" and self._resolved_exe_path:
            try:
                subprocess.Popen([self._resolved_exe_path])
                logger.info(f"WhatsApp launched via EXE: {self._resolved_exe_path}")
                return True
            except Exception as e:
                logger.warning(f"EXE launch failed: {e}. Falling back to URI...")

        # Next fallback: URI scheme
        try:
            subprocess.Popen("start whatsapp:", shell=True)
            logger.info("WhatsApp launched via URI scheme")
            return True
        except Exception as e:
            logger.warning(f"URI launch failed: {e}. Falling back to browser...")

        # Ultimate fallback: WhatsApp Web in browser
        try:
            import webbrowser
            webbrowser.open("https://web.whatsapp.com")
            logger.info("WhatsApp launched via browser fallback (https://web.whatsapp.com)")
            return True
        except Exception as e:
            logger.error(f"All WhatsApp launch methods failed: {e}")
            return False

    def open_app(self, text: str) -> bool:
        """
        Opens WhatsApp Desktop.

        If it is already running, the existing window is raised instead of
        starting a second instance — "open whatsapp" twice in a row should
        not leave two windows behind.
        """
        logger.info("Plugin Action: Launching WhatsApp Desktop")

        from computer_use.app_focus import AppState, ensure_active, get_state

        state = get_state(
            "whatsapp",
            title_hints=self._WINDOW_TITLE_HINTS,
            process_hints=self._PROCESS_HINTS,
        )
        if state == AppState.ACTIVE:
            logger.info("WhatsApp is already open and focused — nothing to launch.")
            return True

        return ensure_active(
            "whatsapp",
            launch=self._launch_whatsapp_exe,
            title_hints=self._WINDOW_TITLE_HINTS,
            process_hints=self._PROCESS_HINTS,
            # "open whatsapp" only needs the app STARTED — the window may
            # still be appearing, and the next command will wait for it.
            require_window=False,
        )

    def close_app(self, text: str) -> bool:
        logger.info("Plugin Action: Force Closing WhatsApp")
        kill_process("WhatsApp*")
        kill_process("WhatsApp.exe")
        kill_process("WhatsApp.Root.exe")
        return True

    def new_chat(self, text: str) -> bool:
        logger.info("Plugin Action: Triggering new chat in WhatsApp")
        self._focus_whatsapp()
        import pyautogui
        pyautogui.hotkey("ctrl", "n")
        return True

    def _set_clipboard(self, value: str) -> bool:
        """Copies text to the Windows clipboard via PowerShell."""
        try:
            safe = value.replace("'", "''")
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{safe}'"],
                check=True, capture_output=True
            )
            return True
        except Exception as e:
            logger.error(f"Clipboard error: {e}")
            return False

    def _focus_whatsapp(self) -> bool:
        """
        Makes sure WhatsApp Desktop is running AND is the foreground window.

        The key behaviour this replaces: the old version ALWAYS relaunched the
        app and slept two seconds, even when WhatsApp was already open and
        focused. That spawned a second instance, stole focus from whatever the
        user was doing, and added two seconds of dead air to every message.

        Now the app state decides:
          already active      -> return immediately, nothing is launched
          running, background -> raise the existing window
          not running         -> launch it, wait for the window, raise it
        """
        from computer_use.app_focus import AppState, ensure_active, get_state

        state = get_state(
            "whatsapp",
            title_hints=self._WINDOW_TITLE_HINTS,
            process_hints=self._PROCESS_HINTS,
        )
        logger.info(f"WhatsApp state before action: {AppState.describe(state)}")

        focused = ensure_active(
            "whatsapp",
            launch=self._launch_whatsapp_exe,
            title_hints=self._WINDOW_TITLE_HINTS,
            process_hints=self._PROCESS_HINTS,
        )

        if not focused:
            logger.warning("WhatsApp could not be brought to the foreground.")

        return focused

    def _parse_with_llm(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Uses local Ollama (qwen2.5) to reliably extract recipient and message body."""
        if not HAS_OLLAMA:
            return None, None

        try:
            system_prompt = (
                "Extract the contact name and message body from a WhatsApp voice command.\n"
                "Return ONLY valid JSON: {\"contact\": \"...\", \"message\": \"...\"}\n"
                "If the user did NOT specify a message to send (e.g. they only said 'send message to [name]' or 'open chat with [name]'), set \"message\": null.\n\n"
                "Examples:\n"
                "User: \"send hi to mom\"\n"
                "{\"contact\": \"mom\", \"message\": \"hi\"}\n"
                "User: \"send message to mom\"\n"
                "{\"contact\": \"mom\", \"message\": null}\n"
                "User: \"open whatsapp and send message to mom saying that i will be late\"\n"
                "{\"contact\": \"mom\", \"message\": \"i will be late\"}\n"
                "User: \"tell dad that dinner is ready\"\n"
                "{\"contact\": \"dad\", \"message\": \"dinner is ready\"}\n"
                "User: \"send a message to rahul\"\n"
                "{\"contact\": \"rahul\", \"message\": null}"
            )

            res = ollama.chat(
                model='qwen2.5:0.5b',
                keep_alive='60s',
                options={'temperature': 0.0, 'num_ctx': 512},
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'User: "{text}"'}
                ]
            )

            content = res.get('message', {}).get('content', '').strip()
            if "```" in content:
                content = re.sub(r"^```(?:json)?", "", content, flags=re.MULTILINE)
                content = content.replace("```", "").strip()

            data = json.loads(content)
            contact = data.get("contact")
            message = data.get("message")
            if contact:
                contact = str(contact).strip(".!?, \t\n")
                if message is not None:
                    message = str(message).strip()
                    if message.lower() in ("null", "none", ""):
                        message = None
                    elif message.lower() not in text.lower():
                        message = None
                logger.info(f"Ollama parsed WhatsApp command: contact='{contact}', message='{message}'")
                return contact, message
        except Exception as e:
            logger.warning(f"Ollama WhatsApp extraction skipped ({e}). Using regex fallback.")
        return None, None

    # ── Lexicon for the parser ────────────────────────────────────────────────

    # Verbs that introduce a message.
    _SEND_VERBS = frozenset({"send", "tell", "text", "message", "msg", "write"})
    # Nouns that mean "a message" rather than the message CONTENT.
    _MESSAGE_NOUNS = frozenset({"message", "msg", "text", "note", "word", "msg"})
    # Words that introduce the message body.
    # "with" and "about" are deliberately NOT here: they appear in "open a
    # chat with mom", where the word after them is the CONTACT, not a body.
    _BODY_MARKERS = (
        "saying that", "saying", "that says", "which says", "that",
    )
    # Platform filler that may sit between the contact and the body.
    _PLATFORM_PHRASES = (
        "on whatsapp", "on whats app", "in whatsapp", "in whats app",
        "via whatsapp", "via whats app", "through whatsapp",
        "on whatsapp desktop", "over whatsapp",
    )
    # Words that describe the ACTION rather than the contact.
    _CONTACT_STOP_WORDS = frozenset({
        "send", "tell", "message", "text", "msg", "note", "word", "chat",
        "open", "start", "launch", "go", "new", "a", "an", "the", "to", "in",
        "on", "via", "and", "that", "saying", "please", "can", "you", "with",
        "whatsapp", "whats", "app", "desktop", "say", "says", "for", "from",
        "conversation", "write", "going",
    })

    def _strip_platform(self, text: str) -> str:
        """Removes platform filler ("on whatsapp") from anywhere in a phrase."""
        cleaned = text
        for phrase in self._PLATFORM_PHRASES:
            cleaned = re.sub(
                rf"\s+{re.escape(phrase)}\b",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )
        return cleaned

    def _clean_contact(self, candidate: str) -> str:
        """Strips command words and platform filler from a contact name."""
        if not candidate:
            return ""

        cleaned = self._strip_platform(candidate)

        # Drop leading "chat with" / "conversation with" ("open chat with mom").
        cleaned = re.sub(
            r"^\s*(?:please\s*)?(?:can\s+you\s*)?"
            r"(?:open\s+|start\s+|launch\s+|go\s+to\s+)?"
            r"(?:a\s+|an\s+|the\s+)?(?:new\s+)?"
            r"(?:chat|conversation)\s+with\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # Drop leading verb words ("send mom" -> "mom").
        cleaned = re.sub(
            r"^\s*(?:send|tell|text|message|msg|write)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip(".!?, \t\n")

        # Remove stop words that survived, but never empty the name entirely.
        words = [w for w in cleaned.split() if w.lower() not in self._CONTACT_STOP_WORDS]
        if words:
            cleaned = " ".join(words)

        return cleaned.strip(".!?, \t\n")

    def _split_body(self, text: str) -> Tuple[str, str]:
        """
        Splits a phrase into (head, body) at the first body marker.

        "saying that dinner was great" -> ("", "dinner was great")
        "that I will be late"          -> ("", "I will be late")
        """
        low = text.lower()
        for marker in self._BODY_MARKERS:
            idx = low.find(marker)
            if idx == -1:
                continue
            # Only treat it as a marker at a word boundary.
            if idx > 0 and text[idx - 1].isalnum():
                continue
            head = text[:idx].strip(" ,")
            body = text[idx + len(marker):].strip(" ,.!?\t\n")
            return head, body
        return text.strip(" ,"), ""

    def _parse_contact_and_message(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts (contact_name, message_body) from a spoken command.

        An ordered rule set, applied most-specific-first. Each rule covers one
        natural way of saying "message someone":

          1. EXPLICIT SEPARATOR — "… to mom SAYING hi", "… to mom THAT hi"
          2. "send <body> to <contact>"
          3. "send [a] message to <contact> [saying <body>]"
          4. "tell <contact> [that] <body>"
          5. "message <contact> [saying <body>]"
          6. "open a chat with <contact>"
          7. Local LLM, when one is running
          8. Last resort: strip the command words and treat what is left as
             the contact name.

        The rules are tried in this order because the earlier ones are
        unambiguous, while the later ones accept more shapes and so can
        mis-capture. The first rule that produces a contact wins.
        """
        raw = (text or "").strip()
        if not raw:
            return None, None

        # A leading "open whatsapp and" is scaffolding, not part of the request.
        raw = re.sub(
            r"^\s*(?:open|launch|start)\s+(?:whats\s*app|whatsapp)\s+and\s+",
            "",
            raw,
            flags=re.IGNORECASE,
        )
        raw = self._strip_platform(raw).strip()
        if not raw:
            return None, None

        low = raw.lower()

        # ── Rule 1: explicit separator ───────────────────────────────────────
        # "send message to mom saying that dinner was great"
        # "message john on whatsapp that I am busy"
        head, body = self._split_body(raw)
        if body:
            contact = self._contact_from_head(head)
            if contact:
                return contact, (body.strip(".!?, \t\n") or None)

        # ── Rule 2: "send <body> to <contact>" ───────────────────────────────
        # "send hi to mom", "send i will be late to dad"
        # The contact is what follows the "to" that introduces the recipient.
        if low.startswith("send ") or low.startswith("text ") or low.startswith("write "):
            split = self._split_recipient(raw)
            if split is not None:
                body_text, contact_part = split
                # "send a message to mom" — "a message" is a noun, not a body.
                if body_text and not self._is_message_noun(body_text):
                    contact = self._clean_contact(contact_part)
                    if contact:
                        return contact, body_text.strip(".!?, \t\n")

        # ── Rule 3: "send [a] message to <contact> [saying <body>]" ─────────
        # "send message to mom", "send a message to mom saying that I am late"
        to_msg = re.match(
            r"^\s*send\s+(?:a\s+|an\s+|the\s+|whatsapp\s+)?"
            r"(?:message|text|msg|note|word)\s+to\s+(?P<contact>.+)$",
            raw,
            re.IGNORECASE,
        )
        if to_msg:
            contact_part, body_part = self._split_body(to_msg.group("contact"))
            contact = self._clean_contact(contact_part)
            if contact:
                return contact, (body_part.strip(".!?, \t\n") or None)

        # ── Rule 4: "tell <contact> [that] <body>" ───────────────────────────
        # "tell mom hi"  -> contact "mom", body "hi"
        # "tell dad that dinner is ready" -> contact "dad", body "dinner is ready"
        tell = re.match(
            r"^\s*tell\s+(?P<rest>.+)$",
            raw,
            re.IGNORECASE,
        )
        if tell:
            rest = tell.group("rest")
            contact_part, body_part = self._split_body(rest)
            if not body_part:
                # No explicit marker — the contact is the FIRST word and the
                # rest is the message ("tell mom hi").
                parts = contact_part.split(None, 1)
                if len(parts) == 2:
                    contact_part, body_part = parts[0], parts[1]
            contact = self._clean_contact(contact_part)
            if contact:
                return contact, (body_part.strip(".!?, \t\n") or None)

        # ── Rule 5: "message <contact> [saying <body>]" ──────────────────────
        # "message mom saying hi", "text john saying hi"
        msg = re.match(
            r"^\s*(?:send\s+)?(?:a\s+|an\s+|the\s+|whatsapp\s+)?"
            r"(?:message|text|msg)\s+(?P<rest>.+)$",
            raw,
            re.IGNORECASE,
        )
        if msg:
            contact_part, body_part = self._split_body(msg.group("rest"))
            contact = self._clean_contact(contact_part)
            if contact:
                return contact, (body_part.strip(".!?, \t\n") or None)

        # ── Rule 6: "open a chat with <contact>" ────────────────────────────
        chat = re.match(
            r"^\s*(?:open\s+)?(?:a\s+|an\s+|the\s+)?(?:new\s+)?"
            r"(?:chat|conversation)\s+with\s+(?P<contact>.+)$",
            raw,
            re.IGNORECASE,
        )
        if chat:
            contact = self._clean_contact(chat.group("contact"))
            if contact:
                return contact, None

        # ── Rule 7: local LLM, when one is available ─────────────────────────
        contact, message = self._parse_with_llm(raw)
        if contact:
            return contact, message

        # ── Rule 8: last resort — strip the command words ────────────────────
        fallback = self._clean_contact(raw)
        return (fallback or None), None

    def _is_message_noun(self, phrase: str) -> bool:
        """True when a phrase is just "a message" / "message" rather than content."""
        words = [w for w in re.split(r"\W+", phrase.lower()) if w]
        if not words:
            return True
        return all(w in self._MESSAGE_NOUNS or w in ("a", "an", "the") for w in words)

    def _last_top_level_to(self, low: str) -> int:
        """
        Index of the last " to " in the text, or -1.

        The last "to" is the one that introduces the recipient: "send invite
        to mom to the party" -> the contact is "mom to the party" only if the
        trailing part is a name, so this returns the LAST one, and the caller
        cleans the remainder. A trailing "to the party" is not a contact, so
        the caller validates the result and falls through when it is not a
        plausible name.
        """
        idx = low.rfind(" to ")
        if idx == -1:
            return -1
        # A "to" that starts the text cannot introduce a recipient.
        return idx if idx > 0 else -1

    def _split_recipient(self, raw: str) -> Optional[Tuple[str, str]]:
        """
        Splits "send <body> to <contact>" into (body, contact).

        The "to" that introduces the recipient is the FIRST one after the
        verb, not the last: in "send invite to mom to the party" the body is
        "invite" and the contact is "mom to the party" is wrong — the
        recipient is "mom" and the trailing "to the party" belongs to the
        body.

        Because both readings are possible, the FIRST "to" is used, and the
        remaining text is cleaned by the caller. When the text after the
        first "to" still contains a "to", the trailing part is appended back
        to the body so the message text is not lost.
        """
        low = raw.lower()
        m = re.search(r"\bto\b", low)
        if not m:
            return None

        idx = m.start()
        before = raw[:idx].strip(" ,")
        after = raw[m.end():].strip(" ,")

        if not before or not after:
            return None

        # Strip the leading verb from the body.
        before = re.sub(r"^\s*(?:send|text|write)\s+", "", before, flags=re.IGNORECASE).strip(" ,")

        return before, after

    def _contact_from_head(self, head: str) -> str:
        """
        Pulls the contact name out of the part of the command BEFORE the
        separator ("send message to mom" -> "mom").
        """
        if not head:
            return ""

        # Prefer the text after the last "to" — that is the contact.
        to_split = re.split(r"\bto\b", head, flags=re.IGNORECASE)
        candidate = to_split[-1] if len(to_split) > 1 else head
        return self._clean_contact(candidate)

    def send_message(self, text: str) -> bool:
        contact_name, message_body = self._parse_contact_and_message(text)
        if not contact_name:
            logger.warning(f"Could not extract contact name from: '{text}'")
            return False

        # Resolve spoken name against saved contacts for better accuracy
        resolved_name = self._resolve_contact(contact_name)
        logger.info(f"WhatsApp target: spoken='{contact_name}' -> resolved='{resolved_name}', message: '{message_body}'")

        # 1. Make sure WhatsApp is running AND focused. When it is already the
        #    active window this does nothing at all — no relaunch, no delay.
        if not self._focus_whatsapp():
            logger.error("WhatsApp is not in the foreground — aborting send.")
            return False

        import pyautogui

        # 2. Open New Chat (Ctrl+N)
        pyautogui.hotkey("ctrl", "n")
        time.sleep(1.0)

        # 3. Paste resolved contact name and search
        if not self._set_clipboard(resolved_name):
            return False
        _press_paste()
        time.sleep(1.8)

        # Select first result & open chat
        _press_key(VK_DOWN)
        time.sleep(0.2)
        pyautogui.press("enter")

        # 4. Type and send message (if provided)
        if message_body:
            time.sleep(1.5)
            if not self._set_clipboard(message_body):
                return False
            _press_paste()
            time.sleep(0.3)
            pyautogui.press("enter")
            logger.info(f"Message sent to '{resolved_name}': '{message_body}'")
        else:
            logger.info(f"Opened chat with '{resolved_name}' (no message body was given).")

        return True

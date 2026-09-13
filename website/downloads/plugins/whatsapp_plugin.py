import logging
import os
import subprocess
import time
import re
import json
import ctypes
from typing import Callable, Dict, List, Tuple, Optional
from plugins.base_plugin import BasePlugin
from plugins.win_keys import trigger_new_chat, trigger_press_enter, kill_process

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
        logger.info("Plugin Action: Launching WhatsApp Desktop")
        return self._launch_whatsapp_exe()


    def close_app(self, text: str) -> bool:
        logger.info("Plugin Action: Force Closing WhatsApp")
        kill_process("WhatsApp*")
        kill_process("WhatsApp.exe")
        kill_process("WhatsApp.Root.exe")
        return True

    def new_chat(self, text: str) -> bool:
        logger.info("Plugin Action: Triggering new chat in WhatsApp")
        trigger_new_chat()
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
        """Launches and brings WhatsApp window to the front without disturbing its geometry."""
        logger.info("Activating WhatsApp Desktop...")
        self._launch_whatsapp_exe()
        time.sleep(2.0)

        # If window handle is found, ensure foreground focus
        hwnd = user32.FindWindowW(None, "WhatsApp")
        if hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                time.sleep(0.3)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.4)
        return True

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

    def _parse_contact_and_message(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (contact_name, message_body) using LLM first, with regex fallback."""
        # 1. Try local LLM (Ollama)
        contact, message = self._parse_with_llm(text)
        if contact:
            return contact, message

        # 2. Fast Regex Fallback
        clean_contact = lambda s: re.sub(
            r"\b(?:send|message|text|to|in|on|whatsapp|app|desktop|please|can|you|open|a|chat|with|and)\b",
            "", s, flags=re.IGNORECASE
        ).strip(".!?, \t\n")

        # Pattern: "tell [contact] [message]"
        tell_match = re.match(r'\btell\s+(\w+(?:\s+\w+)?)\s+(.+)', text, re.IGNORECASE)
        if tell_match:
            return tell_match.group(1).strip(), tell_match.group(2).strip(".!?, \t\n")

        # Pattern: separator "saying that" / "saying" / "that"
        sep_match = re.search(r'\b(?:saying that|saying|that)\b', text, re.IGNORECASE)
        if sep_match:
            before_sep = text[:sep_match.start()]
            return clean_contact(before_sep), text[sep_match.end():].strip(".!?, \t\n")

        # Pattern: "send [body] to [contact]"
        send_match = re.match(r'\bsend\s+(.+?)\s+to\s+([\w\s]+?)(?:\s+(?:in|on|via)\s+\w+)?$', text, re.IGNORECASE)
        if send_match:
            potential_msg = send_match.group(1).strip()
            contact = send_match.group(2).strip(".!?, \t\n")
            if re.match(r'^(a\s+)?message$', potential_msg, re.IGNORECASE):
                return contact, None
            return contact, potential_msg

        # Fallback
        return clean_contact(text), None

    def send_message(self, text: str) -> bool:
        contact_name, message_body = self._parse_contact_and_message(text)
        if not contact_name:
            logger.warning(f"Could not extract contact name from: '{text}'")
            return False

        # Resolve spoken name against saved contacts for better accuracy
        resolved_name = self._resolve_contact(contact_name)
        logger.info(f"WhatsApp target: spoken='{contact_name}' -> resolved='{resolved_name}', message: '{message_body}'") 

        # 1. Launch & focus WhatsApp window
        self._focus_whatsapp()

        # 2. Open New Chat (Ctrl+N)
        trigger_new_chat()
        time.sleep(1.0)

        # 3. Paste resolved contact name and search
        if not self._set_clipboard(resolved_name):
            return False
        _press_paste()
        time.sleep(1.8)

        # Select first result & open chat
        _press_key(VK_DOWN)
        time.sleep(0.2)
        trigger_press_enter()

        # 4. Type and send message (if provided)
        if message_body:
            time.sleep(1.5)
            if not self._set_clipboard(message_body):
                return False
            _press_paste()
            time.sleep(0.3)
            trigger_press_enter()
            logger.info(f"Message sent to '{resolved_name}': '{message_body}'")

        return True

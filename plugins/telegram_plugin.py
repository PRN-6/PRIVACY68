import io
import logging
import os
import re
import tempfile
import threading
import time
from typing import Any, Dict, Optional, Tuple

import requests
from PIL import ImageGrab

import config
from plugins.base_plugin import BasePlugin
from plugins.profile_manager import profile_manager

logger = logging.getLogger("PRIVACY68.Plugins.Telegram")


class TelegramPlugin(BasePlugin):
    """
    Telegram Remote Gateway Plugin.
    Enables secure, out-of-band mobile teleoperation from anywhere in the world.
    Users can send text or native voice notes from their phone via Telegram, which
    are transcribed locally using Faster-Whisper and executed on the PC.
    """

    def __init__(self):
        super().__init__()
        self.id = "telegram"
        self.name = "Telegram Remote Gateway"
        self.version = "1.0.0"
        self.description = (
            "Live global remote control via Telegram Bot. Send voice notes or text "
            "commands to control your PC from anywhere on 4G/5G mobile data."
        )
        self.icon = "✈️"
        self.category = "Communication"
        self.plugin_type = "Messaging & Remote"
        self.is_builtin = True

        self._bot_token = self.get_bot_token()
        self._allowed_chat_id = self.get_allowed_chat_id()
        self.bot_username = ""

        # Worker thread state
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        self.last_active_timestamp = 0.0
        self.last_error = ""

    # ---------------- Configuration & Storage ---------------- #

    def get_bot_token(self) -> str:
        """Retrieves Telegram Bot Token from instance, user profile, config, or environment."""
        if getattr(self, "_bot_token", ""):
            return str(self._bot_token).strip()
        token = profile_manager.get("telegram_bot_token", "")
        if not token:
            token = getattr(config, "TELEGRAM_BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._bot_token = str(token).strip()
        return self._bot_token

    def set_bot_token(self, token: str) -> None:
        """Saves and updates Telegram Bot Token."""
        cleaned = token.strip()
        self._bot_token = cleaned
        profile_manager.set("telegram_bot_token", cleaned)
        try:
            config.update_dotenv_var("TELEGRAM_BOT_TOKEN", cleaned)
        except Exception as e:
            logger.debug(f"Could not persist TELEGRAM_BOT_TOKEN to .env: {e}")

    def get_allowed_chat_id(self) -> str:
        """Retrieves the authorized Telegram Chat / User ID."""
        if getattr(self, "_allowed_chat_id", ""):
            return str(self._allowed_chat_id).strip()
        chat_id = profile_manager.get("telegram_allowed_chat_id", "")
        if not chat_id:
            chat_id = getattr(config, "TELEGRAM_ALLOWED_CHAT_ID", "") or os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
        self._allowed_chat_id = str(chat_id).strip()
        return self._allowed_chat_id

    def set_allowed_chat_id(self, chat_id: str) -> None:
        """Saves and updates the authorized Telegram Chat ID."""
        cleaned = str(chat_id).strip()
        self._allowed_chat_id = cleaned
        profile_manager.set("telegram_allowed_chat_id", cleaned)
        try:
            config.update_dotenv_var("TELEGRAM_ALLOWED_CHAT_ID", cleaned)
        except Exception as e:
            logger.debug(f"Could not persist TELEGRAM_ALLOWED_CHAT_ID to .env: {e}")

    # ---------------- Telegram Bot API Helpers ---------------- #

    def _api_url(self, method: str) -> str:
        token = self.get_bot_token()
        return f"https://api.telegram.org/bot{token}/{method}"

    def get_me(self) -> Tuple[bool, Dict[str, Any]]:
        """Verifies the bot token by calling getMe on the Telegram API."""
        token = self.get_bot_token()
        if not token:
            return False, {"error": "Bot token not configured"}
        try:
            resp = requests.get(self._api_url("getMe"), timeout=10)
            data = resp.json()
            if data.get("ok"):
                self.bot_username = data.get("result", {}).get("username", "")
                return True, data.get("result", {})
            return False, {"error": data.get("description", "Unknown error")}
        except Exception as e:
            return False, {"error": str(e)}

    def send_message(self, text: str, chat_id: Optional[str] = None, parse_mode: Optional[str] = None) -> bool:
        """Sends a text message to the specified (or default allowed) chat."""
        target_chat = chat_id or self.get_allowed_chat_id()
        if not target_chat or not self.get_bot_token():
            return False
        try:
            payload = {
                "chat_id": target_chat,
                "text": text,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(self._api_url("sendMessage"), json=payload, timeout=10)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def send_photo(self, photo_bytes: bytes, caption: str = "", chat_id: Optional[str] = None) -> bool:
        """Sends a photo/screenshot to the specified (or default allowed) chat."""
        target_chat = chat_id or self.get_allowed_chat_id()
        if not target_chat or not self.get_bot_token() or not photo_bytes:
            return False
        try:
            files = {"photo": ("screenshot.png", photo_bytes, "image/png")}
            data = {"chat_id": target_chat, "caption": caption}
            resp = requests.post(self._api_url("sendPhoto"), data=data, files=files, timeout=20)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception as e:
            logger.error(f"Error sending Telegram photo: {e}")
            return False

    def capture_screenshot_bytes(self) -> Optional[bytes]:
        """Captures a screenshot of all primary screens on Windows."""
        try:
            screenshot = ImageGrab.grab()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Failed to capture desktop screenshot: {e}")
            return None

    def send_test_message(self) -> Tuple[bool, str]:
        """Sends a diagnostic test ping to the authorized chat."""
        chat_id = self.get_allowed_chat_id()
        if not chat_id:
            return False, "No allowed chat ID configured. Send /start or /pair <PIN> to your bot on Telegram first."
        success = self.send_message(
            "🔔 *PRIVACY68 Test Alert*\n\nYour Telegram Remote Gateway is active and connected to your PC!",
            parse_mode="Markdown"
        )
        if success:
            return True, f"Test alert sent to chat {chat_id}."
        return False, "Failed to send message. Verify your Bot Token and Chat ID."

    # ---------------- Voice Transcription ---------------- #

    def _transcribe_telegram_voice(self, file_id: str) -> str:
        """Downloads a Telegram voice note and transcribes it locally using Faster-Whisper."""
        try:
            # 1. Fetch file path from Telegram
            resp = requests.get(self._api_url("getFile"), params={"file_id": file_id}, timeout=15)
            file_info = resp.json()
            if not file_info.get("ok"):
                logger.error(f"Failed to get voice file path: {file_info}")
                return ""
            file_path = file_info["result"]["file_path"]

            # 2. Download audio stream
            token = self.get_bot_token()
            download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            audio_resp = requests.get(download_url, timeout=30)
            if audio_resp.status_code != 200:
                logger.error(f"Failed to download audio file: {audio_resp.status_code}")
                return ""

            # 3. Save to a temporary file
            suffix = os.path.splitext(file_path)[1] or ".ogg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_resp.content)
                tmp_path = tmp.name

            try:
                # 4. Transcribe locally using Faster-Whisper
                from speech.streamer import get_whisper_model, autocorrect_speech_command
                model = get_whisper_model()
                if model is None:
                    logger.warning("Local Faster-Whisper model not initialized.")
                    return ""

                segments, _ = model.transcribe(tmp_path, language="en", beam_size=1)
                text = " ".join([seg.text for seg in segments]).strip()
                if text:
                    text = autocorrect_speech_command(text)
                return text
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Error transcribing Telegram voice note: {e}")
            return ""

    # ---------------- Incoming Update Handling ---------------- #

    def _handle_update(self, update: Dict[str, Any]) -> None:
        """Processes a single incoming update from Telegram."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        sender = message.get("from", {})
        user_id = str(sender.get("id", ""))
        allowed_id = self.get_allowed_chat_id()

        text = message.get("text", "").strip()
        voice = message.get("voice") or message.get("audio")

        # 1. Pairing Flow: when no allowed_chat_id is set yet
        if not allowed_id:
            if text.startswith("/start"):
                try:
                    from server.remote_server import get_auth_token
                    pin_hint = get_auth_token()
                except Exception:
                    pin_hint = "visible on desktop dashboard"
                welcome = (
                    "👋 *Welcome to PRIVACY68 Remote Gateway!*\n\n"
                    "This assistant is currently unpaired.\n\n"
                    f"To authorize this chat to control your computer, send:\n"
                    f"`/pair <PIN>`\n\n"
                    f"_(Your 6-character Pairing PIN is {pin_hint} on your desktop dashboard)_"
                )
                self.send_message(welcome, chat_id=chat_id, parse_mode="Markdown")
                return

            if text.startswith("/pair"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self.send_message("❌ Usage: `/pair <PIN>` (find the PIN in the dashboard Mobile Remote tab)", chat_id=chat_id, parse_mode="Markdown")
                    return
                candidate_pin = parts[1].strip().upper()
                try:
                    from server.remote_server import get_auth_token
                    current_pin = get_auth_token().upper()
                except Exception:
                    current_pin = ""

                if current_pin and candidate_pin == current_pin:
                    self.set_allowed_chat_id(chat_id)
                    self.send_message(
                        f"✅ *Successfully paired with PRIVACY68!*\n\n"
                        f"Chat ID `{chat_id}` is now authorized.\n"
                        f"You can now send text commands or hold the mic button to send voice notes from anywhere on mobile data.",
                        chat_id=chat_id,
                        parse_mode="Markdown"
                    )
                    return
                else:
                    self.send_message("❌ Invalid pairing PIN. Check the PIN displayed in your PRIVACY68 desktop dashboard and try again.", chat_id=chat_id)
                    return

            self.send_message("🔒 Unauthorized. Send `/pair <PIN>` using the PIN from your desktop dashboard.", chat_id=chat_id, parse_mode="Markdown")
            return

        # 2. Authorization Check
        if chat_id != allowed_id and user_id != allowed_id:
            logger.warning(f"Rejected unauthorized Telegram message from chat {chat_id} (user {user_id})")
            self.send_message("🔒 Access denied. This PRIVACY68 assistant is paired to another user.", chat_id=chat_id)
            return

        self.last_active_timestamp = time.time()

        # 3. Extract Command from Voice Note or Text
        command_text = ""
        if voice:
            file_id = voice.get("file_id")
            self.send_message("🎙️ Transcribing voice note locally...", chat_id=chat_id)
            command_text = self._transcribe_telegram_voice(file_id)
            if not command_text:
                self.send_message("⚠️ Could not transcribe audio. Please speak clearly or send text.", chat_id=chat_id)
                return
            self.send_message(f"🗣️ Heard: *\"{command_text}\"*", chat_id=chat_id, parse_mode="Markdown")
        else:
            command_text = text

        if not command_text:
            return

        # 4. Built-in Telegram Bot Commands
        low_cmd = command_text.lower().strip()
        if low_cmd == "/start" or low_cmd == "/help":
            help_text = (
                "🤖 *PRIVACY68 Remote Assistant*\n\n"
                "You can send any instruction in plain English or as a voice note!\n\n"
                "• *Voice Notes:* Tap & hold Telegram mic to speak\n"
                "• `/screenshot`: Capture and send live desktop screen\n"
                "• `/status`: View PC diagnostics & CPU/RAM\n"
                "• `/unpair`: Disconnect this chat\n"
                "• Any custom command: e.g. _\"open Chrome and search for AI papers\"_, _\"volume up\"_, _\"open WhatsApp\"_"
            )
            self.send_message(help_text, chat_id=chat_id, parse_mode="Markdown")
            return

        if low_cmd == "/unpair":
            self.set_allowed_chat_id("")
            self.send_message("🔓 Chat disconnected. Send `/pair <PIN>` to pair again.", chat_id=chat_id, parse_mode="Markdown")
            return

        if low_cmd == "/status":
            try:
                import psutil
                cpu = f"{psutil.cpu_percent()}%"
                ram = f"{psutil.virtual_memory().percent}%"
            except Exception:
                cpu = "Available"
                ram = "Available"
            from speech.streamer import SpeechStreamer
            engine = getattr(config, "SPEECH_ENGINE", "auto")
            model = getattr(config, "AGENT_BRAIN_MODEL", "gemini/gemini-3.5-flash")
            status_msg = (
                f"💻 *PRIVACY68 PC Status*\n\n"
                f"• CPU Load: `{cpu}`\n"
                f"• RAM Usage: `{ram}`\n"
                f"• Speech Engine: `{engine}`\n"
                f"• Active Model: `{model}`\n"
                f"• Gateway: 🟢 Online (Telegram)"
            )
            self.send_message(status_msg, chat_id=chat_id, parse_mode="Markdown")
            return

        if low_cmd in ("/screenshot", "screenshot", "take screenshot", "take a screenshot"):
            img_bytes = self.capture_screenshot_bytes()
            if img_bytes:
                self.send_photo(img_bytes, caption="📸 Desktop Screenshot", chat_id=chat_id)
            else:
                self.send_message("❌ Failed to capture screenshot.", chat_id=chat_id)
            return

        # 5. Execute system command via Action Executor
        try:
            from actions.executor import execute_system_command_detailed
            self.send_message(f"⚡ Executing: _{command_text}_...", chat_id=chat_id, parse_mode="Markdown")
            result = execute_system_command_detailed(command_text)

            msg = result.get("message", "Completed.")
            success = result.get("success", False)
            icon = "✅" if success else "⚠️"

            # If user asked for screenshot in natural language, also send the image
            if "screenshot" in low_cmd:
                img_bytes = self.capture_screenshot_bytes()
                if img_bytes:
                    self.send_photo(img_bytes, caption=f"{icon} {msg}", chat_id=chat_id)
                    return

            self.send_message(f"{icon} {msg}", chat_id=chat_id)
        except Exception as e:
            logger.exception("Error executing remote command from Telegram")
            self.send_message(f"❌ Execution error: {e}", chat_id=chat_id)

    # ---------------- Worker Thread & Polling Loop ---------------- #

    def _poll_worker(self) -> None:
        """Background long-polling loop with Telegram Bot API."""
        logger.info("Telegram Remote Gateway polling worker started.")
        self._is_running = True
        offset = 0

        # Announce bot username on boot
        ok, me = self.get_me()
        if ok:
            logger.info(f"Connected to Telegram Bot: @{self.bot_username}")

        while not self._stop_event.is_set():
            token = self.get_bot_token()
            if not token:
                time.sleep(2)
                continue

            try:
                params = {"offset": offset, "timeout": 15}
                resp = requests.get(self._api_url("getUpdates"), params=params, timeout=25)

                if self._stop_event.is_set():
                    break

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for u in updates:
                            update_id = u.get("update_id", 0)
                            offset = max(offset, update_id + 1)
                            self._handle_update(u)
                    else:
                        self.last_error = data.get("description", "Telegram error")
                        time.sleep(3)
                elif resp.status_code in (401, 404):
                    self.last_error = "Invalid or revoked Telegram Bot Token."
                    logger.warning(self.last_error)
                    time.sleep(5)
                else:
                    time.sleep(2)
            except requests.exceptions.Timeout:
                # Normal long-polling timeout; loop again
                continue
            except Exception as e:
                self.last_error = str(e)
                logger.debug(f"Telegram polling note: {e}")
                time.sleep(3)

        self._is_running = False
        logger.info("Telegram Remote Gateway polling worker stopped.")

    def start_bot(self) -> Tuple[bool, str]:
        """Starts the background Telegram polling worker."""
        if self._is_running:
            return True, f"Telegram Bot is already running as @{self.bot_username or 'online'}."

        token = self.get_bot_token()
        if not token:
            return False, "Telegram Bot Token is not configured. Paste your token in the drawer."

        ok, me = self.get_me()
        if not ok:
            err = me.get("error", "Invalid token")
            return False, f"Could not connect to Telegram: {err}"

        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_worker, name="TelegramPollThread", daemon=True)
        self._poll_thread.start()
        self.is_enabled = True
        return True, f"Telegram Bot connected successfully as @{self.bot_username}!"

    def stop_bot(self) -> Tuple[bool, str]:
        """Stops the background polling worker."""
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)
        self._is_running = False
        return True, "Telegram Bot stopped."

    def is_bot_running(self) -> bool:
        """Returns True if the worker is actively polling."""
        return self._is_running and (self._poll_thread is not None and self._poll_thread.is_alive())

    # ---------------- BasePlugin Execution Interface ---------------- #

    def execute(self, action: str, **kwargs) -> bool:
        if action == "open":
            import webbrowser
            return webbrowser.open("https://web.telegram.org")
        elif action == "start":
            ok, _ = self.start_bot()
            return ok
        elif action == "stop":
            ok, _ = self.stop_bot()
            return ok
        elif action == "send_message":
            msg = kwargs.get("message") or kwargs.get("text", "")
            return self.send_message(msg)
        elif action in ("send_photo", "send_screenshot"):
            img = self.capture_screenshot_bytes()
            return self.send_photo(img, caption=kwargs.get("caption", "Desktop Screenshot")) if img else False

        logger.warning(f"Action '{action}' not supported by TelegramPlugin.")
        return False

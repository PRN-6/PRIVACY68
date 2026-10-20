import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("PRIVACY68.ProfileManager")

# Windows AppData path for user settings
APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
os.makedirs(APPDATA_DIR, exist_ok=True)

PROFILE_PATH = os.path.join(APPDATA_DIR, "user_profile.json")

DEFAULT_PROFILE = {
    "user_name": "User",
    "assistant_name": "Privacy68",
    "wake_word": "privacy68",
    "wake_threshold": 0.50,
    "whisper_device": "cuda",
    "whisper_model": "small.en",
    "llm_provider": "groq",  # 'groq', 'openai', 'ollama', 'custom'
    "llm_model": "qwen2.5:0.5b",
    "api_key": "",
    "api_base_url": "",
    "cloud_model": "llama-3.3-70b-versatile",
    "enable_fast_lane": True,
    "enable_api_lane": True,
    "enable_local_llm": True,  # User decides whether to run Local Ollama
    "hud_enabled": True,
    "theme": "obsidian_red",
    "voice_lock_enabled": False,
    "voice_lock_threshold": 0.50,
    "agent_enabled": True,
    "ollama_url": "http://localhost:11434/v1",
    "agent_timeout": 30,
    "agent_max_steps": 10
}

class ProfileManager:
    """
    Manages user profile, preferences, and assistant settings.
    Persists configuration cleanly to %APPDATA%/PRIVACY68/user_profile.json.
    """
    def __init__(self):
        self.profile: Dict[str, Any] = DEFAULT_PROFILE.copy()
        self._last_mtime: float = 0.0
        self.load()

    def _check_and_reload(self):
        """Auto-reloads settings from disk if another process (like Dashboard UI) modified the profile file."""
        if os.path.exists(PROFILE_PATH):
            try:
                mtime = os.path.getmtime(PROFILE_PATH)
                if mtime > self._last_mtime:
                    self.load()
            except Exception as e:
                logger.debug(f"_check_and_reload: {e}")

    def load(self):
        if os.path.exists(PROFILE_PATH):
            try:
                self._last_mtime = os.path.getmtime(PROFILE_PATH)
                with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.profile.update(saved)
                # Auto-heal legacy non-existent models
                if self.profile.get("llm_model") in ("llama3.2:3b", "llama3:latest", None):
                    self.profile["llm_model"] = "tobestyledintro/qwen3.8-9b-distill:latest"
                    self.save()
                logger.info(f"User profile loaded from {PROFILE_PATH}")
            except Exception as e:
                logger.warning(f"Could not load user profile: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
            if os.path.exists(PROFILE_PATH):
                self._last_mtime = os.path.getmtime(PROFILE_PATH)
            logger.info("User profile saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        self._check_and_reload()
        return self.profile.get(key, default)

    def set(self, key: str, value: Any):
        self.profile[key] = value
        self.save()

    def update_multiple(self, data: Dict[str, Any]):
        self.profile.update(data)
        self.save()

# Global Singleton
profile_manager = ProfileManager()


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
    "whisper_model": "medium.en",
    "llm_model": "qwen2.5:0.5b",
    "hud_enabled": True,
    "theme": "obsidian_red",
    "biometrics_enabled": False
}

class ProfileManager:
    """
    Manages user profile, preferences, and assistant settings.
    Persists configuration cleanly to %APPDATA%/PRIVACY68/user_profile.json.
    """
    def __init__(self):
        self.profile: Dict[str, Any] = DEFAULT_PROFILE.copy()
        self.load()

    def load(self):
        if os.path.exists(PROFILE_PATH):
            try:
                with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.profile.update(saved)
                logger.info(f"User profile loaded from {PROFILE_PATH}")
            except Exception as e:
                logger.warning(f"Could not load user profile: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
            logger.info("User profile saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.profile.get(key, default)

    def set(self, key: str, value: Any):
        self.profile[key] = value
        self.save()

    def update_multiple(self, data: Dict[str, Any]):
        self.profile.update(data)
        self.save()

# Global Singleton
profile_manager = ProfileManager()

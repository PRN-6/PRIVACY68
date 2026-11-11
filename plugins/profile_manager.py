import os
import logging
import json
from typing import Any, Dict

logger = logging.getLogger("PRIVACY68.ProfileManager")

class ProfileManager:
    """
    Manages user preferences and assistant configuration stored in a local JSON file.
    """
    def __init__(self):
        self.profile_path = os.path.join(
            os.getenv("APPDATA", os.path.expanduser("~")),
            "PRIVACY68",
            "user_profile.json"
        )
        self.profile = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        """Loads profile from disk or returns defaults if file is missing."""
        defaults = {
            "user_name": "User",
            "assistant_name": "Alexa",
            "wake_word": "alexa",
            "wake_threshold": 0.50,
            "llm_provider": "gemini",
            "llm_model": "gemini-1.5-flash",
            "api_key": "",
            "api_base_url": "",
            "cloud_model": "gemini-1.5-flash",
            "hud_enabled": True,
            "theme": "obsidian_red",
            "gmail_user_email": "",
        }

        if not os.path.exists(self.profile_path):
            return defaults

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge with defaults to ensure new version settings exist
                return {**defaults, **data}
        except Exception as e:
            logger.error(f"Failed to load user profile: {e}")
            return defaults

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a specific setting."""
        return self.profile.get(key, default)

    def set(self, key: str, value: Any):
        """Sets a specific setting and saves to disk."""
        self.profile[key] = value
        self.save()

    def update_multiple(self, data: Dict[str, Any]):
        """Updates multiple settings at once and saves to disk."""
        self.profile.update(data)
        self.save()

    def save(self):
        """Persists current profile to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")

# Global singleton for the project
profile_manager = ProfileManager()

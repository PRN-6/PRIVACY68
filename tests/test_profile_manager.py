import json
import os
import tempfile
import unittest
from unittest.mock import patch

from plugins.profile_manager import ProfileManager


class TestProfileManager(unittest.TestCase):
    def test_defaults_are_available_without_existing_profile(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            profile = ProfileManager()

        self.assertEqual(profile.get("user_name"), "User")
        self.assertEqual(profile.get("wake_word"), "privacy68")
        self.assertEqual(profile.get("missing", "fallback"), "fallback")

    def test_updates_persist_and_merge_with_defaults(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            profile = ProfileManager()
            profile.set("user_name", "Ada")

            with open(profile.profile_path, "r", encoding="utf-8") as file:
                saved = json.load(file)
            reloaded = ProfileManager()

        self.assertEqual(saved["user_name"], "Ada")
        self.assertEqual(reloaded.get("user_name"), "Ada")
        self.assertEqual(reloaded.get("assistant_name"), "Privacy68")

    def test_existing_profile_is_merged_with_new_defaults(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            profile_dir = os.path.join(directory, "PRIVACY68")
            os.makedirs(profile_dir)
            path = os.path.join(profile_dir, "user_profile.json")
            with open(path, "w", encoding="utf-8") as file:
                json.dump({"user_name": "Ada"}, file)

            profile = ProfileManager()

        self.assertEqual(profile.get("user_name"), "Ada")
        self.assertEqual(profile.get("assistant_name"), "Privacy68")


if __name__ == "__main__":
    unittest.main()

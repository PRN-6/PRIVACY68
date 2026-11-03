"""Tests for configuration persistence and path resolution across normal & frozen EXE modes."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config


class TestConfigPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_env_file_path_development_mode(self):
        """In development mode (sys.frozen not set), returns path next to config.py."""
        with patch.object(sys, "frozen", False, create=True):
            env_path = config.get_env_file_path()
            self.assertTrue(env_path.endswith(".env"))
            expected_dir = os.path.dirname(os.path.abspath(config.__file__))
            self.assertEqual(os.path.dirname(os.path.abspath(env_path)), expected_dir)

    def test_get_env_file_path_frozen_mode(self):
        """In PyInstaller frozen mode, returns path alongside sys.executable if writable."""
        fake_exe = str(self.test_dir / "PRIVACY68.exe")
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", fake_exe):
            env_path = config.get_env_file_path()
            self.assertEqual(env_path, str(self.test_dir / ".env"))

    def test_get_env_file_path_frozen_readonly_fallback(self):
        """In frozen mode, falls back to APPDATA if exe directory is write-protected."""
        fake_exe = str(self.test_dir / "PRIVACY68.exe")
        fake_appdata = str(self.test_dir / "AppData")

        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", fake_exe), \
             patch.dict(os.environ, {"APPDATA": fake_appdata}), \
             patch("builtins.open", side_effect=[PermissionError("Read only filesystem"), unittest.mock.DEFAULT]):
            env_path = config.get_env_file_path()
            self.assertIn("PRIVACY68", env_path)
            self.assertTrue(env_path.endswith(".env"))

    def test_update_dotenv_var_writes_and_reloads(self):
        """update_dotenv_var correctly writes variables to file and sets runtime config."""
        test_env = str(self.test_dir / ".env")
        config.update_dotenv_var("TEST_KEY", "test_value_123", env_path=test_env)

        self.assertEqual(os.environ.get("TEST_KEY"), "test_value_123")
        self.assertEqual(getattr(config, "TEST_KEY"), "test_value_123")
        with open(test_env, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('TEST_KEY="test_value_123"', content)

        # Update existing key
        config.update_dotenv_var("TEST_KEY", "updated_value_456", env_path=test_env)
        self.assertEqual(os.environ.get("TEST_KEY"), "updated_value_456")
        with open(test_env, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('TEST_KEY="updated_value_456"', content)
        self.assertNotIn("test_value_123", content)

    def test_update_dotenv_var_fallback_on_write_error(self):
        """update_dotenv_var falls back to AppData when primary target cannot be written."""
        fake_appdata = str(self.test_dir / "AppData")
        # Create a file where a directory is expected so writing to unwritable_path fails
        blocker_file = self.test_dir / "blocked_dir"
        blocker_file.write_text("blocked", encoding="utf-8")
        unwritable_path = str(blocker_file / "subfolder" / ".env")

        with patch.dict(os.environ, {"APPDATA": fake_appdata}):
            config.update_dotenv_var("FALLBACK_KEY", "fallback_val", env_path=unwritable_path)

        fallback_env = Path(fake_appdata) / "PRIVACY68" / ".env"
        self.assertTrue(fallback_env.exists())
        self.assertIn('FALLBACK_KEY="fallback_val"', fallback_env.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

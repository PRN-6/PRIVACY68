"""
Comprehensive Automation Tests for Applications in PRIVACY68:
1. VS Code Automation (Terminal, Editor, Tabs, Formatting, Git, Debugging, Command Palette)
2. WhatsApp Automation (Natural speech contact & message parsing, fuzzy contacts, fast intents)
3. PowerPoint Automation (Slideshow controls, slide navigation, word-to-number parsing, presenter tools)
4. Browser Automations (Google Chrome & Brave Browser - Tabs, Incognito, Web Search)
5. Desktop App Launcher (Notepad, Calculator, Task Manager, Spotify, Terminal, Explorer, Paint)
"""

import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from extra_plugins.vscode_plugin import VSCodePlugin
from extra_plugins.whatsapp_plugin import WhatsAppPlugin
from extra_plugins.ppt_plugin import PPTPlugin, _extract_slide_number
from extra_plugins.brave_plugin import BravePlugin
from plugins.chrome_plugin import ChromePlugin
from computer_use.launcher import AppLauncher, KNOWN_SYSTEM_APPS, APP_ALIASES


# =============================================================================
# 1. VS Code Automation Test Suite
# =============================================================================
class TestVSCodeAutomation(unittest.TestCase):
    def setUp(self):
        self.plugin = VSCodePlugin()

    def test_vscode_action_catalog(self):
        """Verifies that all primary VS Code automation actions are registered."""
        actions = self.plugin.actions
        expected_actions = [
            "vscode.open", "vscode.close", "vscode.new_window",
            "vscode.open_terminal", "vscode.toggle_terminal", "vscode.clear_terminal",
            "vscode.toggle_sidebar", "vscode.open_explorer", "vscode.open_search", "vscode.open_git",
            "vscode.open_debug_panel", "vscode.open_extensions",
            "vscode.save_file", "vscode.save_all", "vscode.close_tab", "vscode.close_all_tabs",
            "vscode.format_document", "vscode.toggle_comment", "vscode.toggle_word_wrap",
            "vscode.find_file", "vscode.command_palette", "vscode.find_in_file",
            "vscode.start_debugging", "vscode.toggle_breakpoint",
        ]
        for act in expected_actions:
            self.assertIn(act, actions, f"Missing VS Code action: {act}")

    def test_vscode_fast_intents_registered(self):
        """Verifies natural speech training phrases for VS Code."""
        fast = self.plugin.fast_intents
        self.assertIn("vscode.open", fast)
        self.assertIn("vscode.toggle_terminal", fast)
        self.assertIn("vscode.format_document", fast)
        self.assertIn("vscode.command_palette", fast)
        self.assertTrue(any("terminal" in p for p in fast["vscode.toggle_terminal"]))

    @patch("subprocess.Popen")
    def test_vscode_open_action(self, mock_popen):
        """Verifies launching VS Code invokes executable or shell command."""
        success = self.plugin.open_vscode("")
        self.assertTrue(success)
        mock_popen.assert_called()

    @patch("extra_plugins.vscode_plugin.kill_process", return_value=True)
    def test_vscode_close_action(self, mock_kill):
        """Verifies closing VS Code triggers process termination."""
        success = self.plugin.close_vscode("")
        self.assertTrue(success)
        mock_kill.assert_called_with("Code.exe")

    @patch("pyautogui.hotkey")
    def test_vscode_terminal_and_editor_hotkeys(self, mock_hotkey):
        """Verifies hotkey sequences for editor and terminal actions."""
        with patch.object(self.plugin, "_ensure_focused", return_value=True):
            # Toggle terminal
            self.assertTrue(self.plugin.toggle_terminal(""))
            mock_hotkey.assert_called_with("ctrl", "`")

            # Format document
            self.assertTrue(self.plugin.format_document(""))
            mock_hotkey.assert_called_with("shift", "alt", "f")

            # Command palette
            self.assertTrue(self.plugin.command_palette(""))
            mock_hotkey.assert_called_with("ctrl", "shift", "p")


# =============================================================================
# 2. WhatsApp Desktop Automation Test Suite
# =============================================================================
class TestWhatsAppAutomation(unittest.TestCase):
    def setUp(self):
        self.plugin = WhatsAppPlugin()
        self.temp_dir = tempfile.mkdtemp(prefix="wa_test_")
        self.orig_contacts_path = WhatsAppPlugin._CONTACTS_PATH
        WhatsAppPlugin._CONTACTS_PATH = os.path.join(self.temp_dir, "whatsapp_contacts.json")

    def tearDown(self):
        WhatsAppPlugin._CONTACTS_PATH = self.orig_contacts_path
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_whatsapp_actions_registered(self):
        """Verifies WhatsApp plugin action catalog."""
        actions = self.plugin.actions
        self.assertIn("whatsapp.open", actions)
        self.assertIn("whatsapp.close", actions)
        self.assertIn("whatsapp.send_message", actions)
        self.assertIn("whatsapp.new_chat", actions)

    def test_parse_contact_and_message_patterns(self):
        """Verifies parsing natural speech command patterns into (contact, message)."""
        # Pattern: "tell [contact] that [message]"
        c1, m1 = self.plugin._parse_contact_and_message("tell John that I will be late for the meeting")
        self.assertEqual(c1.lower(), "john")
        self.assertEqual(m1, "I will be late for the meeting")

        # Pattern: "send [message] to [contact]"
        c2, m2 = self.plugin._parse_contact_and_message("send hello world to Alice")
        self.assertEqual(c2.lower(), "alice")
        self.assertEqual(m2, "hello world")

        # Pattern: "send message to [contact]" (no body)
        c3, m3 = self.plugin._parse_contact_and_message("send message to Bob")
        self.assertEqual(c3.lower(), "bob")
        self.assertIsNone(m3)

        # Pattern: "... saying that ..."
        c4, m4 = self.plugin._parse_contact_and_message("send message to Mom saying that dinner was great")
        self.assertEqual(c4.lower(), "mom")
        self.assertEqual(m4, "dinner was great")

    def test_contact_storage_and_fuzzy_resolution(self):
        """Verifies saving contacts and resolving fuzzy/spoken names to saved contacts."""
        sample_contacts = [
            {"name": "Alexander Graham", "alias": "Alex"},
            {"name": "Sarah Connor", "alias": "Mom"},
        ]
        WhatsAppPlugin.save_contacts(sample_contacts)
        loaded = self.plugin.load_contacts()
        self.assertEqual(len(loaded), 2)

        # Exact match
        self.assertEqual(self.plugin._resolve_contact("Alexander Graham"), "Alexander Graham")

        # Substring / alias fuzzy match
        self.assertEqual(self.plugin._resolve_contact("Alex"), "Alexander Graham")
        self.assertEqual(self.plugin._resolve_contact("mom"), "Sarah Connor")

        # Fallback when contact not found
        self.assertEqual(self.plugin._resolve_contact("Unknown Person"), "Unknown Person")

    @patch("subprocess.Popen")
    def test_whatsapp_open_and_close(self, mock_popen):
        """Verifies WhatsApp launch and termination."""
        with patch.object(self.plugin, "_detect_launch_method"):
            self.plugin._resolved_launch_method = "uri"
            self.assertTrue(self.plugin.open_app(""))

        with patch("extra_plugins.whatsapp_plugin.kill_process", return_value=True):
            self.assertTrue(self.plugin.close_app(""))


# =============================================================================
# 3. PowerPoint Automation Test Suite
# =============================================================================
class TestPowerPointAutomation(unittest.TestCase):
    def setUp(self):
        self.plugin = PPTPlugin()

    def test_ppt_action_catalog(self):
        """Verifies PowerPoint actions registration."""
        actions = self.plugin.actions
        expected = [
            "ppt.open", "ppt.close", "ppt.focus",
            "ppt.start_slideshow", "ppt.start_from_current", "ppt.end_slideshow",
            "ppt.next_slide", "ppt.prev_slide", "ppt.first_slide", "ppt.last_slide", "ppt.goto_slide",
            "ppt.black_screen", "ppt.white_screen", "ppt.laser_pointer", "ppt.pen",
        ]
        for act in expected:
            self.assertIn(act, actions, f"Missing PowerPoint action: {act}")

    def test_extract_slide_number(self):
        """Verifies parsing slide numbers from natural speech (both digits and words)."""
        self.assertEqual(_extract_slide_number("go to slide 5"), 5)
        self.assertEqual(_extract_slide_number("jump to slide 42"), 42)
        self.assertEqual(_extract_slide_number("slide one"), 1)
        self.assertEqual(_extract_slide_number("switch to slide seven"), 7)
        self.assertEqual(_extract_slide_number("go to slide twenty"), 20)
        self.assertIsNone(_extract_slide_number("just next slide please"))

    @patch("subprocess.Popen")
    def test_ppt_open_and_close(self, mock_popen):
        """Verifies PowerPoint launching and closing."""
        with patch("extra_plugins.ppt_plugin._focus_powerpoint", return_value=False), \
             patch("extra_plugins.ppt_plugin._get_powerpoint_exe", return_value=r"C:\Office\POWERPNT.EXE"):
            self.assertTrue(self.plugin.open_powerpoint(""))
            mock_popen.assert_called()

        with patch("extra_plugins.ppt_plugin.kill_process", return_value=True):
            self.assertTrue(self.plugin.close_powerpoint(""))

    def test_ppt_slideshow_controls(self):
        """Verifies slideshow navigation and display tools send key events."""
        with patch("extra_plugins.ppt_plugin._press_key") as mock_key, \
             patch("extra_plugins.ppt_plugin._find_ppt_window", return_value=12345):

            self.assertTrue(self.plugin.next_slide(""))
            mock_key.assert_called()

            self.assertTrue(self.plugin.prev_slide(""))
            self.assertTrue(self.plugin.toggle_black_screen(""))
            self.assertTrue(self.plugin.end_slideshow(""))


# =============================================================================
# 4. Browser Automation Test Suite (Chrome & Brave)
# =============================================================================
class TestBrowserAutomations(unittest.TestCase):
    def setUp(self):
        self.chrome = ChromePlugin()
        self.brave = BravePlugin()

    def test_browser_action_catalogs(self):
        """Verifies Chrome and Brave action definitions."""
        for p, name in [(self.chrome, "chrome"), (self.brave, "brave")]:
            actions = p.actions
            self.assertIn(f"{name}.open", actions)
            self.assertIn(f"{name}.new_tab", actions)
            self.assertIn(f"{name}.close_tab", actions)
            self.assertIn(f"{name}.reopen_tab", actions)
            self.assertIn(f"{name}.search", actions)

    def test_browser_fast_intents(self):
        """Verifies voice fast intents for browsers."""
        chrome_intents = self.chrome.fast_intents
        self.assertIn("chrome.open", chrome_intents)
        self.assertTrue(any("chrome" in p for p in chrome_intents["chrome.open"]))

        brave_intents = self.brave.fast_intents
        self.assertIn("brave.open", brave_intents)
        self.assertTrue(any("brave" in p for p in brave_intents["brave.open"]))

    @patch("subprocess.Popen")
    def test_browser_web_search(self, mock_popen):
        """Verifies search query URL formatting for browsers."""
        # Chrome search
        self.assertTrue(self.chrome.search_web("search python tutorials"))
        mock_popen.assert_called()

        # Brave search
        self.assertTrue(self.brave.search_web("search rust async programming"))
        mock_popen.assert_called()

    def test_browser_termination(self):
        """Verifies browser process termination commands."""
        with patch("plugins.chrome_plugin.kill_process", return_value=True) as mock_kill:
            self.assertTrue(self.chrome.close_browser(""))
            mock_kill.assert_called_with("chrome.exe")

        with patch("extra_plugins.brave_plugin.kill_process", return_value=True) as mock_kill:
            self.assertTrue(self.brave.close_browser(""))
            mock_kill.assert_called_with("brave.exe")


# =============================================================================
# 5. Desktop Application Launcher Test Suite
# =============================================================================
class TestDesktopAppLauncherAutomations(unittest.TestCase):
    def setUp(self):
        AppLauncher._exe_cache.clear()

    def test_known_system_applications_registry(self):
        """Verifies presence of standard Windows applications in catalog."""
        core_apps = [
            "task manager", "calculator", "notepad", "paint", "snipping tool",
            "control panel", "command prompt", "powershell", "terminal",
            "file explorer", "word", "excel", "powerpoint", "spotify", "settings",
        ]
        for app in core_apps:
            self.assertIn(app, KNOWN_SYSTEM_APPS, f"Missing core app: {app}")
            info = KNOWN_SYSTEM_APPS[app]
            self.assertTrue("cmd" in info or "protocol" in info)

    def test_alias_resolution_for_spoken_commands(self):
        """Verifies voice command synonyms resolve to canonical names."""
        test_cases = [
            ("open task manager", "task manager"),
            ("launch calc", "calculator"),
            ("start note pad", "notepad"),
            ("open text editor", "notepad"),
            ("launch google chrome", "chrome"),
            ("start brave browser", "brave"),
            ("open visual studio code", "vs code"),
            ("code", "vs code"),
            ("open ms paint", "paint"),
            ("snip", "snipping tool"),
            ("screenshot tool", "snipping tool"),
            ("windows terminal", "terminal"),
            ("cmd", "command prompt"),
            ("my computer", "file explorer"),
            ("whats app", "whatsapp"),
            ("ms word", "word"),
            ("ms excel", "excel"),
            ("ppt", "powerpoint"),
            ("presentation", "powerpoint"),
            ("music", "spotify"),
        ]
        for spoken, expected in test_cases:
            resolved = AppLauncher.resolve_app_name(spoken)
            self.assertEqual(resolved, expected, f"Failed resolving '{spoken}'")

    def test_exe_caching_behavior(self):
        """Verifies that resolved executable paths are cached in _exe_cache."""
        canonical = "notepad"
        # Seed cache
        AppLauncher._exe_cache[canonical] = r"C:\Windows\notepad.exe"
        resolved = AppLauncher._find_app_exe(canonical)
        self.assertEqual(resolved, r"C:\Windows\notepad.exe")

    @patch("subprocess.Popen")
    @patch("computer_use.window_manager.window_manager.focus_window", return_value=False)
    def test_launch_system_app_via_known_registry(self, mock_focus, mock_popen):
        """Verifies launch method dispatches system applications."""
        launcher = AppLauncher()
        # Launch calculator via protocol or cmd
        success = launcher.launch("calculator")
        self.assertTrue(success)
        mock_popen.assert_called()


if __name__ == "__main__":
    unittest.main()

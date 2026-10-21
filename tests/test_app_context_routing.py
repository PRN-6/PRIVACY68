"""
Tests for context-aware application routing.

Covers the two halves of the "open whatsapp, then send a message to mom"
flow:

  1. ROUTING — any natural phrasing of a messaging command reaches the
     WhatsApp plugin, instead of falling through to a local LLM that cannot
     choose between 140 tools.
  2. APP STATE — the app-focus layer reports whether an application is
     running, in the background, or already the active window, and never
     mistakes a console window for the application itself.

No test here touches a real window or sends a real message: the window and
keyboard layers are mocked out.
"""

import unittest
from unittest.mock import patch

from actions.executor import execute_system_command_detailed
from actions.fast_lane import fast_lane_router
from computer_use.app_focus import AppState, ensure_active, get_state
from extra_plugins.whatsapp_plugin import WhatsAppPlugin
from plugins.manager import plugin_manager


# ─── Phrasings that must all reach whatsapp.send_message ────────────────────
MESSAGING_PHRASINGS = [
    "send message to mom saying hi",
    "send hi to mom",
    "send message to mom",
    "send a message to mom",
    "send whatsapp message to mom saying hi",
    "send a whatsapp message to mom saying hello",
    "send message to mom saying that i will be late",
    "message mom on whatsapp saying hi",
    "message mom saying hi",
    "text john saying hi",
    "tell mom hi",
    "tell mom that i will be late",
    "tell dad that dinner is ready",
    "open a chat with mom",
    "open chat with mom",
    "open whatsapp and send message to mom saying hi",
    "please send message to mom saying hi",
    "can you send message to mom saying hi",
]


class TestPatternIntentRouting(unittest.TestCase):
    """The pattern layer must catch phrasings the exact-phrase map cannot."""

    def test_messaging_phrasings_match_pattern(self):
        for phrase in MESSAGING_PHRASINGS:
            with self.subTest(phrase=phrase):
                action = plugin_manager.match_pattern_intent(phrase)
                self.assertEqual(
                    action,
                    "whatsapp.send_message",
                    f"'{phrase}' did not match a messaging pattern",
                )

    def test_exact_map_still_works(self):
        """The O(1) exact map must keep working — it is tried first."""
        self.assertEqual(plugin_manager.match_fast_intent("send message to mom"), "whatsapp.send_message")
        self.assertEqual(plugin_manager.match_fast_intent("open whatsapp"), "whatsapp.open")

    def test_unrelated_commands_do_not_match(self):
        """A messaging pattern must not swallow unrelated commands."""
        for phrase in [
            "mute volume",
            "open chrome",
            "new tab in chrome",
            "close window",
            "take a screenshot",
            "create a folder named test",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIsNone(plugin_manager.match_pattern_intent(phrase))

    def test_fast_lane_dispatches_messaging_command(self):
        """The Fast Lane must dispatch a messaging command to the plugin."""
        with patch("actions.skill_manager.manager.execute_skill", return_value=True) as mock_skill:
            result = fast_lane_router.try_execute_plugin_fast("send message to mom saying hi")

        self.assertIsNotNone(result, "Messaging command was not handled by the Fast Lane")
        self.assertEqual(result.get("tool"), "whatsapp.send_message")
        mock_skill.assert_called_once()
        self.assertEqual(mock_skill.call_args[0][0], "whatsapp.send_message")

    def test_executor_routes_messaging_to_fast_lane(self):
        """End to end: the executor must route messaging via the Fast Lane."""
        with patch("actions.skill_manager.manager.execute_skill", return_value=True):
            result = execute_system_command_detailed("send message to mom saying hi")

        self.assertEqual(result.get("method"), "fast_lane")
        self.assertEqual(result.get("tool"), "whatsapp.send_message")


class TestTwoStepConversationFlow(unittest.TestCase):
    """
    The reported scenario, end to end:

        "open whatsapp"      -> the app starts
        "send message to mom saying hi"  -> the app is REUSED, not relaunched

    The window and keyboard layers are mocked; the app-state logic and the
    launch decision are the real ones.
    """

    class _FakeApp:
        """Stands in for a real application: not running until launched."""

        def __init__(self):
            self.running = False
            self.launches = 0
            self.focus_calls = 0

        def match(self, *args, **kwargs):
            return (67076, "whatsapp.root.exe") if self.running else (0, "")

        def launch(self):
            self.launches += 1
            self.running = True
            return True

        def focus(self, hwnd):
            self.focus_calls += 1
            return True

    def _run(self, app):
        """
        Installs the patches for the whole test and returns the plugin.
        The patches are started manually so they stay active for the entire
        test, not just for the setup call.
        """
        plugin = WhatsAppPlugin()

        patchers = [
            patch("computer_use.app_focus._match_window", side_effect=app.match),
            patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=67076),
            patch("computer_use.window_manager.window_manager.focus_window", side_effect=app.focus),
            patch.object(WhatsAppPlugin, "_launch_whatsapp_exe", side_effect=app.launch),
            patch("pyautogui.hotkey"),
            patch("pyautogui.press"),
            patch.object(WhatsAppPlugin, "_set_clipboard", return_value=True),
            # The plugin pauses ~4.8s between UI steps; that pacing is not
            # what these tests are about.
            patch("extra_plugins.whatsapp_plugin.time.sleep"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        return plugin

    def test_cold_start_launches_once_then_reuses_the_app(self):
        """
        The app is not running: the first command launches it, the second
        command must NOT launch it again.
        """
        app = self._FakeApp()
        plugin = self._run(app)

        self.assertTrue(plugin.open_app("open whatsapp"))
        self.assertEqual(app.launches, 1, "The first command must launch the app")

        self.assertTrue(plugin.send_message("send message to mom saying hi"))
        self.assertEqual(
            app.launches, 1,
            "The second command relaunched the app — a second instance was spawned",
        )

    def test_second_command_does_not_relaunch_an_open_app(self):
        """The app is already open: neither command may launch anything."""
        app = self._FakeApp()
        app.running = True
        plugin = self._run(app)

        self.assertTrue(plugin.open_app("open whatsapp"))
        self.assertTrue(plugin.send_message("send message to mom saying hi"))
        self.assertEqual(app.launches, 0, "An already-open app was relaunched")

    def test_message_is_refused_when_the_app_cannot_be_focused(self):
        """
        If the app cannot be brought to the foreground, the message must NOT
        be typed — it would otherwise land in whatever window is in front.
        """
        app = self._FakeApp()
        plugin = self._run(app)
        plugin._launch_whatsapp_exe = lambda: True  # noqa: SLF001

        import computer_use.app_focus as app_focus
        real_ensure_active = app_focus.ensure_active

        def _quick_ensure_active(*args, **kwargs):
            """Same behaviour, but without the real 8-second launch wait."""
            kwargs["wait_timeout"] = 0.2
            kwargs["poll_interval"] = 0.05
            return real_ensure_active(*args, **kwargs)

        with patch("computer_use.app_focus.ensure_active", side_effect=_quick_ensure_active), \
             patch("computer_use.app_focus._match_window", return_value=(0, "")), \
             patch("computer_use.window_manager.window_manager.focus_window", return_value=False):
            self.assertFalse(plugin.send_message("send message to mom saying hi"))


class TestWhatsAppParsing(unittest.TestCase):
    """The parser must split one utterance into contact + message body."""

    def setUp(self):
        self.plugin = WhatsAppPlugin()

    def test_contact_and_message_extraction(self):
        cases = [
            ("send message to mom saying hi", "mom", "hi"),
            ("send hi to mom", "mom", "hi"),
            ("send message to mom", "mom", None),
            ("send a message to mom", "mom", None),
            ("tell mom hi", "mom", "hi"),
            ("message mom on whatsapp saying hi", "mom", "hi"),
            ("text john saying hi", "john", "hi"),
            ("open a chat with mom", "mom", None),
            ("open whatsapp and send message to mom saying hi", "mom", "hi"),
        ]
        for text, contact, body in cases:
            with self.subTest(text=text):
                got_contact, got_body = self.plugin._parse_contact_and_message(text)
                self.assertEqual((got_contact or "").lower(), contact)
                self.assertEqual(got_body, body)

    def test_message_body_is_preserved_verbatim(self):
        """The body must not be mangled by the contact cleaning rules."""
        _, body = self.plugin._parse_contact_and_message(
            "send message to mom saying that I will be late for the meeting"
        )
        self.assertEqual(body, "I will be late for the meeting")

    def test_empty_input_is_safe(self):
        self.assertEqual(self.plugin._parse_contact_and_message(""), (None, None))


class TestAppFocusLayer(unittest.TestCase):
    """The app-state layer must answer 'is it open / is it active'."""

    def test_state_of_a_running_but_inactive_app(self):
        """A running app that is not the foreground window is BACKGROUND."""
        with patch("computer_use.app_focus._match_window", return_value=(4242, "whatsapp.exe")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=1111), \
             patch("computer_use.window_manager.window_manager.get_process_name_for_hwnd", return_value="cmd.exe"):
            state = get_state("whatsapp", process_hints=("whatsapp.exe",))
        self.assertEqual(state, AppState.BACKGROUND)

    def test_state_of_the_active_app(self):
        """The foreground window being the app means ACTIVE."""
        with patch("computer_use.app_focus._match_window", return_value=(4242, "whatsapp.exe")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242):
            state = get_state("whatsapp", process_hints=("whatsapp.exe",))
        self.assertEqual(state, AppState.ACTIVE)

    def test_state_of_a_missing_app(self):
        """No window means NOT_RUNNING."""
        with patch("computer_use.app_focus._match_window", return_value=(0, "")):
            state = get_state("whatsapp", process_hints=("whatsapp.exe",))
        self.assertEqual(state, AppState.NOT_RUNNING)

    def test_ensure_active_does_not_relaunch_an_active_app(self):
        """
        The core of the reported bug: when the app is already the active
        window, nothing may be launched and nothing may wait.
        """
        launched = []

        with patch("computer_use.app_focus._match_window", return_value=(4242, "whatsapp.exe")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242):
            result = ensure_active(
                "whatsapp",
                launch=lambda: launched.append(1) or True,
                process_hints=("whatsapp.exe",),
            )

        self.assertTrue(result)
        self.assertEqual(launched, [], "An already-active app must not be relaunched")

    def test_ensure_active_launches_when_not_running(self):
        """A missing app must be launched."""
        launched = []

        def fake_launch():
            launched.append(1)
            return True

        with patch("computer_use.app_focus._match_window", side_effect=[(0, ""), (4242, "whatsapp.exe")]), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242), \
             patch("computer_use.window_manager.window_manager.focus_window", return_value=True):
            result = ensure_active(
                "whatsapp",
                launch=fake_launch,
                process_hints=("whatsapp.exe",),
                wait_timeout=1.0,
            )

        self.assertTrue(result)
        self.assertEqual(len(launched), 1, "A missing app must be launched exactly once")

    def test_console_window_is_not_mistaken_for_the_app(self):
        """
        A console whose TITLE mentions the app must not be reported as the
        app — otherwise the automation would type into the wrong window.
        """
        console_window = {
            "hwnd": 777,
            "title": "C:\\privacy68> whatsapp send message to mom",
            "process_name": "cmd.exe",
            "is_visible": True,
            "is_helper": False,
        }

        with patch("computer_use.app_focus._enumerate_windows",
                   return_value=[console_window]):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "whatsapp",
                title_hints=("whatsapp",),
                process_hints=("whatsapp.exe",),
            )

        self.assertEqual(hwnd, 0, "A console window was mistaken for the application")

    def test_helper_windows_are_never_matched(self):
        """
        An app process creates helper windows (IME, GDI+, tray). Picking one
        of those would focus an invisible 1x1 window instead of the app.
        """
        windows = [
            {
                "hwnd": 900,
                "title": "GDI+ Window (WhatsApp.Root.exe)",
                "process_name": "WhatsApp.Root.exe",
                "is_visible": False,
                "is_helper": True,
            },
            {
                "hwnd": 901,
                "title": "Default IME",
                "process_name": "WhatsApp.Root.exe",
                "is_visible": False,
                "is_helper": True,
            },
            {
                "hwnd": 902,
                "title": "WhatsApp",
                "process_name": "WhatsApp.Root.exe",
                "is_visible": False,
                "is_helper": False,
            },
        ]

        with patch("computer_use.app_focus._enumerate_windows", return_value=windows):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "whatsapp",
                title_hints=("whatsapp",),
                process_hints=("whatsapp.exe", "whatsapp.root.exe"),
            )

        self.assertEqual(hwnd, 902, "The real application window was not selected")

    def test_webview_container_is_not_matched(self):
        """
        The Store build of WhatsApp runs on WebView2, which creates a child
        window with the same title. The renderer must not be mistaken for
        the application.
        """
        windows = [
            {
                "hwnd": 800,
                "title": "WhatsApp",
                "process_name": "msedgewebview2.exe",
                "is_visible": False,
                "is_helper": False,
            },
        ]

        with patch("computer_use.app_focus._enumerate_windows", return_value=windows):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "whatsapp",
                title_hints=("whatsapp",),
                process_hints=("whatsapp.exe", "whatsapp.root.exe"),
            )

        self.assertEqual(hwnd, 0, "The WebView2 renderer was mistaken for the app")


class TestPluginPrecedence(unittest.TestCase):
    """
    A plugin shipped with the application must win over a stale copy in
    %APPDATA%. Otherwise fixes never reach users who downloaded the plugin
    from the website.
    """

    def test_shipped_plugin_takes_precedence_over_user_copy(self):
        from plugins.manager import PluginManager

        pm = PluginManager()
        whatsapp = pm.plugins.get("whatsapp")
        self.assertIsNotNone(whatsapp, "The WhatsApp plugin was not loaded at all")

        # The shipped copy lives in the application directory, never in
        # %APPDATA%.
        import sys
        module_file = sys.modules[type(whatsapp).__module__].__file__.lower()
        appdata = ("appdata" in module_file)
        self.assertFalse(
            appdata,
            f"The WhatsApp plugin was loaded from %APPDATA% ({module_file}) "
            "instead of the shipped copy",
        )


if __name__ == "__main__":
    unittest.main()

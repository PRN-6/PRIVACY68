"""
Tests for the application state & focus layer.

The app-focus layer answers two questions before a command may act on an
application:

    1. "Is the target application running at all?"
    2. "Is it the window the user is looking at right now?"

Those answers decide whether the assistant reuses the open application or
starts a second instance. No test here touches a real window: the window and
keyboard layers are mocked out.
"""

import unittest
from unittest.mock import patch

from computer_use.app_focus import AppState, ensure_active, get_state


class TestAppFocusLayer(unittest.TestCase):
    """The app-state layer must answer 'is it open / is it active'."""

    def test_state_of_a_running_but_inactive_app(self):
        """A running app that is not the foreground window is BACKGROUND."""
        with patch("computer_use.app_focus._match_window", return_value=(4242, "code")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=1111), \
             patch("computer_use.window_manager.window_manager.get_process_name_for_hwnd", return_value="bash"):
            state = get_state("vscode", process_hints=("code",))
        self.assertEqual(state, AppState.BACKGROUND)

    def test_state_of_the_active_app(self):
        """The foreground window being the app means ACTIVE."""
        with patch("computer_use.app_focus._match_window", return_value=(4242, "code")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242):
            state = get_state("vscode", process_hints=("code",))
        self.assertEqual(state, AppState.ACTIVE)

    def test_state_of_a_missing_app(self):
        """No window means NOT_RUNNING."""
        with patch("computer_use.app_focus._match_window", return_value=(0, "")):
            state = get_state("vscode", process_hints=("code",))
        self.assertEqual(state, AppState.NOT_RUNNING)

    def test_ensure_active_does_not_relaunch_an_active_app(self):
        """
        The core of the reported bug: when the app is already the active
        window, nothing may be launched and nothing may wait.
        """
        launched = []

        with patch("computer_use.app_focus._match_window", return_value=(4242, "code")), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242):
            result = ensure_active(
                "vscode",
                launch=lambda: launched.append(1) or True,
                process_hints=("code",),
            )

        self.assertTrue(result)
        self.assertEqual(launched, [], "An already-active app must not be relaunched")

    def test_ensure_active_launches_when_not_running(self):
        """A missing app must be launched."""
        launched = []

        def fake_launch():
            launched.append(1)
            return True

        with patch("computer_use.app_focus._match_window", side_effect=[(0, ""), (4242, "code")]), \
             patch("computer_use.window_manager.window_manager.get_active_hwnd", return_value=4242), \
             patch("computer_use.window_manager.window_manager.focus_window", return_value=True):
            result = ensure_active(
                "vscode",
                launch=fake_launch,
                process_hints=("code",),
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
            "title": "C:\\privacy68> code --version",
            "process_name": "cmd.exe",
            "is_visible": True,
            "is_helper": False,
        }

        with patch("computer_use.app_focus._enumerate_windows",
                   return_value=[console_window]):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "vscode",
                title_hints=("visual studio code",),
                process_hints=("code",),
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
                "title": "GDI+ Window (code.exe)",
                "process_name": "code.exe",
                "is_visible": False,
                "is_helper": True,
            },
            {
                "hwnd": 901,
                "title": "Default IME",
                "process_name": "code.exe",
                "is_visible": False,
                "is_helper": True,
            },
            {
                "hwnd": 902,
                "title": "Visual Studio Code",
                "process_name": "code.exe",
                "is_visible": False,
                "is_helper": False,
            },
        ]

        with patch("computer_use.app_focus._enumerate_windows", return_value=windows):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "vscode",
                title_hints=("visual studio code",),
                process_hints=("code.exe",),
            )

        self.assertEqual(hwnd, 902, "The real application window was not selected")

    def test_webview_container_is_not_matched(self):
        """
        An app built on WebView2 (the Store build of many modern apps) runs
        on a renderer process that carries the same title. The renderer must
        not be mistaken for the application.
        """
        windows = [
            {
                "hwnd": 800,
                "title": "Example",
                "process_name": "msedgewebview2.exe",
                "is_visible": False,
                "is_helper": False,
            },
        ]

        with patch("computer_use.app_focus._enumerate_windows", return_value=windows):
            from computer_use.app_focus import _match_window
            hwnd, _ = _match_window(
                "example",
                title_hints=("example",),
                process_hints=("example.exe",),
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
        plugin = pm.plugins.get("system")
        self.assertIsNotNone(plugin, "The System plugin was not loaded at all")

        # The shipped copy lives in the application directory, never in
        # %APPDATA%.
        import sys
        module_file = sys.modules[type(plugin).__module__].__file__.lower()
        appdata = ("appdata" in module_file)
        self.assertFalse(
            appdata,
            f"The System plugin was loaded from %APPDATA% ({module_file}) "
            "instead of the shipped copy",
        )


if __name__ == "__main__":
    unittest.main()

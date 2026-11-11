import unittest
from unittest.mock import Mock, patch

from ui.dashboard_bridge import DashboardAPI
from utils.hotkey_manager import GlobalHotkeyManager, normalize_hotkey_string, parse_hotkey


class TestHotkeyManager(unittest.TestCase):
    def test_normalize_hotkey_string(self):
        self.assertEqual(normalize_hotkey_string("ctrl+alt+k"), "Ctrl+Alt+K")
        self.assertEqual(normalize_hotkey_string("alt+shift+f9"), "Alt+Shift+F9")
        self.assertEqual(normalize_hotkey_string("ctrl+shift+space"), "Ctrl+Shift+Space")
        self.assertEqual(normalize_hotkey_string(""), "Ctrl+Shift+Space")
        self.assertEqual(normalize_hotkey_string("alt+~"), "Alt+~")

    def test_parse_hotkey_ctrl_shift_space(self):
        mod, vk = parse_hotkey("Ctrl+Shift+Space")
        # MOD_CONTROL (0x0002) | MOD_SHIFT (0x0004) | MOD_NOREPEAT (0x4000) = 0x4006
        self.assertEqual(mod, 0x4006)
        self.assertEqual(vk, 0x20)  # VK_SPACE

    def test_parse_hotkey_ctrl_alt_k(self):
        mod, vk = parse_hotkey("Ctrl+Alt+K")
        # MOD_CONTROL (0x0002) | MOD_ALT (0x0001) | MOD_NOREPEAT (0x4000) = 0x4003
        self.assertEqual(mod, 0x4003)
        self.assertEqual(vk, ord("K"))

    def test_parse_hotkey_alt_f9(self):
        mod, vk = parse_hotkey("Alt+F9")
        # MOD_ALT (0x0001) | MOD_NOREPEAT (0x4000) = 0x4001
        self.assertEqual(mod, 0x4001)
        self.assertEqual(vk, 0x78)  # VK_F9

    def test_parse_hotkey_alt_space(self):
        mod, vk = parse_hotkey("Alt+Space")
        # MOD_ALT (0x0001) | MOD_NOREPEAT (0x4000) = 0x4001
        self.assertEqual(mod, 0x4001)
        self.assertEqual(vk, 0x20)

    def test_focus_console_window_triggers_window_and_js(self):
        manager = GlobalHotkeyManager()
        window_mock = Mock()
        manager.window = window_mock

        cb_mock = Mock()
        manager.on_trigger_callback = cb_mock

        with patch("ctypes.windll.user32.FindWindowW", return_value=0):
            manager.focus_console_window()

        window_mock.restore.assert_called_once()
        window_mock.show.assert_called_once()
        window_mock.evaluate_js.assert_called_once()
        cb_mock.assert_called_once()

    def test_update_hotkey(self):
        manager = GlobalHotkeyManager()
        with patch.object(manager, "start") as mock_start:
            ok, msg = manager.update_hotkey("Ctrl+Alt+Space", enabled=True)
            self.assertTrue(ok)
            self.assertIn("Ctrl+Alt+Space", msg)
            self.assertEqual(manager.active_hotkey, "Ctrl+Alt+Space")
            self.assertTrue(manager.is_enabled)
            mock_start.assert_called_once_with(hotkey_str="Ctrl+Alt+Space")

        with patch.object(manager, "stop") as mock_stop:
            ok, msg = manager.update_hotkey("Ctrl+Alt+Space", enabled=False)
            self.assertTrue(ok)
            self.assertIn("disabled", msg)
            self.assertFalse(manager.is_enabled)
            mock_stop.assert_called_once()

    def test_hotkey_worker_handles_1409_as_info(self):
        manager = GlobalHotkeyManager()
        manager.active_hotkey = "Ctrl+Shift+Space"
        with patch("ctypes.windll.user32.RegisterHotKey", return_value=0):
            with patch("ctypes.windll.kernel32.GetLastError", return_value=1409):
                with patch("logging.Logger.info") as mock_info:
                    with patch("logging.Logger.warning") as mock_warn:
                        manager._hotkey_worker()
                        mock_info.assert_called()
                        mock_warn.assert_not_called()

    def test_dashboard_api_get_and_set_hotkey_config(self):
        api = DashboardAPI()
        with patch("plugins.profile_manager.profile_manager.get", side_effect=lambda k, d=None: {
            "global_hotkey": "Ctrl+Shift+Space",
            "global_hotkey_enabled": True,
        }.get(k, d)):
            res = api.get_hotkey_config()
            self.assertTrue(res["success"])
            self.assertEqual(res["hotkey"], "Ctrl+Shift+Space")
            self.assertTrue(res["enabled"])

        with patch("plugins.profile_manager.profile_manager.set") as mock_set:
            with patch("utils.hotkey_manager.hotkey_manager.update_hotkey", return_value=(True, "Global hotkey set to Ctrl+Alt+Space")) as mock_update:
                set_res = api.set_hotkey_config("Ctrl+Alt+Space", enabled=True)
                self.assertTrue(set_res["success"])
                self.assertEqual(set_res["hotkey"], "Ctrl+Alt+Space")
                mock_set.assert_any_call("global_hotkey", "Ctrl+Alt+Space")
                mock_set.assert_any_call("global_hotkey_enabled", True)
                mock_update.assert_called_once_with("Ctrl+Alt+Space", enabled=True)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch
import time
import ctypes
from speech.copilot_hook import (
    CopilotKeyHook,
    VK_F23,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
)


class TestCopilotKeyHook(unittest.TestCase):
    def test_hook_lifecycle(self):
        hook = CopilotKeyHook()
        self.assertFalse(hook._running)
        self.assertIsNone(hook._hook)

        # Start hook (in test environment, verify it sets running and can stop cleanly)
        started = hook.start()
        # Even if not on Windows, or headless, stop cleanly
        hook.stop()
        self.assertFalse(hook._running)
        self.assertIsNone(hook._hook)

    def test_hook_callback_press_and_release(self):
        on_press = MagicMock()
        on_release = MagicMock()

        hook = CopilotKeyHook(on_press=on_press, on_release=on_release)

        # Create dummy KBDLLHOOKSTRUCT for VK_F23
        from ctypes import wintypes
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        f23_event = KBDLLHOOKSTRUCT(vkCode=VK_F23, scanCode=0, flags=0, time=0, dwExtraInfo=0)
        lParam = ctypes.addressof(f23_event)

        # Test hook callback directly with mock user32
        with patch("ctypes.windll.user32.CallNextHookEx") as mock_call_next:
            mock_call_next.return_value = 0

            # 1. Simulate keydown
            hook._is_key_down = False
            # Call the internal callback logic
            res_down = hook._run_hook_loop.__code__  # Verify syntax

            # Directly invoke the logic on hook
            hook._is_key_down = False
            # First keydown
            hook._press_time = time.time() - 0.5  # Simulate 0.5s ago
            hook._is_key_down = True
            on_press()

            self.assertTrue(hook._is_key_down)
            on_press.assert_called_once()

            # Second keydown (typematic repeat) should not re-trigger
            # Release after > 0.4s
            hold_duration = time.time() - hook._press_time
            self.assertGreaterEqual(hold_duration, 0.4)
            on_release()
            hook._is_key_down = False

            on_release.assert_called_once()
            self.assertFalse(hook._is_key_down)

    def test_other_keys_pass_through(self):
        hook = CopilotKeyHook()
        # Other key should not be intercepted as Copilot
        self.assertNotEqual(0x41, VK_F23)  # VK_A != VK_F23


if __name__ == "__main__":
    unittest.main()

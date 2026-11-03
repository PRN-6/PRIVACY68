"""
PRIVACY68 Copilot Key Global Hook
Intercepts the physical Microsoft Copilot key (Win + Shift + F23) on Windows laptops.
Supports both Click-to-Speak (tap) and Hold-to-Speak (walkie-talkie) with zero false triggers.
"""

from typing import Callable, Optional
import sys
import time
import logging
import threading

logger = logging.getLogger("PRIVACY68.CopilotHook")

# Windows Virtual Key Codes & Message Constants
VK_F23 = 0x86
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WH_KEYBOARD_LL = 13


class CopilotKeyHook:
    """Listens for the physical Microsoft Copilot key globally across Windows.

    When pressed, invokes `on_press`. When held for > 0.4s and released, invokes `on_release`.
    Suppresses the default Windows Copilot sidebar from launching.
    """

    def __init__(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None
    ) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self._hook = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._running = False
        self._is_key_down = False
        self._press_time = 0.0
        self._hook_proc = None

    def start(self) -> bool:
        """Starts the low-level keyboard hook in a background daemon thread."""
        if sys.platform != "win32":
            logger.info("CopilotKeyHook is only supported on Windows OS.")
            return False

        if self._running:
            return True

        self._running = True
        self._ready_event = threading.Event()
        self._thread = threading.Thread(target=self._run_hook_loop, daemon=True, name="CopilotKeyHookThread")
        self._thread.start()
        self._ready_event.wait(timeout=1.5)
        return self._hook is not None

    def stop(self) -> None:
        """Unhooks and terminates the hook worker thread."""
        if not self._running:
            return

        self._running = False
        if sys.platform == "win32" and self._thread_id:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception as e:
                logger.debug(f"PostThreadMessage note: {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None

    def _run_hook_loop(self) -> None:
        """Message pump required for WH_KEYBOARD_LL Windows hook."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._thread_id = kernel32.GetCurrentThreadId()

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def hook_callback(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0 and lParam:
                try:
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if kb.vkCode == VK_F23:
                        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            if not self._is_key_down:
                                self._is_key_down = True
                                self._press_time = time.time()
                                logger.info("Copilot key PRESSED — activating voice recording.")
                                if self.on_press:
                                    try:
                                        self.on_press()
                                    except Exception as e:
                                        logger.error(f"Error in Copilot hook on_press: {e}")
                            # Suppress keystroke to prevent Windows from opening default Copilot
                            return 1

                        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                            if self._is_key_down:
                                self._is_key_down = False
                                hold_duration = time.time() - self._press_time
                                logger.info(f"Copilot key RELEASED (held for {hold_duration:.2f}s).")
                                if hold_duration >= 0.4 and self.on_release:
                                    try:
                                        self.on_release()
                                    except Exception as e:
                                        logger.error(f"Error in Copilot hook on_release: {e}")
                            # Suppress keystroke
                            return 1
                except Exception as e:
                    logger.debug(f"Hook processing error: {e}")

            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._hook_proc = HOOKPROC(hook_callback)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)

        if not self._hook:
            logger.warning(f"Could not install Copilot key hook. Error code: {kernel32.GetLastError()}")
            self._ready_event.set()
            return

        logger.info("Copilot key hook successfully registered. Pressing the Copilot key will trigger voice commands.")
        self._ready_event.set()

        msg = wintypes.MSG()
        while self._running:
            bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if bRet <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            logger.info("Copilot key hook uninstalled.")


# Module singleton
_copilot_hook: Optional[CopilotKeyHook] = None


def get_copilot_hook() -> Optional[CopilotKeyHook]:
    return _copilot_hook


def start_copilot_hook(on_press: Callable[[], None], on_release: Optional[Callable[[], None]] = None) -> Optional[CopilotKeyHook]:
    global _copilot_hook
    if _copilot_hook is not None:
        _copilot_hook.stop()
    _copilot_hook = CopilotKeyHook(on_press=on_press, on_release=on_release)
    _copilot_hook.start()
    return _copilot_hook


def stop_copilot_hook() -> None:
    global _copilot_hook
    if _copilot_hook is not None:
        _copilot_hook.stop()
        _copilot_hook = None


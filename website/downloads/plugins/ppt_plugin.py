import logging
import os
import re
import time
import ctypes
import subprocess
from typing import Callable, Dict, List, Optional
from plugins.base_plugin import BasePlugin
from plugins.win_keys import kill_process

logger = logging.getLogger("PRIVACY68.Plugin.PPT")
user32 = ctypes.windll.user32

# Virtual Key Codes
VK_LBUTTON = 0x01
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_PAUSE = 0x13
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21  # Page Up
VK_NEXT = 0x22   # Page Down
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E

# Standard Alphanumeric Keys
VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_5 = 0x35
VK_6 = 0x36
VK_7 = 0x37
VK_8 = 0x38
VK_9 = 0x39

VK_A = 0x41
VK_B = 0x42
VK_C = 0x43
VK_D = 0x44
VK_E = 0x45
VK_F = 0x46
VK_G = 0x47
VK_H = 0x48
VK_I = 0x49
VK_J = 0x4A
VK_L = 0x4C
VK_M = 0x4D
VK_N = 0x4E
VK_O = 0x4F
VK_P = 0x50
VK_S = 0x53
VK_W = 0x57
VK_Y = 0x59
VK_Z = 0x5A

# Function Keys
VK_F5 = 0x74
VK_F12 = 0x7B

# OEM Keys
VK_OEM_PLUS = 0xBB   # '+' key
VK_OEM_MINUS = 0xBD  # '-' key

KEYEVENTF_KEYUP = 0x0002


def _press_key(vk: int, delay: float = 0.04):
    """Presses and releases a single virtual key code."""
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(delay)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _press_combo(*vkeys, delay: float = 0.05):
    """Presses multiple keys down in sequence and releases them in reverse order."""
    for vk in vkeys:
        user32.keybd_event(vk, 0, 0, 0)
    time.sleep(delay)
    for vk in reversed(vkeys):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _get_powerpoint_exe() -> Optional[str]:
    """Finds PowerPoint executable from Windows Registry or standard paths."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\powerpnt.exe") as key:
            val, _ = winreg.QueryValueEx(key, "")
            if val and os.path.exists(val):
                return val
    except Exception:
        pass

    candidates = [
        r"C:\Program Files\Microsoft Office\Root\Office16\POWERPNT.EXE",
        r"C:\Program Files (x86)\Microsoft Office\Root\Office16\POWERPNT.EXE",
        r"C:\Program Files\Microsoft Office\Office16\POWERPNT.EXE",
        r"C:\Program Files (x86)\Microsoft Office\Office16\POWERPNT.EXE",
        r"C:\Program Files\Microsoft Office\Office15\POWERPNT.EXE",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _find_ppt_window() -> Optional[int]:
    """
    Finds the active PowerPoint window handle (Slideshow or Editor).
    Prioritizes active Slide Show full-screen windows if currently presenting.
    """
    found_windows = []

    def enum_windows_proc(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                t_lower = title.lower()
                if "powerpoint" in t_lower or "slide show" in t_lower:
                    found_windows.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    proc = WNDENUMPROC(enum_windows_proc)
    user32.EnumWindows(proc, 0)

    # 1. Check for active full-screen Slide Show window first
    for hwnd, title in found_windows:
        if "slide show" in title.lower():
            return hwnd

    # 2. Return general PowerPoint window
    if found_windows:
        return found_windows[0][0]

    return None


def _focus_powerpoint() -> bool:
    """Brings PowerPoint or its active slideshow into the foreground."""
    hwnd = _find_ppt_window()
    if hwnd:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.1)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.12)
        return True
    return False


WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
}


def _extract_slide_number(text: str) -> Optional[int]:
    """Extracts a slide number from user speech (digits or word forms)."""
    text_clean = text.lower()
    # Check for direct digits e.g. "slide 5", "5"
    digits = re.findall(r'\b\d+\b', text_clean)
    if digits:
        try:
            return int(digits[0])
        except ValueError:
            pass

    # Check for word representations
    for word, num in WORD_TO_NUM.items():
        if re.search(rf'\b{word}\b', text_clean):
            return num

    return None


class PPTPlugin(BasePlugin):
    """
    Comprehensive PowerPoint Full Control Plugin for PRIVACY68 Voice Assistant.
    Provides complete hands-free navigation, slide shows, annotations, editing, and screen controls.
    """
    id = "ppt"
    name = "PowerPoint Controller"
    icon = "🖥️"
    description = "Full control for Microsoft PowerPoint: slides, slideshows, laser pointer, pen, blank screen, and navigation."
    version = "1.0.0"
    author = "PRIVACY68 Core"
    is_builtin = False

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            # Application Lifecycle
            "ppt.open": self.open_powerpoint,
            "ppt.close": self.close_powerpoint,
            "ppt.focus": self.focus_powerpoint,

            # Slideshow Control
            "ppt.start_slideshow": self.start_slideshow,
            "ppt.start_from_current": self.start_from_current_slide,
            "ppt.end_slideshow": self.end_slideshow,
            "ppt.next_slide": self.next_slide,
            "ppt.prev_slide": self.prev_slide,
            "ppt.first_slide": self.first_slide,
            "ppt.last_slide": self.last_slide,
            "ppt.goto_slide": self.goto_slide,

            # Screen & Live Display Controls
            "ppt.black_screen": self.toggle_black_screen,
            "ppt.white_screen": self.toggle_white_screen,
            "ppt.toggle_subtitles": self.toggle_subtitles,

            # Presenter Tools & Annotation
            "ppt.laser_pointer": self.enable_laser_pointer,
            "ppt.pen": self.enable_pen,
            "ppt.arrow_pointer": self.enable_arrow_pointer,
            "ppt.erase_ink": self.erase_ink,

            # Presentation Editing & Management
            "ppt.new_presentation": self.new_presentation,
            "ppt.new_slide": self.new_slide,
            "ppt.duplicate_slide": self.duplicate_slide,
            "ppt.save": self.save_presentation,
            "ppt.save_as": self.save_as_presentation,
            "ppt.open_file": self.open_presentation_file,
            "ppt.undo": self.undo,
            "ppt.redo": self.redo,
            "ppt.zoom_in": self.zoom_in,
            "ppt.zoom_out": self.zoom_out,
            "ppt.play_pause_media": self.play_pause_media,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            # Application Lifecycle
            "ppt.open": [
                "open powerpoint",
                "launch powerpoint",
                "start powerpoint",
                "open power point",
                "launch power point",
                "start power point",
                "open ppt",
                "launch ppt",
                "start ppt",
                "open ms powerpoint",
                "launch ms powerpoint",
                "start presentation app",
            ],
            "ppt.close": [
                "close powerpoint",
                "exit powerpoint",
                "quit powerpoint",
                "kill powerpoint",
                "close power point",
                "exit power point",
                "close ppt",
                "exit ppt",
            ],
            "ppt.focus": [
                "focus powerpoint",
                "switch to powerpoint",
                "bring powerpoint to front",
                "show powerpoint",
            ],

            # Slideshow Control
            "ppt.start_slideshow": [
                "start presentation",
                "start slideshow",
                "begin presentation",
                "play presentation",
                "present slides",
                "start the slide show",
                "run presentation",
                "f5 presentation",
            ],
            "ppt.start_from_current": [
                "present from current slide",
                "start from current slide",
                "slideshow from current",
                "resume presentation here",
                "present this slide",
            ],
            "ppt.end_slideshow": [
                "end presentation",
                "stop presentation",
                "exit slideshow",
                "end slideshow",
                "stop slideshow",
                "close presentation view",
                "stop presenting",
                "escape presentation",
            ],
            "ppt.next_slide": [
                "next slide",
                "go to next slide",
                "advance slide",
                "next page",
                "move forward slide",
                "next slide please",
                "forward slide",
            ],
            "ppt.prev_slide": [
                "previous slide",
                "go back slide",
                "back slide",
                "prev slide",
                "prior slide",
                "last slide go back",
                "slide back",
            ],
            "ppt.first_slide": [
                "go to first slide",
                "first slide",
                "jump to beginning",
                "start of presentation",
                "go to start slide",
                "beginning slide",
            ],
            "ppt.last_slide": [
                "go to last slide",
                "last slide",
                "jump to end",
                "end of presentation slide",
                "final slide",
            ],
            "ppt.goto_slide": [
                "go to slide",
                "jump to slide",
                "switch to slide",
                "open slide number",
                "go to slide 1",
                "go to slide 2",
                "go to slide 3",
                "go to slide 4",
                "go to slide 5",
                "go to slide 6",
                "go to slide 7",
                "go to slide 8",
                "go to slide 9",
                "go to slide 10",
            ],

            # Screen & Live Display Controls
            "ppt.black_screen": [
                "black screen",
                "blank screen",
                "turn screen black",
                "pause presentation screen",
                "blackout screen",
            ],
            "ppt.white_screen": [
                "white screen",
                "whiteout screen",
                "turn screen white",
            ],
            "ppt.toggle_subtitles": [
                "toggle subtitles",
                "toggle captions",
                "turn on subtitles",
                "turn on captions",
                "turn off subtitles",
            ],

            # Presenter Tools & Annotation
            "ppt.laser_pointer": [
                "laser pointer",
                "turn on laser pointer",
                "show laser pointer",
                "activate laser",
            ],
            "ppt.pen": [
                "turn on pen",
                "pen tool",
                "activate pen",
                "draw mode",
            ],
            "ppt.arrow_pointer": [
                "arrow pointer",
                "normal pointer",
                "mouse pointer",
                "turn off laser",
                "turn off pen",
            ],
            "ppt.erase_ink": [
                "erase ink",
                "clear drawings",
                "erase annotations",
                "clear slide ink",
            ],

            # Presentation Editing & Management
            "ppt.new_presentation": [
                "new presentation",
                "create new presentation",
                "new ppt file",
                "create blank presentation",
            ],
            "ppt.new_slide": [
                "new slide",
                "insert slide",
                "add slide",
                "create new slide",
            ],
            "ppt.duplicate_slide": [
                "duplicate slide",
                "copy slide",
                "clone slide",
            ],
            "ppt.save": [
                "save presentation",
                "save ppt",
                "save slide",
                "save this presentation",
            ],
            "ppt.save_as": [
                "save presentation as",
                "save ppt as",
            ],
            "ppt.open_file": [
                "open presentation file",
                "open ppt file",
                "open slide file",
                "open existing presentation",
            ],
            "ppt.undo": [
                "undo slide",
                "undo ppt change",
            ],
            "ppt.redo": [
                "redo slide",
                "redo ppt change",
            ],
            "ppt.zoom_in": [
                "ppt zoom in",
                "zoom in slide",
                "zoom into presentation",
            ],
            "ppt.zoom_out": [
                "ppt zoom out",
                "zoom out slide",
                "zoom out presentation",
            ],
            "ppt.play_pause_media": [
                "play slide video",
                "pause slide video",
                "play slide audio",
                "pause presentation video",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "ppt.open": "- ppt.open: Opens Microsoft PowerPoint application.",
            "ppt.close": "- ppt.close: Closes PowerPoint and all presentations.",
            "ppt.focus": "- ppt.focus: Brings PowerPoint or the active slideshow to the foreground.",
            "ppt.start_slideshow": "- ppt.start_slideshow: Starts the full-screen PowerPoint slideshow from the first slide.",
            "ppt.start_from_current": "- ppt.start_from_current: Starts the slideshow beginning from the currently selected slide.",
            "ppt.end_slideshow": "- ppt.end_slideshow: Exits the presentation slideshow mode back to editor.",
            "ppt.next_slide": "- ppt.next_slide: Navigates to the next slide in PowerPoint.",
            "ppt.prev_slide": "- ppt.prev_slide: Navigates to the previous slide in PowerPoint.",
            "ppt.first_slide": "- ppt.first_slide: Jumps to the very first slide.",
            "ppt.last_slide": "- ppt.last_slide: Jumps to the last slide in the deck.",
            "ppt.goto_slide": "- ppt.goto_slide: Jumps directly to a specific slide number in PowerPoint.",
            "ppt.black_screen": "- ppt.black_screen: Toggles a blank black screen during presentation.",
            "ppt.white_screen": "- ppt.white_screen: Toggles a blank white screen during presentation.",
            "ppt.toggle_subtitles": "- ppt.toggle_subtitles: Toggles live subtitles/captions during a slideshow.",
            "ppt.laser_pointer": "- ppt.laser_pointer: Switches the cursor to a laser pointer during slideshow.",
            "ppt.pen": "- ppt.pen: Activates the drawing pen tool during slideshow.",
            "ppt.arrow_pointer": "- ppt.arrow_pointer: Reverts the cursor back to the standard arrow pointer.",
            "ppt.erase_ink": "- ppt.erase_ink: Erases all drawn ink annotations on the current slide.",
            "ppt.new_presentation": "- ppt.new_presentation: Creates a new blank PowerPoint presentation.",
            "ppt.new_slide": "- ppt.new_slide: Inserts a new slide into the presentation.",
            "ppt.duplicate_slide": "- ppt.duplicate_slide: Duplicates the currently selected slide.",
            "ppt.save": "- ppt.save: Saves the current PowerPoint presentation.",
            "ppt.save_as": "- ppt.save_as: Opens the Save As dialog for the presentation.",
            "ppt.open_file": "- ppt.open_file: Opens an existing presentation file or triggers file picker.",
            "ppt.undo": "- ppt.undo: Reverses the last action in PowerPoint.",
            "ppt.redo": "- ppt.redo: Redoes the last undone action in PowerPoint.",
            "ppt.zoom_in": "- ppt.zoom_in: Zooms in on the PowerPoint slide view.",
            "ppt.zoom_out": "- ppt.zoom_out: Zooms out on the PowerPoint slide view.",
            "ppt.play_pause_media": "- ppt.play_pause_media: Plays or pauses embedded media in the current slide.",
        }

    # ==================== Action Implementations ==================== #

    def open_powerpoint(self, text: str = "") -> bool:
        """Launches PowerPoint or brings existing window to focus."""
        try:
            if _focus_powerpoint():
                logger.info("Focused existing PowerPoint window.")
                return True

            exe_path = _get_powerpoint_exe()
            if exe_path:
                subprocess.Popen([exe_path])
                logger.info(f"Launched PowerPoint executable: {exe_path}")
                return True
            else:
                subprocess.Popen("start powerpnt", shell=True)
                logger.info("Launched PowerPoint via shell command.")
                return True
        except Exception as e:
            logger.error(f"Failed to launch PowerPoint: {e}")
            return False

    def close_powerpoint(self, text: str = "") -> bool:
        """Kills the PowerPoint process cleanly."""
        logger.info("Closing PowerPoint...")
        return kill_process("POWERPNT.EXE")

    def focus_powerpoint(self, text: str = "") -> bool:
        """Brings PowerPoint to the front."""
        return _focus_powerpoint()

    def start_slideshow(self, text: str = "") -> bool:
        """Starts the presentation from the beginning (F5)."""
        _focus_powerpoint()
        _press_key(VK_F5)
        logger.info("Triggered slideshow start (F5)")
        return True

    def start_from_current_slide(self, text: str = "") -> bool:
        """Starts presentation from current slide (Shift + F5)."""
        _focus_powerpoint()
        _press_combo(VK_SHIFT, VK_F5)
        logger.info("Triggered slideshow from current slide (Shift+F5)")
        return True

    def end_slideshow(self, text: str = "") -> bool:
        """Exits slideshow view (Escape)."""
        _focus_powerpoint()
        _press_key(VK_ESCAPE)
        logger.info("Ended slideshow (Escape)")
        return True

    def next_slide(self, text: str = "") -> bool:
        """Advances to the next slide (Right Arrow / Page Down)."""
        _focus_powerpoint()
        _press_key(VK_RIGHT)
        logger.info("Advanced to next slide (Right Arrow)")
        return True

    def prev_slide(self, text: str = "") -> bool:
        """Returns to the previous slide (Left Arrow / Page Up)."""
        _focus_powerpoint()
        _press_key(VK_LEFT)
        logger.info("Navigated to previous slide (Left Arrow)")
        return True

    def first_slide(self, text: str = "") -> bool:
        """Jumps to the first slide (Home / Ctrl+Home)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_HOME)
        logger.info("Navigated to first slide (Ctrl+Home)")
        return True

    def last_slide(self, text: str = "") -> bool:
        """Jumps to the last slide (End / Ctrl+End)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_END)
        logger.info("Navigated to last slide (Ctrl+End)")
        return True

    def goto_slide(self, text: str = "") -> bool:
        """Jumps directly to a specified slide number."""
        num = _extract_slide_number(text)
        if num is None:
            logger.warning(f"Could not parse slide number from: '{text}'")
            return False

        _focus_powerpoint()
        # In PowerPoint slideshow mode, typing <number> followed by Enter jumps to that slide
        digits = str(num)
        for d in digits:
            vk = VK_0 + int(d)
            _press_key(vk, delay=0.03)
            time.sleep(0.02)
        _press_key(VK_RETURN)
        logger.info(f"Jumped to slide {num}")
        return True

    def toggle_black_screen(self, text: str = "") -> bool:
        """Toggles a blank black screen in presentation mode (B)."""
        _focus_powerpoint()
        _press_key(VK_B)
        logger.info("Toggled black screen (B)")
        return True

    def toggle_white_screen(self, text: str = "") -> bool:
        """Toggles a blank white screen in presentation mode (W)."""
        _focus_powerpoint()
        _press_key(VK_W)
        logger.info("Toggled white screen (W)")
        return True

    def toggle_subtitles(self, text: str = "") -> bool:
        """Toggles live subtitles / captions (J)."""
        _focus_powerpoint()
        _press_key(VK_J)
        logger.info("Toggled live subtitles (J)")
        return True

    def enable_laser_pointer(self, text: str = "") -> bool:
        """Activates the laser pointer tool (Ctrl + L)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_L)
        logger.info("Activated laser pointer (Ctrl+L)")
        return True

    def enable_pen(self, text: str = "") -> bool:
        """Activates the drawing pen tool (Ctrl + P)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_P)
        logger.info("Activated pen tool (Ctrl+P)")
        return True

    def enable_arrow_pointer(self, text: str = "") -> bool:
        """Reverts cursor to standard arrow pointer (Ctrl + A)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_A)
        logger.info("Restored standard arrow pointer (Ctrl+A)")
        return True

    def erase_ink(self, text: str = "") -> bool:
        """Erases all pen annotations from the current slide (E)."""
        _focus_powerpoint()
        _press_key(VK_E)
        logger.info("Erased ink annotations (E)")
        return True

    def new_presentation(self, text: str = "") -> bool:
        """Creates a new presentation (Ctrl + N)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_N)
        logger.info("Created new presentation (Ctrl+N)")
        return True

    def new_slide(self, text: str = "") -> bool:
        """Inserts a new slide (Ctrl + M)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_M)
        logger.info("Inserted new slide (Ctrl+M)")
        return True

    def duplicate_slide(self, text: str = "") -> bool:
        """Duplicates the current slide (Ctrl + D)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_D)
        logger.info("Duplicated current slide (Ctrl+D)")
        return True

    def save_presentation(self, text: str = "") -> bool:
        """Saves current presentation (Ctrl + S)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_S)
        logger.info("Saved presentation (Ctrl+S)")
        return True

    def save_as_presentation(self, text: str = "") -> bool:
        """Opens Save As dialog (F12)."""
        _focus_powerpoint()
        _press_key(VK_F12)
        logger.info("Opened Save As dialog (F12)")
        return True

    def open_presentation_file(self, text: str = "") -> bool:
        """Triggers open file dialog (Ctrl + O)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_O)
        logger.info("Opened presentation dialog (Ctrl+O)")
        return True

    def undo(self, text: str = "") -> bool:
        """Reverses the last action (Ctrl + Z)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_Z)
        logger.info("Undid last action (Ctrl+Z)")
        return True

    def redo(self, text: str = "") -> bool:
        """Redoes the undone action (Ctrl + Y)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_Y)
        logger.info("Redid action (Ctrl+Y)")
        return True

    def zoom_in(self, text: str = "") -> bool:
        """Zooms into the slide view (Ctrl + Plus)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_OEM_PLUS)
        logger.info("Zoomed in slide view")
        return True

    def zoom_out(self, text: str = "") -> bool:
        """Zooms out of the slide view (Ctrl + Minus)."""
        _focus_powerpoint()
        _press_combo(VK_CONTROL, VK_OEM_MINUS)
        logger.info("Zoomed out slide view")
        return True

    def play_pause_media(self, text: str = "") -> bool:
        """Plays/pauses embedded media (Alt + P)."""
        _focus_powerpoint()
        _press_combo(VK_MENU, VK_P)
        logger.info("Toggled slide media play/pause (Alt+P)")
        return True

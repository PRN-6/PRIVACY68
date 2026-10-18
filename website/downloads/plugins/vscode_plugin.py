import logging
import os
import re
import subprocess
import time
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_utils import kill_process, type_text

logger = logging.getLogger("PRIVACY68.Plugin.VSCode")

CODE_EXE_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft VS Code", "Code.exe"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft VS Code", "Code.exe"),
]

class VSCodePlugin(BasePlugin):
    """
    Complete Professional Visual Studio Code Automation Suite for PRIVACY68.
    Provides hands-free voice control over:
    - Window & Session Management (Launch, Close, New Window, Zen Mode)
    - Terminal Automation (Open, Toggle, Hide, Clear, Split, Kill)
    - Side Bar & Panels (Toggle Sidebar, Explorer, Git/Source Control, Search, Debug, Extensions, Bottom Panel)
    - Editor & Code Operations (Save, Save All, Close Tab, Close All, Format Document, Comment, Word Wrap, Split Editor)
    - Navigation & Search (Quick Open File, Command Palette, Go to Line, Find in File)
    - Debugging & Execution (Start Debug, Run without Debug, Stop Debug, Toggle Breakpoint, Step Over/Into)
    - Zoom & View Controls (Zoom In, Zoom Out, Reset Zoom)
    """
    id = "vscode"
    name = "VS Code Master"
    icon = "🧑‍💻"
    description = "Complete hands-free automation for Visual Studio Code: terminal, sidebars, tabs, formatting, debugging, and file navigation."
    version = "2.0.0"
    author = "PRIVACY68 Core"
    is_builtin = False
    category = "Developer"
    plugin_type = "IDE & Code"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            # Application Lifecycle
            "vscode.open": self.open_vscode,
            "vscode.close": self.close_vscode,
            "vscode.new_window": self.new_window,

            # Terminal Operations
            "vscode.open_terminal": self.open_terminal,
            "vscode.toggle_terminal": self.toggle_terminal,
            "vscode.hide_terminal": self.hide_terminal,
            "vscode.clear_terminal": self.clear_terminal,
            "vscode.split_terminal": self.split_terminal,

            # Side Bar & Layout Views
            "vscode.toggle_sidebar": self.toggle_sidebar,
            "vscode.hide_sidebar": self.hide_sidebar,
            "vscode.show_sidebar": self.show_sidebar,
            "vscode.open_explorer": self.open_explorer,
            "vscode.open_search": self.open_search,
            "vscode.open_git": self.open_git,
            "vscode.open_debug_panel": self.open_debug_panel,
            "vscode.open_extensions": self.open_extensions,
            "vscode.toggle_panel": self.toggle_panel,
            "vscode.toggle_zen_mode": self.toggle_zen_mode,

            # Editor & Tab Operations
            "vscode.save_file": self.save_file,
            "vscode.save_all": self.save_all,
            "vscode.close_tab": self.close_tab,
            "vscode.close_all_tabs": self.close_all_tabs,
            "vscode.split_editor": self.split_editor,
            "vscode.format_document": self.format_document,
            "vscode.toggle_comment": self.toggle_comment,
            "vscode.toggle_word_wrap": self.toggle_word_wrap,

            # Navigation & Palette
            "vscode.find_file": self.find_file,
            "vscode.command_palette": self.command_palette,
            "vscode.go_to_line": self.go_to_line,
            "vscode.find_in_file": self.find_in_file,
            "vscode.search_files": self.search_files_on_disk,

            # Debugging & Execution
            "vscode.start_debugging": self.start_debugging,
            "vscode.run_without_debugging": self.run_without_debugging,
            "vscode.stop_debugging": self.stop_debugging,
            "vscode.toggle_breakpoint": self.toggle_breakpoint,

            # Zoom & View
            "vscode.zoom_in": self.zoom_in,
            "vscode.zoom_out": self.zoom_out,
            "vscode.zoom_reset": self.zoom_reset,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            # Application Lifecycle
            "vscode.open": [
                "open vscode",
                "open vs code",
                "launch vscode",
                "launch vs code",
                "start vscode",
                "start vs code",
                "open visual studio code",
                "launch visual studio code",
                "start visual studio code",
                "focus vscode",
                "focus vs code",
            ],
            "vscode.close": [
                "close vscode",
                "close vs code",
                "exit vscode",
                "exit vs code",
                "quit vscode",
                "quit vs code",
                "kill vscode",
                "kill vs code",
                "close visual studio code",
                "terminate vscode",
            ],
            "vscode.new_window": [
                "new window in vscode",
                "new window in vs code",
                "open new window in vscode",
                "open new vs code window",
                "vscode new window",
                "vs code new window",
            ],

            # Terminal Operations
            "vscode.open_terminal": [
                "open terminal in vscode",
                "open terminal in vs code",
                "open terminal in visual studio code",
                "open vscode terminal",
                "open vs code terminal",
                "new terminal in vscode",
                "new terminal in vs code",
                "create terminal in vscode",
                "create terminal in vs code",
                "open integrated terminal",
                "open integrated terminal in vs code",
                "open a terminal in vscode",
                "open a terminal in vs code",
                "start terminal in vscode",
                "start terminal in vs code",
            ],
            "vscode.toggle_terminal": [
                "toggle terminal in vscode",
                "toggle terminal in vs code",
                "toggle vscode terminal",
                "toggle vs code terminal",
                "toggle integrated terminal",
                "switch terminal in vscode",
            ],
            "vscode.hide_terminal": [
                "hide terminal in vscode",
                "hide terminal in vs code",
                "hide vscode terminal",
                "hide vs code terminal",
                "close terminal in vscode",
                "close terminal in vs code",
                "dismiss terminal in vscode",
            ],
            "vscode.clear_terminal": [
                "clear terminal in vscode",
                "clear terminal in vs code",
                "clear vscode terminal",
                "clear vs code terminal",
                "clean terminal in vscode",
            ],
            "vscode.split_terminal": [
                "split terminal in vscode",
                "split terminal in vs code",
                "split vscode terminal",
                "split vs code terminal",
            ],

            # Side Bar & Layout Views
            "vscode.toggle_sidebar": [
                "toggle sidebar in vscode",
                "toggle sidebar in vs code",
                "toggle side bar in vscode",
                "toggle side bar in vs code",
                "toggle vscode sidebar",
                "toggle vs code sidebar",
            ],
            "vscode.hide_sidebar": [
                "hide sidebar in vscode",
                "hide sidebar in vs code",
                "hide side bar in vscode",
                "hide side bar in vs code",
                "close sidebar in vscode",
                "close sidebar in vs code",
                "hide vscode sidebar",
                "hide vs code sidebar",
            ],
            "vscode.show_sidebar": [
                "show sidebar in vscode",
                "show sidebar in vs code",
                "show side bar in vscode",
                "show side bar in vs code",
                "open sidebar in vscode",
                "open sidebar in vs code",
            ],
            "vscode.open_explorer": [
                "open explorer in vscode",
                "open explorer in vs code",
                "show explorer in vscode",
                "show explorer in vs code",
                "open file tree in vscode",
                "show file tree in vscode",
                "open file explorer in vscode",
                "open file explorer in vs code",
                "open files sidebar in vscode",
            ],
            "vscode.open_search": [
                "open search in vscode",
                "open search in vs code",
                "show search in vscode",
                "show search in vs code",
                "search in workspace in vscode",
                "global search in vscode",
                "global search in vs code",
            ],
            "vscode.open_git": [
                "open git in vscode",
                "open git in vs code",
                "show git in vscode",
                "show git in vs code",
                "open source control in vscode",
                "open source control in vs code",
                "show source control in vscode",
            ],
            "vscode.open_debug_panel": [
                "open debug panel in vscode",
                "open debug panel in vs code",
                "show debug panel in vscode",
                "show debug in vs code",
                "open run and debug in vscode",
            ],
            "vscode.open_extensions": [
                "open extensions in vscode",
                "open extensions in vs code",
                "show extensions in vscode",
                "show extensions in vs code",
                "open plugin marketplace in vscode",
                "open marketplace in vs code",
            ],
            "vscode.toggle_panel": [
                "toggle panel in vscode",
                "toggle panel in vs code",
                "toggle bottom panel in vscode",
                "toggle bottom panel in vs code",
                "hide panel in vscode",
                "show panel in vscode",
            ],
            "vscode.toggle_zen_mode": [
                "toggle zen mode in vscode",
                "toggle zen mode in vs code",
                "enable zen mode in vscode",
                "zen mode in vscode",
                "zen mode in vs code",
                "distraction free mode in vscode",
            ],

            # Editor & Tab Operations
            "vscode.save_file": [
                "save file in vscode",
                "save file in vs code",
                "save this file in vscode",
                "save code in vscode",
                "save in vs code",
                "save in vscode",
            ],
            "vscode.save_all": [
                "save all files in vscode",
                "save all files in vs code",
                "save all in vscode",
                "save all in vs code",
            ],
            "vscode.close_tab": [
                "close tab in vscode",
                "close tab in vs code",
                "close file in vscode",
                "close file in vs code",
                "close current tab in vscode",
            ],
            "vscode.close_all_tabs": [
                "close all tabs in vscode",
                "close all tabs in vs code",
                "close all files in vscode",
                "close all files in vs code",
            ],
            "vscode.split_editor": [
                "split editor in vscode",
                "split editor in vs code",
                "split screen in vscode",
                "split screen in vs code",
                "split editor right in vscode",
            ],
            "vscode.format_document": [
                "format document in vscode",
                "format document in vs code",
                "format code in vscode",
                "format code in vs code",
                "format file in vscode",
                "format file in vs code",
                "beautify code in vscode",
                "clean code in vscode",
            ],
            "vscode.toggle_comment": [
                "comment code in vscode",
                "comment code in vs code",
                "toggle comment in vscode",
                "toggle comment in vs code",
                "comment line in vscode",
                "uncomment line in vscode",
            ],
            "vscode.toggle_word_wrap": [
                "toggle word wrap in vscode",
                "toggle word wrap in vs code",
                "toggle wrap in vscode",
                "toggle wrap in vs code",
                "word wrap in vscode",
                "word wrap in vs code",
            ],

            # Navigation & Palette
            "vscode.find_file": [
                "find file in vscode",
                "find file in vs code",
                "open file in vscode",
                "open file in vs code",
                "search file in vscode",
                "search file in vs code",
                "quick open in vscode",
                "quick open in vs code",
                "jump to file in vscode",
                "jump to file in vs code",
            ],
            "vscode.command_palette": [
                "open command palette in vscode",
                "open command palette in vs code",
                "show command palette in vscode",
                "show command palette in vs code",
                "command palette in vscode",
                "command palette in vs code",
            ],
            "vscode.go_to_line": [
                "go to line in vscode",
                "go to line in vs code",
                "jump to line in vscode",
                "jump to line in vs code",
            ],
            "vscode.find_in_file": [
                "find in file in vscode",
                "find in file in vs code",
                "search in file in vscode",
                "find text in vscode",
            ],
            "vscode.search_files": [
                "search for a file in vscode",
                "search for a file in vs code",
                "search files on computer in vscode",
                "locate file on disk in vscode",
            ],

            # Debugging & Execution
            "vscode.start_debugging": [
                "start debugging in vscode",
                "start debugging in vs code",
                "run debug in vscode",
                "run debug in vs code",
                "debug in vscode",
                "debug in vs code",
            ],
            "vscode.run_without_debugging": [
                "run code in vscode",
                "run code in vs code",
                "run without debugging in vscode",
                "run without debugging in vs code",
                "execute code in vscode",
                "execute file in vscode",
            ],
            "vscode.stop_debugging": [
                "stop debugging in vscode",
                "stop debugging in vs code",
                "stop debug in vscode",
                "stop debug in vs code",
            ],
            "vscode.toggle_breakpoint": [
                "toggle breakpoint in vscode",
                "toggle breakpoint in vs code",
                "set breakpoint in vscode",
                "remove breakpoint in vscode",
                "add breakpoint in vscode",
            ],

            # Zoom & View
            "vscode.zoom_in": [
                "zoom in in vscode",
                "zoom in in vs code",
                "zoom in vscode",
                "zoom in vs code",
                "increase font size in vscode",
            ],
            "vscode.zoom_out": [
                "zoom out in vscode",
                "zoom out in vs code",
                "zoom out vscode",
                "zoom out vs code",
                "decrease font size in vscode",
            ],
            "vscode.zoom_reset": [
                "reset zoom in vscode",
                "reset zoom in vs code",
                "reset font in vscode",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "vscode.open": "- vscode.open: Launch or bring Visual Studio Code to the foreground.",
            "vscode.close": "- vscode.close: Close or terminate Visual Studio Code.",
            "vscode.new_window": "- vscode.new_window: Open a new VS Code window.",
            "vscode.open_terminal": "- vscode.open_terminal: Open a new integrated terminal in VS Code.",
            "vscode.toggle_terminal": "- vscode.toggle_terminal: Toggle terminal visibility on/off.",
            "vscode.hide_terminal": "- vscode.hide_terminal: Hide or dismiss the active terminal.",
            "vscode.clear_terminal": "- vscode.clear_terminal: Clear terminal screen content.",
            "vscode.split_terminal": "- vscode.split_terminal: Split current terminal into side-by-side panes.",
            "vscode.toggle_sidebar": "- vscode.toggle_sidebar: Show or hide the Primary Side Bar.",
            "vscode.hide_sidebar": "- vscode.hide_sidebar: Hide the Primary Side Bar.",
            "vscode.show_sidebar": "- vscode.show_sidebar: Show the Primary Side Bar.",
            "vscode.open_explorer": "- vscode.open_explorer: Focus the File Explorer tree view.",
            "vscode.open_search": "- vscode.open_search: Focus global workspace search.",
            "vscode.open_git": "- vscode.open_git: Focus Source Control / Git view.",
            "vscode.open_debug_panel": "- vscode.open_debug_panel: Focus Run and Debug view.",
            "vscode.open_extensions": "- vscode.open_extensions: Focus Extensions Marketplace.",
            "vscode.toggle_panel": "- vscode.toggle_panel: Show/hide the bottom output panel.",
            "vscode.toggle_zen_mode": "- vscode.toggle_zen_mode: Toggle distraction-free Zen Mode.",
            "vscode.save_file": "- vscode.save_file: Save the active open file.",
            "vscode.save_all": "- vscode.save_all: Save all modified files in the workspace.",
            "vscode.close_tab": "- vscode.close_tab: Close the current active editor tab.",
            "vscode.close_all_tabs": "- vscode.close_all_tabs: Close all open tabs in the editor.",
            "vscode.split_editor": "- vscode.split_editor: Split the editor pane horizontally or vertically.",
            "vscode.format_document": "- vscode.format_document: Auto-format document code formatting.",
            "vscode.toggle_comment": "- vscode.toggle_comment: Comment or uncomment the current line of code.",
            "vscode.toggle_word_wrap": "- vscode.toggle_word_wrap: Toggle text word wrap on/off.",
            "vscode.find_file": "- vscode.find_file: Quick Open file search by filename.",
            "vscode.command_palette": "- vscode.command_palette: Open the full Command Palette.",
            "vscode.go_to_line": "- vscode.go_to_line: Jump to a specific line number.",
            "vscode.find_in_file": "- vscode.find_in_file: Find in the active file.",
            "vscode.search_files": "- vscode.search_files: Find and open a file from user storage.",
            "vscode.start_debugging": "- vscode.start_debugging: Start debugging active application.",
            "vscode.run_without_debugging": "- vscode.run_without_debugging: Execute active file without debugging.",
            "vscode.stop_debugging": "- vscode.stop_debugging: Stop the active debug session.",
            "vscode.toggle_breakpoint": "- vscode.toggle_breakpoint: Toggle a code breakpoint on the current line.",
            "vscode.zoom_in": "- vscode.zoom_in: Increase the interface zoom level.",
            "vscode.zoom_out": "- vscode.zoom_out: Decrease the interface zoom level.",
            "vscode.zoom_reset": "- vscode.zoom_reset: Reset the interface zoom level.",
        }

    # ================= Helper Methods ================= #

    @staticmethod
    def _code_exe() -> str:
        """Returns the path to Code.exe if found, else empty string."""
        for candidate in CODE_EXE_CANDIDATES:
            if candidate and os.path.exists(candidate):
                return candidate
        return ""

    def _launch_vscode(self) -> bool:
        """Launches VS Code via executable or CLI."""
        try:
            exe = self._code_exe()
            if exe:
                subprocess.Popen([exe], shell=False)
            else:
                subprocess.Popen("start code", shell=True)
            logger.info("Plugin Action: VS Code launched.")
            return True
        except Exception as e:
            logger.error(f"Plugin Action: Failed to launch VS Code: {e}")
            return False

    def _focus_vscode(self) -> bool:
        """Brings an existing VS Code window to foreground."""
        from computer_use.window_manager import window_manager
        return (
            window_manager.focus_window("vs code") or
            window_manager.focus_window("Visual Studio Code") or
            window_manager.focus_window("Code")
        )

    def _ensure_focused(self) -> bool:
        """Ensures VS Code is running and focused before sending hotkeys."""
        if not self._focus_vscode():
            if not self._launch_vscode():
                return False
            time.sleep(2.5)
            self._focus_vscode()
        return True

    @staticmethod
    def _extract_query(text: str) -> str:
        """Pulls user target parameters out of spoken text."""
        cleaned = re.sub(
            r"\b(vscode|visual\s*studio\s*code|vs\s*code|code|find|search|locate|look|for|the|a|an|called|named|me|please|open|show|file|files|in|on|computer|jump|to|start|launch|line|number)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip(" \t.,:!?-")

    # ================= Action Implementations ================= #

    def open_vscode(self, text: str) -> bool:
        logger.info("Plugin Action: Opening VS Code")
        return self._launch_vscode() or self._focus_vscode()

    def close_vscode(self, text: str) -> bool:
        logger.info("Plugin Action: Closing VS Code")
        return kill_process("Code.exe")

    def new_window(self, text: str) -> bool:
        logger.info("Plugin Action: Opening new VS Code window")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "n")
        return True

    # --- Terminal ---

    def open_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Opening new integrated terminal")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "shift", "`")
        return True

    def toggle_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling integrated terminal panel")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "`")
        return True

    def hide_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Hiding integrated terminal panel")
        return self.toggle_terminal(text)

    def clear_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Clearing terminal")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "k")
        return True

    def split_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Splitting terminal pane")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "5")
        return True

    # --- Side Bar & Views ---

    def toggle_sidebar(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling primary sidebar")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "b")
        return True

    def hide_sidebar(self, text: str) -> bool:
        return self.toggle_sidebar(text)

    def show_sidebar(self, text: str) -> bool:
        return self.toggle_sidebar(text)

    def open_explorer(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Explorer view")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "e")
        return True

    def open_search(self, text: str) -> bool:
        logger.info("Plugin Action: Opening global search view")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "f")
        return True

    def open_git(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Source Control view")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "g")
        return True

    def open_debug_panel(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Run & Debug view")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "d")
        return True

    def open_extensions(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Extensions view")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "x")
        return True

    def toggle_panel(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling bottom panel")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "j")
        return True

    def toggle_zen_mode(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling Zen Mode")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.1)
        pyautogui.press("z")
        return True

    # --- Editor & Tabs ---

    def save_file(self, text: str) -> bool:
        logger.info("Plugin Action: Saving active file")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "s")
        return True

    def save_all(self, text: str) -> bool:
        logger.info("Plugin Action: Saving all files")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.1)
        pyautogui.press("s")
        return True

    def close_tab(self, text: str) -> bool:
        logger.info("Plugin Action: Closing active tab")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "w")
        return True

    def close_all_tabs(self, text: str) -> bool:
        logger.info("Plugin Action: Closing all tabs")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.1)
        pyautogui.press("w")
        return True

    def split_editor(self, text: str) -> bool:
        logger.info("Plugin Action: Splitting editor")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "\\")
        return True

    def format_document(self, text: str) -> bool:
        logger.info("Plugin Action: Formatting active document")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("shift", "alt", "f")
        return True

    def toggle_comment(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling line comment")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "/")
        return True

    def toggle_word_wrap(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling word wrap")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("alt", "z")
        return True

    # --- Navigation & Find ---

    def find_file(self, text: str) -> bool:
        query = self._extract_query(text)
        logger.info(f"Plugin Action: Quick Open file for '{query}'")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "p")
        time.sleep(0.25)
        if query:
            type_text(query)
            time.sleep(0.6)
            pyautogui.press("enter")
        return True

    def command_palette(self, text: str) -> bool:
        logger.info("Plugin Action: Opening Command Palette")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "shift", "p")
        return True

    def go_to_line(self, text: str) -> bool:
        line_match = re.search(r"\b(\d+)\b", text)
        line_num = line_match.group(1) if line_match else ""
        logger.info(f"Plugin Action: Go to line '{line_num}'")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.25)
        if line_num:
            type_text(line_num)
            time.sleep(0.3)
            pyautogui.press("enter")
        return True

    def find_in_file(self, text: str) -> bool:
        query = self._extract_query(text)
        logger.info(f"Plugin Action: Find in active file for '{query}'")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.2)
        if query:
            type_text(query)
        return True

    def search_files_on_disk(self, text: str) -> bool:
        query = self._extract_query(text)
        if not query:
            return self.find_file("")
        logger.info(f"Plugin Action: Searching disk for '{query}'")
        pattern = query if "*" in query else f"*{query}*"
        safe_pattern = pattern.replace("'", "''")
        ps_cmd = (
            f"Get-ChildItem -Path $HOME -Recurse -File -Filter '{safe_pattern}' "
            "-ErrorAction SilentlyContinue "
            "| Sort-Object LastWriteTime -Descending "
            "| Select-Object -First 1 -ExpandProperty FullName"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=25,
            )
            path = result.stdout.strip()
            if path:
                logger.info(f"Plugin Action: Found '{path}' — opening in VS Code.")
                subprocess.Popen(f'code "{path}"', shell=True)
                return True
        except Exception as e:
            logger.error(f"Plugin Action: File search failed: {e}")
        return False

    # --- Debugging & Execution ---

    def start_debugging(self, text: str) -> bool:
        logger.info("Plugin Action: Starting debug session")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.press("f5")
        return True

    def run_without_debugging(self, text: str) -> bool:
        logger.info("Plugin Action: Running code without debugging")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "f5")
        return True

    def stop_debugging(self, text: str) -> bool:
        logger.info("Plugin Action: Stopping debug session")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("shift", "f5")
        return True

    def toggle_breakpoint(self, text: str) -> bool:
        logger.info("Plugin Action: Toggling breakpoint")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.press("f9")
        return True

    # --- Zoom Controls ---

    def zoom_in(self, text: str) -> bool:
        logger.info("Plugin Action: Zooming in")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "=")
        return True

    def zoom_out(self, text: str) -> bool:
        logger.info("Plugin Action: Zooming out")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "-")
        return True

    def zoom_reset(self, text: str) -> bool:
        logger.info("Plugin Action: Resetting zoom")
        if not self._ensure_focused():
            return False
        import pyautogui
        pyautogui.FAILSAFE = False
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "numpad0")
        return True
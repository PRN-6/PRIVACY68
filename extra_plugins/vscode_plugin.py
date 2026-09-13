import ctypes
import logging
import os
import re
import subprocess
import time
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_keys import (
    VK_CONTROL,
    VK_SHIFT,
    press_hotkey,
    trigger_press_enter,
    type_text,
    kill_process,
)

logger = logging.getLogger("PRIVACY68.Plugin.VSCode")

# Virtual-Key Codes used by this plugin
VK_P = 0x50        # P key  (Quick Open file)
VK_F = 0x46        # F key  (full-text search)
VK_OEM_3 = 0xC0    # ` key (integrated terminal)

CODE_EXE_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft VS Code", "Code.exe"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft VS Code", "Code.exe"),
]

class VSCodePlugin(BasePlugin):
    """
    Standalone VS Code plugin for PRIVACY68 Assistant.
    Provides launch, close, open terminal, quick-open files, and on-disk file search.
    """
    id = "vscode"
    name = "VS Code"
    icon = "🧑‍💻"
    description = "Control Visual Studio Code: launch, close, open terminal, find files."
    version = "1.0.0"
    author = "Community Plugin"
    is_builtin = False

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "vscode.open": self.open_vscode,
            "vscode.close": self.close_vscode,
            "vscode.open_terminal": self.open_terminal,
            "vscode.find_file": self.find_file,
            "vscode.search_files": self.search_files_on_disk,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "vscode.open": [
                "open vscode",
                "launch vscode",
                "start vscode",
                "open visual studio code",
                "launch visual studio code",
                "open vs code",
                "start visual studio code",
            ],
            "vscode.close": [
                "close vscode",
                "exit vscode",
                "quit vscode",
                "kill vscode",
                "close visual studio code",
                "close vs code",
            ],
            "vscode.open_terminal": [
                "open terminal in vscode",
                "open vscode terminal",
                "new terminal in vscode",
                "open integrated terminal",
                "open a terminal in vscode",
                "start terminal in vscode",
            ],
            "vscode.find_file": [
                "find file in vscode",
                "open file in vscode",
                "search file in vscode",
                "find files in vscode",
                "find file called",
                "open file called",
                "jump to file in vscode",
            ],
            "vscode.search_files": [
                "search for a file in vscode",
                "search files in vscode",
                "find a file on the computer",
                "locate a file in vscode",
                "look for a file in vscode",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "vscode.open": "- vscode.open: Launch or open Visual Studio Code.",
            "vscode.close": "- vscode.close: Force close or terminate Visual Studio Code.",
            "vscode.open_terminal": "- vscode.open_terminal: Open an integrated terminal inside Visual Studio Code.",
            "vscode.find_file": "- vscode.find_file: Open the Quick Open file finder in VS Code to jump to a file by name.",
            "vscode.search_files": "- vscode.search_files: Search the user directory for a file by name and open it in VS Code.",
        }

    @staticmethod
    def _code_exe() -> str:
        """Returns the path to Code.exe if it can be found, else empty string."""
        for candidate in CODE_EXE_CANDIDATES:
            if candidate and os.path.exists(candidate):
                return candidate
        return ""

    def _launch_vscode(self) -> bool:
        """Launches VS Code via CLI or common install paths."""
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
        """Brings an existing VS Code window to the foreground. Returns True if found."""
        user32 = ctypes.windll.user32

        def _contains_vscode(hwnd) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return False
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return False
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return "visual studio code" in buf.value.lower()

        def _enum_proc(hwnd, _):
            if _contains_vscode(hwnd):
                found.append(hwnd)
                return False
            return True

        found = []
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_enum_proc), 0)
        if found:
            user32.ShowWindow(found[0], 9)      # SW_RESTORE
            user32.SetForegroundWindow(found[0])
            return True
        return False

    def _ensure_focused(self) -> bool:
        """Ensures VS Code is running and focused before sending keystrokes."""
        if not self._focus_vscode():
            if not self._launch_vscode():
                return False
            time.sleep(3.0)
            self._focus_vscode()
        return True

    @staticmethod
    def _extract_query(text: str) -> str:
        """Pulls the target file name/pattern out of a spoken command."""
        cleaned = re.sub(
            r"\b(vscode|visual\s*studio\s*code|vs\s*code|code|find|search|locate|look|for|the|a|an|called|named|me|please|open|show|file|files|in|on|computer|jump|to|start|launch)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t.,:!?-")
        return cleaned

    def open_vscode(self, text: str) -> bool:
        logger.info("Plugin Action: Opening VS Code")
        return self._launch_vscode()

    def close_vscode(self, text: str) -> bool:
        logger.info("Plugin Action: Closing VS Code")
        return kill_process("Code.exe")

    def open_terminal(self, text: str) -> bool:
        logger.info("Plugin Action: Opening integrated terminal in VS Code")
        if not self._ensure_focused():
            return False
        time.sleep(0.4)
        press_hotkey(VK_CONTROL, VK_SHIFT, VK_OEM_3)  # Ctrl+Shift+` = new terminal
        return True

    def find_file(self, text: str) -> bool:
        query = self._extract_query(text)
        logger.info(f"Plugin Action: Quick Open file finder for '{query}'")
        if not self._ensure_focused():
            return False
        time.sleep(0.4)
        press_hotkey(VK_CONTROL, VK_P)  # Ctrl+P = Quick Open
        time.sleep(0.3)
        if query:
            type_text(query)
            time.sleep(0.8)
            trigger_press_enter()
        return True

    def search_files_on_disk(self, text: str) -> bool:
        query = self._extract_query(text)
        if not query:
            logger.info("Plugin Action: No file pattern given; opening Quick Open instead.")
            return self.find_file("")
        logger.info(f"Plugin Action: Searching disk for files matching '{query}'")
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
                timeout=30,
            )
        except Exception as e:
            logger.error(f"Plugin Action: File search failed: {e}")
            return False

        path = result.stdout.strip()
        if not path:
            logger.info(f"Plugin Action: No files found matching '{query}'.")
            return False

        logger.info(f"Plugin Action: Found '{path}' — opening in VS Code.")
        try:
            subprocess.Popen(f'code "{path}"', shell=True)
            return True
        except Exception as e:
            logger.error(f"Plugin Action: Failed to open file in VS Code: {e}")
            return False
import logging
import subprocess
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin
from plugins.win_utils import kill_process

logger = logging.getLogger("PRIVACY68.Plugin.Notepad")


class NotepadPlugin(BasePlugin):
    """
    Windows Notepad automation plugin for PRIVACY68.
    Provides hands-free launching, closing, and note-taking commands.
    """
    id = "notepad"
    name = "Notepad Utility"
    icon = "📝"
    description = "Launch, close, and manage Windows Notepad text editor."
    version = "1.0.0"
    author = "Privacy68 Team"
    is_builtin = False
    category = "Productivity"
    plugin_type = "Text Editor"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "notepad.open": self.open_notepad,
            "notepad.close": self.close_notepad,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "notepad.open": [
                "open notepad",
                "launch notepad",
                "start notepad",
                "open text editor",
                "create a note",
            ],
            "notepad.close": [
                "close notepad",
                "exit notepad",
                "quit notepad",
                "kill notepad",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "notepad.open": "Opens the Windows Notepad text editor application.",
            "notepad.close": "Terminates all running Windows Notepad instances.",
        }

    def open_notepad(self, text: str = "") -> bool:
        try:
            subprocess.Popen(["notepad.exe"])
            logger.info("Notepad launched successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to open notepad: {e}")
            return False

    def close_notepad(self, text: str = "") -> bool:
        return kill_process("notepad.exe")
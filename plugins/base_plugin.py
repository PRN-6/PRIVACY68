from typing import Callable, Dict, List, Any

class BasePlugin:
    """
    Abstract base class for modular app plugins in Privacy68.
    Each plugin can expose multiple in-app voice commands and skills.

    Window interaction helpers delegate to:
      computer_use.window_manager  -- Win32-level focus/find (lightweight)
      computer_use.windows_uia     -- UIA element search (pywinauto backend)
      computer_use.actions         -- High-level UIA actions (click, type, hotkey)
    """
    id: str = "base"
    name: str = "Base Plugin"
    icon: str = "??"
    description: str = "Base plugin description"
    version: str = "1.0.0"
    author: str = "Privacy68 Team"
    is_builtin: bool = False

    def __init__(self, is_enabled: bool = True):
        self.is_enabled = is_enabled

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        """Dictionary mapping action names to executable functions."""
        raise NotImplementedError

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        """Dictionary mapping action names to fast-lane training phrases."""
        raise NotImplementedError

    @property
    def descriptions(self) -> Dict[str, str]:
        """Dictionary mapping action names to Ollama AI system prompt descriptions."""
        raise NotImplementedError

    def execute(self, action_name: str, text: str) -> bool:
        """Executes the specific action if available in this plugin."""
        if not self.is_enabled:
            return False
        action = self.actions.get(action_name)
        if action:
            return action(text)
        return False

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns Ollama-compatible JSON Schema tool specifications for this plugin."""
        tools = []
        try:
            for action_name, desc in self.descriptions.items():
                clean_name = action_name.replace(".", "_")
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"plugin_{clean_name}",
                        "description": f"[{self.name}] {desc}",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "input_text": {
                                    "type": "string",
                                    "description": f"Voice command or parameter for {action_name}"
                                }
                            },
                            "required": []
                        }
                    }
                })
        except Exception:
            tools.append({
                "type": "function",
                "function": {
                    "name": f"plugin_{self.id}",
                    "description": f"[{self.name}] {self.description}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": f"Command or instruction for {self.name}"
                            }
                        },
                        "required": ["command"]
                    }
                }
            })
        return tools

    # -------------------------- Context & Window Helpers (UIA Stack) --------------------------

    @staticmethod
    def get_active_window_title() -> str:
        """Returns the title of the currently focused foreground window."""
        try:
            from computer_use.window_manager import window_manager
            info = window_manager.get_active_window()
            return info.get("title", "")
        except Exception:
            return ""

    @staticmethod
    def is_active_window(keyword: str) -> bool:
        """Checks if the currently active foreground window title contains keyword."""
        try:
            from computer_use.window_manager import window_manager
            return window_manager.is_window_active(keyword)
        except Exception:
            return False

    @staticmethod
    def focus_window(target) -> bool:
        """Brings a window matching the title keyword or HWND to the foreground."""
        try:
            from computer_use.window_manager import window_manager
            return window_manager.focus_window(target)
        except Exception:
            return False

    @staticmethod
    def send_keys(*key_names: str):
        """
        Simulates a hotkey sequence on the active window via pyautogui.
        Pass key names as strings e.g. send_keys('ctrl', 't').
        """
        try:
            import pyautogui
            pyautogui.hotkey(*[str(k).lower() for k in key_names])
        except Exception:
            pass

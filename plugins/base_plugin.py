from typing import Callable, Dict, List, Any

class BasePlugin:
    """
    Abstract base class for modular app plugins in Privacy68.
    Each plugin can expose multiple in-app voice commands and skills.
    """
    id: str = "base"
    name: str = "Base Plugin"
    icon: str = "🧩"
    description: str = "Base plugin description"
    version: str = "1.0.0"
    author: str = "Privacy68 Team"
    is_builtin: bool = False
    
    def __init__(self, is_enabled: bool = True):
        self.is_enabled = is_enabled

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        """
        Dictionary mapping action names to executable functions.
        Example: {'brave.new_tab': self.new_tab, 'brave.close_tab': self.close_tab}
        """
        raise NotImplementedError

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        """
        Dictionary mapping action names to fast-lane training phrases.
        """
        raise NotImplementedError

    @property
    def descriptions(self) -> Dict[str, str]:
        """
        Dictionary mapping action names to Ollama AI system prompt descriptions.
        """
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
        """
        Returns Ollama-compatible JSON Schema tool specifications for this plugin.
        By default, auto-generates schema from the plugin's actions and descriptions.
        """
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

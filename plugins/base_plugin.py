from typing import Callable, Dict, List

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

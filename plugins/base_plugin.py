import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("PRIVACY68.Plugins")

class BasePlugin(ABC):
    """
    Abstract Base Class for all PRIVACY68 plugins.
    Ensures a consistent interface for the Agentic Brain to interact with.
    """

    def __init__(self):
        self.id = self.__class__.__name__.lower().replace("plugin", "")
        self.name = "Base Plugin"
        self.version = "1.0.0"
        self.description = "Abstract base for OS automation."
        self.icon = "🔌"
        self.is_enabled = True
        self.is_builtin = False
        self.category = "General"
        self.plugin_type = "Custom Application"

    @abstractmethod
    def execute(self, action: str, **kwargs) -> bool:
        """
        Main execution entry point.
        :param action: The specific action name (e.g., 'open_url').
        :param kwargs: Parameters for the action.
        :return: True if successful, False otherwise.
        """
        pass

    def log_action(self, action: str, status: str):
        logger.info(f"[{self.name}] Action: {action} | Status: {status}")

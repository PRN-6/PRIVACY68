import os
import logging
import importlib
import inspect
from typing import Dict, Any, List, Optional
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.PluginManager")

class PluginManager:
    """
    The central hub for discovering, loading, and managing PRIVACY68 plugins.
    Supports hot-reloading and dynamic capability indexing for the Agentic Brain.
    """
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_dir = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68", "plugins")
        os.makedirs(self.plugin_dir, exist_ok=True)
        self.load_builtin_plugins()
        self.load_external_plugins()

    def load_builtin_plugins(self):
        """Loads the core plugins shipped with the application."""
        try:
            from plugins.chrome_plugin import ChromePlugin
            from plugins.system_plugin import SystemPlugin

            self.register_plugin(ChromePlugin())
            self.register_plugin(SystemPlugin())
            logger.info("Built-in core plugins loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load built-in plugins: {e}")

    def load_external_plugins(self):
        """Scans the AppData plugins folder and dynamically loads Python scripts."""
        if not os.path.exists(self.plugin_dir):
            return

        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_plugin_file(os.path.join(self.plugin_dir, filename))

    def _load_plugin_file(self, filepath: str):
        """Dynamically imports a Python file and instantiates the BasePlugin subclass."""
        try:
            module_name = os.path.basename(filepath).replace(".py", "")
            # Create a unique module name to avoid collisions
            full_module_name = f"plugins.external_{module_name}"

            spec = importlib.util.spec_from_file_location(full_module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find the class that inherits from BasePlugin
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        self.register_plugin(obj())
                        logger.info(f"Dynamically loaded external plugin: {name}")
                        break
        except Exception as e:
            logger.error(f"Failed to load plugin from {filepath}: {e}")

    def register_plugin(self, plugin: BasePlugin):
        """Registers a plugin instance into the active toolkit."""
        # Use the class name as ID if no ID is provided
        pid = getattr(plugin, "id", plugin.__class__.__name__.lower().replace("plugin", ""))
        self.plugins[pid] = plugin
        logger.info(f"Plugin registered: {pid} ({plugin.name})")

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Retrieves a plugin by its ID."""
        return self.plugins.get(plugin_id.lower())

    def get_all_plugins(self) -> List[BasePlugin]:
        """Returns a list of all currently active plugins."""
        return list(self.plugins.values())

    def set_plugin_enabled(self, plugin_id: str, enabled: bool):
        """Toggles a plugin's active state."""
        plugin = self.get_plugin(plugin_id)
        if plugin:
            plugin.is_enabled = enabled

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Removes a plugin from the active list (and deletes file if external)."""
        if plugin_id in self.plugins:
            # Only allow uninstalling external plugins
            plugin = self.plugins[plugin_id]
            if getattr(plugin, "is_builtin", False):
                return False
            del self.plugins[plugin_id]
            return True
        return False

    def check_and_reload_if_changed(self):
        """Simple hot-reload check to refresh plugins without restarting the app."""
        # In a full implementation, this would track file modification times
        self.load_external_plugins()

    def create_plugin_template(self, pid, pname, picon, pdesc, pcmd) -> str:
        """Generates a basic plugin template for the user."""
        content = f"""from plugins.base_plugin import BasePlugin

class {pid.capitalize()}Plugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.name = "{pname}"
        self.version = "1.0.0"
        self.description = "{pdesc}"
        self.icon = "{picon}"
        self.is_builtin = False

    def execute(self, action: str, **kwargs) -> bool:
        if action == "main":
            print("Executing {pname}...")
            return True
        return False
"""
        path = os.path.join(self.plugin_dir, f"{pid}_plugin.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def install_plugin_from_file(self, file_path: str) -> bool:
        """Copies a .py file into the plugins directory and loads it."""
        try:
            import shutil
            filename = os.path.basename(file_path)
            dest = os.path.join(self.plugin_dir, filename)
            shutil.copy2(file_path, dest)
            self._load_plugin_file(dest)
            return True
        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False

# Global singleton for the project
plugin_manager = PluginManager()

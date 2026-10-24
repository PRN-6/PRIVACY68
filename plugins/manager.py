import os
import logging
import importlib
import inspect
import json
import re
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
        self.plugin_paths: Dict[str, str] = {}
        self.plugin_mtimes: Dict[str, int] = {}
        self.plugin_dir = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68", "plugins")
        os.makedirs(self.plugin_dir, exist_ok=True)
        self.last_error = ""
        self.load_builtin_plugins()
        self.load_external_plugins()

    def load_builtin_plugins(self):
        """Loads the core plugins shipped with the application."""
        try:
            from plugins.chrome_plugin import ChromePlugin
            from plugins.github_plugin import GitHubPlugin
            from plugins.system_plugin import SystemPlugin
            from plugins.whatsapp_plugin import WhatsAppPlugin

            self.register_plugin(ChromePlugin(), is_builtin=True)
            self.register_plugin(GitHubPlugin(), is_builtin=True)
            self.register_plugin(SystemPlugin(), is_builtin=True)
            self.register_plugin(WhatsAppPlugin(), is_builtin=True)
            logger.info("Built-in core plugins loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load built-in plugins: {e}")

    def load_external_plugins(self):
        """Scans the AppData plugins folder and dynamically loads Python scripts."""
        plugin_files = set()
        if os.path.exists(self.plugin_dir):
            for filename in os.listdir(self.plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    filepath = os.path.abspath(os.path.join(self.plugin_dir, filename))
                    plugin_files.add(filepath)
                    self._load_plugin_file(filepath)

        for plugin_id, filepath in list(self.plugin_paths.items()):
            if filepath not in plugin_files:
                del self.plugins[plugin_id]
                del self.plugin_paths[plugin_id]
        for filepath in list(self.plugin_mtimes):
            if filepath not in plugin_files:
                del self.plugin_mtimes[filepath]

    def _load_plugin_file(self, filepath: str):
        """Dynamically imports a Python file and instantiates the BasePlugin subclass."""
        self.last_error = ""
        filepath = os.path.abspath(filepath)
        try:
            modified_at = os.stat(filepath).st_mtime_ns
            if self.plugin_mtimes.get(filepath) == modified_at and filepath in self.plugin_paths.values():
                return
            previous_ids = [
                plugin_id for plugin_id, registered_path in self.plugin_paths.items()
                if registered_path == filepath
            ]
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
                        plugin = obj()
                        self.register_plugin(plugin, plugin_path=filepath)
                        self.plugin_mtimes[filepath] = modified_at
                        for previous_id in previous_ids:
                            if previous_id != plugin.id:
                                del self.plugins[previous_id]
                                del self.plugin_paths[previous_id]
                        logger.info(f"Dynamically loaded external plugin: {name}")
                        break
                else:
                    self.last_error = "No BasePlugin subclass was found in the Python file."
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Failed to load plugin from {filepath}: {e}")

    def register_plugin(self, plugin: BasePlugin, plugin_path: Optional[str] = None,
                        is_builtin: bool = False):
        """Registers a plugin instance into the active toolkit."""
        # Use the class name as ID if no ID is provided
        pid = str(getattr(plugin, "id", plugin.__class__.__name__.lower().replace("plugin", ""))).strip().lower()
        existing = self.plugins.get(pid)
        registered_path = self.plugin_paths.get(pid)
        requested_path = os.path.abspath(plugin_path) if plugin_path else None
        if existing and (getattr(existing, "is_builtin", False) or registered_path != requested_path):
            raise ValueError(f"A plugin with ID '{pid}' is already registered.")
        enabled = bool(existing.is_enabled) if existing else bool(getattr(plugin, "is_enabled", True))
        plugin.id = pid
        plugin.name = getattr(plugin, "name", plugin.__class__.__name__)
        plugin.version = getattr(plugin, "version", "1.0.0")
        plugin.description = getattr(plugin, "description", "No description provided.")
        plugin.icon = getattr(plugin, "icon", "🔌")
        plugin.is_enabled = enabled
        plugin.category = getattr(plugin, "category", "General")
        plugin.plugin_type = getattr(plugin, "plugin_type", "Custom Application")
        plugin.is_builtin = is_builtin
        self.plugins[pid] = plugin
        if plugin_path:
            self.plugin_paths[pid] = os.path.abspath(plugin_path)
        logger.info(f"Plugin registered: {pid} ({plugin.name})")

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Retrieves a plugin by its ID."""
        return self.plugins.get(plugin_id.lower())

    def get_all_plugins(self) -> List[BasePlugin]:
        """Returns a list of all currently active plugins."""
        return list(self.plugins.values())

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> bool:
        """Toggles a plugin's active state."""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False
        plugin.is_enabled = bool(enabled)
        return True

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Removes a plugin from the active list (and deletes file if external)."""
        plugin_id = plugin_id.lower()
        if plugin_id in self.plugins:
            # Only allow uninstalling external plugins
            plugin = self.plugins[plugin_id]
            if getattr(plugin, "is_builtin", False):
                return False
            filepath = self.plugin_paths.get(plugin_id)
            if not filepath:
                return False
            plugin_dir = os.path.abspath(self.plugin_dir)
            if os.path.normcase(os.path.commonpath([plugin_dir, filepath])) != os.path.normcase(plugin_dir):
                logger.error("Refusing to uninstall plugin outside the plugin directory: %s", filepath)
                return False
            try:
                os.remove(filepath)
            except OSError as e:
                logger.error("Failed to remove plugin file %s: %s", filepath, e)
                return False
            del self.plugins[plugin_id]
            del self.plugin_paths[plugin_id]
            self.plugin_mtimes.pop(filepath, None)
            return True
        return False

    def check_and_reload_if_changed(self):
        """Simple hot-reload check to refresh plugins without restarting the app."""
        # In a full implementation, this would track file modification times
        self.load_external_plugins()

    def create_plugin_template(self, pid, pname, picon, pdesc, pcmd) -> str:
        """Generates a basic plugin template for the user."""
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", pid):
            raise ValueError("Plugin ID must start with a letter and contain only letters, numbers, or underscores.")
        if pid in self.plugins:
            raise ValueError(f"A plugin with ID '{pid}' is already registered.")
        path = os.path.join(self.plugin_dir, f"{pid}_plugin.py")
        if os.path.exists(path):
            raise FileExistsError(f"A plugin file already exists for '{pid}'.")

        literal = lambda value: json.dumps(value, ensure_ascii=True)
        content = f"""from plugins.base_plugin import BasePlugin

class {pid.capitalize()}Plugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.id = {literal(pid)}
        self.name = {literal(pname)}
        self.version = "1.0.0"
        self.description = {literal(pdesc)}
        self.icon = {literal(picon)}
        self.is_builtin = False

    def execute(self, action: str, **kwargs) -> bool:
        if action == "main":
            print("Executing " + self.name + "...")
            return True
        return False
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self._load_plugin_file(path)
        if self.plugin_paths.get(pid) != os.path.abspath(path):
            os.remove(path)
            raise RuntimeError(self.last_error or "The generated plugin could not be loaded.")
        return path

    def install_plugin_from_file(self, file_path: str) -> bool:
        """Copies a .py file into the plugins directory and loads it."""
        try:
            import shutil
            self.last_error = ""
            if not file_path.lower().endswith(".py"):
                self.last_error = "Only Python plugin files (.py) are supported."
                return False
            filename = os.path.basename(file_path)
            dest = os.path.join(self.plugin_dir, filename)
            if os.path.abspath(file_path) == os.path.abspath(dest):
                self.last_error = "The plugin is already installed."
                return False
            if os.path.exists(dest):
                self.last_error = f"A plugin file named '{filename}' is already installed."
                return False
            shutil.copy2(file_path, dest)
            self._load_plugin_file(dest)
            if os.path.abspath(dest) not in self.plugin_paths.values():
                os.remove(dest)
                return False
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Install failed: {e}")
            return False

# Global singleton for the project
plugin_manager = PluginManager()

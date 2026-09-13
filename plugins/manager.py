import json
import logging
import os
import sys
import shutil
import zipfile
import importlib
import importlib.util
import inspect
from typing import Callable, Dict, List, Optional
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.PluginManager")

# 1. Paths Configuration
APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
USER_PLUGINS_DIR = os.path.join(APPDATA_DIR, "plugins")
CONFIG_PATH = os.path.join(APPDATA_DIR, "plugins_config.json")
BUILTIN_PLUGINS_DIR = os.path.dirname(__file__)

# Legacy AppData path (older builds stored user plugins under %APPDATA%/SANA)
LEGACY_APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "SANA")
LEGACY_USER_PLUGINS_DIR = os.path.join(LEGACY_APPDATA_DIR, "plugins")
LEGACY_CONFIG_PATH = os.path.join(LEGACY_APPDATA_DIR, "plugins_config.json")

# Ensure AppData directories exist
os.makedirs(APPDATA_DIR, exist_ok=True)
os.makedirs(USER_PLUGINS_DIR, exist_ok=True)


def _migrate_legacy_data():
    """Migrates user plugins & config from the legacy %APPDATA%/SANA folder."""
    if not os.path.isdir(LEGACY_USER_PLUGINS_DIR):
        return
    migrated = False
    for filename in os.listdir(LEGACY_USER_PLUGINS_DIR):
        src = os.path.join(LEGACY_USER_PLUGINS_DIR, filename)
        dst = os.path.join(USER_PLUGINS_DIR, filename)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            migrated = True
    if os.path.isfile(LEGACY_CONFIG_PATH) and not os.path.exists(CONFIG_PATH):
        shutil.copy2(LEGACY_CONFIG_PATH, CONFIG_PATH)
        migrated = True
    if migrated:
        logger.info("Migrated user plugins/config from legacy %APPDATA%/SANA folder.")


_migrate_legacy_data()

class PluginManager:
    """
    Production-grade Plugin Architecture for PRIVACY68:
    - Shipped Built-In Plugins: In application directory (Read-only / Safe).
    - Custom User Plugins: In %APPDATA%/PRIVACY68/plugins/ (Read-write / Portable).
    - User Configuration: In %APPDATA%/PRIVACY68/plugins_config.json.
    """
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self._reload_listeners: List[Callable[[], None]] = []
        
        # Discover plugins from both sources
        self.discover_plugins()
        
        # Load user configuration
        self._load_config()

    def discover_plugins(self):
        """Discovers both Built-in and User AppData plugins."""
        self.plugins.clear()

        # 1. Load Built-In Shipped Plugins
        self._scan_directory(BUILTIN_PLUGINS_DIR, is_builtin=True)

        # 2. Load Extra Shipped Plugins (e.g. PowerPoint, WhatsApp, Notepad, Brave)
        extra_plugins_dir = os.path.abspath(os.path.join(BUILTIN_PLUGINS_DIR, "..", "extra_plugins"))
        if os.path.exists(extra_plugins_dir):
            self._scan_directory(extra_plugins_dir, is_builtin=True)

        # 3. Load User Custom Plugins from AppData
        if os.path.exists(USER_PLUGINS_DIR):
            self._scan_directory(USER_PLUGINS_DIR, is_builtin=False)

    def _scan_directory(self, folder_path: str, is_builtin: bool = False):
        """Scans a directory for .py plugin files."""
        if not os.path.exists(folder_path):
            return

        ignore_files = ["base_plugin.py", "manager.py", "profile_manager.py", "win_keys.py", "__init__.py"]

        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ignore_files:
                module_name = filename[:-3]
                file_path = os.path.join(folder_path, filename)
                self._load_plugin_file(module_name, file_path, is_builtin=is_builtin)

    def _load_plugin_file(self, module_name: str, file_path: str, is_builtin: bool = False):
        """Dynamically loads and registers a plugin class from a file."""
        try:
            prefix = "builtin" if is_builtin else "user"
            unique_mod_name = f"privacy68_plugins_{prefix}_{module_name}"
            spec = importlib.util.spec_from_file_location(unique_mod_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_mod_name] = module
                spec.loader.exec_module(module)

                # Find BasePlugin subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if inspect.isclass(attr) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                        plugin_instance = attr()
                        plugin_instance.is_builtin = is_builtin
                        self.plugins[plugin_instance.id] = plugin_instance
                        logger.info(f"Loaded {'[Built-In]' if is_builtin else '[Custom]'} Plugin: '{plugin_instance.name}' ({plugin_instance.id})")
        except Exception as e:
            logger.error(f"Error loading plugin from {file_path}: {e}")

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                for pid, enabled in config.items():
                    if pid in self.plugins:
                        self.plugins[pid].is_enabled = bool(enabled)
            except Exception as e:
                logger.warning(f"Could not load plugin config from {CONFIG_PATH}: {e}")

    def _save_config(self):
        try:
            config = {pid: p.is_enabled for pid, p in self.plugins.items()}
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            logger.info("Plugin configuration saved.")
        except Exception as e:
            logger.error(f"Could not save plugin config: {e}")

    def get_all_plugins(self) -> List[BasePlugin]:
        return list(self.plugins.values())

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        return self.plugins.get(plugin_id)

    def set_plugin_enabled(self, plugin_id: str, is_enabled: bool):
        if plugin_id in self.plugins:
            self.plugins[plugin_id].is_enabled = is_enabled
            self._save_config()
            logger.info(f"Plugin '{plugin_id}' set to {'ENABLED' if is_enabled else 'DISABLED'}")
            self.notify_reload()

    def register_reload_listener(self, listener: Callable[[], None]):
        self._reload_listeners.append(listener)

    def notify_reload(self):
        """Notifies router and system components to re-index training phrases."""
        for listener in self._reload_listeners:
            try:
                listener()
            except Exception as e:
                logger.error(f"Error in plugin reload listener: {e}")

    def get_active_fast_intents(self) -> Dict[str, List[str]]:
        """Aggregates all fast-lane training phrases from enabled plugins."""
        intents = {}
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                intents.update(plugin.fast_intents)
        return intents

    def get_active_system_descriptions(self) -> str:
        """Aggregates tool descriptions for Ollama AI system prompt."""
        descriptions = []
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                for desc in plugin.descriptions.values():
                    descriptions.append(desc)
        return "\n".join(descriptions)

    def execute_action(self, action_name: str, text: str) -> bool:
        """Finds the plugin that owns this action and executes it."""
        for plugin in self.plugins.values():
            if plugin.is_enabled and action_name in plugin.actions:
                return plugin.execute(action_name, text)
        return False

    def install_plugin_from_file(self, source_path: str) -> bool:
        """Installs a .py plugin or extracts a .zip into the User AppData folder."""
        try:
            if not os.path.exists(source_path):
                return False

            if source_path.endswith(".py"):
                dest_file = os.path.join(USER_PLUGINS_DIR, os.path.basename(source_path))
                shutil.copy2(source_path, dest_file)
                self.discover_plugins()
                self._load_config()
                self.notify_reload()
                return True

            elif source_path.endswith(".zip"):
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(USER_PLUGINS_DIR)
                self.discover_plugins()
                self._load_config()
                self.notify_reload()
                return True
        except Exception as e:
            logger.error(f"Failed to install plugin into AppData from {source_path}: {e}")
        return False

    def create_plugin_template(self, plugin_id: str, name: str, icon: str, description: str, sample_command: str) -> str:
        """Scaffolds a new user plugin in the User AppData plugins directory."""
        clean_id = plugin_id.strip().lower().replace(" ", "_")
        filename = f"{clean_id}_plugin.py"
        file_path = os.path.join(USER_PLUGINS_DIR, filename)

        class_name = "".join(word.capitalize() for word in clean_id.split("_")) + "Plugin"

        code = f'''import logging
import subprocess
from typing import Callable, Dict, List
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugin.{class_name}")

class {class_name}(BasePlugin):
    id = "{clean_id}"
    name = "{name}"
    icon = "{icon}"
    description = "{description}"
    version = "1.0.0"
    author = "Custom User"
    is_builtin = False

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {{
            "{clean_id}.main_action": self.handle_main_action,
        }}

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {{
            "{clean_id}.main_action": [
                "{sample_command.lower()}",
                "open {name.lower()}",
                "launch {name.lower()}",
            ]
        }}

    @property
    def descriptions(self) -> Dict[str, str]:
        return {{
            "{clean_id}.main_action": "- {clean_id}.main_action: {description}",
        }}

    def handle_main_action(self, text: str) -> bool:
        logger.info("Executing custom plugin action: {name}")
        # Insert your custom automation code or process launch here
        return True
'''
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Reload plugins
        self.discover_plugins()
        self._load_config()
        self.notify_reload()
        return file_path

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Deletes a custom plugin file from %APPDATA%/PRIVACY68/plugins/."""
        plugin = self.get_plugin(plugin_id)
        if not plugin or plugin.is_builtin:
            # Cannot uninstall built-in core plugins
            return False

        filename = f"{plugin_id}_plugin.py"
        file_path = os.path.join(USER_PLUGINS_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.discover_plugins()
                self._load_config()
                self.notify_reload()
                return True
            except Exception as e:
                logger.error(f"Error removing user plugin {file_path}: {e}")
        return False

# Global singleton instance
plugin_manager = PluginManager()

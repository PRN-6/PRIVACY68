import json
import logging
import os
import re
import sys
import shutil
import zipfile
import importlib
import importlib.util
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple
from plugins.base_plugin import BasePlugin
from core.platform import PLATFORM_ID, app_data_dir

logger = logging.getLogger("PRIVACY68.PluginManager")

# 1. Paths Configuration
APPDATA_DIR = app_data_dir()
USER_PLUGINS_DIR = os.path.join(APPDATA_DIR, "plugins")
CONFIG_PATH = os.path.join(APPDATA_DIR, "plugins_config.json")
BUILTIN_PLUGINS_DIR = os.path.dirname(__file__)

# Legacy AppData path (older builds stored user plugins under %APPDATA%/SANA)
LEGACY_APPDATA_DIR = os.path.join(os.path.dirname(APPDATA_DIR), "SANA")
LEGACY_USER_PLUGINS_DIR = os.path.join(LEGACY_APPDATA_DIR, "plugins")
LEGACY_CONFIG_PATH = os.path.join(LEGACY_APPDATA_DIR, "plugins_config.json")

# Ensure AppData directories exist
os.makedirs(APPDATA_DIR, exist_ok=True)
os.makedirs(USER_PLUGINS_DIR, exist_ok=True)

# Ensure plugin paths are in sys.path for external dependencies and relative imports
if USER_PLUGINS_DIR not in sys.path:
    sys.path.append(USER_PLUGINS_DIR)
if BUILTIN_PLUGINS_DIR not in sys.path:
    sys.path.append(BUILTIN_PLUGINS_DIR)

# Expose BasePlugin and win_utils in sys.modules so plugins importing either
# `from plugins.base_plugin import BasePlugin` or `from base_plugin import BasePlugin` work seamlessly
import plugins.base_plugin
sys.modules["base_plugin"] = plugins.base_plugin
try:
    import plugins.win_utils
    sys.modules["win_utils"] = plugins.win_utils
except Exception as e:
    logger.debug(f"module: {e}")


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
        self._fast_intents_cache: Optional[Dict[str, List[str]]] = None
        self._fast_intents_phrase_map: Optional[Dict[str, str]] = None
        self._pattern_intents_cache: Optional[List[Tuple[str, Any]]] = None
        self.last_error: str = ""
        self._folder_snapshots: Dict[str, float] = {}
        
        # Discover plugins from both sources
        self.discover_plugins()
        
        # Load user configuration
        self._load_config()

    def _get_snapshot(self) -> Dict[str, float]:
        """Collects file modification timestamps across all scanned plugin directories."""
        snapshot = {}
        dirs_to_check = [BUILTIN_PLUGINS_DIR]
        extra_plugins_dir = os.path.abspath(os.path.join(BUILTIN_PLUGINS_DIR, "..", "extra_plugins"))
        if os.path.exists(extra_plugins_dir):
            dirs_to_check.append(extra_plugins_dir)
        if os.path.exists(USER_PLUGINS_DIR):
            dirs_to_check.append(USER_PLUGINS_DIR)

        for d in dirs_to_check:
            try:
                for f in os.listdir(d):
                    if f.endswith(".py"):
                        p = os.path.join(d, f)
                        snapshot[p] = os.path.getmtime(p)
            except Exception:
                continue
        return snapshot

    def check_and_reload_if_changed(self) -> bool:
        """
        Hot-detects if any plugin files were added, deleted, or modified on disk.
        Automatically re-indexes without requiring an application restart.
        """
        current_snapshot = self._get_snapshot()
        if current_snapshot != self._folder_snapshots:
            logger.info("Plugin directory modification detected. Hot-reloading all plugins...")
            self.discover_plugins()
            self._load_config()
            self.notify_reload()
            return True
        return False

    def discover_plugins(self):
        """
        Discovers built-in shipped plugins and user AppData plugins.

        Precedence: a plugin SHIPPED with the application always wins over a
        file of the same name in %APPDATA%. A user copy is only a fallback
        for a plugin the application does not ship.

        This matters in practice: a user who downloaded a plugin from the
        website keeps a copy in %APPDATA%. When a later release ships an
        improved version of that same plugin, the stale download must not
        shadow the shipped one — otherwise the fix never reaches the user.
        """
        self.plugins.clear()

        # 1. Load Built-In Shipped Plugins
        self._scan_directory(BUILTIN_PLUGINS_DIR, is_builtin=True)

        # 2. Load Extra Shipped Plugins (e.g. PowerPoint, Notepad, Brave, GitHub)
        extra_plugins_dir = os.path.abspath(os.path.join(BUILTIN_PLUGINS_DIR, "..", "extra_plugins"))
        if os.path.exists(extra_plugins_dir):
            self._scan_directory(extra_plugins_dir, is_builtin=True)

        # 3. Load User Custom Plugins from AppData, EXCEPT those already
        #    provided by a shipped plugin (a shipped version is newer).
        if os.path.exists(USER_PLUGINS_DIR):
            self._scan_directory(USER_PLUGINS_DIR, is_builtin=False, skip_ids=set(self.plugins.keys()))

        # Update snapshot
        self._folder_snapshots = self._get_snapshot()

    def _scan_directory(self, folder_path: str, is_builtin: bool = False, skip_ids: Optional[set] = None):
        """
        Scans a directory for .py plugin files.

        `skip_ids` names plugin IDs that are already registered, so a user
        copy cannot replace a shipped plugin of the same ID.
        """
        if not os.path.exists(folder_path):
            return

        ignore_files = [
            "base_plugin.py", "manager.py", "profile_manager.py", "win_utils.py",
            "win_keys.py", "__init__.py", "boilerplate_plugin.py"
        ]

        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ignore_files:
                module_name = filename[:-3]
                file_path = os.path.join(folder_path, filename)
                self._load_plugin_file(module_name, file_path, is_builtin=is_builtin, skip_ids=skip_ids)

    def _load_plugin_file(
        self,
        module_name: str,
        file_path: str,
        is_builtin: bool = False,
        skip_ids: Optional[set] = None,
    ) -> Optional[BasePlugin]:
        """
        Dynamically loads and registers a plugin class from a file.

        When `skip_ids` contains the plugin's ID, the file is loaded but NOT
        registered — a shipped plugin of that ID already won.
        """
        try:
            import re
            prefix = "builtin" if is_builtin else "user"
            clean_module_name = re.sub(r'[^a-zA-Z0-9_]', '_', module_name)
            unique_mod_name = f"privacy68_plugins_{prefix}_{clean_module_name}"
            spec = importlib.util.spec_from_file_location(unique_mod_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_mod_name] = module
                spec.loader.exec_module(module)

                def _is_base_plugin(cls):
                    if not inspect.isclass(cls):
                        return False
                    if cls is BasePlugin or cls.__name__ == "BasePlugin":
                        return False
                    try:
                        if issubclass(cls, BasePlugin):
                            return True
                    except Exception as e:
                        logger.debug(f"_is_base_plugin: {e}")
                    # MRO inspection in case of duplicate or differently-imported BasePlugin definitions
                    return any(b.__name__ == "BasePlugin" for b in getattr(cls, "__mro__", []))

                # Find BasePlugin subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if _is_base_plugin(attr):
                        plugin_instance = attr()
                        plugin_instance.is_builtin = is_builtin

                        if skip_ids and plugin_instance.id in skip_ids:
                            logger.info(
                                f"Skipped user copy of plugin '{plugin_instance.id}' "
                                f"({os.path.basename(file_path)}) — a shipped version takes precedence."
                            )
                            return None

                        # A plugin that only works on another operating system is
                        # not registered here — the platform specific variant
                        # (e.g. linux_plugin) takes its place.
                        if not plugin_instance.is_supported_on(PLATFORM_ID):
                            logger.info(
                                f"Skipped plugin '{plugin_instance.id}' — it does not support {PLATFORM_ID}."
                            )
                            return None

                        self.plugins[plugin_instance.id] = plugin_instance
                        logger.info(f"Loaded {'[Built-In]' if is_builtin else '[Custom]'} Plugin: '{plugin_instance.name}' ({plugin_instance.id})")
                        return plugin_instance
        except Exception as e:
            self.last_error = f"Error loading plugin from {os.path.basename(file_path)}: {e}"
            logger.error(f"Error loading plugin from {file_path}: {e}")
        return None

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

    @property
    def all_actions(self) -> Dict[str, Callable[[str], bool]]:
        """Aggregates all action callables from currently enabled plugins."""
        actions = {}
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                actions.update(plugin.actions)
        return actions

    def get_all_plugins(self) -> List[BasePlugin]:
        self.check_and_reload_if_changed()
        return list(self.plugins.values())

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        self.check_and_reload_if_changed()
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
        self._fast_intents_cache = None
        self._fast_intents_phrase_map = None
        self._pattern_intents_cache = None
        for listener in self._reload_listeners:
            try:
                listener()
            except Exception as e:
                logger.error(f"Error in plugin reload listener: {e}")

    def _rebuild_fast_intents_cache(self):
        intents = {}
        phrase_map = {}
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                intents.update(plugin.fast_intents)
                for action_name, phrases in plugin.fast_intents.items():
                    for p in phrases:
                        phrase_map[p.lower().strip()] = action_name
        self._fast_intents_cache = intents
        self._fast_intents_phrase_map = phrase_map

    def _rebuild_pattern_intents_cache(self):
        """
        Compiles every enabled plugin's `pattern_intents` into one ordered
        list of (action_name, compiled_regex) pairs.

        Order follows plugin registration order, and within a plugin the
        order the patterns are declared. That matters: the first match wins,
        so a plugin must list its most specific pattern first.
        """
        compiled: List[Tuple[str, Any]] = []
        for plugin in self.plugins.values():
            if not plugin.is_enabled:
                continue
            try:
                patterns = plugin.pattern_intents
            except Exception as e:
                logger.warning(f"Could not read pattern_intents from plugin '{plugin.id}': {e}")
                continue
            for action_name, raw_patterns in (patterns or {}).items():
                for raw in raw_patterns:
                    try:
                        compiled.append((action_name, re.compile(raw, re.IGNORECASE)))
                    except re.error as e:
                        logger.warning(
                            f"Invalid pattern for '{action_name}' in plugin '{plugin.id}': {e}"
                        )
        self._pattern_intents_cache = compiled

    def get_active_fast_intents(self) -> Dict[str, List[str]]:
        """Aggregates all fast-lane training phrases from enabled plugins (cached)."""
        self.check_and_reload_if_changed()
        if self._fast_intents_cache is None:
            self._rebuild_fast_intents_cache()
        return self._fast_intents_cache

    def match_fast_intent(self, phrase: str) -> Optional[str]:
        """O(1) instant lookup for plugin fast-lane phrases."""
        if not phrase:
            return None
        self.check_and_reload_if_changed()
        if self._fast_intents_phrase_map is None:
            self._rebuild_fast_intents_cache()
        return self._fast_intents_phrase_map.get(phrase.strip().lower())

    def match_pattern_intent(self, phrase: str) -> Optional[str]:
        """
        Matches a command against the enabled plugins' `pattern_intents`.

        Returns the action name of the first plugin whose pattern matches, or
        None when nothing matches. The exact-phrase map is tried first by the
        caller; this is the generalisation step that catches phrasings a
        plugin could not enumerate.
        """
        if not phrase or not phrase.strip():
            return None
        self.check_and_reload_if_changed()
        if self._pattern_intents_cache is None:
            self._rebuild_pattern_intents_cache()
        if not self._pattern_intents_cache:
            return None

        text = phrase.strip().lower()
        for action_name, regex in self._pattern_intents_cache:
            if regex.search(text):
                return action_name
        return None

    def get_active_system_descriptions(self) -> str:
        """Aggregates tool descriptions for Ollama AI system prompt."""
        self.check_and_reload_if_changed()
        descriptions = []
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                for desc in plugin.descriptions.values():
                    descriptions.append(desc)
        return "\n".join(descriptions)

    def get_active_tool_definitions(self) -> List[Dict[str, Any]]:
        """Aggregates all Hermes tool schemas from enabled plugins."""
        self.check_and_reload_if_changed()
        tools = []
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                try:
                    tools.extend(plugin.get_tool_definitions())
                except Exception as e:
                    logger.warning(f"Failed to get tool definition for plugin '{plugin.id}': {e}")
        return tools

    def execute_action(self, action_name: str, text: str) -> bool:
        """Finds the plugin that owns this action and executes it."""
        self.check_and_reload_if_changed()
        for plugin in self.plugins.values():
            if plugin.is_enabled and action_name in plugin.actions:
                return plugin.execute(action_name, text)
        return False

    def install_plugin_from_file(self, source_path: str) -> bool:
        """Installs a .py plugin or extracts a .zip into the User AppData folder and validates activation."""
        try:
            if not os.path.exists(source_path):
                self.last_error = f"Source file does not exist: {source_path}"
                return False

            base_name = os.path.basename(source_path)
            dest_file = os.path.join(USER_PLUGINS_DIR, base_name)

            if source_path.endswith(".py"):
                # Snapshot existing plugin IDs
                pre_plugins = set(self.plugins.keys())

                shutil.copy2(source_path, dest_file)
                self.discover_plugins()
                self._load_config()

                # Verify that the plugin actually loaded successfully
                post_plugins = set(self.plugins.keys())
                new_ids = post_plugins - pre_plugins

                # If it updated an existing plugin ID or added a new one, verify file is registered
                loaded = False
                for pid, p in self.plugins.items():
                    if not p.is_builtin and (pid in new_ids or pid in base_name.lower()):
                        loaded = True
                        p.is_enabled = True
                        break

                if not loaded and post_plugins == pre_plugins:
                    # Test if any custom plugin in user directory matches
                    module_name = base_name[:-3]
                    p_inst = self._load_plugin_file(module_name, dest_file, is_builtin=False)
                    if p_inst:
                        p_inst.is_enabled = True
                        self.plugins[p_inst.id] = p_inst
                        loaded = True

                if not loaded:
                    # Installation failed to produce a valid working BasePlugin
                    if os.path.exists(dest_file):
                        try:
                            os.remove(dest_file)
                        except Exception as e:
                            logger.debug(f"install_plugin_from_file: {e}")
                    self.discover_plugins()
                    if not self.last_error:
                        self.last_error = f"File '{base_name}' did not define a valid BasePlugin subclass."
                    logger.error(f"[PLUGIN_INSTALL] {self.last_error}")
                    return False

                self._save_config()
                self.notify_reload()
                logger.info(f"[PLUGIN_INSTALL] Successfully installed and activated plugin from {base_name}")
                return True

            elif source_path.endswith(".zip"):
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(USER_PLUGINS_DIR)
                self.discover_plugins()
                self._load_config()
                self._save_config()
                self.notify_reload()
                return True
        except Exception as e:
            self.last_error = f"Installation error: {e}"
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

import logging
import re
from typing import Any, Dict, List, Optional
from plugins.manager import plugin_manager

logger = logging.getLogger("PRIVACY68.PluginActionManager")

# Words that flip gesture control off/on when the command contains explicit state words
GESTURE_DISABLE_WORDS = ("disable", "stop", "turn off", "turnoff", "deactivate", "switch off", "off")
GESTURE_ENABLE_WORDS = ("enable", "start", "turn on", "turnon", "activate", "on")

# Generic name tokens that shouldn't identify a plugin on their own
GENERIC_APP_TOKENS = frozenset({
    "windows", "browser", "app", "application", "controller", "desktop",
    "hand", "gestures", "studio", "code", "the", "a", "an", "for",
})


class PluginActionManager:
    """
    Central action coordinator for dynamic plugins.
    Bridges the Semantic Router (Lane 2) and fast-lane plugin actions.
    """

    def __init__(self):
        self._action_aliases: Dict[str, str] = {}
        self._rebuild_action_aliases()
        plugin_manager.register_reload_listener(self._rebuild_action_aliases)
        logger.info(f"PluginActionManager initialized with {len(plugin_manager.get_all_plugins())} plugins.")

    def get_all_intents(self) -> Dict[str, List[str]]:
        """Collects fast-lane training phrases from all enabled plugins."""
        return plugin_manager.get_active_fast_intents()

    def get_system_prompt_descriptions(self) -> str:
        """Collects action descriptions from all enabled plugins."""
        return plugin_manager.get_active_system_descriptions()

    @staticmethod
    def _normalize(text: str) -> str:
        """Stabilizes arbitrary AI/speech text into a case/space/punctuation-insensitive key."""
        return (
            text.lower().strip()
            .replace(" ", "").replace("_", "").replace("-", "")
            .replace(".", "").replace("/", "").replace(",", "")
        )

    def _plugin_default_action(self, plugin) -> str:
        """Returns the most sensible 'primary' action for a plugin (e.g., its .open action)."""
        actions = dict(plugin.actions)
        pid = plugin.id
        for candidate in (f"{pid}.open", "open"):
            if candidate in actions:
                return candidate
        for name in actions:
            if name.endswith(".open"):
                return name
        return ""

    def _rebuild_action_aliases(self):
        """Builds a dynamic alias table from currently enabled plugins."""
        aliases = {}
        for plugin in plugin_manager.get_all_plugins():
            if not plugin.is_enabled:
                continue
            pid = (plugin.id or "").strip()
            if not pid:
                continue

            default_action = self._plugin_default_action(plugin)
            if default_action:
                name = (plugin.name or "").strip()
                name_tokens = name.split()

                identities = {pid, name}
                if name_tokens:
                    first_token = name_tokens[0]
                    if len(first_token) >= 3 and first_token.lower() not in GENERIC_APP_TOKENS:
                        identities.add(first_token)

                for identity in identities:
                    identity = (identity or "").strip()
                    if not identity:
                        continue
                    for variant in (identity, f"open {identity}", f"{identity} open"):
                        key = self._normalize(variant)
                        if key:
                            aliases.setdefault(key, default_action)

            # Every concrete action is also addressable by its own normalized name
            for action_name in plugin.actions:
                norm = self._normalize(action_name)
                if norm:
                    aliases.setdefault(norm, action_name)

            # Gesture plugin explicit aliases
            if pid == "gesture":
                gesture_keys = (
                    "gesture", "gestures", "hand gesture", "hand gestures", "webcam",
                    "enable gesture", "start gesture", "activate gesture",
                    "disable gesture", "stop gesture", "turn off gesture",
                    "turn on gesture", "turnoff gesture", "deactivate gesture",
                    "switch off gesture", "open gesture", "launch gesture",
                )
                for key in gesture_keys:
                    aliases[self._normalize(key)] = "gesture.enable"

        self._action_aliases = aliases
        logger.debug(f"Rebuilt plugin alias table with {len(aliases)} entries.")

    def _resolve_gesture(self, resolved: str, text: str) -> str:
        """Resolves gesture enable/disable based on spoken intent words."""
        if not resolved.startswith("gesture."):
            return resolved
        low = text.lower()
        if any(w in low for w in GESTURE_DISABLE_WORDS):
            return "gesture.disable"
        if any(w in low for w in GESTURE_ENABLE_WORDS):
            return "gesture.enable"
        return resolved

    def execute_skill(self, tool_name: str, text: str) -> bool:
        """Finds the correct plugin action and executes it."""
        # 1. Direct match in registered plugin actions
        if tool_name in plugin_manager.all_actions:
            return plugin_manager.execute_action(tool_name, text)

        # 2. Resolve against dynamic alias table
        resolved = tool_name.strip()
        norm = self._normalize(resolved)
        if norm in self._action_aliases:
            resolved = self._action_aliases[norm]
        elif "gesture" in norm or "webcam" in norm:
            resolved = "gesture.enable"

        # 3. Gesture disambiguation
        resolved = self._resolve_gesture(resolved, text)

        # 4. Execute the resolved plugin action
        if plugin_manager.execute_action(resolved, text):
            return True

        logger.info(f"Unknown tool '{tool_name}' resolved to '{resolved}' — no plugin action found.")
        return False


# Compatibility alias
SkillManager = PluginActionManager

# Global singleton instance
manager = PluginActionManager()
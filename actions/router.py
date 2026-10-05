"""
LLM-Powered Semantic Router for Privacy68.

Routes user voice commands to the correct plugin action using a local
Ollama LLM (tool-calling / function-calling).  Replaces the previous
TF-IDF cosine-similarity approach with true natural-language understanding.

Flow:
  1. Collect tool definitions from all enabled plugins.
  2. Send the user's command + tool schemas to Ollama.
  3. The LLM picks the best matching tool (or none).
  4. Return the resolved action name to the executor.
"""

import json
import logging
import threading
from typing import Optional

import ollama

from plugins.manager import plugin_manager
from plugins.profile_manager import profile_manager

logger = logging.getLogger("PRIVACY68.LLMRouter")

# ─── System prompt that tells the LLM what it is and how to behave ───────────
SYSTEM_PROMPT = """\
You are Privacy68, a local voice assistant for Windows desktop automation.

Your ONLY job is to pick the single best matching tool for the user's spoken command.
- If a tool clearly matches, call it immediately.
- If nothing matches, respond with plain text: "NO_MATCH"
- NEVER make up tool names. Only use the tools provided.
- NEVER ask follow-up questions. Decide immediately.
- The 'input_text' parameter should contain the user's original command text.
"""


class LLMRouter:
    """
    Routes voice commands to plugin actions via Ollama tool-calling.
    Thread-safe, auto-reloads when plugins change.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._tools = []
        self._tool_name_map = {}  # Maps 'plugin_chrome_open' -> 'chrome.open'
        self.reload()
        plugin_manager.register_reload_listener(self.reload)

    def reload(self):
        """Re-indexes tool definitions from all enabled plugins."""
        with self._lock:
            self._tools = plugin_manager.get_active_tool_definitions()
            self._tool_name_map = {}
            for plugin in plugin_manager.get_all_plugins():
                if not plugin.is_enabled:
                    continue
                for action_name in plugin.actions:
                    clean_name = f"plugin_{action_name.replace('.', '_')}"
                    self._tool_name_map[clean_name] = action_name

            logger.info(
                f"LLM Router indexed {len(self._tools)} tool definitions "
                f"from {len(plugin_manager.get_all_plugins())} plugins."
            )

    def route(self, user_text: str) -> Optional[str]:
        """
        Sends the user command to Ollama with all available tool schemas.
        Returns the resolved plugin action name (e.g. 'chrome.open'),
        or None if no tool matched.
        """
        if not user_text or not user_text.strip():
            return None

        with self._lock:
            tools = list(self._tools)
            name_map = dict(self._tool_name_map)

        if not tools:
            logger.warning("LLM Router has no tools indexed. Skipping.")
            return None

        model = profile_manager.get("llm_model", "qwen2.5:0.5b")
        timeout = profile_manager.get("agent_timeout", 30)

        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text.strip()},
                ],
                tools=tools,
                options={"temperature": 0.0, "num_predict": 128},
            )

            # Check if the LLM made a tool call
            message = response.get("message", {})
            tool_calls = message.get("tool_calls")

            if tool_calls:
                tool_call = tool_calls[0]  # Take the first tool call
                func_name = tool_call.get("function", {}).get("name", "")
                action_name = name_map.get(func_name)

                if action_name:
                    logger.info(
                        f"LLM Router matched '{action_name}' "
                        f"(LLM tool call: {func_name})"
                    )
                    return action_name
                else:
                    logger.warning(
                        f"LLM called unknown tool '{func_name}'. "
                        f"Available: {list(name_map.keys())}"
                    )
                    return None

            # No tool call — LLM decided nothing matched
            content = message.get("content", "").strip()
            logger.info(
                f"LLM Router: no tool matched for '{user_text}' "
                f"(LLM response: '{content[:100]}')"
            )
            return None

        except Exception as e:
            logger.error(f"LLM Router error: {e}")
            return None

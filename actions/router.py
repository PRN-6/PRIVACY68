import json
import logging
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

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
    Routes voice commands to plugin actions via Ollama (Local Air-Gapped)
    or Cloud Providers (OpenAI, Groq, Custom API Key).
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
        Sends the user command to either local Ollama or Cloud API depending on user settings.
        Returns the resolved plugin action name (e.g. 'chrome.open'), or None if no match.
        """
        if not user_text or not user_text.strip():
            return None

        with self._lock:
            tools = list(self._tools)
            name_map = dict(self._tool_name_map)

        if not tools:
            logger.warning("LLM Router has no tools indexed. Skipping.")
            return None

        provider = profile_manager.get("llm_provider", "ollama").lower()

        # 1. Cloud Provider Route (OpenAI / Groq / Custom API)
        if provider in ("openai", "groq", "custom") and profile_manager.get("api_key"):
            action = self._route_cloud(user_text, provider, tools, name_map)
            if action:
                return action
            logger.info("Cloud LLM did not match or failed. Falling back to local Ollama...")

        # 2. Local Air-Gapped Route (Ollama)
        return self._route_ollama(user_text, tools, name_map)

    def _route_ollama(self, user_text: str, tools: list, name_map: dict) -> Optional[str]:
        """Routes through local Ollama server."""
        try:
            import ollama
            model = profile_manager.get("llm_model", "qwen2.5:0.5b")
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text.strip()},
                ],
                tools=tools,
                options={"temperature": 0.0, "num_predict": 128},
            )

            message = response.get("message", {})
            tool_calls = message.get("tool_calls")
            if tool_calls:
                func_name = tool_calls[0].get("function", {}).get("name", "")
                action_name = name_map.get(func_name)
                if action_name:
                    logger.info(f"Ollama Local matched '{action_name}' (tool: {func_name})")
                    return action_name

            content = message.get("content", "").strip()
            logger.info(f"Ollama Local: no tool matched for '{user_text}' ('{content[:80]}')")
            return None
        except Exception as e:
            logger.error(f"Local Ollama router error: {e}")
            return None

    def _route_cloud(self, user_text: str, provider: str, tools: list, name_map: dict) -> Optional[str]:
        """Routes through an OpenAI-compatible cloud REST API endpoint."""
        api_key = profile_manager.get("api_key", "").strip()
        if not api_key:
            return None

        # Determine endpoint and default model
        if provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            model = profile_manager.get("cloud_model", "llama-3.3-70b-versatile")
        elif provider == "openai":
            endpoint = "https://api.openai.com/v1/chat/completions"
            model = profile_manager.get("cloud_model", "gpt-4o-mini")
        else:
            endpoint = profile_manager.get("api_base_url", "https://api.openai.com/v1/chat/completions").strip()
            model = profile_manager.get("cloud_model", "gpt-4o-mini")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text.strip()}
            ],
            "tools": tools,
            "temperature": 0.0,
            "max_tokens": 128
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "PRIVACY68/1.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as res:
                body = json.loads(res.read().decode("utf-8"))
                choice = body.get("choices", [{}])[0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    func_name = tool_calls[0].get("function", {}).get("name", "")
                    action_name = name_map.get(func_name)
                    if action_name:
                        logger.info(f"Cloud [{provider.upper()}] matched '{action_name}' (tool: {func_name})")
                        return action_name
                return None
        except Exception as e:
            logger.warning(f"Cloud LLM call ({provider}) failed: {e}")
            return None

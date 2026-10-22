"""
PRIVACY68 — Lane 2: the API Lane.

This lane talks to the outside world:

  1. DIRECT APIs — live weather, the public IP address, web searches and
     the file system commands (create / rename / delete), all of them
     declared in the command catalogue. No API key, no model, ~100ms.
  2. CLOUD LLM — when a cloud provider is configured, the utterance is
     turned into a tool call by Groq, Gemini, Claude, OpenAI, OpenRouter
     or any OpenAI-compatible endpoint.

The catalogue owns part 1, so this file no longer contains a chain of
"if the text contains ..." checks. Part 2 is inherently open-ended, so it
keeps its own plumbing.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from actions.dispatch import execute, resolve
from actions.registry import LANE_API

logger = logging.getLogger("PRIVACY68.APILane")

# System prompt for Cloud LLM Tool Selection
SYSTEM_PROMPT = """\
You are Privacy68, an intelligent voice assistant for Windows desktop automation.

Your ONLY job is to pick the single best matching tool for the user's spoken command.
- If a tool clearly matches, call it immediately.
- If nothing matches, respond with plain text: "NO_MATCH"
- NEVER make up tool names. Only use the tools provided.
- NEVER ask follow-up questions. Decide immediately.
- The 'input_text' parameter should contain the user's original command text.
"""

#: Used when the request is a question rather than a command.
CHAT_SYSTEM_PROMPT = """\
You are Privacy68, a warm and concise voice assistant running on the user's Windows PC.
The user asked you a question out loud, so answer in at most three short sentences.
Speak plainly, skip the preamble, and never describe yourself as a language model.
"""

#: Providers that expose an OpenAI-compatible chat completions API.
_OPENAI_COMPATIBLE = ("groq", "gemini", "google", "openrouter", "openai", "custom")

#: Maximum number of tool definitions sent to the cloud in one request.
_MAX_TOOLS = 40


class APILaneRouter:
    """
    Lane 2: direct web/application APIs and cloud LLM tool calling.

    It runs before the local model, so a machine without Ollama still
    understands the full catalogue of commands.
    """

    def try_execute_api(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to execute the command via Lane 2.

        Returns a result dict when handled, or None to fall through to
        Lane 3 (the local model).
        """
        if not text or not text.strip():
            return None

        # ─── Part 1: direct web & application APIs (from the catalogue) ────
        resolved = resolve(text, LANE_API)
        if resolved is not None:
            spec, slots = resolved
            result = execute(spec, slots, text, LANE_API)
            if result is not None:
                return result

        # ─── Part 2: cloud LLM semantic tool calling ────────────────────────
        return self._handle_cloud_llm(text.strip())

    # ─── Cloud LLM ──────────────────────────────────────────────────────────
    def _handle_cloud_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Invokes the cloud LLM tool-calling route if one is configured."""
        from plugins.profile_manager import profile_manager

        provider = profile_manager.get("llm_provider", "").lower()
        api_key = profile_manager.get("api_key", "").strip()

        if not api_key:
            return None
        if provider not in _OPENAI_COMPATIBLE and provider not in ("claude", "anthropic"):
            return None

        from actions.skill_manager import manager
        from plugins.manager import plugin_manager

        raw_tools = plugin_manager.get_active_tool_definitions()
        if not raw_tools:
            return None

        tools = self._select_relevant_tools(text, raw_tools, max_tools=_MAX_TOOLS)

        name_map = {}
        for plugin in plugin_manager.get_all_plugins():
            if not plugin.is_enabled:
                continue
            for action_name in plugin.actions:
                clean_name = f"plugin_{action_name.replace('.', '_')}"
                name_map[clean_name] = action_name

        action_name = self._call_cloud_endpoint(text, provider, api_key, tools, name_map)
        if action_name:
            logger.info("[API LANE] Cloud matched '%s' for '%s'", action_name, text)
            success = manager.execute_skill(action_name, text)
            message = (f"Executed '{action_name}' via API Lane (Cloud)" if success
                       else f"Failed executing '{action_name}'")
            return {
                "handled": True,
                "tool": action_name,
                "method": "api_lane",
                "success": success,
                "message": message,
            }

        # The cloud understood the request but it is not a tool call — it is
        # a question. Answer it instead of reporting "command not recognized".
        # Only for questions: a command that merely failed to match a tool
        # is better left to the local model.
        from actions.intent_classifier import intent_classifier

        _, intent, _ = intent_classifier.classify(text)
        if intent != "llm_reasoning":
            return None

        answer = self._call_cloud_chat(text, provider, api_key)
        if answer:
            logger.info("[API LANE] Cloud answered '%s'", text)
            return {
                "handled": True,
                "tool": "chat_response",
                "method": "api_lane",
                "success": True,
                "message": answer,
                "details": {"answer": answer},
            }

        return None

    def _select_relevant_tools(self, text: str, tools: list, max_tools: int = _MAX_TOOLS) -> list:
        """
        Ranks and trims the tool definitions to stay safely within the
        provider's schema limits and token quotas.

        Core OS tools get a baseline score; tools whose name or
        description overlaps the command get a much higher one.
        """
        if len(tools) <= max_tools:
            return tools

        text_words = set(re.findall(r"\w+", text.lower()))
        scored_tools = []

        for tool in tools:
            function = tool.get("function", {})
            name = function.get("name", "").lower()
            description = function.get("description", "").lower()
            score = 0

            # Baseline priority for core OS and system tools
            if any(part in name for part in ("windows", "system", "app", "chrome", "media")):
                score += 2

            # Lexical overlap with the command
            for word in text_words:
                if len(word) > 2:
                    if word in name:
                        score += 6
                    if word in description:
                        score += 3

            scored_tools.append((score, tool))

        scored_tools.sort(key=lambda item: item[0], reverse=True)
        return [tool for _, tool in scored_tools[:max_tools]]

    def _call_cloud_endpoint(
        self,
        text: str,
        provider: str,
        api_key: str,
        tools: list,
        name_map: dict,
    ) -> Optional[str]:
        """Sends the command to the cloud provider and resolves the tool call."""
        if provider in ("claude", "anthropic"):
            return self._call_claude_endpoint(text, api_key, tools, name_map)

        endpoint, model = self._cloud_target(provider)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text.strip()},
            ],
            "tools": tools,
            "temperature": 0.0,
            "max_tokens": 128,
        }

        try:
            body = self._post_json(endpoint, payload, api_key)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            logger.warning("[API LANE] Cloud request failed (%s) %s: %s",
                           provider, exc.code, body)

            if exc.code == 429:
                return self._retry_after_rate_limit(endpoint, payload, api_key, name_map, body)
            if exc.code == 404 and provider == "groq":
                return self._retry_with_groq_fallback(endpoint, payload, api_key, name_map)
            return None
        except Exception as exc:
            logger.warning("[API LANE] Cloud request failed (%s): %s", provider, exc)
            return None

        return self._resolve_tool_call(body, name_map)

    def _cloud_target(self, provider: str):
        """Returns the (endpoint, model) pair for a provider."""
        from plugins.profile_manager import profile_manager

        if provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            model = profile_manager.get("cloud_model", "qwen/qwen3.8-27b")
            if model in ("llama-3.3-70b-versatile", "llama3-70b-8192"):
                model = "qwen/qwen3.8-27b"
            return endpoint, model
        if provider in ("gemini", "google"):
            return ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    profile_manager.get("cloud_model", "gemini-2.0-flash"))
        if provider == "openrouter":
            return ("https://openrouter.ai/api/v1/chat/completions",
                    profile_manager.get("cloud_model", "meta-llama/llama-3.3-70b-instruct:free"))
        if provider == "openai":
            return ("https://api.openai.com/v1/chat/completions",
                    profile_manager.get("cloud_model", "gpt-4o-mini"))
        return (profile_manager.get("api_base_url",
                                    "https://api.openai.com/v1/chat/completions").strip(),
                profile_manager.get("cloud_model", "gpt-4o-mini"))

    @staticmethod
    def _post_json(endpoint: str, payload: dict, api_key: str) -> dict:
        """POSTs a JSON payload to an OpenAI-compatible endpoint."""
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "PRIVACY68/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=6.0) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _resolve_tool_call(body: dict, name_map: dict) -> Optional[str]:
        """Maps a provider's tool call back to a plugin action name."""
        choices = body.get("choices") or [{}]
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return None
        function_name = tool_calls[0].get("function", {}).get("name", "")
        return name_map.get(function_name)

    def _retry_after_rate_limit(
        self,
        endpoint: str,
        payload: dict,
        api_key: str,
        name_map: dict,
        error_body: str = "",
    ) -> Optional[str]:
        """Waits out a 429 and tries once more."""
        wait_seconds = 3.0
        match = re.search(r"try again in (\d+(?:\.\d+)?)s", error_body or "")
        if match:
            wait_seconds = min(float(match.group(1)) + 0.5, 20.0)
        logger.info("[API LANE] Rate limit hit — retrying in %.1fs.", wait_seconds)
        time.sleep(wait_seconds)
        try:
            body = self._post_json(endpoint, payload, api_key)
            return self._resolve_tool_call(body, name_map)
        except Exception as exc:
            logger.warning("[API LANE] Rate-limit retry failed: %s", exc)
            return None

    def _retry_with_groq_fallback(
        self,
        endpoint: str,
        payload: dict,
        api_key: str,
        name_map: dict,
    ) -> Optional[str]:
        """Falls back to the current Groq model when the configured one is gone."""
        logger.info("[API LANE] Groq model unavailable — retrying with the current model.")
        payload = dict(payload)
        payload["model"] = "qwen/qwen3.8-27b"
        try:
            body = self._post_json(endpoint, payload, api_key)
            return self._resolve_tool_call(body, name_map)
        except Exception as exc:
            logger.warning("[API LANE] Groq fallback failed: %s", exc)
            return None

    def _call_claude_endpoint(
        self,
        text: str,
        api_key: str,
        tools: list,
        name_map: dict,
    ) -> Optional[str]:
        """Calls the Anthropic Messages API with native tool-calling."""
        from plugins.profile_manager import profile_manager

        endpoint = "https://api.anthropic.com/v1/messages"
        model = profile_manager.get("cloud_model", "claude-3-5-haiku-20241022")

        # Convert the OpenAI tool schemas to Anthropic's tool schema
        claude_tools = []
        for tool in tools:
            function = tool.get("function", {})
            claude_tools.append({
                "name": function.get("name", ""),
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
            })

        payload = {
            "model": model,
            "max_tokens": 128,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text.strip()}],
            "tools": claude_tools,
        }

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "PRIVACY68/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=6.0) as response:
                body = json.loads(response.read().decode("utf-8"))
            for block in body.get("content", []):
                if block.get("type") == "tool_use":
                    function_name = block.get("name", "")
                    matched = name_map.get(function_name)
                    if matched:
                        return matched
        except Exception as exc:
            logger.warning("[API LANE] Claude API request failed: %s", exc)
        return None

    def _call_cloud_chat(self, text: str, provider: str, api_key: str) -> Optional[str]:
        """
        Asks the cloud model a plain question and returns its answer.

        A voice assistant that can only pick tools is not much of an
        assistant: "explain quantum computing" has no tool to call, so
        the model is asked directly and its answer is what the user
        hears.
        """
        if provider in ("claude", "anthropic"):
            return self._call_claude_chat(text, api_key)

        endpoint, model = self._cloud_target(provider)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": text.strip()},
            ],
            "temperature": 0.4,
            "max_tokens": 400,
        }

        try:
            body = self._post_json(endpoint, payload, api_key)
        except Exception as exc:
            logger.warning("[API LANE] Cloud chat request failed (%s): %s", provider, exc)
            return None

        choices = body.get("choices") or [{}]
        content = (choices[0].get("message", {}) or {}).get("content") or ""
        return content.strip() or None

    def _call_claude_chat(self, text: str, api_key: str) -> Optional[str]:
        """Asks the Anthropic Messages API a plain question."""
        from plugins.profile_manager import profile_manager

        endpoint = "https://api.anthropic.com/v1/messages"
        model = profile_manager.get("cloud_model", "claude-3-5-haiku-20241022")

        payload = {
            "model": model,
            "max_tokens": 400,
            "system": CHAT_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text.strip()}],
        }

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "PRIVACY68/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=8.0) as response:
                body = json.loads(response.read().decode("utf-8"))
            parts = [block.get("text", "") for block in body.get("content", [])
                     if block.get("type") == "text"]
            return "".join(parts).strip() or None
        except Exception as exc:
            logger.warning("[API LANE] Claude chat request failed: %s", exc)
            return None


api_lane_router = APILaneRouter()

"""
PRIVACY68 API Lane Router & Dispatcher (Lane 2).
High-priority execution lane designed to run on ANY computer:
1. Direct Application & Web APIs (Weather, Public IP, Network status, Web Search)
   - Zero local RAM/GPU footprint
   - Instant HTTP responses (<150ms)
   - 100% lightweight Python urllib
2. Cloud LLM Semantic Router (Groq, OpenAI, Custom REST endpoint)
   - Dispatches natural language tool selection to high-speed cloud APIs
   - Leaves 100% of the PC's CPU/GPU free
"""

import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, Optional

from plugins.manager import plugin_manager
from plugins.profile_manager import profile_manager

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


class APILaneRouter:
    """
    Lane 2 Router: Handles direct application REST/Web APIs and Cloud LLM tool calling.
    Prioritized before heavy local models so PRIVACY68 runs smoothly on all computers.
    """

    def try_execute_api(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to execute the command via Lane 2 (API Lane):
        1. Checks direct web/app APIs (Weather, IP, etc.)
        2. Checks Cloud LLM Tool Router (Groq / OpenAI / Custom) if configured
        Returns result dict if handled, or None to fall through to Lane 3 (Local LLM).
        """
        if not text or not text.strip():
            return None

        clean = text.strip()
        low = clean.lower()

        # ─── Part 1: Direct Application & Web APIs ───
        direct_result = self._handle_direct_apis(clean, low)
        if direct_result is not None:
            return direct_result

        # ─── Part 2: Cloud LLM Semantic Tool Calling ───
        cloud_result = self._handle_cloud_llm(clean)
        if cloud_result is not None:
            return cloud_result

        return None

    def _handle_direct_apis(self, text: str, low: str) -> Optional[Dict[str, Any]]:
        """Direct, lightweight Web & Application APIs with zero API key requirement."""
        # 1. Weather API (wttr.in or Open-Meteo)
        weather_match = re.search(
            r"\b(?:what(?:\'s|\s+is)\s+the\s+weather|weather\s+today|check\s+weather|how(?:\'s|\s+is)\s+the\s+weather|temperature\s+outside|is\s+it\s+raining)\b(?:\s+(?:in|for|at)\s+([a-zA-Z\s]+))?",
            low,
        )
        if weather_match:
            city = (weather_match.group(1) or "").strip()
            return self._query_weather_api(city)

        # 2. Public IP / Network Info API (ipify.org)
        if any(p in low for p in ["what is my ip", "what's my ip", "check my ip", "my public ip", "check ip address"]):
            return self._query_ip_api()

        # 3. Direct Web Search & Compound Browser APIs
        web_res = self._handle_web_search_and_browser(text, low)
        if web_res is not None:
            return web_res

        # 4. Direct File & Folder CRUD APIs
        fs_res = self._handle_filesystem_apis(text, low)
        if fs_res is not None:
            return fs_res

        return None

    def _handle_web_search_and_browser(self, text: str, low: str) -> Optional[Dict[str, Any]]:
        """Handles web searches, scoped browser queries, and compound browser navigation via ML slot extraction."""
        from computer_use.system_tools import open_web_or_search
        from actions.param_extractor import param_extractor

        is_web = any(k in low for k in ("search", "google", "look up", "play ", "go to ", "visit ")) or (
            "open " in low and any(b in low for b in ("chrome", "brave", "edge", "firefox", "browser", "youtube", "reddit"))
        )
        if not is_web:
            return None

        intent = "compound_browser" if ("and " in low or "play " in low or "in chrome" in low or "in brave" in low) else "web_search"
        slots = param_extractor.extract_slots(text, intent)

        query = slots.get("query", "")
        site = slots.get("site")
        browser = slots.get("browser")

        if not query and not site and not browser:
            return None

        res = open_web_or_search(query=query, site_target=site, browser=browser)
        return {
            "handled": True,
            "tool": "open_web_or_search",
            "method": "api_lane",
            "success": res.get("success", False),
            "details": res,
            "message": res.get("message", f"Searched for '{query}'." if query else "Opened browser."),
        }

    def _handle_filesystem_apis(self, text: str, low: str) -> Optional[Dict[str, Any]]:
        """Handles create folder, create file, rename, and delete operations via ML slot extraction."""
        from computer_use.system_tools import (
            create_folder,
            create_file,
            rename_item,
            delete_file,
            resolve_path,
        )
        from actions.param_extractor import param_extractor

        # 1. Create Folder
        if "folder" in low and any(k in low for k in ("create", "make", "new", "add")):
            slots = param_extractor.extract_slots(text, "create_folder")
            name = slots.get("name")
            path = slots.get("path", "")
            if name:
                res = create_folder(path=path, name=name)
                return {
                    "handled": True,
                    "tool": "create_folder",
                    "method": "api_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Created folder '{name}'."),
                }

        # 2. Create File
        if "file" in low and any(k in low for k in ("create", "make", "new", "add")):
            slots = param_extractor.extract_slots(text, "create_file")
            name = slots.get("name")
            path = slots.get("path", "")
            content = slots.get("content", "")
            if name:
                res = create_file(path=path, name=name, content=content)
                return {
                    "handled": True,
                    "tool": "create_file",
                    "method": "api_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Created file '{name}'."),
                }

        # 3. Rename
        if "rename" in low or "change name" in low:
            slots = param_extractor.extract_slots(text, "rename_item")
            src = slots.get("source")
            dst = slots.get("name")
            path = slots.get("path")
            if src and dst:
                res = rename_item(source_name_or_path=src, new_name=dst, base_directory=path)
                return {
                    "handled": True,
                    "tool": "rename_item",
                    "method": "api_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Renamed '{src}' to '{dst}'."),
                }

        # 4. Delete
        if "delete" in low or "remove" in low:
            slots = param_extractor.extract_slots(text, "delete_item")
            target = slots.get("name")
            path = slots.get("path")
            if target:
                full_path = os.path.join(resolve_path(path), target) if path else resolve_path(target)
                res = delete_file(path=full_path)
                return {
                    "handled": True,
                    "tool": "delete_file",
                    "method": "api_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Deleted '{target}'."),
                }

        return None

    def _query_weather_api(self, city: str) -> Dict[str, Any]:
        """Fetches live weather via lightweight public JSON/text API."""
        try:
            target = urllib.parse.quote(city) if city else ""
            url = f"https://wttr.in/{target}?format=%C:+%t+(humidity+%h,+wind+%w)&m"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "curl/7.68.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = resp.read().decode("utf-8").strip()
                if data:
                    prefix = f"Weather in {city.title()}: " if city else "Local Weather: "
                    msg = f"{prefix}{data}"
                    logger.info(f"[API LANE] {msg}")
                    return {
                        "handled": True,
                        "tool": "api_weather",
                        "method": "api_lane",
                        "success": True,
                        "message": msg,
                        "details": {"weather": data, "city": city},
                    }
        except Exception as e:
            logger.warning(f"[API LANE] Weather API call failed: {e}")
        return {
            "handled": True,
            "tool": "api_weather",
            "method": "api_lane",
            "success": False,
            "message": "Could not retrieve weather information at this time.",
        }

    def _query_ip_api(self) -> Dict[str, Any]:
        """Fetches public IP address via ipify API."""
        try:
            req = urllib.request.Request(
                "https://api.ipify.org?format=json",
                headers={"User-Agent": "PRIVACY68/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ip = data.get("ip", "unknown")
                msg = f"Your public IP address is {ip}."
                logger.info(f"[API LANE] {msg}")
                return {
                    "handled": True,
                    "tool": "api_ip_info",
                    "method": "api_lane",
                    "success": True,
                    "message": msg,
                    "details": {"ip": ip},
                }
        except Exception as e:
            logger.warning(f"[API LANE] IP info API failed: {e}")
        return {
            "handled": True,
            "tool": "api_ip_info",
            "method": "api_lane",
            "success": False,
            "message": "Could not determine public IP address.",
        }

    def _handle_cloud_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Invokes Cloud LLM tool-calling if cloud provider and API key are configured."""
        provider = profile_manager.get("llm_provider", "").lower()
        api_key = profile_manager.get("api_key", "").strip()

        # If user explicitly configured cloud (or provided an API key), route through API Lane
        cloud_providers = ("groq", "gemini", "google", "openrouter", "claude", "anthropic", "openai", "custom")
        if (provider in cloud_providers or api_key) and api_key:
            from actions.skill_manager import manager
            raw_tools = plugin_manager.get_active_tool_definitions()
            if not raw_tools:
                return None

            # Prune tools to top 40 to strictly stay under Groq's 7000 token limit
            tools = self._select_relevant_tools(text, raw_tools, max_tools=40)

            name_map = {}
            for plugin in plugin_manager.get_all_plugins():
                if not plugin.is_enabled:
                    continue
                for action_name in plugin.actions:
                    clean_name = f"plugin_{action_name.replace('.', '_')}"
                    name_map[clean_name] = action_name

            action_name = self._call_cloud_endpoint(text, provider, api_key, tools, name_map)
            if action_name:
                logger.info(f"[API LANE] Cloud matched '{action_name}' for '{text}'")
                success = manager.execute_skill(action_name, text)
                msg = f"Executed '{action_name}' via API Lane (Cloud)" if success else f"Failed executing '{action_name}'"
                return {
                    "handled": True,
                    "tool": action_name,
                    "method": "api_lane",
                    "success": success,
                    "message": msg,
                }

        return None

    def _select_relevant_tools(self, text: str, tools: list, max_tools: int = 10) -> list:
        """
        Ranks and trims tools to stay safely within provider schema limits (Groq max 128)
        and token limits (Groq free tier 7,000 ITPM).
        Gives priority to core OS, system, and keywords matching the user prompt.
        """
        if len(tools) <= max_tools:
            return tools

        text_words = set(re.findall(r"\w+", text.lower()))
        scored_tools = []

        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name", "").lower()
            desc = fn.get("description", "").lower()
            score = 0

            # Baseline priority for core OS and system tools
            if any(p in name for p in ("windows", "system", "app", "chrome", "media")):
                score += 2

            # Lexical overlap with command
            for w in text_words:
                if len(w) > 2:
                    if w in name:
                        score += 6
                    if w in desc:
                        score += 3

            scored_tools.append((score, t))

        scored_tools.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored_tools[:max_tools]]

    def _call_cloud_endpoint(self, text: str, provider: str, api_key: str, tools: list, name_map: dict) -> Optional[str]:
        # Always prune tools to stay under provider tool count limits (Groq max 128) and token quotas
        tools = self._select_relevant_tools(text, tools, max_tools=10)

        # Provider endpoint & model mapping
        if provider in ("claude", "anthropic"):
            return self._call_claude_endpoint(text, api_key, tools, name_map)

        if provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            model = profile_manager.get("cloud_model", "qwen/qwen3.8-27b")
            if model in ("llama-3.3-70b-versatile", "llama3-70b-8192"):
                model = "qwen/qwen3.8-27b"
        elif provider in ("gemini", "google"):
            endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            model = profile_manager.get("cloud_model", "gemini-2.0-flash")
        elif provider == "openrouter":
            endpoint = "https://openrouter.ai/api/v1/chat/completions"
            model = profile_manager.get("cloud_model", "meta-llama/llama-3.3-70b-instruct:free")
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
                {"role": "user", "content": text.strip()},
            ],
            "tools": tools,
            "temperature": 0.0,
            "max_tokens": 128,
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "PRIVACY68/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=6.0) as res:
                body = json.loads(res.read().decode("utf-8"))
                choice = body.get("choices", [{}])[0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    func_name = tool_calls[0].get("function", {}).get("name", "")
                    matched = name_map.get(func_name)
                    if matched:
                        return matched
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning(f"[API LANE] Cloud LLM request failed ({provider}) {e.code}: {err_body}")
            # Auto-retry on rate limit (429) with dynamic backoff
            if e.code == 429:
                m_wait = re.search(r"try again in (\d+(?:\.\d+)?)s", err_body)
                wait_sec = min(float(m_wait.group(1)) + 0.5, 20.0) if m_wait else 3.0
                logger.info(f"[API LANE] Rate limit 429 hit ({provider}). Backing off {wait_sec:.1f}s and retrying...")
                time.sleep(wait_sec)
                try:
                    with urllib.request.urlopen(req, timeout=6.0) as retry_res:
                        r_body = json.loads(retry_res.read().decode("utf-8"))
                        t_calls = r_body.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                        if t_calls:
                            f_name = t_calls[0].get("function", {}).get("name", "")
                            return name_map.get(f_name)
                except Exception as r_err:
                    logger.warning(f"[API LANE] 429 retry failed: {r_err}")

            # Auto-fallback for Groq if model was deprecated
            if provider == "groq" and e.code == 404 and model != "qwen/qwen3.8-27b":
                logger.info("[API LANE] Groq model fallback: attempting 'qwen/qwen3.8-27b'...")
                payload["model"] = "qwen/qwen3.8-27b"
                try:
                    retry_req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}",
                            "User-Agent": "PRIVACY68/1.0",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(retry_req, timeout=6.0) as retry_res:
                        r_body = json.loads(retry_res.read().decode("utf-8"))
                        t_calls = r_body.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                        if t_calls:
                            f_name = t_calls[0].get("function", {}).get("name", "")
                            return name_map.get(f_name)
                except Exception as r_err:
                    logger.warning(f"[API LANE] Groq fallback failed: {r_err}")
        except Exception as e:
            logger.warning(f"[API LANE] Cloud LLM request failed ({provider}): {e}")
        return None

    def _call_claude_endpoint(self, text: str, api_key: str, tools: list, name_map: dict) -> Optional[str]:
        """Calls Anthropic Claude Messages API with native tool-calling."""
        endpoint = "https://api.anthropic.com/v1/messages"
        model = profile_manager.get("cloud_model", "claude-3-5-haiku-20241022")

        # Convert OpenAI tool schemas to Anthropic Claude tool schemas
        claude_tools = []
        for t in tools:
            fn = t.get("function", {})
            claude_tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })

        payload = {
            "model": model,
            "max_tokens": 128,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": text.strip()}
            ],
            "tools": claude_tools,
        }

        req = urllib.request.Request(
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
            with urllib.request.urlopen(req, timeout=6.0) as res:
                body = json.loads(res.read().decode("utf-8"))
                contents = body.get("content", [])
                for block in contents:
                    if block.get("type") == "tool_use":
                        func_name = block.get("name", "")
                        matched = name_map.get(func_name)
                        if matched:
                            return matched
        except Exception as e:
            logger.warning(f"[API LANE] Claude API request failed: {e}")
        return None


api_lane_router = APILaneRouter()

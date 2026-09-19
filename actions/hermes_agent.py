import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
import ollama

from actions.skill_manager import manager
from plugins.profile_manager import profile_manager
from plugins.manager import plugin_manager

logger = logging.getLogger("PRIVACY68.HermesAgent")

class HermesAgent:
    """
    Autonomous Hermes Agent & Function-Calling Engine for PRIVACY68.
    
    Supports:
    1. Native Ollama Tool Calling (via `tools=[...]` parameter) for models like Hermes 3, Llama 3.2, Qwen 2.5 3B/7B.
    2. Hermes ChatML XML & JSON Fallback (`<tool_call>...`) for lightweight models like Qwen 2.5 0.5B/1.5B.
    3. Structured parameter extraction and direct execution.
    """

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Returns Ollama-compatible JSON Schema tool specifications for active skills and plugins.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": "Opens or launches a desktop application or browser (e.g. Chrome, Brave, VS Code, Notepad, PowerPoint, WhatsApp).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "The name of the app to launch (e.g. 'chrome', 'brave', 'vscode', 'notepad', 'powerpoint', 'whatsapp')"
                            }
                        },
                        "required": ["app_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Searches Google or the web for answers, general knowledge, current events, weather, or topics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The exact search query or question to look up"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "system_control",
                    "description": "Controls Windows system functions such as volume, muting, locking screen, sleep, or shutdown.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "System action: 'volume_up', 'volume_down', 'mute', 'unmute', 'lock', 'sleep', 'shutdown', 'restart'"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send",
                    "description": "Opens WhatsApp and sends a message to a specific contact or opens a chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact": {
                                "type": "string",
                                "description": "Recipient name (e.g. 'Mom', 'Alex', 'Rahul')"
                            },
                            "message": {
                                "type": "string",
                                "description": "The message text to send (optional if just opening chat)"
                            }
                        },
                        "required": ["contact"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "powerpoint_control",
                    "description": "Controls PowerPoint presentations (next/prev slide, start/end slideshow, laser pointer, pen, black screen, go to slide).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "The presentation action: 'next', 'previous', 'start', 'end', 'laser', 'pen', 'black_screen', 'white_screen', 'goto_slide'"
                            },
                            "slide_number": {
                                "type": "integer",
                                "description": "Slide number if jumping to a specific slide"
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "gesture_control",
                    "description": "Enables or disables webcam hand gesture recognition controls.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "'enable' to start hand gestures, or 'disable' to stop tracking"
                            }
                        },
                        "required": ["action"]
                    }
                }
            }
        ]

        # Dynamically append schemas for all active custom & community plugins
        try:
            plugin_tools = plugin_manager.get_active_tool_definitions()
            existing_names = {t.get("function", {}).get("name") for t in tools if "function" in t}
            for pt in plugin_tools:
                pt_name = pt.get("function", {}).get("name")
                if pt_name and pt_name not in existing_names:
                    tools.append(pt)
                    existing_names.add(pt_name)
        except Exception as e:
            logger.warning(f"Failed to query active plugin tool schemas: {e}")

        return tools

    def _build_hermes_prompt(self, user_text: str) -> Tuple[str, str]:
        """
        Builds a Hermes 3 formatted system prompt containing tool schemas for prompt-based function calling.
        """
        tools = self.get_tool_definitions()
        tools_str = json.dumps(tools, indent=2)

        system_prompt = (
            "You are PRIVACY68, an intelligent autonomous desktop assistant powered by Hermes Agent.\n"
            "You have access to the following tools:\n"
            f"<tools>\n{tools_str}\n</tools>\n\n"
            "To call a tool, respond ONLY with a <tool_call> XML block containing a valid JSON object with 'name' and 'arguments'.\n"
            "Example:\n"
            "<tool_call>\n"
            "{\"name\": \"whatsapp_send\", \"arguments\": {\"contact\": \"Mom\", \"message\": \"I am on my way\"}}\n"
            "</tool_call>\n\n"
            "If no tool matches the request, call the 'web_search' tool with the user query."
        )

        return system_prompt, user_text

    def parse_tool_call_from_text(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Extracts tool name and arguments from XML tags (<tool_call>...</tool_call>) or JSON blocks.
        """
        if not text:
            return None

        # 1. Look for <tool_call> tags
        match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                return data.get("name"), data.get("arguments", {})
            except Exception as e:
                logger.warning(f"Could not parse <tool_call> JSON: {e}")

        # 2. Look for markdown code blocks containing JSON with "name" and "arguments"
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if "name" in data:
                    return data.get("name"), data.get("arguments", {})
            except Exception as e:
                pass

        # 3. Check if the entire response is raw JSON
        trimmed = text.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                data = json.loads(trimmed)
                if "name" in data:
                    return data.get("name"), data.get("arguments", {})
            except Exception:
                pass

        return None

    def execute_tool_call(self, tool_name: str, arguments: Dict[str, Any], raw_text: str = "") -> bool:
        """
        Dispatches the parsed tool call and arguments to the appropriate skill / plugin.
        """
        logger.info(f"Hermes Agent Executing: '{tool_name}' with args={arguments}")
        
        # Route through manager's structured executor
        return manager.execute_tool_with_args(tool_name, arguments, raw_text)

    def run(self, user_text: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs the Hermes Agent against the user command.
        Returns dict: {"success": bool, "tool": str, "method": str, "message": str}
        """
        if not model_name:
            model_name = profile_manager.get("llm_model", "qwen2.5:0.5b")

        tools = self.get_tool_definitions()

        # Step 1: Attempt Native Ollama Function Calling
        try:
            logger.info(f"Hermes Agent querying model '{model_name}' with native tools...")
            response = ollama.chat(
                model=model_name,
                keep_alive="60s",
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 1024
                },
                messages=[
                    {
                        "role": "system",
                        "content": "You are PRIVACY68, an offline autonomous AI assistant. Use the provided tools to fulfill the user's intent."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ],
                tools=tools
            )

            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                first_call = tool_calls[0]
                fn_name = first_call.get("function", {}).get("name")
                fn_args = first_call.get("function", {}).get("arguments", {})
                
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                logger.info(f"Hermes Native Tool Call: {fn_name}({fn_args})")
                success = self.execute_tool_call(fn_name, fn_args, user_text)
                return {
                    "success": success,
                    "tool": fn_name,
                    "method": "hermes_native",
                    "message": f"Executed '{fn_name}' via Hermes Agent" if success else f"Failed executing '{fn_name}'"
                }

            # If model returned text instead of tool_calls, check for embedded Hermes XML tags
            content = msg.get("content", "").strip()
            parsed = self.parse_tool_call_from_text(content)
            if parsed:
                fn_name, fn_args = parsed
                logger.info(f"Hermes XML Tag Parsed from Native Mode: {fn_name}({fn_args})")
                success = self.execute_tool_call(fn_name, fn_args, user_text)
                return {
                    "success": success,
                    "tool": fn_name,
                    "method": "hermes_xml",
                    "message": f"Executed '{fn_name}' via Hermes Agent" if success else f"Failed executing '{fn_name}'"
                }

        except Exception as e:
            logger.warning(f"Native tool calling failed or not supported by model '{model_name}': {e}. Falling back to Hermes Prompt Mode.")

        # Step 2: Fallback to Hermes Prompt Mode (ChatML / XML Schema)
        try:
            sys_prompt, user_content = self._build_hermes_prompt(user_text)
            response = ollama.chat(
                model=model_name,
                keep_alive="60s",
                options={
                    "temperature": 0.1,
                    "num_ctx": 1024
                },
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_content}
                ]
            )

            content = response.get("message", {}).get("content", "").strip()
            logger.info(f"Hermes Prompt Output: {content}")

            parsed = self.parse_tool_call_from_text(content)
            if parsed:
                fn_name, fn_args = parsed
                success = self.execute_tool_call(fn_name, fn_args, user_text)
                return {
                    "success": success,
                    "tool": fn_name,
                    "method": "hermes_prompt",
                    "message": f"Executed '{fn_name}' via Hermes Prompt Mode" if success else f"Failed executing '{fn_name}'"
                }

            # If model returned plain text name of a tool (e.g. 'chrome', 'web_search')
            clean_token = content.strip().lower().replace(" ", "").replace("_", "").replace(".", "")
            if "search" in clean_token or "google" in clean_token:
                success = manager.execute_tool_with_args("web_search", {"query": user_text}, user_text)
                return {"success": success, "tool": "web_search", "method": "hermes_fallback", "message": f"Searched for '{user_text}'"}

        except Exception as e:
            logger.error(f"Hermes Agent error: {e}")

        # Step 3: Catch-All Fallback (Web Search)
        logger.info(f"Hermes Agent falling back to web search for '{user_text}'")
        success = manager.execute_tool_with_args("web_search", {"query": user_text}, user_text)
        return {
            "success": success,
            "tool": "web_search",
            "method": "catch_all",
            "message": f"Searched the web for '{user_text}'"
        }

# Global Hermes Agent instance
hermes_agent = HermesAgent()

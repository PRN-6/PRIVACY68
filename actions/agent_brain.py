import os
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
from pathlib import Path
import logging
import urllib.request
from typing import Any, Dict, List, Optional
import litellm
import config
from actions.agent_runner import run_agent_code

# Disable telemetry and remote network calls for offline/sandboxed stability
litellm.telemetry = False
litellm.suppress_debug_info = True

logger = logging.getLogger("PRIVACY68.AgentBrain")


def is_ollama_online(host: Optional[str] = None) -> bool:
    """Quick non-blocking check if local or remote Ollama website/host is reachable."""
    target_host = host or getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        headers = {}
        api_key = getattr(config, "OLLAMA_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        req = urllib.request.Request(f"{target_host.rstrip('/')}/api/tags", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


class AgentBrain:
    """
    The 'Brain' of the Agentic System.
    Uses LiteLLM to communicate with the configured Ollama or cloud model,
    with an Open-Interpreter style self-healing execution loop.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or getattr(config, "AGENT_BRAIN_MODEL", "groq/llama-3.3-70b-versatile")
        self.max_retries = getattr(config, "AGENT_BRAIN_MAX_RETRIES", 2)
        self.last_code = ""
        self.last_reasoning = ""
        self.active_provider_used = self.model

    def get_fallback_models(self, current_model: str) -> List[str]:
        """
        Returns an ordered list of alternative models that are configured and ready to use,
        excluding the currently selected model.
        """
        fallbacks: List[str] = []
        cur_low = (current_model or "").lower()

        gemini_key = getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        groq_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        claude_key = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        openai_key = getattr(config, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

        # 1. Google Gemini (Fast & Generous Free Tier)
        if gemini_key and "gemini" not in cur_low:
            fallbacks.append("gemini/gemini-3.5-flash")

        # 2. Groq Cloud (Ultra-Fast Free Tier)
        if groq_key and "groq" not in cur_low:
            fallbacks.append("groq/openai/gpt-oss-120b")

        # 3. Anthropic Claude (Frontier Intelligence)
        if claude_key and "claude" not in cur_low and "anthropic" not in cur_low:
            fallbacks.append("claude-3-5-sonnet-20241022")

        # 4. OpenAI (GPT-4o mini)
        if openai_key and "openai" not in cur_low and "gpt" not in cur_low:
            fallbacks.append("openai/gpt-4o-mini")

        # 5. Local Ollama (if running)
        if "ollama" not in cur_low and is_ollama_online():
            fallbacks.append("ollama/llama3.2:latest")

        return fallbacks

    def _resolve_user_paths(self) -> Dict[str, str]:
        """Resolves active user directory paths, including OneDrive redirections."""
        home = Path.home()
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer") or os.environ.get("OneDriveCommercial") or ""

        desktop = str(home / "Desktop")
        if onedrive and os.path.exists(os.path.join(onedrive, "Desktop")):
            desktop = os.path.join(onedrive, "Desktop")

        downloads = str(home / "Downloads")
        if onedrive and os.path.exists(os.path.join(onedrive, "Downloads")):
            downloads = os.path.join(onedrive, "Downloads")

        documents = str(home / "Documents")
        if onedrive and os.path.exists(os.path.join(onedrive, "Documents")):
            documents = os.path.join(onedrive, "Documents")

        return {
            "home": str(home),
            "desktop": desktop,
            "downloads": downloads,
            "documents": documents,
            "onedrive": onedrive,
        }

    def _build_system_prompt(self) -> str:
        paths = self._resolve_user_paths()
        env_lines = [
            f"- User Home: r'{paths['home']}'",
            f"- Desktop: r'{paths['desktop']}'",
            f"- Downloads: r'{paths['downloads']}'",
            f"- Documents: r'{paths['documents']}'",
        ]
        if paths["onedrive"]:
            env_lines.append(f"- OneDrive Root: r'{paths['onedrive']}'")
        env_str = "\n".join(env_lines)

        return (
            "You are the core of PRIVACY68, a professional Windows OS Automation Agent. "
            "Your goal is to execute the user's request by writing a Python script.\n\n"
            f"SYSTEM ENVIRONMENT (Use these exact paths for user directories):\n{env_str}\n\n"
            "PRIORITY TOOLBOX (Use in this order):\n"
            "1. Built-in Plugin Logic: For Chrome, Brave, WhatsApp, GitHub, and Windows System controls, "
            "use the existing plugins in the project. Brave is 'from plugins.brave_plugin import BravePlugin'; "
            "Chrome is 'from plugins.chrome_plugin import ChromePlugin'.\n"
            "2. pyautogui: For mouse/keyboard control and hotkeys.\n"
            "3. pywinauto: For deep Windows application interaction.\n"
            "4. os/subprocess/shutil: For shell commands and file management.\n"
            "5. playwright: Use ONLY as a last resort for complex web scraping/automation.\n\n"
            "RULES:\n"
            "1. ONLY output the Python code. No explanations, no markdown blocks.\n"
            "2. Always import necessary libraries (e.g. os, shutil, glob).\n"
            "3. Ensure scripts are self-contained and handle exceptions. Prefer executable top-level code; "
            "if you define a main() function, call main() at the end of the script.\n"
            "4. CRITICAL IMPORT PATHS: Use the actual module names, such as 'from plugins.brave_plugin import BravePlugin' "
            "and 'from plugins.chrome_plugin import ChromePlugin'. Do NOT invent plugin module names.\n"
            "5. For web searches, generate the direct search URL and open it with an available browser plugin.\n"
            "6. USER FOLDERS: When accessing Desktop, Downloads, or Documents, ALWAYS use the exact paths from "
            "the SYSTEM ENVIRONMENT block above. Do not hardcode C:\\Users\\...\\Desktop if Desktop is redirected by OneDrive.\n"
            "7. If you cannot perform the action, return a print statement explaining why."
        )

    @property
    def system_prompt(self) -> str:
        return self._build_system_prompt()

    def _call_single_model(self, model: str, messages: list) -> str:
        """Executes a single LiteLLM completion with provider credential binding."""
        api_key = None
        api_base = None
        model_lower = model.lower()

        if "gemini" in model_lower:
            api_key = getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key.strip()
                os.environ["GOOGLE_API_KEY"] = api_key.strip()
            is_mocked = hasattr(litellm.completion, "mock_calls") or hasattr(litellm.completion, "return_value")
            if not is_mocked and not api_key:
                raise ValueError("Google Gemini API key is not configured. Go to the 'AI Brain' tab in the dashboard and paste your Gemini API key.")

        elif "claude" in model_lower or "anthropic" in model_lower:
            api_key = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key.strip()
            is_mocked = hasattr(litellm.completion, "mock_calls") or hasattr(litellm.completion, "return_value")
            if not is_mocked and not api_key:
                raise ValueError("Anthropic Claude API key is not configured. Go to the 'AI Brain' tab in the dashboard and paste your Claude API key.")

        elif "groq" in model_lower:
            api_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
            if api_key:
                os.environ["GROQ_API_KEY"] = api_key.strip()
            is_mocked = hasattr(litellm.completion, "mock_calls") or hasattr(litellm.completion, "return_value")
            if not is_mocked and not api_key:
                raise ValueError("Groq API key is not configured. Go to the 'AI Brain' tab in the dashboard and paste your free Groq API key.")

        elif "gpt" in model_lower or "openai" in model_lower:
            api_key = getattr(config, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key.strip()
            is_mocked = hasattr(litellm.completion, "mock_calls") or hasattr(litellm.completion, "return_value")
            if not is_mocked and not api_key:
                raise ValueError("OpenAI API key is not configured. Go to the 'AI Brain' tab in the dashboard and paste your OpenAI API key.")

        elif "ollama" in model_lower:
            ollama_url = getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            api_base = ollama_url.rstrip("/")
            api_key = getattr(config, "OLLAMA_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
            os.environ["OLLAMA_API_BASE"] = api_base
            is_mocked = hasattr(litellm.completion, "mock_calls") or hasattr(litellm.completion, "return_value")
            if not is_mocked and not is_ollama_online():
                raise ConnectionError(f"Cannot reach Ollama API at {api_base}. Use a Cloud API (Gemini, Claude, or Groq [Free]) in the AI Brain tab, or check your Ollama API endpoint.")

        call_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0,
        }
        if api_base:
            call_kwargs["api_base"] = api_base
        if api_key:
            call_kwargs["api_key"] = api_key.strip()

        response = litellm.completion(**call_kwargs)
        code = response.choices[0].message.content.strip()

        if code.startswith("```python"):
            code = code.split("```python")[1].split("```")[0].strip()
        elif code.startswith("```"):
            code = code.split("```")[1].split("```")[0].strip()
        return code

    def _get_code_from_llm(self, text: str, error_context: Optional[str] = None) -> str:
        """Uses LiteLLM to get Python code from configured models with automated multi-provider failover."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": text},
        ]
        if error_context and self.last_code:
            messages.append({"role": "assistant", "content": self.last_code})
            messages.append({
                "role": "user",
                "content": (
                    f"The previous script failed with this error:\n{error_context}\n"
                    "Please fix the Python script to resolve this error. Output ONLY valid Python code."
                )
            })

        # Try primary model first, then auto-failover through any other configured providers
        models_to_try = [self.model] + self.get_fallback_models(self.model)
        primary_exception = None
        last_exception = None

        for idx, model_name in enumerate(models_to_try):
            try:
                if idx > 0:
                    logger.warning(f"[AGENT BRAIN] Auto-Failover: Primary provider failed. Switching to fallback provider '{model_name}'...")
                code = self._call_single_model(model_name, messages)
                if code:
                    self.active_provider_used = model_name
                    if idx > 0:
                        logger.info(f"[AGENT BRAIN] Auto-Failover succeeded via '{model_name}'!")
                    return code
            except Exception as exc:
                if idx == 0:
                    primary_exception = exc
                last_exception = exc
                logger.warning(f"[AGENT BRAIN] Model '{model_name}' call failed ({exc}).")

        if primary_exception:
            raise primary_exception
        if last_exception:
            raise last_exception
        return ""

    def generate_and_execute(self, text: str) -> Dict[str, Any]:
        """
        Generates code via LiteLLM and executes it in a separate process,
        with automated self-repair on error (Open-Interpreter pattern).
        """
        self.last_code = ""
        self.last_reasoning = f"Analyzing request: {text}"

        # Fast-Path: Check Learned Skills library first (0ms latency, zero API tokens)
        try:
            from actions.skill_manager import skill_manager
            matched_skill = skill_manager.find_matching_skill(text)
            if matched_skill:
                logger.info(f"[SKILL RECALL] Running learned skill '{matched_skill['name']}' for '{text}' (0ms fast-path)")
                skill_res = skill_manager.execute_skill(matched_skill)
                if skill_res.get("success"):
                    self.last_code = matched_skill.get("code", "")
                    self.last_reasoning = f"Executed learned skill: {matched_skill['name']} (0ms)"
                    skill_manager.record_execution(matched_skill["id"], success=True)
                    return {
                        "success": True,
                        "message": f"Executed learned skill: {matched_skill['name']}",
                        "output": skill_res.get("output", ""),
                        "method": "learned_skill",
                        "tool": "learned_skill",
                    }
                else:
                    logger.warning(f"[SKILL RECALL] Skill '{matched_skill['name']}' failed; escalating to LLM self-healing...")
        except Exception as sm_err:
            logger.debug(f"[SKILL RECALL] Lookup note: {sm_err}")

        try:
            logger.info(f"[AGENT BRAIN] Reasoning via {self.model}: {text}")

            # Step 1: Get code from LLM
            try:
                code = self._get_code_from_llm(text)
            except Exception as e:
                err_str = str(e)
                err_name = type(e).__name__
                if "API key is not configured" in err_str or "Cannot reach Ollama API" in err_str:
                    logger.warning(f"[AGENT BRAIN] {err_str}")
                    return {
                        "success": False,
                        "message": err_str,
                        "output": err_str,
                        "method": "agentic_engine",
                    }
                if "not found" in err_str.lower() or "notfounderror" in err_name.lower():
                    logger.error(f"[AGENT BRAIN] Model '{self.model}' not found in API: {e}")
                    if "ollama" in self.model.lower():
                        msg = f"Model '{self.model}' is not installed in Ollama. Verify model name or switch to Gemini / Groq in the dashboard."
                    else:
                        msg = f"Model '{self.model}' was not found or is deprecated by the provider API. Please select an active model (such as 'gemini/gemini-3.5-flash') in the AI Brain tab."
                    return {
                        "success": False,
                        "message": msg,
                        "output": err_str,
                        "method": "agentic_engine",
                    }
                if "10061" in err_str or "Connection refused" in err_str or "APIConnectionError" in err_name:
                    logger.error(f"[AGENT BRAIN] API connection failed: {e}")
                    return {
                        "success": False,
                        "message": "AI API connection failed. Check your API key and network connection, or switch to Groq (Free) / Claude in the dashboard.",
                        "output": err_str,
                        "method": "agentic_engine",
                    }
                raise e

            self.last_code = code

            if not code:
                return {"success": False, "message": "LLM failed to generate code.", "method": "agentic_brain"}

            # Self-healing execution loop
            attempt = 0
            current_code = code

            while attempt <= self.max_retries:
                logger.info(f"[AGENT BRAIN] Executing generated code (attempt {attempt + 1}):\n{current_code}")
                result = run_agent_code(current_code, timeout=30)

                if result.returncode == 0:
                    # Self-improving loop: crystallize working code into a reusable skill
                    try:
                        from actions.skill_manager import skill_manager
                        skill_manager.learn_skill(trigger_command=text, code=current_code)
                    except Exception as learn_err:
                        logger.debug(f"[SELF-IMPROVING] Could not save skill: {learn_err}")

                    provider_note = f" (via {self.active_provider_used})" if self.active_provider_used != self.model else ""
                    return {
                        "success": True,
                        "message": f"Task executed successfully via Agent Brain{provider_note}.",
                        "output": result.stdout,
                        "method": "agentic_engine",
                    }

                attempt += 1
                if attempt <= self.max_retries:
                    logger.warning(f"[AGENT BRAIN] Execution error (attempt {attempt}). Initiating self-correction...")
                    self.last_reasoning = f"Self-repairing code: {result.stderr.strip()[:80]}..."
                    try:
                        repaired = self._get_code_from_llm(text, error_context=result.stderr)
                        if repaired:
                            current_code = repaired
                            self.last_code = current_code
                            continue
                    except Exception as re_err:
                        logger.warning(f"[AGENT BRAIN] Self-healing attempt failed: {re_err}")
                        break

            return {
                "success": False,
                "message": f"Execution error: {result.stderr}",
                "output": result.stderr,
                "method": "agentic_engine",
            }

        except Exception as e:
            logger.error(f"[AGENT BRAIN] Critical Failure: {e}")
            return {
                "success": False,
                "message": f"Agent Brain Error: {str(e)}",
                "method": "agentic_engine",
            }


agent_brain = AgentBrain()

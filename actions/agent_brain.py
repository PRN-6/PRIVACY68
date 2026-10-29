import os
from pathlib import Path
import logging
from typing import Any, Dict
import litellm
from actions.agent_runner import run_agent_code

logger = logging.getLogger("PRIVACY68.AgentBrain")

class AgentBrain:
    """
    The 'Brain' of the Agentic System.
    Uses LiteLLM to communicate with the configured Ollama model and a specialized
    subprocess runner for persistent-like execution.
    """

    def __init__(self):
        # LiteLLM uses the user's local Ollama service, which may proxy a cloud model.
        self.model = "ollama/gemma4:31b-cloud"

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

    def _get_code_from_llm(self, text: str) -> str:
        """Uses LiteLLM to get Python code from the configured model."""
        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        code = response.choices[0].message.content.strip()

        if code.startswith("```python"):
            code = code.split("```python")[1].split("```")[0].strip()
        elif code.startswith("```"):
            code = code.split("```")[1].split("```")[0].strip()
        return code

    def generate_and_execute(self, text: str) -> Dict[str, Any]:
        """
        Generates code via LiteLLM and executes it in a separate process.
        """
        self.last_code = ""
        self.last_reasoning = f"Analyzing request: {text}"
        try:
            logger.info(f"[AGENT BRAIN] Reasoning via {self.model}: {text}")

            # Step 1: Get the code from Local LLM
            code = self._get_code_from_llm(text)

            # Store for UI visibility
            self.last_code = code

            if not code:
                return {"success": False, "message": "LLM failed to generate code.", "method": "agentic_brain"}

            logger.info(f"[AGENT BRAIN] Executing generated code:\n{code}")

            # Run in a separate process; the runner uses a Python subprocess in
            # source mode and the executable's internal runner in frozen builds.
            result = run_agent_code(code, timeout=30)

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Task executed successfully via Agent Brain.",
                    "output": result.stdout,
                    "method": "agentic_engine",
                }
            else:
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

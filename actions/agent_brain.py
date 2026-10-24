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
        self.system_prompt = (
            "You are the la-core of PRIVACY68, a professional Windows OS Automation Agent. "
            "Your goal is to execute the user's request by writing a Python script. \n\n"
            "PRIORITY TOOLBOX (Use in this order):\n"
            "1. Built-in Plugin Logic: For Chrome, Brave, WhatsApp, PowerPoint, VS Code, and System controls, "
            "use the existing plugins in the project. Use the 'plugins' package structure.\n"
            "2. pyautogui: For mouse/keyboard control and hotkeys.\n"
            "3. pywinauto: For deep Windows application interaction.\n"
            "4. os/subprocess: For shell commands and file management.\n"
            "5. playwright: Use ONLY as a last resort for complex web scraping/automation.\n\n"
            "RULES:\n"
            "1. ONLY output the Python code. No explanations, no markdown blocks.\n"
            "2. Always import necessary libraries.\n"
            "3. Ensure scripts are self-contained and handle exceptions.\n"
            "4. CRITICAL IMPORT PATHS: Always import plugins as 'from plugins.chrome_plugin import ChromePlugin' or 'from plugins.system_plugin import SystemPlugin'. Do NOT use 'from plugins.chrome'.\n"
            "5. For web searches, ALWAYS generate the direct search URL (e.g., 'https://www.google.com/search?q=QUERY') and use the Chrome/Brave plugin to open that URL.\n"
            "6. If you cannot perform the action, return a print statement explaining why."
        )

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

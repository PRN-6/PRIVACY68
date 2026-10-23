import logging
from typing import Any, Dict
import litellm
import subprocess
import sys

logger = logging.getLogger("PRIVACY68.AgentBrain")

class AgentBrain:
    """
    The 'Brain' of the Agentic System.
    Uses litellm for reliable local LLM communication and a specialized
    subprocess runner for persistent-like execution.
    """

    def __init__(self):
        # 1. Local LLM Configuration (via litellm)
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
        """Uses litellm to get Python code from the local model."""
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
        Generates code via litellm and executes it directly using the system Python.
        This completely bypasses the broken OpenInterpreter model-check loop.
        """
        try:
            logger.info(f"[AGENT BRAIN] Reasoning via {self.model}: {text}")

            # Step 1: Get the code from Local LLM
            code = self._get_code_from_llm(text)

            # Store for UI visibility
            self.last_code = code
            self.last_reasoning = f"Analyzing request: {text}"

            if not code:
                return {"success": False, "message": "LLM failed to generate code.", "method": "agentic_brain"}

            logger.info(f"[AGENT BRAIN] Executing generated code:\n{code}")

            # Step 2: Execute directly using a subprocess.
            # This is the most reliable way to ensure the code runs exactly as intended
            # without external library interference.
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=30
            )

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

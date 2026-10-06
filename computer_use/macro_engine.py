"""
PRIVACY68 Macro & Workflow Automation Engine.

Enables compound multi-step workflows ("Coding Mode", "Meeting Mode", "Focus Mode", etc.)
and allows dynamic registration of user-defined automation skills.
"""

import time
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("PRIVACY68.MacroEngine")


class MacroWorkflow:
    def __init__(self, name: str, description: str, steps: List[Dict[str, Any]]):
        self.name = name
        self.description = description
        self.steps = steps  # List of {"action": str, "params": dict, "delay": float}


class MacroEngine:
    """
    Executes predefined and user-customized multi-step action routines.
    """

    def __init__(self):
        self._workflows: Dict[str, MacroWorkflow] = {}
        self._register_default_modes()

    def register_workflow(self, name: str, description: str, steps: List[Dict[str, Any]]):
        key = name.lower().strip()
        self._workflows[key] = MacroWorkflow(name=name, description=description, steps=steps)
        logger.info(f"[MACRO] Registered workflow: '{name}' with {len(steps)} steps.")

    def _register_default_modes(self):
        # 1. Coding Mode
        self.register_workflow(
            name="coding mode",
            description="Launches VS Code, opens GitHub in browser, and prepares developer workspace",
            steps=[
                {"action": "open_app", "params": {"app_name": "vscode"}, "delay": 0.5},
                {"action": "open_web", "params": {"query": "https://github.com"}, "delay": 0.5},
                {"action": "toast_message", "params": {"message": "Coding mode activated. Happy coding!"}, "delay": 0.0},
            ]
        )

        # 2. Focus Mode
        self.register_workflow(
            name="focus mode",
            description="Minimizes distractions, sets volume to calm level, and shows desktop",
            steps=[
                {"action": "show_desktop", "params": {}, "delay": 0.2},
                {"action": "set_volume", "params": {"level": 25}, "delay": 0.1},
                {"action": "toast_message", "params": {"message": "Focus mode activated. Distractions minimized."}, "delay": 0.0},
            ]
        )

        # 3. Meeting Mode
        self.register_workflow(
            name="meeting mode",
            description="Prepares audio levels and brings active presentation / meeting forward",
            steps=[
                {"action": "set_volume", "params": {"level": 60}, "delay": 0.1},
                {"action": "toast_message", "params": {"message": "Meeting mode activated."}, "delay": 0.0},
            ]
        )

    def match_and_execute(self, text: str, executor_func: Callable[[str, Dict[str, Any]], Any]) -> Optional[Dict[str, Any]]:
        """Checks if text activates any registered macro and executes all compound steps."""
        lower = text.lower().strip(" .!?")
        for key, wf in self._workflows.items():
            if key in lower or lower in [f"start {key}", f"activate {key}", f"turn on {key}", f"enter {key}"]:
                logger.info(f"[MACRO] Triggering compound workflow: '{wf.name}'")
                results = []
                for step in wf.steps:
                    action = step.get("action", "")
                    params = step.get("params", {})
                    delay = step.get("delay", 0.0)
                    try:
                        res = executor_func(action, params)
                        results.append(res)
                    except Exception as e:
                        logger.error(f"[MACRO] Step failed '{action}': {e}")
                    if delay > 0:
                        time.sleep(delay)

                return {
                    "success": True,
                    "workflow": wf.name,
                    "steps_executed": len(results),
                    "message": f"Successfully activated '{wf.name}'.",
                }
        return None


# Global singleton instance
macro_engine = MacroEngine()

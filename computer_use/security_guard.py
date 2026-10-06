"""
PRIVACY68 Security & Permission Guard.

Implements the 3-Tier Security Execution Model:
  Level 1 (SAFE): Instant execution (navigation, launch, volume, window control, search)
  Level 2 (SENSITIVE): Requires confirmation ("Are you sure?") before execution
                       (file deletion, process termination, network toggle, settings changes)
  Level 3 (RESTRICTED/CRITICAL): High-risk operations (formatting, registry changes, uninstalling)
"""

import time
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("PRIVACY68.SecurityGuard")


class ActionRiskLevel(Enum):
    SAFE = 1        # Execute immediately
    SENSITIVE = 2   # Prompt for voice/UI confirmation
    CRITICAL = 3    # Requires explicit verification


class PendingAction:
    def __init__(self, action_id: str, action_func: Callable, args: tuple, kwargs: dict, description: str, risk_level: ActionRiskLevel):
        self.action_id = action_id
        self.action_func = action_func
        self.args = args
        self.kwargs = kwargs
        self.description = description
        self.risk_level = risk_level
        self.timestamp = time.time()
        self.timeout_seconds = 15.0  # 15 second confirmation window

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.timeout_seconds


class SecurityGuard:
    """
    Manages action permissions, safety allowlists, audit logging,
    and interactive confirmation flows for desktop actions.
    """

    def __init__(self):
        self._pending_action: Optional[PendingAction] = None
        self._audit_log = []
        self._action_risk_rules: Dict[str, ActionRiskLevel] = {
            # Safe Actions (Level 1)
            "open_app": ActionRiskLevel.SAFE,
            "open_settings": ActionRiskLevel.SAFE,
            "window_focus": ActionRiskLevel.SAFE,
            "window_minimize": ActionRiskLevel.SAFE,
            "window_maximize": ActionRiskLevel.SAFE,
            "window_restore": ActionRiskLevel.SAFE,
            "volume_control": ActionRiskLevel.SAFE,
            "screenshot": ActionRiskLevel.SAFE,
            "create_folder": ActionRiskLevel.SAFE,
            "create_file": ActionRiskLevel.SAFE,
            "search_files": ActionRiskLevel.SAFE,
            "read_clipboard": ActionRiskLevel.SAFE,
            "get_system_info": ActionRiskLevel.SAFE,
            "media_control": ActionRiskLevel.SAFE,

            # Sensitive Actions (Level 2)
            "delete_file": ActionRiskLevel.SENSITIVE,
            "delete_folder": ActionRiskLevel.SENSITIVE,
            "empty_recycle_bin": ActionRiskLevel.SENSITIVE,
            "kill_process": ActionRiskLevel.SENSITIVE,
            "force_close_app": ActionRiskLevel.SENSITIVE,
            "network_disconnect": ActionRiskLevel.SENSITIVE,
            "shutdown_pc": ActionRiskLevel.SENSITIVE,
            "restart_pc": ActionRiskLevel.SENSITIVE,
            "modify_startup": ActionRiskLevel.SENSITIVE,
            "clear_clipboard": ActionRiskLevel.SENSITIVE,
            "git_push_force": ActionRiskLevel.SENSITIVE,

            # Critical Actions (Level 3)
            "format_drive": ActionRiskLevel.CRITICAL,
            "modify_registry": ActionRiskLevel.CRITICAL,
            "uninstall_app": ActionRiskLevel.CRITICAL,
            "delete_system_directory": ActionRiskLevel.CRITICAL,
        }

    def get_risk_level(self, action_name: str) -> ActionRiskLevel:
        """Determines the risk classification of a given action."""
        return self._action_risk_rules.get(action_name, ActionRiskLevel.SAFE)

    def request_execution(
        self,
        action_name: str,
        action_func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        description: str = "",
        bypass_confirmation: bool = False,
    ) -> Tuple[bool, str, Optional[Any]]:
        """
        Evaluates the action risk level:
          - If SAFE or bypassed: executes immediately.
          - If SENSITIVE/CRITICAL: queues action and returns a confirmation prompt.
        """
        if kwargs is None:
            kwargs = {}

        risk = self.get_risk_level(action_name)

        if risk == ActionRiskLevel.SAFE or bypass_confirmation:
            try:
                result = action_func(*args, **kwargs)
                self._log_audit(action_name, description, risk, "EXECUTED")
                return True, "Executed successfully", result
            except Exception as e:
                logger.error(f"[SECURITY] Error executing safe action '{action_name}': {e}")
                self._log_audit(action_name, description, risk, f"ERROR: {e}")
                return False, str(e), None

        # Queue for confirmation
        self._pending_action = PendingAction(
            action_id=action_name,
            action_func=action_func,
            args=args,
            kwargs=kwargs,
            description=description or f"Execute '{action_name}'",
            risk_level=risk,
        )

        warning_prefix = "⚠️ Critical Warning:" if risk == ActionRiskLevel.CRITICAL else "⚠️ Sensitive Action:"
        prompt_message = (
            f"{warning_prefix} You requested to {self._pending_action.description}. "
            f"Are you sure? Say 'Yes' or 'Confirm' to proceed, or 'Cancel'."
        )
        logger.info(f"[SECURITY] Queued confirmation for '{action_name}': {self._pending_action.description}")
        return False, prompt_message, {"requires_confirmation": True, "action": action_name}

    def check_has_pending(self) -> bool:
        """Checks if a valid, unexpired confirmation request is waiting."""
        if not self._pending_action:
            return False
        if self._pending_action.is_expired():
            logger.info(f"[SECURITY] Pending action '{self._pending_action.action_id}' timed out.")
            self._pending_action = None
            return False
        return True

    def confirm_pending(self) -> Tuple[bool, str, Optional[Any]]:
        """Executes the currently pending action upon user confirmation."""
        if not self.check_has_pending():
            return False, "No active action is waiting for confirmation.", None

        action = self._pending_action
        self._pending_action = None

        try:
            result = action.action_func(*action.args, **action.kwargs)
            self._log_audit(action.action_id, action.description, action.risk_level, "CONFIRMED_EXECUTED")
            logger.info(f"[SECURITY] Confirmed and executed '{action.action_id}'")
            return True, f"Confirmed: {action.description} executed successfully.", result
        except Exception as e:
            logger.error(f"[SECURITY] Failed executing confirmed action '{action.action_id}': {e}")
            self._log_audit(action.action_id, action.description, action.risk_level, f"CONFIRMED_ERROR: {e}")
            return False, f"Failed executing '{action.action_id}': {e}", None

    def cancel_pending(self) -> str:
        """Cancels the currently pending action."""
        if not self._pending_action:
            return "No action was pending."
        desc = self._pending_action.description
        self._log_audit(self._pending_action.action_id, desc, self._pending_action.risk_level, "CANCELLED_BY_USER")
        self._pending_action = None
        logger.info(f"[SECURITY] Cancelled pending action: {desc}")
        return f"Cancelled: '{desc}' has been aborted."

    def _log_audit(self, action_name: str, description: str, risk: ActionRiskLevel, status: str):
        self._audit_log.append({
            "timestamp": time.time(),
            "action": action_name,
            "description": description,
            "risk_level": risk.name,
            "status": status,
        })
        if len(self._audit_log) > 500:
            self._audit_log.pop(0)


# Global singleton security guard instance
security_guard = SecurityGuard()

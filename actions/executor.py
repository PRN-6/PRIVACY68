"""
PRIVACY68 — the command executor.

This is the pipeline every spoken (or typed, or remote) command travels
through:

    1. INTERCEPTORS — a pending security confirmation is answered, a
       bare greeting is acknowledged. Both consume the utterance.
    2. MACROS — scripted multi-step workflows ("activate coding mode").
    3. THE COMPOUND PLANNER — "mute the volume and open chrome" becomes
       two ordered commands.
    4. THE LANES — Lane 1 (fast, local), Lane 2 (API), Lane 3 (local LLM).

The lanes themselves are driven by the command catalogue
(`actions/catalog.py`); this file only decides which lane gets the
utterance first and what to do with the answer.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from actions.api_lane import api_lane_router
from actions.fast_lane import fast_lane_router
from actions.router import LLMRouter
from actions.skill_manager import manager
from computer_use.macro_engine import macro_engine
from computer_use.security_guard import security_guard
from speech.streamer import autocorrect_speech_command

logger = logging.getLogger("PRIVACY68.ActionExecutor")
llm_router = LLMRouter()

# ─── Vocabulary of the interceptors ─────────────────────────────────────────
STANDALONE_GREETINGS = frozenset({
    "alexa", "nova", "privacy68", "jarvis", "jarvice", "jarves", "friday", "leo", "serena",
    "hey alexa", "hey nova", "hey privacy68", "hey jarvis", "hey jarvice",
    "hi", "hello", "hey", "yes", "okay", "ok", "yeah", "no", "bye", "goodbye",
    "good morning", "good afternoon", "good evening", "good night",
    "thank you", "thanks", "thankyou", "welcome", "sorry", "nice", "cool",
    "great", "awesome", "well done", "good job",
})

SECURITY_CONFIRM_WORDS = frozenset({"yes", "confirm", "proceed", "sure", "do it", "yeah", "ok", "okay"})
SECURITY_CANCEL_WORDS = frozenset({"no", "cancel", "abort", "stop", "don't", "dont", "nevermind", "never mind"})


def _notify(on_status_callback, on_action_callback, tool: str, success: bool, message: str):
    """Uniform notification helper for UI callbacks."""
    if on_status_callback:
        on_status_callback("completed" if success else "error", message)
    if on_action_callback:
        try:
            on_action_callback(tool, success, message)
        except TypeError:
            on_action_callback(tool, success)


def _handle_security_intercept(cleaned: str, low: str) -> Optional[Dict[str, Any]]:
    """Answers a pending security confirmation ('yes' / 'no')."""
    if not security_guard.check_has_pending():
        return None

    if low in SECURITY_CONFIRM_WORDS:
        success, message, details = security_guard.confirm_pending()
        return {
            "success": success,
            "tool": "security_confirmation",
            "method": "security_guard",
            "message": message,
            "details": details,
        }

    if low in SECURITY_CANCEL_WORDS:
        message = security_guard.cancel_pending()
        return {
            "success": True,
            "tool": "security_cancel",
            "method": "security_guard",
            "message": message,
        }

    return None


def _handle_greeting(cleaned: str, low: str) -> Optional[Dict[str, Any]]:
    """Acknowledges a bare greeting without touching the system."""
    if low in STANDALONE_GREETINGS or len(cleaned) <= 2:
        logger.info("Input '%s' is a standalone greeting. No external action required.", cleaned)
        return {
            "success": True,
            "tool": "greeting_ack",
            "method": "none",
            "message": "Listening for command...",
        }
    return None


#: Interceptors run first and may consume the utterance entirely.
_INTERCEPTORS: List[Callable[[str, str], Optional[Dict[str, Any]]]] = [
    _handle_security_intercept,
    _handle_greeting,
]


def _execute_single_clause(clause: str) -> Optional[Dict[str, Any]]:
    """
    Runs one clause through the normal lane path.

    Returns None if the clause was not handled at all.
    """
    fast_result = fast_lane_router.try_execute_fast(clause)
    if fast_result is None:
        fast_result = fast_lane_router.try_execute_plugin_fast(clause)
    if fast_result is not None:
        return {
            "success": fast_result.get("success", False),
            "tool": fast_result.get("tool", "fast_tool"),
            "method": "fast_lane",
            "message": fast_result.get("message", f"Executed '{fast_result.get('tool', 'fast_tool')}' via Fast Lane"),
            "details": fast_result.get("details"),
        }

    api_result = api_lane_router.try_execute_api(clause)
    if api_result is not None:
        return {
            "success": api_result.get("success", False),
            "tool": api_result.get("tool", "api_tool"),
            "method": api_result.get("method", "api_lane"),
            "message": api_result.get("message", f"Executed '{api_result.get('tool', 'api_tool')}' via API Lane"),
            "details": api_result.get("details"),
        }

    plugin_tool = llm_router.route(clause)
    if plugin_tool:
        success = manager.execute_skill(plugin_tool, clause)
        return {
            "success": success,
            "tool": plugin_tool,
            "method": "llm_lane",
            "message": f"Executed '{plugin_tool}' via Local LLM" if success else f"Failed executing '{plugin_tool}'",
        }

    return None


def _execute_compound_command(text: str, on_action_callback=None, on_status_callback=None) -> Optional[Dict[str, Any]]:
    """
    Detects and executes a compound utterance ("mute the volume and open
    chrome") by running each clause in order through the normal lane path.

    Returns None when the utterance is NOT a compound command, so the
    caller continues with single-command handling exactly as before.
    """
    from actions.command_planner import split_compound_command

    clauses = split_compound_command(text)
    if not clauses:
        return None

    logger.info("[COMPOUND] Executing %d clauses: %s", len(clauses), clauses)

    results = []
    pending_confirmation = False
    for clause in clauses:
        result = _execute_single_clause(clause)
        if result is None:
            # One clause failed — report the whole thing as a partial success
            # rather than silently pretending everything worked.
            results.append({
                "success": False,
                "tool": "none",
                "method": "none",
                "message": f"Command not recognized: '{clause}'",
            })
        else:
            results.append(result)
            if result.get("method") == "security_guard":
                # A sensitive action is queued for voice confirmation. The rest
                # of the compound still runs — the sensitive one is gated.
                pending_confirmation = True
        _notify(
            on_status_callback,
            on_action_callback,
            results[-1].get("tool", "none"),
            results[-1].get("success", False),
            results[-1].get("message", ""),
        )

    succeeded = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    summary = " | ".join(r.get("message", "") for r in results if r.get("message"))

    return {
        "success": not failed,
        "tool": "compound_command" if not failed else "compound_command_partial",
        "method": "compound_planner",
        "message": summary,
        "details": {
            "clauses": clauses,
            "results": results,
            "succeeded": len(succeeded),
            "failed": len(failed),
            "awaiting_confirmation": pending_confirmation,
        },
    }


def _run_macro_step(action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Runs one step of a macro workflow as a real command.

    The workflows used to hand the dispatcher a string like
    "open_app vscode", which no command understood, so the macros
    reported success while doing nothing. Each step is now turned into a
    command the assistant can actually run.
    """
    if action == "toast_message":
        # A message for the user, not an action on the machine.
        return {
            "handled": True,
            "tool": "toast",
            "success": True,
            "message": params.get("message", ""),
        }

    command = _macro_step_command(action, params)
    if not command:
        return None

    result = fast_lane_router.try_execute_fast(command)
    if result is None:
        result = fast_lane_router.try_execute_plugin_fast(command)
    return result


def _macro_step_command(action: str, params: Dict[str, Any]) -> Optional[str]:
    """Turns a macro step into a command the assistant understands."""
    if action == "open_app":
        app = params.get("app_name", "").strip()
        return f"open {app}" if app else None
    if action == "open_web":
        target = params.get("query", "").strip()
        return f"open {target}" if target else None
    if action == "show_desktop":
        return "show desktop"
    if action == "set_volume":
        level = params.get("level")
        return f"set volume to {level}" if level is not None else "volume up"
    return None


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Runs one command end to end and reports what happened.

    The command travels through the interceptors, the macro engine, the
    compound planner and the three lanes, in that order.
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    low = cleaned.lower().strip(".!?, ")

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 1 — INTERCEPTORS (security confirmation, greetings)
    # ─────────────────────────────────────────────────────────────────────────
    for interceptor in _INTERCEPTORS:
        outcome = interceptor(cleaned, low)
        if outcome is None:
            continue
        if outcome.get("tool") == "greeting_ack":
            return outcome
        _notify(
            on_status_callback,
            on_action_callback,
            outcome.get("tool", "interceptor"),
            outcome.get("success", True),
            outcome.get("message", ""),
        )
        return outcome

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 2 — MACRO WORKFLOWS
    # ─────────────────────────────────────────────────────────────────────────
    step_messages: List[tuple] = []

    def _macro_executor(action: str, params: Dict[str, Any]):
        result = _run_macro_step(action, params)
        if result and result.get("message"):
            step_messages.append((action, result))
        return result

    macro_res = macro_engine.match_and_execute(cleaned, _macro_executor)
    if macro_res is not None:
        # Surface the individual step messages (the toasts) before the
        # workflow summary.
        for action, result in step_messages:
            _notify(on_status_callback, on_action_callback,
                    result.get("tool", action), result.get("success", True),
                    result.get("message", ""))
        message = macro_res.get("message", "Workflow executed")
        _notify(on_status_callback, on_action_callback,
                macro_res.get("workflow", "macro"), True, message)
        return {
            "success": True,
            "tool": "macro_workflow",
            "method": "macro_engine",
            "message": message,
            "details": macro_res,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 3 — THE COMPOUND COMMAND PLANNER
    # "mute the volume and open chrome" -> runs BOTH actions, in order.
    # ─────────────────────────────────────────────────────────────────────────
    compound_res = _execute_compound_command(cleaned, on_action_callback, on_status_callback)
    if compound_res is not None:
        return compound_res

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 4 — LANE 1: THE FAST LANE
    # Deterministic OS tools & plugin fast intents. 100% local, <5ms.
    # ─────────────────────────────────────────────────────────────────────────
    fast_result = fast_lane_router.try_execute_fast(cleaned)
    if fast_result is None:
        # Plugin fast intents (Chrome tabs, GitHub shortcuts, app controls)
        fast_result = fast_lane_router.try_execute_plugin_fast(cleaned)

    if fast_result is not None:
        success = fast_result.get("success", False)
        tool_name = fast_result.get("tool", "fast_tool")
        message = fast_result.get("message", f"Executed '{tool_name}' via Fast Lane")
        _notify(on_status_callback, on_action_callback, tool_name, success, message)
        return {
            "success": success,
            "tool": tool_name,
            "method": "fast_lane",
            "message": message,
            "details": fast_result.get("details"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 5 — LANE 2: THE API LANE
    # Direct app/web APIs & the cloud LLM semantic router.
    # ─────────────────────────────────────────────────────────────────────────
    api_result = api_lane_router.try_execute_api(cleaned)
    if api_result is not None:
        success = api_result.get("success", False)
        tool_name = api_result.get("tool", "api_tool")
        message = api_result.get("message", f"Executed '{tool_name}' via API Lane")
        _notify(on_status_callback, on_action_callback, tool_name, success, message)
        return {
            "success": success,
            "tool": tool_name,
            "method": api_result.get("method", "api_lane"),
            "message": message,
            "details": api_result.get("details"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 6 — LANE 3: THE LOCAL LLM LANE
    # Optional, air-gapped, chosen by the user.
    # ─────────────────────────────────────────────────────────────────────────
    plugin_tool = llm_router.route(cleaned)
    if plugin_tool:
        logger.info("[LOCAL LLM ROUTER] Command matched plugin: %s", plugin_tool)
        success = manager.execute_skill(plugin_tool, cleaned)
        plugin_message = (f"Executed '{plugin_tool}' via Local LLM" if success
                          else f"Failed executing '{plugin_tool}'")
        _notify(on_status_callback, on_action_callback, plugin_tool, success, plugin_message)
        return {
            "success": success,
            "tool": plugin_tool,
            "method": "llm_lane",
            "message": plugin_message,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # NOT RECOGNISED
    # ─────────────────────────────────────────────────────────────────────────
    message = f"Command not recognized: '{cleaned}'"
    logger.info("[ROUTER] %s", message)
    _notify(on_status_callback, on_action_callback, "unknown", False, message)
    return {
        "success": False,
        "tool": "none",
        "method": "none",
        "message": message,
    }


def execute_system_command(text: str, on_action_callback=None, on_status_callback=None) -> bool:
    """Sends user text to the command pipeline. Returns True if successful."""
    result = execute_system_command_detailed(
        text,
        on_action_callback=on_action_callback,
        on_status_callback=on_status_callback
    )
    return result.get("success", False)

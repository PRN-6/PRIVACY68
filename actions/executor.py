import logging
from actions.skill_manager import manager
from actions.router import LLMRouter
from actions.fast_lane import fast_lane_router
from speech.streamer import autocorrect_speech_command

logger = logging.getLogger("PRIVACY68.ActionExecutor")
llm_router = LLMRouter()


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Two-Lane Command Architecture:
    1. Fast Lane — Regex deterministic tools -> instant execution (<5ms, zero LLM)
       Handles: app launches, window navigation, command prompt, web search, settings, file/folder ops, system volume/lock.
    2. LLM Lane — Ollama tool-calling -> intelligent plugin execution (WhatsApp, Chrome, VS Code, etc.)
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    # Standalone wake words or greetings — no action needed
    STANDALONE_WAKE_WORDS = {
        "alexa", "nova", "privacy68", "jarvis", "friday", "leo", "serena",
        "hey alexa", "hey nova", "hey privacy68", "hey jarvis",
        "hi", "hello", "hey", "yes", "okay", "ok", "yeah", "no", "bye", "goodbye",
        "good morning", "good afternoon", "good evening", "good night",
        "thank you", "thanks", "thankyou", "welcome", "sorry", "nice", "cool",
        "great", "awesome", "well done", "good job",
    }
    if cleaned.lower().strip(".!?, ") in STANDALONE_WAKE_WORDS or len(cleaned) <= 2:
        logger.info(f"Input '{cleaned}' is a standalone wake greeting. No external action required.")
        return {"success": True, "tool": "greeting_ack", "method": "none", "message": "Listening for command..."}

    # ─────────────────────────────────────────────────────────────────────────
    # LANE 1: FAST LANE (Deterministic OS Tools & Navigation — Instant)
    # ─────────────────────────────────────────────────────────────────────────
    fast_result = fast_lane_router.try_execute_fast(cleaned)
    if fast_result is not None:
        success = fast_result.get("success", False)
        tool_name = fast_result.get("tool", "fast_tool")
        message = fast_result.get("message", f"Executed '{tool_name}' via Fast Lane")
        if on_status_callback:
            status_type = "completed" if success else "error"
            on_status_callback(status_type, message)
        if on_action_callback:
            try:
                on_action_callback(tool_name, success, message)
            except TypeError:
                on_action_callback(tool_name, success)
        return {
            "success": success,
            "tool": tool_name,
            "method": "fast_lane",
            "message": message,
            "details": fast_result.get("details"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LANE 2: LLM LANE (Ollama Tool-Calling for Plugin Actions)
    # ─────────────────────────────────────────────────────────────────────────
    plugin_tool = llm_router.route(cleaned)
    if plugin_tool:
        logger.info(f"[LLM ROUTER] Command matched plugin: {plugin_tool}")
        success = manager.execute_skill(plugin_tool, cleaned)
        plugin_message = f"Executed '{plugin_tool}' via LLM" if success else f"Failed executing '{plugin_tool}'"
        if on_status_callback:
            status_type = "completed" if success else "error"
            on_status_callback(status_type, plugin_message)
        if on_action_callback:
            try:
                on_action_callback(plugin_tool, success, plugin_message)
            except TypeError:
                on_action_callback(plugin_tool, success)
        return {
            "success": success,
            "tool": plugin_tool,
            "method": "llm_lane",
            "message": plugin_message,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # UNRECOGNIZED COMMAND
    # ─────────────────────────────────────────────────────────────────────────
    msg = f"Command not recognized: '{cleaned}'"
    logger.info(f"[ROUTER] {msg}")
    if on_status_callback:
        on_status_callback("error", msg)
    if on_action_callback:
        try:
            on_action_callback("unknown", False, msg)
        except TypeError:
            on_action_callback("unknown", False)

    return {
        "success": False,
        "tool": "none",
        "method": "none",
        "message": msg,
    }


def execute_system_command(text: str, on_action_callback=None, on_status_callback=None) -> bool:
    """Sends user text to the command pipeline. Returns True if successful."""
    result = execute_system_command_detailed(
        text,
        on_action_callback=on_action_callback,
        on_status_callback=on_status_callback
    )
    return result.get("success", False)
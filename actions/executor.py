import logging
from speech.streamer import autocorrect_speech_command
from computer_use.security_guard import security_guard

logger = logging.getLogger("PRIVACY68.ActionExecutor")

# Security words for confirmation
SECURITY_CONFIRM_WORDS = frozenset({"yes", "confirm", "proceed", "sure", "do it", "yeah", "ok", "okay"})
SECURITY_CANCEL_WORDS = frozenset({"no", "cancel", "abort", "stop", "don't", "dont", "nevermind", "never mind"})
GREETINGS = frozenset({
    "hi",
    "hello",
    "hey",
    "hi there",
    "hello there",
    "hey there",
    "good morning",
    "good afternoon",
    "good evening",
})

def _notify(on_status_callback, on_action_callback, tool: str, success: bool, message: str):
    """Uniform notification helper for UI callbacks."""
    if on_status_callback:
        on_status_callback("completed" if success else "error", message)
    if on_action_callback:
        try:
            on_action_callback(tool, success, message)
        except TypeError:
            on_action_callback(tool, success)

def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    ULTRA-LEAN AGENTIC ARCHITECTURE
    Everything is handled by the Agent Brain (LLM-driven code execution).
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    low = cleaned.lower().strip(".!?, ")

    # 1. Security Guard Intercept
    if security_guard.check_has_pending():
        if low in SECURITY_CONFIRM_WORDS:
            success, msg, res = security_guard.confirm_pending()
            _notify(on_status_callback, on_action_callback, "security_confirmation", success, msg)
            return {"success": success, "tool": "security_confirmation", "method": "security_guard", "message": msg, "details": res}
        if low in SECURITY_CANCEL_WORDS:
            msg = security_guard.cancel_pending()
            _notify(on_status_callback, on_action_callback, "security_cancel", True, msg)
            return {"success": True, "tool": "security_cancel", "method": "security_guard", "message": msg}

    # 2. GREETINGS (Fast bypass)
    if low in GREETINGS:
        return {"success": True, "tool": "greeting", "method": "none", "message": "I'm listening. How can I help you with your computer today?"}

    # 3. THE BRAIN (Everything else goes here)
    # The Agent Brain handles apps, files, web, and system tools via generated code.
    from actions.agent_brain import agent_brain
    result = agent_brain.generate_and_execute(cleaned)

    if result and result.get("success"):
        _notify(on_status_callback, on_action_callback, "agent_brain", True, result["message"])
        return result

    # 4. FAILSAFE
    msg = f"I couldn't figure out how to do that: '{cleaned}'"
    _notify(on_status_callback, on_action_callback, "unknown", False, msg)
    return {"success": False, "tool": "none", "method": "none", "message": msg}

def execute_system_command(text: str, on_action_callback=None, on_status_callback=None) -> bool:
    result = execute_system_command_detailed(text, on_action_callback, on_status_callback)
    return result.get("success", False)

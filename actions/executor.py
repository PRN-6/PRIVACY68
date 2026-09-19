import logging
import ollama
from actions.skill_manager import manager
from actions.router import SemanticRouter
from speech.streamer import autocorrect_speech_command
from plugins.profile_manager import profile_manager

from actions.hermes_agent import hermes_agent

logger = logging.getLogger("PRIVACY68.ActionExecutor")
fast_router = SemanticRouter()

def get_active_llm_model() -> str:
    """Returns the user-selected Ollama model from profile settings."""
    return profile_manager.get("llm_model", "qwen2.5:0.5b")

def preload_ai_model():
    model_name = get_active_llm_model()
    logger.info(f"preloading ai model ({model_name})")
    try:
        ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': 'ping'}],
            keep_alive="60s",
            options={
                'num_ctx': 512
            }
        )
        logger.info(f"ai model ({model_name}) preloaded successfully")
    except Exception as e:
        logger.warning(f"could not preload ai model ({model_name}): {e}")

def _web_search_fallback(text: str, on_action_callback = None) -> dict:
    """Searches the web for ANY words that no other tool handled."""
    logger.info(f"Catch-all web search: '{text}'")
    success = manager.execute_skill("web_search", text)
    if on_action_callback:
        on_action_callback("web_search", success)
    return {
        "success": success,
        "tool": "web_search",
        "method": "fallback_web_search",
        "message": f"Searched the web for '{text}'" if success else f"Failed to search the web for '{text}'"
    }

def execute_system_command_detailed(text: str, on_action_callback = None) -> dict:
    """
    Executes a command via Fast Lane Semantic Router or Hermes Agent Lane.
    Returns a dict: {"success": bool, "tool": str, "method": str, "message": str}
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    # Ignore standalone wake words or greetings (never search them in Chrome)
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

    # 1. Fast Lane (Instant Execution for standard phrases)
    fast_tool = fast_router.route(cleaned)
    if fast_tool:
        success = manager.execute_skill(fast_tool, cleaned)
        if on_action_callback:
            on_action_callback(fast_tool, success)
        return {
            "success": success,
            "tool": fast_tool,
            "method": "fast_lane",
            "message": f"Executed '{fast_tool}' via Fast Lane" if success else f"Failed executing '{fast_tool}'"
        }

    # 2. Smart Lane (Hermes Agent / Structured Tool Calling)
    logger.info(f"Command '{cleaned}' is complex. Routing to Hermes Agent...")
    active_model = get_active_llm_model()
    result = hermes_agent.run(cleaned, model_name=active_model)
    
    if on_action_callback:
        on_action_callback(result.get("tool", "web_search"), result.get("success", False))
    return result

def execute_system_command(text: str, on_action_callback = None) -> bool:
    """
    Sends user text to the router/skill manager. Returns True if successful.
    """
    result = execute_system_command_detailed(text, on_action_callback=on_action_callback)
    return result["success"]
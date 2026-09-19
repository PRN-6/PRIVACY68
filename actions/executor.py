import logging
import ollama
from actions.skill_manager import manager
from actions.router import SemanticRouter
from speech.streamer import autocorrect_speech_command
from plugins.profile_manager import profile_manager

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
    Executes a command via Fast Lane Semantic Router or Ollama AI Fallback.
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

    # 1. Fast Lane (Instant Execution)
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

    # 2. Slow AI Lane (Fallback)
    logger.info(f"Command '{cleaned}' is complex. Sending to Ollama AI...")
    
    # Dynamically generate the system prompt based on active skills!
    available_tools = manager.get_system_prompt_descriptions()
    
    system_prompt = (
        "You are the brain of PRIVACY68, a desktop assistant.\n"
        "You must select the most appropriate tool to run based on the user's request.\n"
        "Available tools:\n"
        f"{available_tools}\n\n"
        "If none of the tools match, return the word: None\n"
        "Otherwise, return ONLY the exact name of the tool. Do not include any punctuation, quotes, or extra text."
    )

    try:
        active_model = get_active_llm_model()
        logger.info(f"Querying local model: '{active_model}'")
        response = ollama.chat(
            model=active_model,
            keep_alive="60s",
            options={
                'temperature': 0.2,
                'top_p': 0.9,
                'top_k': 40,
                'num_ctx': 512
            },
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': cleaned}
            ]
        )

        selected_tool = response['message']['content'].strip()
        logger.info(f"AI Selected: '{selected_tool}' for input: '{cleaned}'")

        if selected_tool != "None":
            success = manager.execute_skill(selected_tool, cleaned)
            if on_action_callback:
                on_action_callback(selected_tool, success)
            return {
                "success": success,
                "tool": selected_tool,
                "method": "ai_lane",
                "message": f"Executed '{selected_tool}' via AI Lane" if success else f"Failed executing '{selected_tool}'"
            }
        # AI matched no tool (or returned None) -> search the web with any words
        logger.info(f"AI matched no tool. Falling back to web search for '{cleaned}'.")
        return _web_search_fallback(cleaned, on_action_callback)

    except Exception as e:
        logger.error(f"Error communicating with local ai: {e}")
        # AI unavailable -> don't leave the user hanging, search the web instead
        logger.info(f"AI unavailable. Falling back to web search for '{cleaned}'.")
        return _web_search_fallback(cleaned, on_action_callback)

def execute_system_command(text: str, on_action_callback = None) -> bool:
    """
    Sends user text to the router/skill manager. Returns True if successful.
    """
    result = execute_system_command_detailed(text, on_action_callback=on_action_callback)
    return result["success"]
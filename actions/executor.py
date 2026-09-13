import logging
import ollama
from actions.skill_manager import manager
from actions.router import SemanticRouter
from speech.streamer import autocorrect_speech_command

logger = logging.getLogger("PRIVACY68.ActionExecutor")
fast_router = SemanticRouter()

def preload_ai_model():
    logger.info("preloading ai model")
    try:
        ollama.chat(
            model='qwen2.5:0.5b',
            messages=[{'role': 'user', 'content': 'ping'}],
            keep_alive="60s",
            options={
                'num_ctx': 512
            }
        )
        logger.info("ai model preloaded successfully")
    except Exception as e:
        logger.warning(f"could not preload ai model: {e}")

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
        "hey alexa", "hey nova", "hey privacy68", "hey jarvis", "hi", "hello", "yes", "okay", "yeah"
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
        response = ollama.chat(
            model='qwen2.5:0.5b',
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
        else:
            if on_action_callback:
                on_action_callback("Unknown", False)
            return {
                "success": False,
                "tool": "Unknown",
                "method": "ai_lane",
                "message": "No matching tool found for command"
            }
        
    except Exception as e:
        logger.error(f"Error communicating with local ai: {e}")
        if on_action_callback:
            on_action_callback("Error", False)
        return {
            "success": False,
            "tool": "Error",
            "method": "error",
            "message": str(e)
        }

def execute_system_command(text: str, on_action_callback = None) -> bool:
    """
    Sends user text to the router/skill manager. Returns True if successful.
    """
    result = execute_system_command_detailed(text, on_action_callback=on_action_callback)
    return result["success"]
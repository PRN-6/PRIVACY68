import logging
from actions.skill_manager import manager
from actions.router import LLMRouter
from actions.fast_lane import fast_lane_router
from actions.api_lane import api_lane_router
from speech.streamer import autocorrect_speech_command
from computer_use.security_guard import security_guard
from computer_use.context_inspector import context_inspector
from computer_use.dev_tools import dev_tools
from computer_use.macro_engine import macro_engine
from computer_use.input_controller import input_controller

logger = logging.getLogger("PRIVACY68.ActionExecutor")
llm_router = LLMRouter()


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


def _handle_system_shortcuts(low: str) -> dict | None:
    """Handles context diagnostics, developer tools, and input controller shortcuts."""
    # RAM Usage
    if any(q in low for q in ("what is using my ram", "what's using my ram", "ram usage", "memory usage", "who is using ram")):
        info = context_inspector.get_top_resource_consumers(count=3)
        top_str = ", ".join(f"{p['name']} ({p['ram_mb']} MB)" for p in info.get("top_ram", []))
        return {"success": True, "tool": "context_inspector", "message": f"Top RAM consumers: {top_str}", "details": info}

    # CPU Usage
    if any(q in low for q in ("what is using my cpu", "what's using my cpu", "cpu usage", "who is using cpu")):
        info = context_inspector.get_top_resource_consumers(count=3)
        top_str = ", ".join(f"{p['name']} ({p['cpu']}%)" for p in info.get("top_cpu", []) if p.get("cpu"))
        msg = f"Top CPU consumers: {top_str}" if top_str else "CPU usage is low across active processes."
        return {"success": True, "tool": "context_inspector", "message": msg, "details": info}

    # Battery
    if any(q in low for q in ("battery status", "battery percentage", "check battery", "power status")):
        b_info = context_inspector.get_battery_and_power_info()
        return {"success": True, "tool": "context_inspector", "message": b_info.get("message", "Battery information retrieved."), "details": b_info}

    # Clipboard Reader
    if any(q in low for q in ("read my clipboard", "read clipboard", "what is on my clipboard", "what's on my clipboard")):
        clip_text = context_inspector.get_clipboard_text()
        msg = f"Clipboard content: '{clip_text[:120]}...'" if len(clip_text) > 120 else (f"Clipboard content: '{clip_text}'" if clip_text else "Clipboard is currently empty.")
        return {"success": True, "tool": "clipboard_reader", "message": msg, "details": {"clipboard": clip_text}}

    # Developer Tools: Git
    if low in {"git status", "check git status", "check git"}:
        return {"success": True, "tool": "dev_tools_git_status", "message": dev_tools.git_status()}

    if any(q in low for q in ("git branch", "what branch", "current branch", "check branch")):
        return {"success": True, "tool": "dev_tools_git_branch", "message": dev_tools.git_branch()}

    if low in {"git pull", "pull latest changes", "pull repo", "pull from github"}:
        return {"success": True, "tool": "dev_tools_git_pull", "message": dev_tools.git_pull()}

    if any(q in low for q in (
        "push my current project changes to github",
        "git push my current project changes to github",
        "git push my changes to github",
        "push changes to github",
        "push my code to github",
        "commit and push my changes to github",
        "commit and push my changes",
        "commit and push",
        "git commit and push",
        "push my code",
        "push code to github",
        "push to my repo",
        "push to repo",
        "push to github",
        "git push",
        "push changes",
        "push current project",
        "push project",
    )):
        res = dev_tools.smart_git_push_workflow()
        return {"success": res.get("success", False), "tool": "dev_tools_smart_git_push", "message": res.get("message", "Pushed changes to GitHub.")}

    if low in {"git commit", "commit my code", "commit changes"}:
        c_res = dev_tools.git_commit("Committed via Privacy68 voice command")
        msg = "Committed changes to repository." if c_res.get("success") else f"Commit failed: {c_res.get('output', '')}"
        return {"success": c_res.get("success", False), "tool": "dev_tools_git_commit", "message": msg}

    # Developer Tools: VS Code
    if any(q in low for q in ("open project in vs code", "open in vs code", "open in vscode", "open project in vscode")):
        res = dev_tools.open_in_vscode()
        return {"success": res.get("success", False), "tool": "dev_tools_vscode", "message": res.get("message", "Opened VS Code.")}

    # Keyboard & System Input Shortcuts
    input_shortcuts = {
        ("copy this", "copy", "copy text"): ("input_copy", input_controller.copy, "Copied to clipboard."),
        ("paste this", "paste", "paste text"): ("input_paste", input_controller.paste, "Pasted."),
        ("select all", "select all text"): ("input_select_all", input_controller.select_all, "Selected all."),
        ("show desktop", "minimize all", "minimize all windows"): ("input_show_desktop", input_controller.show_desktop, "Showing desktop."),
        ("open task manager", "task manager", "open task view"): ("input_task_manager", input_controller.open_task_manager, "Opened Task Manager."),
        ("switch window", "alt tab", "switch application"): ("input_switch_window", input_controller.switch_window_alt_tab, "Switched window."),
    }
    for triggers, (tool_name, func, msg) in input_shortcuts.items():
        if low in triggers:
            func()
            return {"success": True, "tool": tool_name, "message": msg}

    return None


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Three-Lane Command Architecture with 3-Tier Security Model:
    1. Security Guard Confirmation Intercept (Yes/Confirm or Cancel)
    2. Compound Workflows & Macros (Coding mode, Focus mode, Meeting mode)
    3. Context, Dev & System Shortcuts (RAM/CPU, Git, clipboard, input controls)
    4. LANE 1: Fast Lane (Highest Priority) — Deterministic OS tools & Plugin Fast Intents (<5ms, zero LLM)
    5. LANE 2: API Lane (High Priority) — Direct App/Web APIs & Cloud LLM Semantic Router (Runs on ANY PC)
    6. LANE 3: Local LLM Lane (Optional / Opt-in) — Local Ollama air-gapped model (User's choice)
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    low = cleaned.lower().strip(".!?, ")

    # ─────────────────────────────────────────────────────────────────────────
    # 0A. SECURITY CONFIRMATION INTERCEPT (Level 2/3 Sensitive Actions)
    # ─────────────────────────────────────────────────────────────────────────
    if security_guard.check_has_pending():
        if low in SECURITY_CONFIRM_WORDS:
            success, msg, res = security_guard.confirm_pending()
            _notify(on_status_callback, on_action_callback, "security_confirmation", success, msg)
            return {"success": success, "tool": "security_confirmation", "method": "security_guard", "message": msg, "details": res}

        if low in SECURITY_CANCEL_WORDS:
            msg = security_guard.cancel_pending()
            _notify(on_status_callback, on_action_callback, "security_cancel", True, msg)
            return {"success": True, "tool": "security_cancel", "method": "security_guard", "message": msg}

    # ─────────────────────────────────────────────────────────────────────────
    # 0B. STANDALONE WAKE WORDS OR GREETINGS (Instant Ack — No External Action)
    # ─────────────────────────────────────────────────────────────────────────
    if low in STANDALONE_GREETINGS or len(cleaned) <= 2:
        logger.info(f"Input '{cleaned}' is a standalone wake greeting. No external action required.")
        return {"success": True, "tool": "greeting_ack", "method": "none", "message": "Listening for command..."}

    # ─────────────────────────────────────────────────────────────────────────
    # 0C. COMPOUND WORKFLOWS & MACROS
    # ─────────────────────────────────────────────────────────────────────────
    macro_res = macro_engine.match_and_execute(
        cleaned,
        lambda act, params: fast_lane_router.try_execute_fast(f"{act} {params.get('app_name', '')} {params.get('query', '')}")
    )
    if macro_res is not None:
        msg = macro_res.get("message", "Workflow executed")
        _notify(on_status_callback, on_action_callback, macro_res.get("workflow", "macro"), True, msg)
        return {"success": True, "tool": "macro_workflow", "method": "macro_engine", "message": msg, "details": macro_res}

    # ─────────────────────────────────────────────────────────────────────────
    # 0D. CONTEXT, DEV TOOLS & INPUT SHORTCUTS
    # ─────────────────────────────────────────────────────────────────────────
    shortcut_res = _handle_system_shortcuts(low)
    if shortcut_res is not None:
        success = shortcut_res.get("success", True)
        tool_name = shortcut_res.get("tool", "system_shortcut")
        message = shortcut_res.get("message", "")
        _notify(on_status_callback, on_action_callback, tool_name, success, message)
        return {
            "success": success,
            "tool": tool_name,
            "method": "fast_lane",
            "message": message,
            "details": shortcut_res.get("details"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LANE 1: FAST LANE (Deterministic OS Tools + Plugin Fast Intents — Instant)
    # Highest Priority! Runs 100% locally on ALL computers (<5ms, zero AI).
    # ─────────────────────────────────────────────────────────────────────────
    fast_result = fast_lane_router.try_execute_fast(cleaned)
    if fast_result is None:
        # Check plugin fast intents (Chrome tabs, GitHub shortcuts, app controls)
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
    # LANE 2: API LANE (Direct Application/Web APIs + Cloud LLM Semantic Router)
    # High Priority! Ultra-fast, zero RAM/GPU required, runs on ALL computers.
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
            "method": "api_lane",
            "message": message,
            "details": api_result.get("details"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LANE 3: LOCAL LLM LANE (Air-Gapped Local Model — Optional / User Choice)
    # Optional! The user decides whether to run local Ollama models.
    # ─────────────────────────────────────────────────────────────────────────
    plugin_tool = llm_router.route(cleaned)
    if plugin_tool:
        logger.info(f"[LOCAL LLM ROUTER] Command matched plugin: {plugin_tool}")
        success = manager.execute_skill(plugin_tool, cleaned)
        plugin_message = f"Executed '{plugin_tool}' via Local LLM" if success else f"Failed executing '{plugin_tool}'"
        _notify(on_status_callback, on_action_callback, plugin_tool, success, plugin_message)
        return {
            "success": success,
            "tool": plugin_tool,
            "method": "llm_lane",
            "message": plugin_message,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # UNRECOGNIZED COMMAND (Graceful guidance for any computer)
    # ─────────────────────────────────────────────────────────────────────────
    msg = f"Command not recognized: '{cleaned}'"
    logger.info(f"[ROUTER] {msg}")
    _notify(on_status_callback, on_action_callback, "unknown", False, msg)
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
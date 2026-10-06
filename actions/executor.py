import logging
from actions.skill_manager import manager
from actions.router import LLMRouter
from actions.fast_lane import fast_lane_router
from speech.streamer import autocorrect_speech_command
from computer_use.security_guard import security_guard, ActionRiskLevel
from computer_use.context_inspector import context_inspector
from computer_use.dev_tools import dev_tools
from computer_use.macro_engine import macro_engine
from computer_use.input_controller import input_controller

logger = logging.getLogger("PRIVACY68.ActionExecutor")
llm_router = LLMRouter()


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Two-Lane Command Architecture with 3-Tier Security Model:
    1. Security Guard Confirmation Intercept (Yes/Confirm or Cancel)
    2. Compound Workflows & Macros (Coding mode, Focus mode, Meeting mode)
    3. Context & Diagnostic Queries (RAM/CPU usage, battery, clipboard)
    4. Developer Tools (Git, VS Code)
    5. Fast Lane — Regex deterministic tools & input controller -> instant execution (<5ms, zero LLM)
    6. LLM Lane — Ollama tool-calling -> intelligent plugin execution (WhatsApp, Chrome, etc.)
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    low = cleaned.lower().strip(".!?, ")

    # ─────────────────────────────────────────────────────────────────────────
    # 0. SECURITY CONFIRMATION INTERCEPT (Level 2/3 Sensitive Actions)
    # ─────────────────────────────────────────────────────────────────────────
    if security_guard.check_has_pending():
        if low in {"yes", "confirm", "proceed", "sure", "do it", "yeah", "ok", "okay"}:
            success, msg, res = security_guard.confirm_pending()
            if on_status_callback:
                on_status_callback("completed" if success else "error", msg)
            if on_action_callback:
                on_action_callback("security_confirmation", success, msg)
            return {"success": success, "tool": "security_confirmation", "method": "security_guard", "message": msg, "details": res}

        if low in {"no", "cancel", "abort", "stop", "don't", "dont", "nevermind", "never mind"}:
            msg = security_guard.cancel_pending()
            if on_status_callback:
                on_status_callback("completed", msg)
            if on_action_callback:
                on_action_callback("security_cancel", True, msg)
            return {"success": True, "tool": "security_cancel", "method": "security_guard", "message": msg}

    # Standalone wake words or greetings — no action needed
    STANDALONE_WAKE_WORDS = {
        "alexa", "nova", "privacy68", "jarvis", "friday", "leo", "serena",
        "hey alexa", "hey nova", "hey privacy68", "hey jarvis",
        "hi", "hello", "hey", "yes", "okay", "ok", "yeah", "no", "bye", "goodbye",
        "good morning", "good afternoon", "good evening", "good night",
        "thank you", "thanks", "thankyou", "welcome", "sorry", "nice", "cool",
        "great", "awesome", "well done", "good job",
    }
    if low in STANDALONE_WAKE_WORDS or len(cleaned) <= 2:
        logger.info(f"Input '{cleaned}' is a standalone wake greeting. No external action required.")
        return {"success": True, "tool": "greeting_ack", "method": "none", "message": "Listening for command..."}

    # ─────────────────────────────────────────────────────────────────────────
    # 0B. COMPOUND WORKFLOWS & MACROS
    # ─────────────────────────────────────────────────────────────────────────
    macro_res = macro_engine.match_and_execute(cleaned, lambda act, params: fast_lane_router.try_execute_fast(f"{act} {params.get('app_name', '')} {params.get('query', '')}"))
    if macro_res is not None:
        msg = macro_res.get("message", "Workflow executed")
        if on_status_callback:
            on_status_callback("completed", msg)
        if on_action_callback:
            on_action_callback(macro_res.get("workflow", "macro"), True, msg)
        return {"success": True, "tool": "macro_workflow", "method": "macro_engine", "message": msg, "details": macro_res}

    # ─────────────────────────────────────────────────────────────────────────
    # 0C. CONTEXT & SYSTEM DIAGNOSTICS (RAM, CPU, Battery, Clipboard)
    # ─────────────────────────────────────────────────────────────────────────
    if any(q in low for q in ["what is using my ram", "what's using my ram", "ram usage", "memory usage", "who is using ram"]):
        info = context_inspector.get_top_resource_consumers(count=3)
        top_str = ", ".join([f"{p['name']} ({p['ram_mb']} MB)" for p in info['top_ram']])
        msg = f"Top RAM consumers: {top_str}"
        if on_status_callback:
            on_status_callback("completed", msg)
        return {"success": True, "tool": "context_inspector", "method": "fast_lane", "message": msg, "details": info}

    if any(q in low for q in ["what is using my cpu", "what's using my cpu", "cpu usage", "who is using cpu"]):
        info = context_inspector.get_top_resource_consumers(count=3)
        top_str = ", ".join([f"{p['name']} ({p['cpu']}%)" for p in info['top_cpu'] if p['cpu']])
        msg = f"Top CPU consumers: {top_str}" if top_str else "CPU usage is low across active processes."
        if on_status_callback:
            on_status_callback("completed", msg)
        return {"success": True, "tool": "context_inspector", "method": "fast_lane", "message": msg, "details": info}

    if any(q in low for q in ["battery status", "battery percentage", "check battery", "power status"]):
        b_info = context_inspector.get_battery_and_power_info()
        msg = b_info.get("message", "Battery information retrieved.")
        if on_status_callback:
            on_status_callback("completed", msg)
        return {"success": True, "tool": "context_inspector", "method": "fast_lane", "message": msg, "details": b_info}

    if any(q in low for q in ["read my clipboard", "read clipboard", "what is on my clipboard", "what's on my clipboard"]):
        clip_text = context_inspector.get_clipboard_text()
        msg = f"Clipboard content: '{clip_text[:120]}...'" if len(clip_text) > 120 else (f"Clipboard content: '{clip_text}'" if clip_text else "Clipboard is currently empty.")
        if on_status_callback:
            on_status_callback("completed", msg)
        return {"success": True, "tool": "clipboard_reader", "method": "fast_lane", "message": msg, "details": {"clipboard": clip_text}}

    # ─────────────────────────────────────────────────────────────────────────
    # 0D. DEVELOPER WORKFLOWS (Git, VS Code)
    # ─────────────────────────────────────────────────────────────────────────
    if low in ["git status", "check git status", "check git"]:
        status_msg = dev_tools.git_status()
        if on_status_callback:
            on_status_callback("completed", status_msg)
        return {"success": True, "tool": "dev_tools_git_status", "method": "fast_lane", "message": status_msg}

    if any(q in low for q in ["git branch", "what branch", "current branch", "check branch"]):
        branch_msg = dev_tools.git_branch()
        if on_status_callback:
            on_status_callback("completed", branch_msg)
        return {"success": True, "tool": "dev_tools_git_branch", "method": "fast_lane", "message": branch_msg}

    if low in ["git pull", "pull latest changes", "pull repo", "pull from github"]:
        pull_msg = dev_tools.git_pull()
        if on_status_callback:
            on_status_callback("completed", pull_msg)
        return {"success": True, "tool": "dev_tools_git_pull", "method": "fast_lane", "message": pull_msg}

    if any(q in low for q in ["push my code", "push code", "push to my repo", "push to repo", "push to github", "git push", "push changes"]):
        push_msg = dev_tools.git_push_workflow(commit_message="Updated via Privacy68 voice assistant")
        if on_status_callback:
            on_status_callback("completed", push_msg)
        return {"success": True, "tool": "dev_tools_git_push", "method": "fast_lane", "message": push_msg}

    if low in ["git commit", "commit my code", "commit changes"]:
        c_res = dev_tools.git_commit("Committed via Privacy68 voice command")
        msg = "Committed changes to repository." if c_res["success"] else f"Commit failed: {c_res.get('output', '')}"
        if on_status_callback:
            on_status_callback("completed" if c_res["success"] else "error", msg)
        return {"success": c_res["success"], "tool": "dev_tools_git_commit", "method": "fast_lane", "message": msg}

    if any(q in low for q in ["open project in vs code", "open in vs code", "open in vscode", "open project in vscode"]):
        res = dev_tools.open_in_vscode()
        msg = res.get("message", "Opened VS Code.")
        if on_status_callback:
            on_status_callback("completed" if res["success"] else "error", msg)
        return {"success": res["success"], "tool": "dev_tools_vscode", "method": "fast_lane", "message": msg}

    # ─────────────────────────────────────────────────────────────────────────
    # 0E. KEYBOARD & INPUT SHORTCUTS
    # ─────────────────────────────────────────────────────────────────────────
    if low in ["copy this", "copy", "copy text"]:
        input_controller.copy()
        return {"success": True, "tool": "input_copy", "method": "fast_lane", "message": "Copied to clipboard."}

    if low in ["paste this", "paste", "paste text"]:
        input_controller.paste()
        return {"success": True, "tool": "input_paste", "method": "fast_lane", "message": "Pasted."}

    if low in ["select all", "select all text"]:
        input_controller.select_all()
        return {"success": True, "tool": "input_select_all", "method": "fast_lane", "message": "Selected all."}

    if low in ["show desktop", "minimize all", "minimize all windows"]:
        input_controller.show_desktop()
        return {"success": True, "tool": "input_show_desktop", "method": "fast_lane", "message": "Showing desktop."}

    if low in ["open task manager", "task manager", "open task view"]:
        input_controller.open_task_manager()
        return {"success": True, "tool": "input_task_manager", "method": "fast_lane", "message": "Opened Task Manager."}

    if low in ["switch window", "alt tab", "switch application"]:
        input_controller.switch_window_alt_tab()
        return {"success": True, "tool": "input_switch_window", "method": "fast_lane", "message": "Switched window."}

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
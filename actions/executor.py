import logging
import re
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

BUILTIN_APP_COMMANDS = (
    (re.compile(r"(?:open|launch|start)\s+(?:(?:google)\s+)?chrome(?:\s+browser)?"), "chrome", "open_url"),
    (re.compile(r"(?:open|launch|start)\s+(?:the\s+)?brave(?:\s+browser)?\s+and\s+(?:create|open)\s+(?:a\s+)?new\s+tab(?:\s+in\s+brave)?"), "brave", "open_new_tab"),
    (re.compile(r"(?:create|open)\s+(?:a\s+)?new\s+tab\s+in\s+brave"), "brave", "open_new_tab"),
    (re.compile(r"(?:open|launch|start)\s+(?:the\s+)?brave(?:\s+browser)?"), "brave", "open"),
    (re.compile(r"(?:open|launch|start)\s+(?:the\s+)?whatsapp(?:\s+desktop)?"), "whatsapp", "open"),
)


def _notify(on_status_callback, on_action_callback, tool: str, success: bool, message: str):
    """Uniform notification helper for UI callbacks."""
    if on_status_callback:
        on_status_callback("completed" if success else "error", message)
    if on_action_callback:
        try:
            on_action_callback(tool, success, message)
        except TypeError:
            on_action_callback(tool, success)


def _execute_builtin_app_command(command: str, plugin_manager, on_action_callback, on_status_callback):
    """Routes common app-launch commands directly to their installed plugins."""
    for pattern, plugin_id, action in BUILTIN_APP_COMMANDS:
        if not pattern.fullmatch(command):
            continue

        plugin = plugin_manager.get_plugin(plugin_id)
        if not plugin:
            message = f"The built-in {plugin_id.title()} plugin is unavailable."
            success = False
        elif not plugin.is_enabled:
            message = f"The {plugin_id.title()} plugin is disabled. Enable it in the Plugins dashboard."
            success = False
        else:
            success = bool(plugin.execute(action))
            if success:
                message = (
                    "Opened a new Brave tab."
                    if plugin_id == "brave" and action == "open_new_tab"
                    else f"Opened {plugin_id.title()}."
                )
            elif plugin_id == "chrome":
                message = "Could not open Chrome. Check that Google Chrome is installed."
            elif plugin_id == "brave":
                message = "Could not open Brave. Check that Brave is installed."
            else:
                message = "Could not open WhatsApp. Check that WhatsApp is installed and its app link is registered."

        _notify(on_status_callback, on_action_callback, plugin_id, success, message)
        return {
            "success": success,
            "tool": plugin_id,
            "method": f"{plugin_id}_plugin",
            "message": message,
            "output": "",
        }

    return None


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Routes built-in commands directly and uses Agent Brain for other requests.
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
        return {
            "success": False,
            "tool": "security_confirmation",
            "method": "security_guard",
            "message": "An action is awaiting confirmation. Say 'confirm' or 'yes' to proceed, or 'cancel' before making another request.",
            "details": {"requires_confirmation": True},
        }

    from plugins.manager import plugin_manager

    if low in GREETINGS:
        return {"success": True, "tool": "greeting", "method": "none", "message": "I'm listening. How can I help you with your computer today?"}

    app_result = _execute_builtin_app_command(
        low,
        plugin_manager,
        on_action_callback,
        on_status_callback,
    )
    if app_result is not None:
        return app_result

    # Route explicit GitHub tasks to the integrated plugin instead of generating shell code.
    github_plugin = plugin_manager.get_plugin("github")
    if github_plugin and not github_plugin.is_enabled and github_plugin.parse_command(cleaned):
        return {
            "success": False,
            "tool": "github",
            "method": "github_plugin",
            "message": "The GitHub plugin is disabled. Enable it in the Plugins dashboard to use GitHub commands.",
        }
    if github_plugin and github_plugin.is_enabled:
        request = github_plugin.parse_command(cleaned)
        if request:
            action = request["action"]
            kwargs = request["kwargs"]
            if action == "unsupported":
                return {
                    "success": False,
                    "tool": "github",
                    "method": "github_plugin",
                    "message": "That GitHub operation is not supported yet. Supported tasks: repository status, current-branch push, list repositories/issues/pull requests, and create issues/pull requests.",
                }
            if action == "create_issue" and not kwargs.get("title"):
                return {
                    "success": False,
                    "tool": "github",
                    "method": "github_plugin",
                    "message": "Specify an issue title, for example: create GitHub issue title Fix login.",
                }
            if action == "create_pull_request" and not all(kwargs.get(key) for key in ("title", "head", "base")):
                return {
                    "success": False,
                    "tool": "github",
                    "method": "github_plugin",
                    "message": "Specify the PR title, head branch, and base branch.",
                }

            def perform_github_action():
                return github_plugin.perform(action, **kwargs)

            if request["requires_confirmation"]:
                risk_action = "github_push" if action == "push" else "github_write"
                success, message, details = security_guard.request_execution(
                    risk_action,
                    perform_github_action,
                    description=request["description"],
                )
                requires_confirmation = bool(details and details.get("requires_confirmation"))
                if not requires_confirmation:
                    _notify(on_status_callback, on_action_callback, "github", success, message)
                return {
                    "success": success or requires_confirmation,
                    "tool": "github",
                    "method": "github_plugin",
                    "message": message,
                    "details": details,
                }

            try:
                result = perform_github_action()
            except (RuntimeError, ValueError) as exc:
                message = str(exc)
                _notify(on_status_callback, on_action_callback, "github", False, message)
                return {"success": False, "tool": "github", "method": "github_plugin", "message": message}
            message = result.get("message", "GitHub request completed.")
            details = result.get("details")
            if details is not None:
                message = f"{message}\n{details}"
            _notify(on_status_callback, on_action_callback, "github", True, message)
            return {**result, "tool": "github", "method": "github_plugin", "message": message}

    # Other requests go to the Agent Brain.
    # The Agent Brain handles apps, files, web, and system tools via generated code.
    from actions.agent_brain import agent_brain
    result = agent_brain.generate_and_execute(cleaned)

    if not result:
        result = {
            "success": False,
            "message": "The Agent Brain returned no result.",
            "method": "agentic_engine",
        }

    result = dict(result)
    success = bool(result.get("success"))
    tool = result.get("tool", "agent_brain")
    result.setdefault("method", "agentic_engine")
    result.setdefault("message", f"I couldn't complete the command: '{cleaned}'")
    _notify(
        on_status_callback,
        on_action_callback,
        tool,
        success,
        result["message"],
    )
    return result

def execute_system_command(text: str, on_action_callback=None, on_status_callback=None) -> bool:
    result = execute_system_command_detailed(text, on_action_callback, on_status_callback)
    return result.get("success", False)

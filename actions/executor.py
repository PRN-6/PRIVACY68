import logging
import re
import urllib.parse
import webbrowser
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
    (re.compile(r"(?:open|launch|start|go to)\s+(?:(?:google)\s+)?chrome(?:\s+browser)?"), "chrome", "open_url"),
    (re.compile(r"(?:open|launch|start|go to)\s+(?:the\s+)?brave(?:\s+browser)?\s+and\s+(?:create|open)\s+(?:a\s+)?new\s+tab(?:\s+in\s+brave)?"), "brave", "open_new_tab"),
    (re.compile(r"(?:create|open)\s+(?:a\s+)?new\s+tab\s+in\s+brave"), "brave", "open_new_tab"),
    (re.compile(r"(?:open|launch|start|go to)\s+(?:the\s+)?brave(?:\s+browser)?"), "brave", "open"),
    (re.compile(r"(?:open|launch|start|check|go to)\s+(?:the\s+)?whatsapp(?:\s+desktop)?"), "whatsapp", "open"),
    (re.compile(r"(?:open|launch|start|check|go to)\s+(?:the\s+)?(?:google\s+)?gmail(?:\s+inbox)?"), "gmail", "open"),
    (re.compile(r"(?:open|launch|start|check|go to)\s+(?:the\s+)?telegram(?:\s+desktop)?"), "telegram", "open"),
)

COMMON_WEB_SERVICES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "wikipedia": "https://www.wikipedia.org",
    "chatgpt": "https://chatgpt.com",
}

APP_LAUNCHERS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "terminal": ["wt.exe"],
}


def _notify(on_status_callback, on_action_callback, tool: str, success: bool, message: str):
    """Uniform notification helper for UI callbacks."""
    if on_status_callback:
        on_status_callback("completed" if success else "error", message)
    if on_action_callback:
        try:
            on_action_callback(tool, success, message)
        except TypeError:
            on_action_callback(tool, success)


def _open_url(url: str, plugin_manager, preferred_browser: str = None) -> bool:
    """Attempts to open URL via Chrome or Brave plugin, falling back to system browser."""
    if preferred_browser == "chrome":
        chrome = plugin_manager.get_plugin("chrome")
        if chrome and chrome.is_enabled and hasattr(chrome, "open_url"):
            try:
                if chrome.open_url(url):
                    return True
            except Exception:
                pass
    elif preferred_browser == "brave":
        brave = plugin_manager.get_plugin("brave")
        if brave and brave.is_enabled and hasattr(brave, "open_url"):
            try:
                if brave.open_url(url):
                    return True
            except Exception:
                pass

    chrome = plugin_manager.get_plugin("chrome")
    if chrome and chrome.is_enabled and hasattr(chrome, "open_url"):
        try:
            if chrome.open_url(url):
                return True
        except Exception:
            pass

    brave = plugin_manager.get_plugin("brave")
    if brave and brave.is_enabled and hasattr(brave, "open_url"):
        try:
            if brave.open_url(url):
                return True
        except Exception:
            pass

    return webbrowser.open(url)


def _execute_builtin_app_command(command: str, plugin_manager, on_action_callback, on_status_callback):
    """Routes common app-launch commands directly to their installed plugins."""
    clean_cmd = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", command.strip()).strip(".!?, \t\n")
    for pattern, plugin_id, action in BUILTIN_APP_COMMANDS:
        if not pattern.fullmatch(clean_cmd):
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
            elif plugin_id == "gmail":
                message = "Could not open Gmail. Check your internet connection or browser."
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


def _execute_web_or_app_command(command: str, plugin_manager, on_action_callback, on_status_callback):
    """
    Directly routes common web searches, website navigations, and desktop app launches
    without requiring LLM/Ollama reasoning.
    """
    clean_cmd = command.strip().strip("'\"")

    # 1. "open <browser> and search for <query>"
    m_browser_search = re.match(
        r"(?:open|launch|start)\s+(?:(?:google)\s+)?(chrome|brave|browser)\s+and\s+search(?:\s+for)?\s+(.+)",
        clean_cmd,
        re.IGNORECASE
    )
    if m_browser_search:
        browser_pref = m_browser_search.group(1).lower()
        query = m_browser_search.group(2).strip().strip("'\"")

        if query.lower() in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[query.lower()]
            target_name = query.title()
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            target_name = f"'{query}'"

        _open_url(url, plugin_manager, preferred_browser=browser_pref)
        msg = f"Opened {browser_pref.title()} and searched for {target_name}."
        _notify(on_status_callback, on_action_callback, "browser", True, msg)
        return {
            "success": True,
            "tool": "browser",
            "method": "browser_search",
            "message": msg,
            "output": url,
        }

    # 2. "search youtube for <query>"
    m_yt = re.match(r"(?:search|look up)\s+youtube\s+for\s+(.+)", clean_cmd, re.IGNORECASE)
    if m_yt:
        query = m_yt.group(1).strip().strip("'\"")
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        _open_url(url, plugin_manager)
        msg = f"Searched YouTube for '{query}'."
        _notify(on_status_callback, on_action_callback, "browser", True, msg)
        return {
            "success": True,
            "tool": "browser",
            "method": "browser_search",
            "message": msg,
            "output": url,
        }

    # 3. "search for <query>" / "search google for <query>"
    m_search = re.match(r"(?:search|look up)(?:\s+for|\s+google for)?\s+(.+)", clean_cmd, re.IGNORECASE)
    if m_search:
        query = m_search.group(1).strip().strip("'\"")
        if query.lower().endswith(" on youtube"):
            clean_q = query[:-11].strip()
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_q)}"
            target = f"YouTube for '{clean_q}'"
        elif query.lower() in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[query.lower()]
            target = query.title()
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            target = f"'{query}'"

        _open_url(url, plugin_manager)
        msg = f"Searched for {target}."
        _notify(on_status_callback, on_action_callback, "browser", True, msg)
        return {
            "success": True,
            "tool": "browser",
            "method": "browser_search",
            "message": msg,
            "output": url,
        }

    # 4. "open <website>" (e.g. "open youtube", "open github")
    m_site = re.fullmatch(r"(?:open|launch|go to)\s+([a-zA-Z0-9_\-\.]+)", clean_cmd, re.IGNORECASE)
    if m_site:
        site_key = m_site.group(1).lower().strip()

        # Prioritize integrated plugins (e.g. gmail, github, whatsapp) over generic web fallback
        plugin = plugin_manager.get_plugin(site_key)
        if plugin:
            if not plugin.is_enabled:
                msg = f"The {site_key.title()} plugin is disabled. Enable it in the Plugins dashboard to use {site_key.title()} commands."
                _notify(on_status_callback, on_action_callback, site_key, False, msg)
                return {
                    "success": False,
                    "tool": site_key,
                    "method": f"{site_key}_plugin",
                    "message": msg,
                }
            if hasattr(plugin, "execute"):
                success = bool(plugin.execute("open"))
            elif hasattr(plugin, "open_inbox"):
                success = bool(plugin.open_inbox())
            elif hasattr(plugin, "open"):
                success = bool(plugin.open())
            else:
                success = False

            if site_key == "gmail":
                msg = "Opened Gmail inbox." if success else "Could not open Gmail inbox."
            else:
                msg = f"Opened {site_key.title()}." if success else f"Could not open {site_key.title()}."

            _notify(on_status_callback, on_action_callback, site_key, success, msg)
            return {
                "success": success,
                "tool": site_key,
                "method": f"{site_key}_plugin",
                "message": msg,
                "output": "",
            }

        if site_key in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[site_key]
            _open_url(url, plugin_manager)
            msg = f"Opened {site_key.title()}."
            _notify(on_status_callback, on_action_callback, "browser", True, msg)
            return {
                "success": True,
                "tool": "browser",
                "method": "website_launcher",
                "message": msg,
                "output": url,
            }
        elif "." in site_key and not site_key.endswith((".exe", ".py", ".txt", ".md")):
            url = f"https://{site_key}"
            _open_url(url, plugin_manager)
            msg = f"Navigated to {site_key}."
            _notify(on_status_callback, on_action_callback, "browser", True, msg)
            return {
                "success": True,
                "tool": "browser",
                "method": "website_launcher",
                "message": msg,
                "output": url,
            }

    # 5. Desktop apps (notepad, calculator, cmd, powershell)
    m_app = re.fullmatch(r"(?:open|launch|start)\s+(notepad|calculator|calc|explorer|file explorer|task manager|cmd|powershell|terminal)", clean_cmd, re.IGNORECASE)
    if m_app:
        app_key = m_app.group(1).lower().strip()
        exe_cmd = APP_LAUNCHERS.get(app_key)
        if exe_cmd:
            try:
                import subprocess
                subprocess.Popen(exe_cmd)
                msg = f"Opened {app_key.title()}."
                _notify(on_status_callback, on_action_callback, "system_app", True, msg)
                return {
                    "success": True,
                    "tool": "system_app",
                    "method": "app_launcher",
                    "message": msg,
                    "output": "",
                }
            except Exception as e:
                logger.error(f"Failed to launch {app_key}: {e}")

    return None


def execute_system_command_detailed(text: str, on_action_callback=None, on_status_callback=None) -> dict:
    """
    Routes built-in commands directly and uses Agent Brain for other requests.
    """
    cleaned = autocorrect_speech_command(text.strip())
    if not cleaned:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

    low = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", cleaned.lower().strip()).strip(".!?, \t\n")
    if not low:
        return {"success": False, "tool": "None", "method": "none", "message": "Empty command"}

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

    # 2. Built-in Core Application Plugins (Exact app opens)
    app_result = _execute_builtin_app_command(
        low,
        plugin_manager,
        on_action_callback,
        on_status_callback,
    )
    if app_result is not None:
        return app_result

    # 3. Direct Web Searches, Websites, and App Launches
    web_result = _execute_web_or_app_command(
        low,
        plugin_manager,
        on_action_callback,
        on_status_callback,
    )
    if web_result is not None:
        return web_result

    # 4. Route explicit Gmail tasks to the integrated plugin.
    gmail_plugin = plugin_manager.get_plugin("gmail")
    if gmail_plugin and not gmail_plugin.is_enabled and gmail_plugin.parse_command(cleaned):
        return {
            "success": False,
            "tool": "gmail",
            "method": "gmail_plugin",
            "message": "The Gmail plugin is disabled. Enable it in the Plugins dashboard to use Gmail commands.",
        }
    if gmail_plugin and gmail_plugin.is_enabled:
        gmail_req = gmail_plugin.parse_command(cleaned)
        if gmail_req and gmail_req.get("action") in ("open", "compose"):
            action = gmail_req["action"]
            kwargs = gmail_req.get("kwargs", {})
            if action == "open":
                success = bool(gmail_plugin.open_inbox(**kwargs))
                msg = "Opened Gmail inbox." if success else "Could not open Gmail inbox."
            elif action == "compose":
                to = kwargs.get("to", "")
                subject = kwargs.get("subject", "")
                body = kwargs.get("body", "")
                success = bool(gmail_plugin.compose_email(to=to, subject=subject, body=body))
                if success:
                    msg = f"Drafted email to {to} in Gmail." if to else "Opened Gmail compose window."
                else:
                    msg = "Could not prepare Gmail draft."

            _notify(on_status_callback, on_action_callback, "gmail", success, msg)
            return {
                "success": success,
                "tool": "gmail",
                "method": "gmail_plugin",
                "message": msg,
                "output": kwargs,
            }

    # 5. Route explicit GitHub tasks to the integrated plugin instead of generating shell code.
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

    # 5. Complex agentic requests go to Agent Brain (Local Ollama / Cloud LLM)
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

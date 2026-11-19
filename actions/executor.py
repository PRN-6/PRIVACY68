import logging
import os
import re
import subprocess
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


def _open_url(url: str, preferred_browser: str = None) -> bool:
    """Attempts to open URL via Chrome or Brave binary, falling back to system browser."""
    if preferred_browser == "chrome":
        for p in [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        ]:
            if os.path.isfile(p):
                try:
                    subprocess.Popen([p, url])
                    return True
                except Exception:
                    pass
    elif preferred_browser == "brave":
        for p in [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]:
            if os.path.isfile(p):
                try:
                    subprocess.Popen([p, url])
                    return True
                except Exception:
                    pass

    return webbrowser.open(url)


def _execute_builtin_app_command(command: str, on_action_callback, on_status_callback):
    """Routes common app-launch commands directly to native services and browsers."""
    clean_cmd = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", command.strip()).strip(".!?, \t\n")
    for pattern, app_id, action in BUILTIN_APP_COMMANDS:
        if not pattern.fullmatch(clean_cmd):
            continue

        success = False
        message = ""
        if app_id == "chrome":
            success = _open_url("https://www.google.com", preferred_browser="chrome")
            message = "Opened Chrome." if success else "Could not open Chrome."
        elif app_id == "brave":
            success = _open_url("https://search.brave.com", preferred_browser="brave")
            message = "Opened a new Brave tab." if action == "open_new_tab" else "Opened Brave."
        elif app_id == "gmail":
            from services.gmail import gmail_service
            if not getattr(gmail_service, "is_enabled", True):
                message = "The Gmail service is disabled. Enable it in the Services dashboard to use Gmail commands."
                _notify(on_status_callback, on_action_callback, "gmail", False, message)
                return {
                    "success": False,
                    "tool": "gmail",
                    "method": "gmail_service",
                    "message": message,
                    "output": "",
                }
            success = bool(gmail_service.open_inbox())
            message = "Opened Gmail inbox." if success else "Could not open Gmail."
        elif app_id == "whatsapp":
            success = webbrowser.open("https://web.whatsapp.com")
            message = "Opened WhatsApp." if success else "Could not open WhatsApp."
        elif app_id == "telegram":
            success = _open_url("https://web.telegram.org")
            message = "Opened Telegram." if success else "Could not open Telegram."
        else:
            success = _open_url("https://www.google.com")
            message = f"Opened {app_id.title()}."

        _notify(on_status_callback, on_action_callback, app_id, success, message)
        return {
            "success": success,
            "tool": app_id,
            "method": f"{app_id}_service",
            "message": message,
            "output": "",
        }

    return None


def _execute_web_or_app_command(command: str, on_action_callback, on_status_callback):
    """
    Directly routes common web searches, website navigations, and desktop app launches
    without requiring LLM/Ollama reasoning.
    """
    clean_cmd = command.strip().strip("'\"")

    # 1. "open <browser> and search for / go to / open <query>"
    m_browser_search = re.match(
        r"(?:open|launch|start)\s+(?:(?:google)\s+)?(chrome|brave|browser)\s+and\s+(?:search(?:\s+for)?|open|go to)\s+(.+)",
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

        _open_url(url, preferred_browser=browser_pref)
        msg = f"Opened {browser_pref.title()} and navigated to {target_name}."
        _notify(on_status_callback, on_action_callback, "browser", True, msg)
        return {
            "success": True,
            "tool": "browser",
            "method": "browser_search",
            "message": msg,
            "output": url,
        }

    # 1b. "open <site/query> in (chrome|brave|browser)" (e.g. "open chatgpt in chrome", "open youtube in brave")
    m_site_in_browser = re.fullmatch(
        r"(?:open|launch|go to)\s+(.+?)\s+in\s+(?:(?:google)\s+)?(chrome|brave|browser)",
        clean_cmd,
        re.IGNORECASE
    )
    if m_site_in_browser:
        target_site = m_site_in_browser.group(1).strip().strip("'\"")
        browser_pref = m_site_in_browser.group(2).lower()
        if browser_pref == "browser":
            browser_pref = None

        if target_site.lower() in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[target_site.lower()]
            target_name = target_site.title()
        elif "." in target_site and not target_site.endswith((".exe", ".py", ".txt", ".md")):
            url = f"https://{target_site}"
            target_name = target_site
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(target_site)}"
            target_name = f"'{target_site}'"

        _open_url(url, preferred_browser=browser_pref)
        pref_label = f" in {browser_pref.title()}" if browser_pref else ""
        msg = f"Opened {target_name}{pref_label}."
        _notify(on_status_callback, on_action_callback, "browser", True, msg)
        return {
            "success": True,
            "tool": "browser",
            "method": "website_launcher",
            "message": msg,
            "output": url,
        }

    # 1c. "search <query> in (chrome|brave|browser)"
    m_search_in_browser = re.fullmatch(
        r"(?:search|search for|look up)\s+(.+?)\s+in\s+(?:(?:google)\s+)?(chrome|brave|browser)",
        clean_cmd,
        re.IGNORECASE
    )
    if m_search_in_browser:
        query = m_search_in_browser.group(1).strip().strip("'\"")
        browser_pref = m_search_in_browser.group(2).lower()
        if browser_pref == "browser":
            browser_pref = None

        if query.lower() in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[query.lower()]
            target_name = query.title()
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            target_name = f"'{query}'"

        _open_url(url, preferred_browser=browser_pref)
        pref_label = f" in {browser_pref.title()}" if browser_pref else ""
        msg = f"Searched for {target_name}{pref_label}."
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
        _open_url(url)
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

        _open_url(url)
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

        if site_key == "gmail":
            from services.gmail import gmail_service
            if not getattr(gmail_service, "is_enabled", True):
                msg = "The Gmail service is disabled. Enable it in the Services dashboard to use Gmail commands."
                _notify(on_status_callback, on_action_callback, "gmail", False, msg)
                return {
                    "success": False,
                    "tool": "gmail",
                    "method": "gmail_service",
                    "message": msg,
                    "output": "",
                }
            success = bool(gmail_service.open_inbox())
            msg = "Opened Gmail inbox." if success else "Could not open Gmail inbox."
            _notify(on_status_callback, on_action_callback, "gmail", success, msg)
            return {
                "success": success,
                "tool": "gmail",
                "method": "gmail_service",
                "message": msg,
                "output": "",
            }
        elif site_key == "whatsapp":
            success = webbrowser.open("https://web.whatsapp.com")
            msg = "Opened WhatsApp." if success else "Could not open WhatsApp."
            _notify(on_status_callback, on_action_callback, "whatsapp", success, msg)
            return {
                "success": success,
                "tool": "whatsapp",
                "method": "whatsapp_service",
                "message": msg,
                "output": "",
            }

        if site_key in COMMON_WEB_SERVICES:
            url = COMMON_WEB_SERVICES[site_key]
            _open_url(url)
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
            _open_url(url)
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

    if low in GREETINGS:
        return {"success": True, "tool": "greeting", "method": "none", "message": "I'm listening. How can I help you with your computer today?"}

    # 2. Built-in Core Application Commands (Exact app opens)
    app_result = _execute_builtin_app_command(
        low,
        on_action_callback,
        on_status_callback,
    )
    if app_result is not None:
        return app_result

    # 3. Direct Web Searches, Websites, and App Launches
    web_result = _execute_web_or_app_command(
        low,
        on_action_callback,
        on_status_callback,
    )
    if web_result is not None:
        return web_result

    # 4. Route explicit Gmail tasks to native service
    from services.gmail import gmail_service
    if not getattr(gmail_service, "is_enabled", True) and gmail_service.parse_command(cleaned):
        return {
            "success": False,
            "tool": "gmail",
            "method": "gmail_service",
            "message": "The Gmail service is disabled. Enable it in the Services dashboard to use Gmail commands.",
        }
    if getattr(gmail_service, "is_enabled", True):
        gmail_req = gmail_service.parse_command(cleaned)
        if gmail_req and gmail_req.get("action") in ("open", "compose"):
            action = gmail_req["action"]
            kwargs = gmail_req.get("kwargs", {})
            if action == "open":
                success = bool(gmail_service.open_inbox(**kwargs))
                msg = "Opened Gmail inbox." if success else "Could not open Gmail inbox."
            elif action == "compose":
                to = kwargs.get("to", "")
                subject = kwargs.get("subject", "")
                body = kwargs.get("body", "")
                success = bool(gmail_service.compose_email(to=to, subject=subject, body=body))
                if success:
                    msg = f"Drafted email to {to} in Gmail." if to else "Opened Gmail compose window."
                else:
                    msg = "Could not prepare Gmail draft."

            _notify(on_status_callback, on_action_callback, "gmail", success, msg)
            return {
                "success": success,
                "tool": "gmail",
                "method": "gmail_service",
                "message": msg,
                "output": kwargs,
            }

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

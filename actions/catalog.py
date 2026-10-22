"""
PRIVACY68 — Built-in Command Catalogue.

This module is the single, declarative description of every command the
assistant ships with. Each command is a `CommandSpec`:

    * a name, the lane that owns it and the intent it is classified as
    * the matchers that recognise it (exact phrase and/or regex)
    * the slot extractor that pulls the arguments out of the utterance
    * the handler that performs it

The dispatcher never branches on "is the intent X?" — it asks the registry
for the spec, the spec's handler runs. Adding a command is a one-entry
change here, and the intent classifier learns it from the same entry.

Layout of this file:

    1. Vocabulary (sites, browsers, apps, folders)
    2. Command tables (system actions, Windows tools, dev tools, ...)
    3. Handlers (one per command family)
    4. Slot extractors (the arguments of each command family)
    5. Spec builders (tables -> CommandSpec objects)
    6. build_registry() (wires everything into the shared registry)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from actions.registry import (
    CommandContext,
    CommandSpec,
    LANE_API,
    LANE_FAST,
    LANE_LLM,
    Matcher,
    STAGE_EXECUTE,
    normalize,
    registry,
)

logger = logging.getLogger("PRIVACY68.Catalog")

# ═══════════════════════════════════════════════════════════════════════════
# 1. VOCABULARY
# ═══════════════════════════════════════════════════════════════════════════

#: Websites that can be opened directly by name.
SITES: Tuple[str, ...] = (
    "youtube", "github", "chatgpt", "openai", "reddit", "twitter", "wikipedia",
    "gmail", "google", "linkedin", "netflix", "spotify", "amazon", "facebook",
    "instagram", "duckduckgo", "bing", "twitch", "stackoverflow", "medium",
    "notion", "figma", "canva", "udemy", "coursera", "pinterest", "tiktok",
    "telegram", "discord", "zoom", "dropbox", "trello", "jira", "linear",
    "substack", "wordpress", "devto", "npm", "pypi", "kaggle", "leetcode",
    "w3schools", "mdn", "huggingface", "producthunt", "ycombinator",
    "weather", "maps", "translate", "outlook", "onedrive", "icloud",
    "mega", "signal", "slack", "asana", "monday", "trello",
)

#: Browsers that can be launched as the target of a web command.
BROWSERS: Tuple[str, ...] = (
    "chrome", "brave", "edge", "firefox", "safari", "opera", "msedge",
    "internet explorer",
)

#: Applications that can be launched by name.
APPS: Tuple[str, ...] = (
    "chrome", "google chrome", "brave", "brave browser", "edge", "microsoft edge",
    "firefox", "notepad", "calculator", "vs code", "visual studio code",
    "vscodium", "vscode", "spotify", "vlc", "media player", "file explorer", "explorer",
    "word", "excel", "powerpoint", "outlook", "paint", "powershell", "terminal",
    "zoom",
    "cmd", "command prompt", "slack", "discord", "teams", "microsoft teams",
    "zoom", "whatsapp", "telegram", "signal", "steam", "obs", "ffmpeg",
    "git bash", "docker", "postman", "obsidian", "notion", "pycharm", "intellij",
    "eclipse", "netbeans", "device manager", "control panel",
    "registry editor", "services", "event viewer", "character map",
    "snipping tool", "sticky notes", "clock", "calendar", "camera",
    "store", "microsoft store", "settings", "regedit", "cmd prompt",
    "system information",
)

#: Folder / location words that resolve to a well-known place on disk.
FOLDERS: Tuple[str, ...] = (
    "downloads", "desktop", "documents", "pictures", "music", "videos",
    "this pc", "my computer", "home", "recycle bin", "temp", "appdata",
    "program files", "program files x86", "favorites", "recent files",
    "one drive", "onedrive", "start menu", "control panel", "user profile",
)

#: Words that only make sense as part of a path, never as an application.
PATH_WORDS = frozenset(FOLDERS) | {"folder", "directory", "drive", "user", "the"}


def _alt(words: Sequence[str]) -> str:
    """Builds a regex alternation, longest first so the longest wins."""
    ordered = sorted(set(words), key=len, reverse=True)
    return "|".join(re.escape(w) for w in ordered)


SITE_RE = _alt(SITES)
BROWSER_RE = _alt(BROWSERS)
APP_RE = _alt(APPS)
FOLDER_RE = _alt(FOLDERS)


# ═══════════════════════════════════════════════════════════════════════════
# 2. COMMAND TABLES
# ═══════════════════════════════════════════════════════════════════════════

# ─── System actions ─────────────────────────────────────────────────────────
# (action, backend, exact phrases, regex)
#
# `backend` selects who performs the action:
#   "system"  -> computer_use.system_tools.system_action  (pyautogui / Win32)
#   "windows" -> the shipped `windows` plugin (richer OS surface)
SYSTEM_ACTION_TABLE: Tuple[Tuple[str, str, Tuple[str, ...], str], ...] = (
    ("volume_up", "system",
     ("volume up", "increase volume", "turn up volume", "turn up the volume",
      "raise the volume", "louder", "make it louder", "volume higher",
      "turn the volume up", "boost the volume"),
     r"\b(?:increase|raise|boost|turn\s+up)\s+(?:the\s+)?volume\b"
     r"|\bturn\s+(?:the\s+)?volume\s+up\b|\bvolume\s+up\b|\blouder\b"
     r"|\bvolume\s+higher\b"),

    ("volume_down", "system",
     ("volume down", "decrease volume", "turn down volume",
      "turn down the volume", "lower the volume", "quieter", "make it quieter",
      "volume lower", "turn the volume down"),
     r"\b(?:decrease|reduce|lower|turn\s+down)\s+(?:the\s+)?volume\b"
     r"|\bturn\s+(?:the\s+)?volume\s+down\b|\bvolume\s+down\b|\bquieter\b"
     r"|\bvolume\s+lower\b"),

    ("volume_unmute", "windows",
     ("unmute", "unmute volume", "unmute the volume", "unmute audio",
      "turn the sound on", "restore sound"),
     r"\bunmute\b|\brestore\s+(?:the\s+)?(?:sound|audio|volume)\b"),

    ("volume_mute", "system",
     ("mute", "mute volume", "mute the volume", "mute audio", "mute sound",
      "silence the audio"),
     r"\bmute\b|\bsilence\s+(?:the\s+)?(?:audio|sound|volume)\b"),

    ("set_volume", "windows",
     ("set volume", "change volume", "set the volume", "adjust the volume"),
     r"\b(?:set|change|adjust)\s+(?:the\s+)?volume\b"),

    ("lock", "system",
     ("lock", "lock screen", "lock pc", "lock my pc", "lock computer",
      "lock the computer", "lock the screen", "lock my computer"),
     r"\block\b"),

    ("screenshot", "system",
     ("screenshot", "take screenshot", "take a screenshot", "capture screen",
      "capture the screen", "grab a screenshot", "save a screenshot"),
     r"\b(?:take|capture|grab|save)\s+(?:a\s+)?screenshot\b|\bscreenshot\b"),

    ("close_window", "system",
     ("close window", "close this window", "close the window",
      "close active window", "close current window", "close it", "close this"),
     r"\bclose\s+(?:this\s+|the\s+|my\s+|active\s+|current\s+)?window\b"
     r"|\bclose\s+it\b|\bclose\s+this\b"),

    ("maximize", "system",
     ("maximize", "maximize window", "maximize this window",
      "maximize the window", "full screen window", "fullscreen the window"),
     r"\bmaximi[sz]e\b|\bfull\s*screen\b"),

    ("minimize", "system",
     ("minimize", "minimize window", "minimize this window",
      "minimize the window"),
     r"\bminimi[sz]e\s+(?:this\s+|the\s+|my\s+)?window\b"),

    ("restore", "windows",
     ("restore window", "restore this window", "unmaximize window",
      "un maximize the window"),
     r"\brestore\s+(?:this\s+|the\s+)?window\b|\bun\s*maximi[sz]e\b"),

    ("enter", "system",
     ("press enter", "hit enter", "press return"),
     r"\b(?:press|hit|push)\s+(?:the\s+)?(?:enter|return)\b"),

    ("tab", "system",
     ("press tab", "hit tab", "press the tab key"),
     r"\b(?:press|hit|push)\s+(?:the\s+)?tab\b"),

    ("brightness_up", "windows",
     ("increase brightness", "turn up brightness", "brightness up",
      "make it brighter", "brighter screen", "increase the screen brightness"),
     r"\b(?:increase|raise|turn\s+up)\s+(?:the\s+)?(?:screen\s+)?brightness\b"
     r"|\bbrightness\s+up\b|\bbrighter\b"),

    ("brightness_down", "windows",
     ("decrease brightness", "turn down brightness", "brightness down",
      "dim the screen", "make it darker", "decrease the screen brightness"),
     r"\b(?:decrease|lower|turn\s+down|dim)\s+(?:the\s+)?(?:screen\s+)?brightness\b"
     r"|\bbrightness\s+down\b|\bdimmer\b"),

    ("sign_out", "windows",
     ("sign out", "log off", "log out"),
     r"\bsign\s+out\b|\blog\s+off\b|\blog\s*out\b"),

    ("sleep", "windows",
     ("go to sleep", "sleep", "put pc to sleep", "put the pc to sleep",
      "hibernate"),
     r"\b(?:go\s+to\s+sleep|put\s+(?:the\s+)?(?:pc|computer)\s+to\s+sleep)\b"
     r"|\bsleep\b|\bhibernate\b"),

    ("restart", "windows",
     ("restart", "restart pc", "restart the pc", "restart computer",
      "reboot"),
     r"\brestart\s+(?:the\s+|my\s+)?(?:pc|computer)?\b|\breboot\b"),

    ("shutdown", "windows",
     ("shut down", "shutdown", "turn off pc", "turn off the computer",
      "power off"),
     r"\bshut\s*down\b|\bturn\s+off\s+(?:the\s+)?(?:pc|computer)\b|\bpower\s+off\b"),

    ("cancel_shutdown", "windows",
     ("cancel shutdown", "abort shutdown", "cancel restart"),
     r"\b(?:cancel|abort)\s+(?:the\s+)?(?:shutdown|restart|power\s+off)\b"),
)


# ─── Windows tool bridge ────────────────────────────────────────────────────
# (windows plugin action, exact phrases, regex, user-facing message)
WINDOWS_TOOL_TABLE: Tuple[Tuple[str, Tuple[str, ...], str, str], ...] = (
    ("windows.control_panel",
     ("control panel", "open control panel", "windows control panel"),
     r"\bcontrol\s+panel\b|\bpower\s+options?\b|\bpower\s+plan\b"
     r"|\bnetwork\s+(?:connections|and\s+sharing)\b|\binternet\s+options\b"
     r"|\bsharing\s+center\b|\buser\s+accounts\b|\bprograms\s+and\s+features\b"
     r"|\buninstall\s+(?:a\s+)?program\b|\b(?:folder|file\s+explorer)\s+options\b"
     r"|\bsystem\s+restore\b|\bcredential\s+manager\b|\bdate\s+and\s+time\b"
     r"|\bregion\b|\bcolor\s+management\b|\bdevices\s+and\s+printers\b"
     r"|\bwindows\s+tools\b",
     "Opened the Windows Control Panel item."),

    ("windows.open_tools",
     ("resource monitor", "disk management", "registry editor",
      "event viewer", "services"),
     r"\bresource\s+monitor\b|\bdisk\s+management\b|\bregistry\s+editor\b"
     r"|\bevent\s+viewer\b|\bservices\b",
     "Opened the Windows system tool."),

    ("windows.system_info",
     ("system information", "windows version", "computer name", "hostname",
      "cpu info", "how much ram", "how much memory", "how much storage",
      "how much battery", "check disk space", "check memory",
      "check storage", "system uptime", "which wifi", "what wifi am i on",
      "check the processor", "check the cpu", "check the gpu",
      "check the graphics card", "check the monitor"),
     r"\bhow\s+much\s+(?:battery|storage|memory|ram)\b"
     r"|\bcheck\s+(?:disk\s+space|memory|battery|storage)\b|\bstorage\s+left\b"
     r"|\bsystem\s+uptime\b|\bwindows\s+version\b|\bwhich\s+wifi\b"
     r"|\bwhat\s+wifi\s+am\s+i\s+on\b|\bcomputer\s+name\b|\bhostname\b"
     r"|\bpower\s+plan\b|\bcheck\s+the\s+(?:processor|cpu|gpu|graphics\s+card|monitor)\b"
     r"|\bcpu\s+info\b|\bram\b",
     "Retrieved the system information."),

    ("windows.empty_recycle_bin",
     ("empty recycle bin", "empty the recycle bin", "clear the recycle bin",
      "empty trash"),
     r"\b(?:empty|clear)\s+(?:the\s+)?recycle\s+bin\b|\bempty\s+(?:the\s+)?trash\b",
     "Emptied the Recycle Bin."),

    ("windows.clipboard_clear",
     ("clear clipboard", "empty clipboard", "wipe clipboard",
      "clear the clipboard"),
     r"\b(?:clear|empty|wipe)\s+(?:the\s+)?clipboard\b",
     "Cleared the clipboard."),

    ("windows.toggle_connectivity",
     ("turn on wifi", "turn off wifi", "enable wifi", "disable wifi",
      "toggle wifi", "turn on bluetooth", "turn off bluetooth",
      "enable bluetooth", "disable bluetooth", "toggle bluetooth"),
     r"\b(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?wi[\s-]?fi\b"
     r"|\b(?:enable|disable)\s+(?:the\s+)?wi[\s-]?fi\b|\btoggle\s+wi[\s-]?fi\b"
     r"|\b(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?bluetooth\b"
     r"|\b(?:enable|disable)\s+(?:the\s+)?bluetooth\b|\btoggle\s+bluetooth\b",
     "Toggled the network radio."),

    ("windows.set_default_browser",
     ("default browser", "set default browser", "change default browser"),
     r"\bdefault\s+browser\b",
     "Opened the Default Apps settings page."),

    ("windows.open_run",
     ("open run", "the run dialog", "run box", "run dialog"),
     r"\bopen\s+run\b|\bthe\s+run\s+dialog\b|\brun\s+box\b|\brun\s+dialog\b",
     "Opened the Run dialog."),
)


# ─── Diagnostics ────────────────────────────────────────────────────────────
# (metric, exact phrases, regex)
DIAGNOSTIC_TABLE: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("ram", ("ram usage", "memory usage", "what is using my ram",
             "what's using my ram", "who is using ram", "check ram usage"),
     r"\b(?:what(?:'s| is)\s+using\s+my\s+ram|ram\s+usage|memory\s+usage"
     r"|who\s+is\s+using\s+ram)\b"),

    ("cpu", ("cpu usage", "what is using my cpu", "what's using my cpu",
             "who is using cpu", "check cpu usage"),
     r"\b(?:what(?:'s| is)\s+using\s+my\s+cpu|cpu\s+usage|who\s+is\s+using\s+cpu)\b"),

    ("battery", ("battery status", "battery percentage", "check battery",
                 "power status"),
     r"\b(?:battery\s+status|battery\s+percentage|check\s+battery|power\s+status)\b"),

    ("clipboard", ("read my clipboard", "read clipboard", "what is on my clipboard",
                   "what's on my clipboard"),
     r"\b(?:read\s+(?:my\s+)?clipboard|what(?:'s| is)\s+on\s+my\s+clipboard)\b"),
)


# ─── Developer tools ────────────────────────────────────────────────────────
# (operation, exact phrases, regex)
GIT_TABLE: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("status", ("git status", "check git status", "check git"),
     r"^(?:check\s+)?git\s+status$"),

    ("branch", ("git branch", "what branch", "current branch", "check branch"),
     r"\bgit\s+branch\b|\bwhat\s+branch\b|\bcurrent\s+branch\b|\bcheck\s+branch\b"),

    ("pull", ("git pull", "pull latest changes", "pull repo", "pull from github"),
     r"^(?:git\s+pull|pull\s+(?:latest\s+changes|repo|from\s+github))$"),

    ("push", ("git push", "push to github", "push my code", "push my code to github",
              "push code to github", "push changes", "push changes to github",
              "push to my repo", "push to repo", "push current project",
              "push project", "push my current project changes to github",
              "commit and push", "commit and push my changes",
              "commit and push my changes to github", "git commit and push",
              "push changes to github"),
     r"\b(?:git\s+push|push\s+(?:my\s+)?(?:code|changes|to\s+\w+|project|repo))"
     r"|\bcommit\s+and\s+push\b"),

    ("commit", ("git commit", "commit my code", "commit changes"),
     r"^(?:git\s+commit|commit\s+(?:my\s+)?(?:code|changes))$"),
)


# ─── Input controls ─────────────────────────────────────────────────────────
# (operation, exact phrases, regex)
INPUT_TABLE: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("copy", ("copy this", "copy", "copy text"),
     r"^(?:copy(?:\s+(?:this|text))?)$"),

    ("paste", ("paste this", "paste", "paste text"),
     r"^(?:paste(?:\s+(?:this|text))?)$"),

    ("select_all", ("select all", "select all text"),
     r"^select\s+all(?:\s+text)?$"),

    ("show_desktop", ("show desktop", "minimize all", "minimize all windows"),
     r"^(?:show\s+(?:the\s+)?desktop|minimi[sz]e\s+all(?:\s+windows)?)$"),

    ("task_manager", ("open task manager", "task manager", "open task view"),
     r"^(?:open\s+)?task\s+(?:manager|view)$"),

    ("switch_window", ("switch window", "alt tab", "switch application"),
     r"^(?:switch\s+(?:window|application)|alt\s*tab)$"),
)


# ═══════════════════════════════════════════════════════════════════════════
# 3. HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

def _result(
    tool: str,
    success: bool,
    message: str,
    details: Any = None,
    method: Optional[str] = None,
) -> Dict[str, Any]:
    """The standard result shape every handler returns."""
    out: Dict[str, Any] = {"tool": tool, "success": success, "message": message}
    if details is not None:
        out["details"] = details
    if method:
        out["method"] = method
    return out


#: Plugin IDs of the operating-system plugins, in priority order. The
#: Windows build ships `windows_plugin.py`, the Linux build ships
#: `linux_plugin.py`; only the one matching the host OS is registered.
_OS_PLUGIN_IDS = ("windows", "linux", "macos")


def _os_plugin():
    """Returns the operating-system plugin for the host platform."""
    from plugins.manager import plugin_manager

    for plugin_id in _OS_PLUGIN_IDS:
        plugin = plugin_manager.plugins.get(plugin_id)
        if plugin is not None:
            return plugin
    return None


def _run_windows_action(action: str, text: str) -> bool:
    """Runs an action of the shipped operating-system plugin."""
    plugin = _os_plugin()
    if not plugin or not getattr(plugin, "is_enabled", False):
        return False
    try:
        return bool(plugin.execute(action, text))
    except Exception as exc:
        logger.error("OS action '%s' failed: %s", action, exc)
        return False


_POLITE = frozenset({
    "please", "can", "could", "would", "will", "you", "hey", "hi", "hello",
    "ok", "okay", "now", "just", "lets", "let", "us", "i", "want", "need",
    "to", "try", "also", "so", "well", "um", "uh", "maybe", "right", "yeah",
    "myself", "me", "go", "ahead", "and", "then",
})


def _strip_leading(text: str, verbs: Sequence[str]) -> str:
    """Removes a leading command verb (and politeness words) from `text`."""
    words = text.strip().split()
    while words and words[0].lower().strip(".!?, ") in _POLITE:
        words.pop(0)
    if words and words[0].lower() in verbs:
        words.pop(0)
    return " ".join(words).strip(" .!?, ")


# ─── System actions ─────────────────────────────────────────────────────────
#: OS actions that the shipped Windows plugin implements better than the
#: generic system tool (it knows about sleep, sign out, brightness, ...).
_WINDOWS_ACTION_FOR: Dict[str, str] = {
    "volume_unmute": "windows.volume_control",
    "volume_mute": "windows.volume_control",
    "set_volume": "windows.volume_control",
    "restore": "windows.window_control",
    "brightness_up": "windows.brightness",
    "brightness_down": "windows.brightness",
    "sign_out": "windows.system_action",
    "sleep": "windows.system_action",
    "restart": "windows.system_action",
    "shutdown": "windows.system_action",
    "cancel_shutdown": "windows.system_action",
}


def handle_system_action(ctx: CommandContext) -> Dict[str, Any]:
    """Performs an OS action: volume, lock, screenshot, window, power."""
    from computer_use.system_tools import system_action

    action = ctx.slot("action")
    if not action:
        return _result("system_action", False, "No system action was recognised.")

    label = action.replace("_", " ")

    # Restoring a window is not an OS-plugin action, so it is done
    # directly through the platform layer.
    if action == "restore":
        try:
            from core.platform import restore_window

            ok = restore_window()
            return _result(
                "system_action", ok,
                "Restored the active window." if ok else "Could not restore the active window.",
            )
        except Exception as exc:
            logger.error("Restore window failed: %s", exc)
            return _result("system_action", False, "Could not restore the active window.")

    backend = ctx.slot("backend") or "system"

    if backend == "windows":
        windows_action = _WINDOWS_ACTION_FOR.get(action, "windows.system_action")
        ok = _run_windows_action(windows_action, ctx.text)
        return _result(
            windows_action, ok,
            f"Executed '{label}'." if ok else f"Could not execute '{label}'.",
        )

    res = system_action(action)
    return _result(
        "system_action",
        bool(res.get("success")),
        res.get("message") or f"Executed '{label}'.",
        res,
    )


# ─── Windows tool bridge ────────────────────────────────────────────────────
def handle_windows_tool(ctx: CommandContext) -> Dict[str, Any]:
    """Runs one of the shipped Windows system tools."""
    action = ctx.slot("action")
    message = ctx.slot("message") or "Opened the Windows tool."
    ok = _run_windows_action(action, ctx.text)
    return _result(action, ok, message if ok else f"Could not run '{action}'.")


# ─── Settings ───────────────────────────────────────────────────────────────
def handle_open_settings(ctx: CommandContext) -> Dict[str, Any]:
    """Opens a Windows Settings deep link."""
    from computer_use.system_tools import open_settings

    page = ctx.slot("page", "").strip()
    res = open_settings(page)

    # The core catalogue only knows the common pages. Anything rarer
    # (recovery, hotspot, ...) lives in the richer Windows plugin list.
    if page and not _known_settings_page(page):
        if _run_windows_action("windows.open_settings", page):
            return _result("open_settings", True, f"Opened the {page.title()} Settings page.")

    return _result(
        "open_settings",
        bool(res.get("success")),
        res.get("message") or "Opened Windows Settings.",
        res,
    )


def _known_settings_page(page: str) -> bool:
    """True when the core catalogue can resolve this settings page."""
    from computer_use.system_tools import SETTINGS_PAGES

    clean = page.lower().strip(" .!?,_-")
    if not clean or clean in ("settings", "windows settings", "system settings",
                              "settings app"):
        return True
    return any(
        re.search(rf"\b{re.escape(key)}\b", clean, re.IGNORECASE)
        for key in SETTINGS_PAGES
    )


# ─── Application launching ──────────────────────────────────────────────────
def handle_open_application(ctx: CommandContext) -> Dict[str, Any]:
    """Launches a desktop application by name."""
    from computer_use.system_tools import open_application

    name = ctx.slot("name", "").strip()
    if not name or name.lower() in ("it", "that", "this", "them", "there"):
        return _result("open_application", False, "Which application should I open?")

    res = open_application(name)
    return _result(
        "open_application",
        bool(res.get("success")),
        res.get("message") or f"Launched '{name}'.",
        res,
    )


# ─── Websites ───────────────────────────────────────────────────────────────
def handle_open_website(ctx: CommandContext) -> Dict[str, Any]:
    """Opens a known website by name."""
    from computer_use.system_tools import open_web_or_search

    site = ctx.slot("site", "").strip()
    res = open_web_or_search(query="", site_target=site)
    return _result(
        "open_web_or_search",
        bool(res.get("success")),
        res.get("message") or f"Opened {site.title()}.",
        res,
    )


# ─── Folders ────────────────────────────────────────────────────────────────
def handle_open_folder(ctx: CommandContext) -> Dict[str, Any]:
    """Opens a folder or location on disk."""
    from computer_use.system_tools import open_path

    path = ctx.slot("path", "").strip()
    if not path:
        return _result("open_path", False, "Which folder should I open?")

    res = open_path(path)
    if not res.get("success"):
        return _result("open_path", False, res.get("message") or f"Could not open '{path}'.", res)

    return _result("open_path", True, res.get("message") or f"Opened '{path}'.", res)


# ─── Dictation ──────────────────────────────────────────────────────────────
def handle_type_text(ctx: CommandContext) -> Dict[str, Any]:
    """Types a literal string into whatever window is focused."""
    from computer_use.system_tools import type_text

    content = ctx.slot("content", "").strip()
    if not content:
        return _result("type_text", False, "What should I type?")

    res = type_text(content)
    return _result(
        "type_text",
        bool(res.get("success")),
        res.get("message") or "Typed text.",
        res,
    )


# ─── Diagnostics ────────────────────────────────────────────────────────────
def handle_diagnostics(ctx: CommandContext) -> Dict[str, Any]:
    """Reports RAM / CPU / battery / clipboard state."""
    from computer_use.context_inspector import context_inspector

    metric = ctx.slot("metric", "ram")

    if metric == "clipboard":
        clip = context_inspector.get_clipboard_text()
        message = (
            f"Clipboard content: '{clip[:120]}...'" if len(clip) > 120
            else (f"Clipboard content: '{clip}'" if clip else "Clipboard is currently empty.")
        )
        return _result("clipboard_reader", True, message, {"clipboard": clip})

    if metric == "battery":
        info = context_inspector.get_battery_and_power_info()
        return _result("context_inspector", True,
                       info.get("message", "Battery information retrieved."), info)

    info = context_inspector.get_top_resource_consumers(count=3)
    if metric == "cpu":
        names = ", ".join(
            f"{p['name']} ({p['cpu']}%)"
            for p in info.get("top_cpu", []) if p.get("cpu")
        )
        message = f"Top CPU consumers: {names}" if names else "CPU usage is low across active processes."
    else:
        names = ", ".join(
            f"{p['name']} ({p['ram_mb']} MB)" for p in info.get("top_ram", [])
        )
        message = f"Top RAM consumers: {names}"
    return _result("context_inspector", True, message, info)


# ─── Developer tools ────────────────────────────────────────────────────────
def handle_dev_git(ctx: CommandContext) -> Dict[str, Any]:
    """Runs a git operation in the current repository."""
    from computer_use.dev_tools import dev_tools

    operation = ctx.slot("operation", "status")

    if operation == "status":
        return _result("dev_tools_git_status", True, dev_tools.git_status())
    if operation == "branch":
        return _result("dev_tools_git_branch", True, dev_tools.git_branch())
    if operation == "pull":
        return _result("dev_tools_git_pull", True, dev_tools.git_pull())
    if operation == "commit":
        res = dev_tools.git_commit("Committed via Privacy68 voice command")
        return _result(
            "dev_tools_git_commit",
            bool(res.get("success")),
            "Committed changes to repository." if res.get("success")
            else f"Commit failed: {res.get('output', '')}",
        )
    if operation == "push":
        res = dev_tools.smart_git_push_workflow()
        return _result(
            "dev_tools_smart_git_push",
            bool(res.get("success")),
            res.get("message", "Pushed changes to GitHub."),
        )

    return _result("dev_tools_git_status", False, f"Unknown git operation '{operation}'.")


def handle_dev_vscode(ctx: CommandContext) -> Dict[str, Any]:
    """Opens the current project in Visual Studio Code."""
    from computer_use.dev_tools import dev_tools

    res = dev_tools.open_in_vscode()
    return _result(
        "dev_tools_vscode",
        bool(res.get("success")),
        res.get("message", "Opened VS Code."),
    )


# ─── Input controls ─────────────────────────────────────────────────────────
def handle_input_control(ctx: CommandContext) -> Dict[str, Any]:
    """Keyboard / clipboard shortcuts."""
    from computer_use.input_controller import input_controller

    operation = ctx.slot("operation", "")
    actions = {
        "copy": (input_controller.copy, "input_copy", "Copied to clipboard."),
        "paste": (input_controller.paste, "input_paste", "Pasted."),
        "select_all": (input_controller.select_all, "input_select_all", "Selected all."),
        "show_desktop": (input_controller.show_desktop, "input_show_desktop", "Showing desktop."),
        "task_manager": (input_controller.open_task_manager, "input_task_manager", "Opened Task Manager."),
        "switch_window": (input_controller.switch_window_alt_tab, "input_switch_window", "Switched window."),
    }

    entry = actions.get(operation)
    if not entry:
        return _result("input_control", False, f"Unknown input operation '{operation}'.")

    func, tool, message = entry
    func()
    return _result(tool, True, message)


# ─── Weather ────────────────────────────────────────────────────────────────
def handle_weather(ctx: CommandContext) -> Dict[str, Any]:
    """Fetches the live weather for a city."""
    import urllib.parse
    import urllib.request

    city = ctx.slot("city", "").strip()
    try:
        target = urllib.parse.quote(city) if city else ""
        url = f"https://wttr.in/{target}?format=%C:+%t+(humidity+%h,+wind+%w)&m"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"}, method="GET")
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = resp.read().decode("utf-8").strip()
            if data:
                prefix = f"Weather in {city.title()}: " if city else "Local Weather: "
                message = f"{prefix}{data}"
                logger.info("[API LANE] %s", message)
                return _result("api_weather", True, message, {"weather": data, "city": city})
    except Exception as exc:
        logger.warning("[API LANE] Weather API call failed: %s", exc)

    return _result("api_weather", False, "Could not retrieve weather information at this time.")


# ─── Public IP ──────────────────────────────────────────────────────────────
def handle_ip_info(ctx: CommandContext) -> Dict[str, Any]:
    """Fetches the machine's public IP address."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://api.ipify.org?format=json",
            headers={"User-Agent": "PRIVACY68/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ip = data.get("ip", "unknown")
            message = f"Your public IP address is {ip}."
            logger.info("[API LANE] %s", message)
            return _result("api_ip_info", True, message, {"ip": ip})
    except Exception as exc:
        logger.warning("[API LANE] IP info API failed: %s", exc)

    return _result("api_ip_info", False, "Could not determine public IP address.")


# ─── Web search / compound browser ──────────────────────────────────────────
def handle_web_search(ctx: CommandContext) -> Dict[str, Any]:
    """Runs a web search, optionally scoped to a site or a browser."""
    from computer_use.system_tools import open_web_or_search

    query = ctx.slot("query", "").strip()
    site = ctx.slot("site", "").strip() or None
    browser = ctx.slot("browser", "").strip() or None

    if not query and not site and not browser:
        return _result("open_web_or_search", False, "What should I search for?")

    res = open_web_or_search(query=query, site_target=site, browser=browser)
    return _result(
        "open_web_or_search",
        bool(res.get("success")),
        res.get("message") or (f"Searched for '{query}'." if query else "Opened browser."),
        res,
    )


# ─── File system ────────────────────────────────────────────────────────────
def handle_create_folder(ctx: CommandContext) -> Dict[str, Any]:
    """Creates a folder."""
    from computer_use.system_tools import create_folder

    name = ctx.slot("name", "").strip()
    path = ctx.slot("path", "").strip()
    if not name:
        return _result("create_folder", False, "What should the folder be called?")

    res = create_folder(path=path, name=name)
    return _result(
        "create_folder",
        bool(res.get("success")),
        res.get("message") or f"Created folder '{name}'.",
        res,
    )


def handle_create_file(ctx: CommandContext) -> Dict[str, Any]:
    """Creates a file, optionally with content."""
    from computer_use.system_tools import create_file

    name = ctx.slot("name", "").strip()
    path = ctx.slot("path", "").strip()
    content = ctx.slot("content", "").strip()
    if not name:
        return _result("create_file", False, "What should the file be called?")

    res = create_file(path=path, name=name, content=content)
    return _result(
        "create_file",
        bool(res.get("success")),
        res.get("message") or f"Created file '{name}'.",
        res,
    )


def handle_rename_item(ctx: CommandContext) -> Dict[str, Any]:
    """Renames a file or a folder."""
    from computer_use.system_tools import rename_item

    source = ctx.slot("source", "").strip()
    new_name = ctx.slot("name", "").strip()
    path = ctx.slot("path", "").strip() or None
    if not source or not new_name:
        return _result("rename_item", False, "Which item should I rename, and to what?")

    res = rename_item(source_name_or_path=source, new_name=new_name, base_directory=path)
    return _result(
        "rename_item",
        bool(res.get("success")),
        res.get("message") or f"Renamed '{source}' to '{new_name}'.",
        res,
    )


def handle_delete_item(ctx: CommandContext) -> Dict[str, Any]:
    """Deletes a file — a sensitive action that needs a voice confirmation."""
    import os

    from computer_use.security_guard import security_guard
    from computer_use.system_tools import delete_file, resolve_path

    target = ctx.slot("name", "").strip()
    path = ctx.slot("path", "").strip()
    if not target:
        return _result("delete_file", False, "What should I delete?")

    full_path = os.path.join(resolve_path(path), target) if path else resolve_path(target)

    executed, message, details = security_guard.request_execution(
        "delete_file",
        delete_file,
        args=(full_path,),
        description=f"delete '{target}'",
    )
    if not executed:
        # Queued for confirmation — the user must say "yes" to proceed.
        return _result("delete_file", False, message, details, method="security_guard")

    res = details if isinstance(details, dict) else {}
    return _result(
        "delete_file",
        bool(res.get("success")),
        res.get("message") or f"Deleted '{target}'.",
        res,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. SLOT EXTRACTORS (used when the matcher did not capture the arguments)
# ═══════════════════════════════════════════════════════════════════════════

def _fallback_system_action(text: str) -> Dict[str, str]:
    low = normalize(text)
    for action, backend, phrases, _pattern in SYSTEM_ACTION_TABLE:
        for phrase in phrases:
            if normalize(phrase) == low:
                return {"action": action, "backend": backend}
    return {}


def _fallback_settings(text: str) -> Dict[str, str]:
    page = _strip_leading(text, ("open", "go to", "show", "launch", "switch to", "view"))
    page = re.sub(r"\b(?:settings|page|tab)\b\s*$", "", page).strip(" .!?, ")
    return {"page": page}


def _fallback_application(text: str) -> Dict[str, str]:
    name = _strip_leading(text, ("open", "launch", "start", "run", "execute"))
    return {"name": name}


def _fallback_website(text: str) -> Dict[str, str]:
    found = re.search(rf"\b({SITE_RE})\b", text, re.IGNORECASE)
    return {"site": found.group(1)} if found else {}


def _fallback_folder(text: str) -> Dict[str, str]:
    path = _strip_leading(text, ("open", "show", "explore", "navigate to", "go to"))
    path = re.sub(r"\b(?:folder|directory)\b", "", path).strip(" .!?, ")
    return {"path": path}


def _fallback_type_text(text: str) -> Dict[str, str]:
    content = _strip_leading(text, ("type", "write", "dictate", "enter", "say"))
    content = re.sub(r"^out\s+", "", content, flags=re.IGNORECASE)
    return {"content": content}


def _fallback_diagnostic(text: str) -> Dict[str, str]:
    low = normalize(text)
    for metric, phrases, _pattern in DIAGNOSTIC_TABLE:
        if any(normalize(p) == low for p in phrases):
            return {"metric": metric}
    for metric, _phrases, pattern in DIAGNOSTIC_TABLE:
        if re.search(pattern, low, re.IGNORECASE):
            return {"metric": metric}
    return {}


def _fallback_git(text: str) -> Dict[str, str]:
    low = normalize(text)
    for operation, phrases, _pattern in GIT_TABLE:
        if any(normalize(p) == low for p in phrases):
            return {"operation": operation}
    for operation, _phrases, pattern in GIT_TABLE:
        if re.search(pattern, low, re.IGNORECASE):
            return {"operation": operation}
    return {}


def _fallback_input(text: str) -> Dict[str, str]:
    low = normalize(text)
    for operation, phrases, _pattern in INPUT_TABLE:
        if any(normalize(p) == low for p in phrases):
            return {"operation": operation}
    for operation, _phrases, pattern in INPUT_TABLE:
        if re.search(pattern, low, re.IGNORECASE):
            return {"operation": operation}
    return {}


def _fallback_web(text: str) -> Dict[str, str]:
    slots: Dict[str, str] = {}
    found = re.search(rf"\b({BROWSER_RE})\b", text, re.IGNORECASE)
    if found:
        slots["browser"] = found.group(1)
    found = re.search(rf"\b({SITE_RE})\b", text, re.IGNORECASE)
    if found:
        slots["site"] = found.group(1)
    query = re.sub(
        r"\b(?:search(?:\s+for)?|look\s+up|google|find|play|watch|listen\s+to)\s+",
        "", text, flags=re.IGNORECASE,
    ).strip()
    slots["query"] = query
    return slots


def _fallback_create_folder(text: str) -> Dict[str, str]:
    return _fallback_named_item(text, ("folder", "directory"))


def _fallback_create_file(text: str) -> Dict[str, str]:
    return _fallback_named_item(text, ("file", "document"))


def _fallback_named_item(text: str, nouns: Sequence[str]) -> Dict[str, str]:
    """Extracts the name, the target folder and the body of a create command."""
    noun_re = _alt(nouns)
    slots: Dict[str, str] = {}

    named = re.search(
        rf"\b(?:named|called|titled)\s+(?P<v>[^/\\]+?)"
        rf"(?=\s+(?:in|on|at|inside|under|with)\s+|$)",
        text, re.IGNORECASE,
    )
    if named:
        slots["name"] = named.group("v").strip()
    else:
        after = re.search(
            rf"^\s*(?:create|make|new|add)\s+(?:a\s+|an\s+)?(?:new\s+)?"
            rf"(?P<v>[^/\\]+?)\s+(?:{noun_re})\b",
            text, re.IGNORECASE,
        )
        if after:
            slots["name"] = after.group("v").strip()
        else:
            direct = re.search(
                rf"^\s*(?:create|make|new|add)\s+(?:a\s+|an\s+)?(?:new\s+)?"
                rf"(?:{noun_re})\s+(?P<v>[^/\\]+?)"
                rf"(?=\s+(?:in|on|at|inside|under|with)\s+|$)",
                text, re.IGNORECASE,
            )
            if direct:
                slots["name"] = direct.group("v").strip()

    where = re.search(
        r"\b(?:in|on|at|inside|under)\s+(?P<v>.+?)\s*$", text, re.IGNORECASE
    )
    if where:
        slots["path"] = where.group("v").strip()

    body = re.search(
        r"\bwith\s+(?:the\s+)?content\s+(?P<v>.+)$", text, re.IGNORECASE
    )
    if body:
        slots["content"] = body.group("v").strip()

    return slots


def _fallback_rename(text: str) -> Dict[str, str]:
    slots: Dict[str, str] = {}
    source = re.search(
        r"\brename\s+(?:the\s+)?(?:file|folder|item|document|directory)?\s*"
        r"(?P<v>.+?)\s+to\s+",
        text, re.IGNORECASE,
    )
    if source:
        slots["source"] = source.group("v").strip()
    else:
        changed = re.search(
            r"\bchange\s+(?:the\s+)?name\s+of\s+(?:the\s+)?(?:file|folder|item)?\s*"
            r"(?P<v>.+?)\s+to\s+",
            text, re.IGNORECASE,
        )
        if changed:
            slots["source"] = changed.group("v").strip()

    target = re.search(
        r"\bto\s+(?P<v>[^/\\]+?)(?=\s+(?:in|on|at|inside|under)\s+|$)",
        text, re.IGNORECASE,
    )
    if target:
        slots["name"] = target.group("v").strip()

    where = re.search(
        r"\b(?:in|on|at|inside|under)\s+(?P<v>.+?)\s*$", text, re.IGNORECASE
    )
    if where:
        slots["path"] = where.group("v").strip()
    return slots


def _fallback_delete(text: str) -> Dict[str, str]:
    slots: Dict[str, str] = {}
    target = re.search(
        r"\b(?:delete|remove|trash)\s+(?:the\s+)?(?:file|folder|item|directory|document)?\s*"
        r"(?P<v>[^/\\]+?)(?=\s+(?:in|on|at|inside|under|from)\s+|$)",
        text, re.IGNORECASE,
    )
    if target:
        slots["name"] = target.group("v").strip()
    where = re.search(
        r"\b(?:in|on|at|inside|under|from)\s+(?P<v>.+?)\s*$", text, re.IGNORECASE
    )
    if where:
        slots["path"] = where.group("v").strip()
    return slots


def _fallback_weather(text: str) -> Dict[str, str]:
    city = re.search(
        r"\b(?:in|for|at)\s+(?P<v>[a-zA-Z][a-zA-Z .'-]*?)\s*$", text, re.IGNORECASE
    )
    return {"city": city.group("v").strip()} if city else {}


# ═══════════════════════════════════════════════════════════════════════════
# 5. SPEC BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def _phrases_and_pattern(
    phrases: Sequence[str],
    pattern: str,
    consts: Sequence[Tuple[str, str]] = (),
    priority: int = 0,
) -> List[Matcher]:
    """Turns a phrase list and a regex into matchers."""
    matchers = [Matcher(phrase=p, consts=tuple(consts), priority=priority) for p in phrases]
    if pattern:
        matchers.append(Matcher(pattern=pattern, consts=tuple(consts), priority=priority))
    return matchers


def _build_system_action_spec() -> CommandSpec:
    matchers: List[Matcher] = []
    examples: List[str] = []
    for action, backend, phrases, pattern in SYSTEM_ACTION_TABLE:
        consts = (("action", action), ("backend", backend))
        matchers.extend(_phrases_and_pattern(phrases, pattern, consts))
        examples.extend(phrases)
    return CommandSpec(
        id="system.action",
        lane=LANE_FAST,
        intent="system_action",
        handler=handle_system_action,
        matchers=tuple(matchers),
        examples=tuple(examples),
        priority=100,
        description="Volume, lock, screenshot, window and power controls.",
        slot_extractor=_fallback_system_action,
    )


def _build_windows_tool_spec() -> CommandSpec:
    matchers: List[Matcher] = []
    examples: List[str] = []
    for action, phrases, pattern, message in WINDOWS_TOOL_TABLE:
        consts = (("action", action), ("message", message))
        matchers.extend(_phrases_and_pattern(phrases, pattern, consts))
        examples.extend(phrases)
    return CommandSpec(
        id="windows.tools",
        lane=LANE_FAST,
        intent="windows_tool",
        handler=handle_windows_tool,
        matchers=tuple(matchers),
        examples=tuple(examples),
        priority=96,
        description="Control Panel, Recycle Bin and other Windows tools.",
    )


def _build_diagnostic_spec() -> CommandSpec:
    matchers: List[Matcher] = []
    examples: List[str] = []
    for metric, phrases, pattern in DIAGNOSTIC_TABLE:
        matchers.extend(_phrases_and_pattern(phrases, pattern, (("metric", metric),)))
        examples.extend(phrases)
    return CommandSpec(
        id="system.diagnostics",
        lane=LANE_FAST,
        intent="system_diagnostics",
        handler=handle_diagnostics,
        matchers=tuple(matchers),
        examples=tuple(examples),
        priority=90,
        description="RAM, CPU, battery and clipboard diagnostics.",
        slot_extractor=_fallback_diagnostic,
    )


def _build_git_spec() -> CommandSpec:
    matchers: List[Matcher] = []
    examples: List[str] = []
    for operation, phrases, pattern in GIT_TABLE:
        matchers.extend(_phrases_and_pattern(phrases, pattern, (("operation", operation),)))
        examples.extend(phrases)
    return CommandSpec(
        id="dev.git",
        lane=LANE_FAST,
        intent="dev_git",
        handler=handle_dev_git,
        matchers=tuple(matchers),
        examples=tuple(examples),
        priority=88,
        description="Git status, branch, pull, commit and push.",
        slot_extractor=_fallback_git,
    )


def _build_input_spec() -> CommandSpec:
    matchers: List[Matcher] = []
    examples: List[str] = []
    for operation, phrases, pattern in INPUT_TABLE:
        matchers.extend(_phrases_and_pattern(phrases, pattern, (("operation", operation),)))
        examples.extend(phrases)
    return CommandSpec(
        id="input.control",
        lane=LANE_FAST,
        intent="input_control",
        handler=handle_input_control,
        matchers=tuple(matchers),
        examples=tuple(examples),
        priority=97,
        description="Clipboard, selection and window switching shortcuts.",
        slot_extractor=_fallback_input,
    )


def _build_settings_spec() -> CommandSpec:
    from computer_use.system_tools import SETTINGS_PAGES

    # A page that is also an application name ("camera") belongs to the
    # application, not to the settings page.
    known = sorted(
        (set(SETTINGS_PAGES) | {
            "recovery", "hotspot", "mobile hotspot", "default apps", "home",
            "printers", "printers and scanners", "personalization",
            "optional features", "about", "date and time", "region", "language",
            "windows update", "delivery optimization", "system", "devices",
        }) - set(APPS),
        key=len, reverse=True,
    )
    known_re = _alt(known)

    matchers = [
        Matcher(phrase=p) for p in (
            "open settings", "settings", "windows settings", "go to settings",
            "open windows settings", "open system settings", "system settings",
            "open the settings app", "launch settings", "show system settings",
        )
    ]
    matchers.append(Matcher(
        pattern=rf"^\s*(?:please\s+)?(?:open|go\s+to|show|launch|switch\s+to|view)\s+"
                  rf"(?:the\s+)?settings(?:\s+app)?\s*$",
    ))
    matchers.append(Matcher(
        pattern=rf"^\s*(?:please\s+)?(?:open|go\s+to|show|launch|switch\s+to|view)\s+"
                  rf"(?:the\s+)?(?P<page>[\w&.\-]+(?:\s+[\w&.\-]+)*?)\s+"
                  rf"(?:settings|page|tab)\s*$",
    ))
    matchers.append(Matcher(
        pattern=rf"^\s*(?:please\s+)?(?:open|go\s+to|show|launch|switch\s+to|view)\s+"
                  rf"(?:the\s+)?(?P<page>{known_re})\s*$",
    ))

    return CommandSpec(
        id="system.settings",
        lane=LANE_FAST,
        intent="open_settings",
        handler=handle_open_settings,
        matchers=tuple(matchers),
        examples=(
            "open settings", "go to settings", "windows settings", "settings",
            "go to system", "go to bluetooth", "go to sound tab", "switch to display",
            "open bluetooth settings", "open wifi settings", "open display settings",
            "open sound settings", "open network settings", "open windows update",
            "open privacy settings", "open apps settings", "open personalization",
            "open time and language", "open storage settings", "open mouse settings",
            "open keyboard settings", "open accounts settings", "open about settings",
            "open gaming settings", "show system settings", "launch settings",
            "switch to sound", "switch to bluetooth",
        ),
        priority=85,
        description="Opens a Windows Settings page.",
        slot_extractor=_fallback_settings,
    )


def _build_website_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|go\s+to|visit|launch|browse)\s+"
                      rf"(?:the\s+)?(?P<site>{SITE_RE})\s*$",
        )
    ]
    return CommandSpec(
        id="system.website",
        lane=LANE_FAST,
        intent="open_website",
        handler=handle_open_website,
        matchers=tuple(matchers),
        examples=(
            "open youtube", "go to youtube", "launch youtube", "open github",
            "go to github", "launch github", "open reddit", "go to reddit",
            "open chatgpt", "go to chatgpt", "open twitter", "open wikipedia",
            "open gmail", "go to gmail", "open linkedin", "open netflix",
            "visit youtube", "visit github",
        ),
        priority=75,
        description="Opens a well-known website.",
        slot_extractor=_fallback_website,
    )


def _build_folder_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|show|explore|go\s+to|navigate\s+to)\s+"
                      rf"(?:the\s+|my\s+)?(?P<path>{FOLDER_RE})\s*$",
        ),
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|show|explore|go\s+to|navigate\s+to)\s+"
                      rf"(?:the\s+|my\s+)?(?P<path>[a-z])\s*drive\s*$",
        ),
    ]
    return CommandSpec(
        id="system.folder",
        lane=LANE_FAST,
        intent="open_folder",
        handler=handle_open_folder,
        matchers=tuple(matchers),
        examples=(
            "open downloads", "open my downloads", "open downloads folder",
            "open desktop", "open desktop folder", "open my documents",
            "open documents folder", "open pictures", "open pictures folder",
            "open music folder", "open videos folder", "open this pc",
            "open recycle bin", "open d drive", "open c drive", "explore downloads",
        ),
        priority=72,
        description="Opens a known folder or drive.",
        slot_extractor=_fallback_folder,
    )


def _build_application_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|launch|start|run|execute)\s+"
                      rf"(?:the\s+)?(?P<name>{APP_RE})\s*$",
        )
    ]
    return CommandSpec(
        id="system.application",
        lane=LANE_FAST,
        intent="open_application",
        handler=handle_open_application,
        matchers=tuple(matchers),
        examples=(
            "open chrome", "launch chrome", "start chrome", "open notepad",
            "launch notepad", "open calculator", "launch calculator",
            "open vs code", "launch vs code", "open brave", "launch brave browser",
            "open firefox", "open edge", "open spotify", "launch vlc",
            "open file explorer", "start word", "open excel",
            "launch powershell", "open terminal", "open cmd", "launch slack",
            "open discord", "open paint",
        ),
        priority=76,
        description="Launches a desktop application.",
        slot_extractor=_fallback_application,
    )


def register_installed_apps() -> int:
    """
    Teaches the fast lane about the applications installed on this computer.

    The catalogue ships a list of common application names. This adds every
    OTHER application the user actually has, so "open <anything>" works
    without a plugin.

    The names are merged into the existing application command instead of
    becoming a second one: an intent must have exactly one owner, otherwise
    the taxonomy and the classifier disagree. Returns the number of
    applications added.
    """
    from core.apps import app_index

    installed = sorted({e.name.lower() for e in app_index.all() if e.source != "path"})
    fresh = [name for name in installed if name not in APPS]
    if not fresh:
        return 0

    current = registry.get("system.application")
    pattern = rf"^\s*(?:please\s+)?(?:open|launch|start|run|execute)\s+" \
              rf"(?:the\s+)?(?P<name>{_alt(list(APPS) + fresh)})\s*$"

    # Re-registering would append a second copy of the pattern.
    registry.unregister("system.application")
    registry.register(CommandSpec(
        id="system.application",
        lane=LANE_FAST,
        intent="open_application",
        handler=handle_open_application,
        matchers=(Matcher(pattern=pattern),),
        examples=current.examples if current else (),
        priority=current.priority if current else 76,
        description="Launches a desktop application.",
        slot_extractor=_fallback_application,
    ))
    logger.info("Fast lane now knows %d more installed applications.", len(fresh))
    return len(fresh)


def _build_type_text_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=r"^\s*(?:please\s+)?(?:type|dictate)\s+"
                    r"(?P<content>.+?)\s*$",
        )
    ]
    return CommandSpec(
        id="system.type_text",
        lane=LANE_FAST,
        intent="type_text",
        handler=handle_type_text,
        matchers=tuple(matchers),
        examples=(
            "type hello world", "type this text out", "write out my notes",
            "type please confirm your appointment", "write hello how are you",
            "type testing 1 2 3", "type python programming",
        ),
        priority=65,
        description="Types a literal string into the focused window.",
        slot_extractor=_fallback_type_text,
    )


def _build_vscode_spec() -> CommandSpec:
    matchers = [
        Matcher(pattern=r"^\s*(?:please\s+)?(?:open\s+(?:the\s+)?project\s+in\s+vs\s*code"
                       r"|open\s+(?:it\s+)?in\s+vs\s*code|open\s+in\s+vscode"
                       r"|open\s+in\s+vs\s+code)\s*$"),
    ]
    return CommandSpec(
        id="dev.vscode",
        lane=LANE_FAST,
        intent="dev_open_vscode",
        handler=handle_dev_vscode,
        matchers=tuple(matchers),
        examples=("open project in vs code", "open in vs code", "open in vscode"),
        priority=87,
        description="Opens the current project in Visual Studio Code.",
    )


def _build_weather_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=r"\b(?:what(?:'s|\s+is)\s+the\s+weather|weather\s+today"
                    r"|check\s+weather|how(?:'s|\s+is)\s+the\s+weather"
                    r"|temperature\s+outside|is\s+it\s+raining"
                    r"|weather\s+forecast)\b",
        )
    ]
    return CommandSpec(
        id="api.weather",
        lane=LANE_API,
        intent="api_weather",
        handler=handle_weather,
        matchers=tuple(matchers),
        examples=(
            "what is the weather in Tokyo", "what is the weather", "what's the weather today",
            "check the weather", "how is the weather in London", "is it raining outside",
            "temperature outside today", "what is the weather forecast",
            "check weather in New York", "weather today", "check weather",
            "how is the weather", "is it raining",
        ),
        priority=50,
        description="Live weather for a city.",
        slot_extractor=_fallback_weather,
    )


def _build_ip_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=r"\b(?:what(?:'s|\s+is)\s+my\s+(?:public\s+)?ip(?:\s+address)?"
                    r"|check\s+my\s+ip|my\s+public\s+ip|check\s+ip\s+address"
                    r"|public\s+ip\s+address)\b",
        )
    ]
    return CommandSpec(
        id="api.ip_info",
        lane=LANE_API,
        intent="api_ip_info",
        handler=handle_ip_info,
        matchers=tuple(matchers),
        examples=(
            "what is my ip", "what's my ip", "check my ip", "my public ip",
            "check ip address", "what is my public ip address", "what is my ip address",
        ),
        priority=50,
        description="The machine's public IP address.",
    )


def _build_web_search_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:search(?:\s+for)?|look\s+up|google|find)\s+"
                      rf"(?P<query>.+?)(?:\s+(?:on|in|at|with|using|via)\s+"
                      rf"(?P<site>{SITE_RE}))?\s*$",
        ),
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:in|using|with)\s+(?P<browser>{BROWSER_RE})\s+"
                      rf"(?:search(?:\s+for)?|look\s+up|google|find)\s+(?P<query>.+?)\s*$",
        ),
        Matcher(
            pattern=r"^\s*(?:please\s+)?(?:open|visit|go\s+to)\s+"
                    r"(?P<query>https?://\S+)\s*$",
        ),
    ]
    return CommandSpec(
        id="api.web_search",
        lane=LANE_API,
        intent="web_search",
        handler=handle_web_search,
        matchers=tuple(matchers),
        examples=(
            "search machine learning algorithms on google", "search python tutorials on google",
            "search quantum computing on wikipedia", "search for latest news on google",
            "search recipes on google", "google best lightweight laptops",
            "search python async await examples", "search stock market today on google",
            "search how to make pizza on google",
        ),
        priority=45,
        description="Searches the web.",
        slot_extractor=_fallback_web,
    )


def _build_compound_browser_spec() -> CommandSpec:
    matchers = [
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?"
                      rf"(?P<browser>{BROWSER_RE})\s+and\s+"
                      rf"(?:search(?:\s+for)?|go\s+to|visit|navigate\s+to|play|watch)\s+"
                      rf"(?P<query>.+?)\s*$",
        ),
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:play|watch|listen\s+to)\s+(?P<query>.+?)\s+"
                      rf"on\s+(?P<site>{SITE_RE})\s*$",
        ),
        Matcher(
            pattern=rf"^\s*(?:please\s+)?(?:open|go\s+to|visit|launch)\s+(?:the\s+)?"
                      rf"(?P<site>{SITE_RE})\s+and\s+(?:search(?:\s+for)?|play|watch)\s+"
                      rf"(?P<query>.+?)\s*$",
        ),
    ]
    return CommandSpec(
        id="api.compound_browser",
        lane=LANE_API,
        intent="compound_browser",
        handler=handle_web_search,
        matchers=tuple(matchers),
        examples=(
            "open chrome and search for youtube", "open chrome and go to reddit.com",
            "open youtube and search for lofi beats", "play believer on youtube",
            "in chrome search for python tutorials",
            "open brave and search for python tutorials on youtube",
            "open edge and search for weather", "open firefox and go to github.com",
            "open youtube and search for rock music", "play shape of you on youtube",
        ),
        priority=44,
        description="Opens a browser and runs a search in one step.",
        slot_extractor=_fallback_web,
    )


def _build_create_folder_spec() -> CommandSpec:
    return CommandSpec(
        id="fs.create_folder",
        lane=LANE_API,
        intent="create_folder",
        handler=handle_create_folder,
        matchers=(
            Matcher(pattern=r"^\s*(?:please\s+)?(?:create|make|new|add)\s+"
                            r"(?:a\s+|an\s+)?(?:new\s+)?(?:folder|directory)\b"),
        ),
        examples=(
            "create folder test in downloads", "create a folder named test_project in downloads",
            "Create a folder named Privacy on Desktop", "Create MCA folder in downloads",
            "create new folder my_project in documents", "make a folder called assets in desktop",
            "create directory backups in d drive", "create a new directory named temp in c drive",
        ),
        priority=40,
        description="Creates a folder.",
        slot_extractor=_fallback_create_folder,
    )


def _build_create_file_spec() -> CommandSpec:
    return CommandSpec(
        id="fs.create_file",
        lane=LANE_API,
        intent="create_file",
        handler=handle_create_file,
        matchers=(
            Matcher(pattern=r"^\s*(?:please\s+)?(?:create|make|new|add)\s+"
                            r"(?:a\s+|an\s+)?(?:new\s+)?(?:file|document)\b"),
        ),
        examples=(
            "create file sample.txt in downloads", "create a file called notes.txt in desktop",
            "make a new file report.docx in documents", "create file todo.txt with content buy groceries",
            "create document draft.md in my project",
        ),
        priority=40,
        description="Creates a file.",
        slot_extractor=_fallback_create_file,
    )


def _build_rename_spec() -> CommandSpec:
    return CommandSpec(
        id="fs.rename",
        lane=LANE_API,
        intent="rename_item",
        handler=handle_rename_item,
        matchers=(
            Matcher(pattern=r"^\s*(?:please\s+)?(?:rename|change\s+the\s+name\s+of|"
                            r"change\s+name\s+of)\b"),
        ),
        examples=(
            "rename file old_doc.txt to final_doc.txt in downloads",
            "rename file old_doc.txt to final_doc.txt",
            "rename sample.txt to test.txt in documents",
            "rename folder temp to archive in desktop",
            "change name of file data.csv to clean_data.csv",
            "rename file old.txt to new.txt",
            "rename item draft.txt to published.txt",
        ),
        priority=40,
        description="Renames a file or folder.",
        slot_extractor=_fallback_rename,
    )


def _build_delete_spec() -> CommandSpec:
    return CommandSpec(
        id="fs.delete",
        lane=LANE_API,
        intent="delete_item",
        handler=handle_delete_item,
        matchers=(
            Matcher(pattern=r"^\s*(?:please\s+)?(?:delete|remove|trash)\b"),
        ),
        examples=(
            "delete file test.txt in downloads", "delete the file notes.txt from desktop",
            "remove folder temp from downloads", "delete old logs file in documents",
            "delete file test.txt", "remove file notes.txt from documents",
            "delete folder temp in downloads",
        ),
        priority=40,
        description="Deletes a file (asks for confirmation first).",
        slot_extractor=_fallback_delete,
    )


def _build_llm_specs() -> Tuple[CommandSpec, ...]:
    """
    Intents that belong to the LLM lane.

    They carry no handler: the dispatcher recognises them, decides that
    only a language model can answer, and hands over. Registering them
    keeps the intent taxonomy complete, so the classifier has a label for
    "this is a conversation, not a command".
    """
    return (
        CommandSpec(
            id="llm.reasoning",
            lane=LANE_LLM,
            intent="llm_reasoning",
            handler=None,
            examples=(
                "explain quantum computing to me",
                "who was the first president of the united states",
                "write a python function to parse json",
                "summarize this article for me",
                "how do neural networks work",
                "write a poem about artificial intelligence",
                "help me debug this error in my react code",
                "what is the difference between processes and threads",
                "draft an email to my manager requesting time off",
                "give me 5 business ideas in automation",
                "could you please capture what is on my screen right now",
                "what is the difference between a process and a thread",
                "tell me a joke about programmers",
            ),
            priority=10,
            description="Open-ended questions that need a language model.",
        ),
        CommandSpec(
            id="llm.plugin_tool",
            lane=LANE_LLM,
            intent="plugin_tool_call",
            handler=None,
            examples=(
                "send a message to mom saying hello",
                "create a powerpoint presentation with 5 slides about space",
                "generate an image of a cybernetic tiger",
                "send it to mom",
                "send hi to mom",
            ),
            priority=10,
            description="A plugin action chosen by a language model.",
        ),
        CommandSpec(
            id="llm.unknown",
            lane=LANE_LLM,
            intent="unknown",
            handler=None,
            examples=(
                "asdkjh askdjh",
                "flurble wozzle",
                "xyzzy plugh",
            ),
            priority=9,
            description="Anything the assistant does not understand.",
        ),
        CommandSpec(
            id="plugin.fast_intent",
            lane=LANE_FAST,
            intent="plugin_fast_intent",
            handler=None,
            examples=(
                "new tab in chrome",
                "close tab in chrome",
                "next track in spotify",
                "previous track in spotify",
                "pause music in spotify",
            ),
            priority=68,
            description="A plugin's own fast intent (handled by the plugin layer).",
        ),
    )


def build_registry() -> CommandRegistry:
    """Fills the shared registry with every built-in command."""
    specs = (
        _build_system_action_spec(),
        _build_windows_tool_spec(),
        _build_input_spec(),
        _build_diagnostic_spec(),
        _build_vscode_spec(),
        _build_git_spec(),
        _build_settings_spec(),
        _build_website_spec(),
        _build_folder_spec(),
        _build_application_spec(),
        _build_type_text_spec(),
        _build_weather_spec(),
        _build_ip_spec(),
        _build_web_search_spec(),
        _build_compound_browser_spec(),
        _build_create_folder_spec(),
        _build_create_file_spec(),
        _build_rename_spec(),
        _build_delete_spec(),
    ) + _build_llm_specs()

    registry.register_all(specs)
    logger.info(
        "Command catalogue loaded: %d commands, %d intents.",
        len(registry.all()), len(registry.intents()),
    )
    return registry


# Build on import so every consumer sees a populated registry.
build_registry()

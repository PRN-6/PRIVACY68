import re
import logging
from typing import Any, Dict, Optional

from computer_use.system_tools import (
    open_settings,
    open_web_or_search,
    open_application,
    open_path,
    system_action,
    type_text,
    SETTINGS_PAGES,
)

logger = logging.getLogger("PRIVACY68.FastLane")

# ─── Deterministic system action shortcuts (<2ms Win32 OS calls) ─────────────
SYSTEM_ACTION_KEYWORDS: Dict[str, str] = {
    "lock the computer": "lock",
    "lock computer": "lock",
    "lock screen": "lock",
    "lock pc": "lock",
    "lock my pc": "lock",
    "mute volume": "volume_mute",
    "unmute volume": "volume_mute",
    "mute audio": "volume_mute",
    "mute": "volume_mute",
    "increase volume": "volume_up",
    "volume up": "volume_up",
    "turn up volume": "volume_up",
    "turn up the volume": "volume_up",
    "louder": "volume_up",
    "decrease volume": "volume_down",
    "volume down": "volume_down",
    "turn down volume": "volume_down",
    "turn down the volume": "volume_down",
    "lower volume": "volume_down",
    "quieter": "volume_down",
    "take screenshot": "screenshot",
    "take a screenshot": "screenshot",
    "capture screen": "screenshot",
    "close this window": "close_window",
    "close current window": "close_window",
    "close active window": "close_window",
    "close window": "close_window",
    "maximize window": "maximize",
    "maximize this window": "maximize",
    "full screen window": "maximize",
    "minimize window": "minimize",
    "minimize this window": "minimize",
    "restore window": "restore",
    "press enter": "enter",
    "hit enter": "enter",
    "press tab": "tab",
    "hit tab": "tab",
}

POPULAR_SITES = frozenset({
    "youtube", "github", "chatgpt", "openai", "reddit",
    "twitter", "wikipedia", "gmail", "linkedin", "netflix", "spotify"
})

FOLDER_KEYWORDS = frozenset({
    "folder", "directory", "drive", "downloads", "desktop", "documents",
    "pictures", "music", "videos", "this pc", "my computer", "home",
    "user", "temp", "recycle bin", "appdata", "program files",
})

# Pre-compiled pattern for fast system action matching
_SYSTEM_ACTIONS_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(SYSTEM_ACTION_KEYWORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Windows system tool regex checks (control panel, task manager, etc.)
WINDOWS_BRIDGE_CHECKS = (
    ("windows.control_panel", re.compile(
        r"\bcontrol panel\b|\bpower options?\b|\bpower plan\b|"
        r"\bnetwork (?:connections|and sharing)\b|\binternet options\b|\bsharing center\b|"
        r"\buser accounts\b|\bprograms and features\b|\buninstall (?:a )?program\b|"
        r"\b(?:folder|file explorer) options\b|\bsystem restore\b|\bcredential manager\b|"
        r"\bdate and time\b|\bregion\b|\bcolor management\b|\bdevice manager\b|"
        r"\bdevices and printers\b|\bsound settings\b|\bwindows tools\b", re.IGNORECASE),
     "Opened the Windows Control Panel item."),
    ("windows.open_tools", re.compile(
        r"\btask manager\b|\bresource monitor\b|\bdevice manager\b|"
        r"\bdisk management\b|\bregistry editor\b|\bevent viewer\b|\bservices\b", re.IGNORECASE),
     "Opened the Windows system tool."),
    ("windows.system_action", re.compile(
        r"\bsign out\b|\blog ?off\b|\bhibernate\b|"
        r"\b(?:put|go) (?:the )?(?:pc|computer) to sleep\b|\bgo to sleep\b|"
        r"\brestart (?:the |my )?(?:pc|computer)\b|\breboot\b|\bshut ?down\b|"
        r"\bturn off (?:the )?(?:pc|computer)\b|\bcancel (?:shutdown|restart)\b|\babort shutdown\b", re.IGNORECASE),
     "Ran the Windows system action."),
    ("windows.brightness", re.compile(r"\bbrightness\b", re.IGNORECASE), "Adjusted the screen brightness."),
    ("windows.system_info", re.compile(
        r"\bhow much (?:battery|storage|memory|ram)\b|"
        r"\bcheck (?:disk space|memory|battery|storage)\b|\bstorage left\b|"
        r"\bwhat(?:'s| is) my ip\b|\bip address\b|\bsystem uptime\b|\bwindows version\b|"
        r"\bwhich wifi\b|\bwhat wifi am i on\b|\bcomputer name\b|\bhostname\b|\bpower plan\b|"
        r"\bcheck the (?:processor|cpu|gpu|graphics card|monitor)\b|\bcpu info\b|\bram\b", re.IGNORECASE),
     "Retrieved the system information."),
    ("windows.empty_recycle_bin", re.compile(
        r"\b(?:empty|clear) (?:the )?recycle bin\b|\bempty (?:the )?trash\b", re.IGNORECASE),
     "Emptied the Recycle Bin."),
    ("windows.show_desktop", re.compile(
        r"\bshow desktop\b|\b(?:show|minimi[sz]e) (?:all|my) windows\b|\bminimi[sz]e everything\b", re.IGNORECASE),
     "Minimized all windows to show the desktop."),
    ("windows.clipboard_clear", re.compile(
        r"\b(?:clear|empty|wipe) (?:the )?clipboard\b", re.IGNORECASE), "Cleared the clipboard."),
    ("windows.toggle_connectivity", re.compile(
        r"\b(?:turn|switch) (?:on|off)\s+(?:the\s+)?wi[\s-]?fi\b|"
        r"\b(?:enable|disable)\s+(?:the\s+)?wi[\s-]?fi\b|\btoggle wi[\s-]?fi\b|"
        r"\b(?:turn|switch) (?:on|off)\s+(?:the\s+)?bluetooth\b|"
        r"\b(?:enable|disable)\s+(?:the\s+)?bluetooth\b|\btoggle bluetooth\b", re.IGNORECASE),
     "Toggled the network radio."),
    ("windows.set_default_browser", re.compile(r"\bdefault browser\b", re.IGNORECASE), "Opened the Default Apps settings page."),
    ("windows.open_run", re.compile(r"\bopen run\b|\bthe run dialog\b|\brun box\b", re.IGNORECASE), "Opened the Run dialog."),
)


class FastLaneRouter:
    """
    Lean ML-Assisted Fast Lane Router for Privacy68.

    Architecture:
    1. Exact keyword lookups (system actions, popular sites) — <1ms, 100% accuracy
    2. Windows system bridge (pre-compiled regex) — <2ms, deterministic
    3. ML Intent Classifier routes remaining commands:
       - Simple intents (open_app, open_site, open_folder, type_text, settings) → execute directly
       - Complex intents (file CRUD, search, compound browser, unknown) → delegate to API Lane
    4. Plugin fast intents — O(1) phrase map lookup

    This replaces ~500 lines of complex regex parameter extraction
    with a trained TF-IDF + LogisticRegression model (<5ms, ~2MB, zero GPU).
    """

    def _run_windows(self, plugin, action: str, text: str, message: str) -> Optional[Dict[str, Any]]:
        """Executes a windows plugin action and wraps it in a fast-lane result dict."""
        if not getattr(plugin, "is_enabled", False):
            return None
        try:
            ok = plugin.execute(action, text)
        except Exception as e:
            logger.error(f"Windows bridge failed for {action}: {e}")
            return None
        if not ok:
            return None
        return {
            "handled": True,
            "tool": action,
            "method": "fast_lane",
            "success": True,
            "details": {"bridge": action},
            "message": message,
        }

    def _windows_bridge(self, text: str, low: str) -> Optional[Dict[str, Any]]:
        """Routes Windows system commands and deep settings to the windows plugin."""
        from plugins.manager import plugin_manager
        plugin = plugin_manager.plugins.get("windows")
        if not plugin:
            return None

        for action, pattern, message in WINDOWS_BRIDGE_CHECKS:
            if pattern.search(low):
                logger.info(f"[ROUTER] Command classified as FAST via windows plugin: {action}")
                return self._run_windows(plugin, action, text, message)

        # Deep Settings pages (e.g. windows update, recovery, hotspot, etc.)
        try:
            from plugins.windows_plugin import ALL_SETTINGS_PAGES
            has_setting_intent = bool(re.search(r"\b(?:settings|open|go to|show|view|check|launch|switch to)\b", low))
            for key in sorted(ALL_SETTINGS_PAGES, key=len, reverse=True):
                if key in SETTINGS_PAGES:
                    continue
                if (has_setting_intent or " " in key) and key in low and re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                    logger.info(f"[ROUTER] Command classified as FAST via windows plugin: windows.open_settings ({key})")
                    return self._run_windows(
                        plugin, "windows.open_settings", text,
                        f"Opened the {key.title()} Settings page.",
                    )
        except Exception as e:
            logger.error(f"Windows settings bridge failed: {e}")
        return None

    def try_execute_fast(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to match and execute user command via Fast Lane.
        Uses ML intent classifier for routing, delegates complex commands to API Lane.
        Returns result dict if handled, or None if the command should proceed to API/LLM Lane.
        """
        cleaned = text.strip()
        low = cleaned.lower()

        # ── 1. System Hardware & Window controls (exact dict lookup, <1ms) ────
        m_sys = _SYSTEM_ACTIONS_PATTERN.search(low)
        if m_sys:
            sys_cmd = SYSTEM_ACTION_KEYWORDS[m_sys.group(1).lower()]
            logger.info(f"[ROUTER] Command classified as FAST: system_action ({sys_cmd})")
            res = system_action(sys_cmd)
            return {
                "handled": True,
                "tool": "system_action",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Executed {sys_cmd}."),
            }

        # ── 2. Windows System Bridge (Settings, Uptime, Wi-Fi, Storage) ──────
        bridged = self._windows_bridge(text, low)
        if bridged is not None:
            return bridged

        # ── 3. ML Intent Classifier routing ──────────────────────────────────
        from actions.intent_classifier import intent_classifier, LANE_FAST

        lane, intent, confidence = intent_classifier.classify(text)
        logger.debug(f"[CLASSIFIER] '{text}' -> {lane}/{intent} ({confidence:.0%})")

        # If classified as API Lane or LLM Lane, delegate immediately!
        if lane != LANE_FAST or confidence < 0.60:
            logger.info(f"[ROUTER] Delegating '{text}' to {lane} (confidence {confidence:.0%})")
            return None

        # 3a. Settings navigation
        if intent == "open_settings":
            logger.info("[ROUTER] Command classified as FAST via classifier: open_settings")
            m_set = re.match(
                r"^(?:please\s*)?(?:open|go\s+to|show|launch|switch\s+to)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\s+(?:settings|page|tab))?$",
                low,
            )
            query = m_set.group(1).strip() if m_set else low
            res = open_settings(query)
            return {
                "handled": True,
                "tool": "open_settings",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", "Opened Windows Settings."),
            }

        # 3b. Direct popular website
        if intent == "open_website" and confidence >= 0.70:
            m_site = re.search(r"\b(" + "|".join(POPULAR_SITES) + r")\b", low)
            if m_site:
                site_name = m_site.group(1)
                logger.info(f"[ROUTER] Command classified as FAST via classifier: open_website ({site_name})")
                res = open_web_or_search(query="", site_target=site_name)
                return {
                    "handled": True,
                    "tool": "open_web_or_search",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Opened {site_name.title()}."),
                }

        # 3c. Folder opening
        if intent == "open_folder":
            from actions.param_extractor import param_extractor
            slots = param_extractor.extract_slots(text, "open_folder")
            cand = slots.get("path") or low.replace("open", "").replace("folder", "").strip()
            if cand:
                res = open_path(cand)
                if res.get("success"):
                    logger.info(f"[ROUTER] Command classified as FAST via classifier: open_folder ({cand})")
                    return {
                        "handled": True,
                        "tool": "open_path",
                        "method": "fast_lane",
                        "success": True,
                        "details": res,
                        "message": res.get("message", f"Opened {res.get('path', 'folder')}."),
                    }

        # 3d. Type/dictation
        if intent == "type_text":
            from actions.param_extractor import param_extractor
            slots = param_extractor.extract_slots(text, "type_text")
            typed_text = slots.get("content") or cleaned.split(" ", 1)[-1]
            logger.info("[ROUTER] Command classified as FAST via classifier: type_text")
            res = type_text(typed_text)
            return {
                "handled": True,
                "tool": "type_text",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": "Typed text.",
            }

        # 3e. Application launching
        if intent == "open_application":
            from actions.param_extractor import param_extractor
            slots = param_extractor.extract_slots(text, "open_application")
            app_cand = slots.get("name") or re.sub(r"^(?:open|launch|start)\s+", "", low).strip()
            if app_cand and len(app_cand.split()) <= 4 and app_cand not in FOLDER_KEYWORDS:
                res = open_application(app_cand)
                if res.get("success"):
                    logger.info(f"[ROUTER] Command classified as FAST via classifier: open_application ({app_cand})")
                    return {
                        "handled": True,
                        "tool": "open_application",
                        "method": "fast_lane",
                        "success": True,
                        "details": res,
                        "message": f"Launched '{app_cand}'.",
                    }

        return None

    def try_execute_plugin_fast(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Fast Lane Plugin Intent Dispatcher:
        Directly checks fast_intents from active plugins (<2ms latency, 0% AI).
        """
        if not text or not text.strip():
            return None

        from actions.skill_manager import manager
        from plugins.manager import plugin_manager

        low = text.lower().strip(".!?, ")
        if "and then" in low or "and after" in low or "and also" in low:
            return None

        cleaned = re.sub(r'^(?:please\s*)?(?:can\s+you\s*)?', '', low).strip()

        action_name = plugin_manager.match_fast_intent(cleaned) or plugin_manager.match_fast_intent(low)
        if action_name:
            logger.info(f"[FAST LANE] Matched plugin fast intent '{action_name}' for '{text}'")
            success = manager.execute_skill(action_name, text)
            return {
                "handled": True,
                "tool": action_name,
                "method": "fast_lane",
                "success": success,
                "message": f"Executed '{action_name}' via Fast Lane",
            }

        return None


fast_lane_router = FastLaneRouter()

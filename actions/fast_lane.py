import os
import re
import logging
from typing import Any, Dict, Optional, Tuple

from computer_use.system_tools import (
    create_folder,
    create_file,
    rename_item,
    delete_file,
    move_item,
    open_settings,
    open_web_or_search,
    open_application,
    open_path,
    list_directory,
    verify_path_exists,
    system_action,
    get_desktop_path,
    get_documents_path,
    get_downloads_path,
    get_pictures_path,
    resolve_path,
    SETTINGS_PAGES,
)

logger = logging.getLogger("PRIVACY68.FastLane")

# Stop words stripped when parsing folder/file names
STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "to", "at", "into", "inside", "under",
    "folder", "directory", "file", "please", "and", "with", "from", "for",
    "desktop", "documents", "downloads", "pictures", "music", "videos", "home",
    "drive", "new", "called", "named", "as", "it", "me", "my", "can", "you",
    "create", "make", "named", "name",
})

class FastLaneRouter:
    """
    Deterministic Fast Lane Router & Execution Engine for Privacy68.
    Directly extracts parameters and executes generic system tools without LLM latency:
    - Settings navigation
    - App launching
    - File & Folder management (Create, Rename, Move, Delete, List, Open)
    - Default web search & quick site navigation (YouTube, Google, GitHub, etc.)
    - System controls (Volume, Lock, Screenshot, Window state, Dictation)
    """

    def _normalize_name(self, text: str) -> str:
        cleaned = re.sub(
            r"\b(?:please|create|make|add|the|a|an|folder|directory|file|"
            r"new\s+(?:folder|directory|file)|"
            r"rename|move|delete|remove|erase|open|launch|start|named|called|app|"
            r"application|program|me|for|from|with|into|inside|on|to|in|at|as|can|you|name\s+it\s+as)\b",
            " ", text, flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip(" .!?,_-")

    def _extract_folder_params(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (folder_name, destination_path) from folder creation commands."""
        quoted = re.search(r'["\']([^"\']+)["\']', text)
        if quoted:
            name = quoted.group(1).strip()
            loc_part = text.replace(quoted.group(0), "")
            path = resolve_path(loc_part)
            return name, path

        m_named = re.search(
            r"\b(?:named|called|name\s+it\s+as|named\s+as|with\s+name)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|on|to|at|inside|into|under)\b|$)",
            text, flags=re.IGNORECASE
        )
        if m_named:
            cand_name = m_named.group(1).strip(" .!?,_-")
            clean_for_loc = text[:m_named.start()] + " " + text[m_named.end():]
            m_loc = re.search(r"\b(?:in|on|to|at|inside|into|under)\s+(.+)$", clean_for_loc, flags=re.IGNORECASE)
            loc_str = m_loc.group(1).strip() if m_loc else "desktop"
            return cand_name, resolve_path(loc_str)

        m_x_folder = re.search(
            r"\b(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?([a-zA-Z0-9_\-\.]+)\s+(?:folder|directory)\s+(?:in|on|at|inside|into|under)\s+(.+)$",
            text, flags=re.IGNORECASE
        )
        if m_x_folder:
            name = m_x_folder.group(1).strip(" .!?,_-")
            loc_str = m_x_folder.group(2).strip()
            return name, resolve_path(loc_str)

        m_folder_x = re.search(
            r"\b(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(.+?)(?:\s+(?:in|on|at|inside|into|under)\s+(.+))?$",
            text, flags=re.IGNORECASE
        )
        if m_folder_x:
            head = m_folder_x.group(1).strip()
            tail_loc = m_folder_x.group(2)
            name = self._normalize_name(head)
            path = resolve_path(tail_loc) if tail_loc else get_desktop_path()
            if name:
                return name, path

        return None, None

    def _extract_file_params(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (file_name, destination_path) from file creation commands."""
        quoted = re.search(r'["\']([^"\']+)["\']', text)
        if quoted:
            name = quoted.group(1).strip()
            loc_part = text.replace(quoted.group(0), "")
            return name, resolve_path(loc_part)

        m_named = re.search(
            r"\b(?:named|called|name\s+it\s+as|named\s+as)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|on|to|at|inside|into|under)\b|$)",
            text, flags=re.IGNORECASE
        )
        if m_named:
            name = m_named.group(1).strip(" .!?,_-")
            clean_for_loc = text[:m_named.start()] + " " + text[m_named.end():]
            m_loc = re.search(r"\b(?:in|on|to|at|inside|into|under)\s+(.+)$", clean_for_loc, flags=re.IGNORECASE)
            loc_str = m_loc.group(1).strip() if m_loc else "desktop"
            return name, resolve_path(loc_str)

        m_file = re.search(
            r"\b(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?(?:text\s+)?(?:file|document)\s+(.+?)(?:\s+(?:in|on|at|inside|into|under)\s+(.+))?$",
            text, flags=re.IGNORECASE
        )
        if m_file:
            head = m_file.group(1).strip()
            tail_loc = m_file.group(2)
            name = self._normalize_name(head)
            if name and not name.endswith((".txt", ".doc", ".py", ".md", ".json")):
                name = f"{name}.txt"
            path = resolve_path(tail_loc) if tail_loc else get_desktop_path()
            if name:
                return name, path

        return None, None

    def _extract_rename_params(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts (old_name, new_name, location_dir) from rename commands:
        e.g. 'rename file notes to final_notes', 'rename test.txt to doc.txt on desktop'
        """
        parts = re.split(r"\s+(?:to|into|as)\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            return None, None, None

        old_phrase, new_phrase = parts
        old_name = self._normalize_name(old_phrase).strip(" .!?,_-'\"")

        # Check if location is specified in new_phrase
        m_loc = re.search(r"\b(?:in|on|at|inside|under)\s+(.+)$", new_phrase, flags=re.IGNORECASE)
        if m_loc:
            loc_dir = resolve_path(m_loc.group(1).strip())
            new_head = new_phrase[:m_loc.start()]
        else:
            loc_dir = get_desktop_path()
            new_head = new_phrase

        new_name = self._normalize_name(new_head).strip(" .!?,_-'\"")

        if old_name and new_name:
            return old_name, new_name, loc_dir
        return None, None, None

    def _extract_delete_params(self, text: str) -> Optional[str]:
        """Extracts target path from delete commands."""
        m_del = re.search(r"\b(?:delete|remove|erase)\s+(?:the\s+)?(?:file|folder|directory)?\s*(.+)$", text, flags=re.IGNORECASE)
        if m_del:
            raw_target = m_del.group(1).strip(" .!?,_-'\"")
            # If target has location clause
            m_loc = re.search(r"\b(?:in|on|at|inside|under)\s+(.+)$", raw_target, flags=re.IGNORECASE)
            if m_loc:
                name_part = self._normalize_name(raw_target[:m_loc.start()])
                base_dir = resolve_path(m_loc.group(1).strip())
                return os.path.join(base_dir, name_part)
            else:
                norm = self._normalize_name(raw_target)
                return resolve_path(norm)
        return None

    def _extract_search_params(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts search query and target platform (e.g. YouTube, Google) from search commands:
        e.g. 'search python tutorials on google', 'search lofi music on youtube', 'google latest tech news'
        """
        low = text.lower().strip()
        m = re.match(
            r"^(?:please\s*)?(?:can\s+you\s*)?(?:search(?:\s+(?:for|about|on))?|google|look\s+up|find(?:\s+(?:information\s+about|info\s+on))?)\s+(.+)$",
            low
        )
        if not m:
            return None, None

        query = m.group(1).strip()
        site_target = None

        if re.search(r"\b(?:on\s+youtube|in\s+youtube|youtube)\b", query):
            site_target = "youtube"
            query = re.sub(r"\b(?:on\s+youtube|in\s+youtube|youtube)\b", "", query).strip()
        elif re.search(r"\b(?:on\s+google|in\s+google|google)\b", query):
            site_target = "google"
            query = re.sub(r"\b(?:on\s+google|in\s+google|google)\b", "", query).strip()

        query = query.strip(" .!?,_-")
        if query:
            return query, site_target
        return None, None

    def try_execute_fast(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to match and execute user command via deterministic Fast Lane.
        Returns result dict if handled, or None if the command should proceed to Agent Lane.
        """
        cleaned = text.strip()
        low = cleaned.lower()

        # ─── 0. Compound Fast Patterns (Executed instantaneously with ZERO LLM latency) ───

        # Pattern 0A: "open settings and (go to|switch to|select) <page>"
        m_set_compound = re.match(
            r"^(?:please\s*)?(?:open|launch|show)\s+(?:windows\s+|system\s+)?settings\s+(?:and\s+)?(?:then\s+)?(?:go\s+to|switch\s+to|select|open|show)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+settings|\s+tab|\s+page)?$",
            low
        )
        if m_set_compound:
            sub_page = m_set_compound.group(1).strip()
            logger.info(f"[ROUTER] Compound command: open settings -> '{sub_page}'")
            res = open_settings(sub_page)
            return {
                "handled": True,
                "tool": "open_settings",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Opened {sub_page.title()} Settings."),
            }

        # Pattern 0B: "open task manager and (go to|switch to|select) <tab>"
        m_task_compound = re.match(
            r"^(?:please\s*)?(?:open|launch)\s+task\s+manager\s+(?:and\s+)?(?:then\s+)?(?:go\s+to|switch\s+to|select|show)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+tab|\s+page)?$",
            low
        )
        if m_task_compound:
            sub_tab = m_task_compound.group(1).strip()
            logger.info(f"[ROUTER] Compound command: open task manager -> tab '{sub_tab}'")
            open_application("task manager")
            import time
            time.sleep(0.5)
            from computer_use.actions import computer_actions
            clicked = computer_actions.click_element(sub_tab)
            return {
                "handled": True,
                "tool": "open_application_and_switch_tab",
                "method": "fast_lane",
                "success": True,
                "message": f"Opened Task Manager and switched to {sub_tab.title()} tab.",
            }

        # Pattern 0C: "open (chrome|brave|edge|firefox|browser) and (go to|navigate to|open|visit) <site/url>"
        m_browser_nav = re.match(
            r"^(?:please\s*)?(?:open|launch)\s+(chrome|brave|edge|firefox|browser|google\s+chrome|brave\s+browser|microsoft\s+edge)\s+(?:and\s+)?(?:then\s+)?(?:go\s+to|navigate\s+to|open|visit|load)\s+(?:the\s+)?(.+)$",
            low
        )
        if m_browser_nav:
            target_browser = m_browser_nav.group(1).strip()
            dest_target = m_browser_nav.group(2).strip()
            logger.info(f"[ROUTER] Compound command: open {target_browser} -> go to '{dest_target}'")
            res = open_web_or_search(query=dest_target, browser=target_browser)
            return {
                "handled": True,
                "tool": "open_web_or_search",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Opened {dest_target} in {target_browser.title()}."),
            }

        # Pattern 0D: "open (youtube|google|chrome|brave|browser|edge|firefox) and (search for|look up|find|play|watch) <query>"
        m_search_compound = re.match(
            r"^(?:please\s*)?(?:open|launch)\s+(youtube|google|chrome|brave|browser|edge|firefox|reddit|github|wikipedia|amazon|twitter|x)\s+(?:and\s+)?(?:then\s+)?(?:search(?:\s+(?:for|about|on))?|look\s+up|find|play|watch|listen\s+to)\s+(.+)$",
            low
        )
        if m_search_compound:
            target_engine = m_search_compound.group(1).strip()
            search_query = m_search_compound.group(2).strip()
            logger.info(f"[ROUTER] Compound command: open {target_engine} -> search '{search_query}'")

            # Check if target_engine is a browser vs a website platform
            if target_engine in ("chrome", "brave", "edge", "firefox", "browser"):
                res = open_web_or_search(query=search_query, browser=target_engine)
            else:
                res = open_web_or_search(query=search_query, site_target=target_engine)

            return {
                "handled": True,
                "tool": "open_web_or_search",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Searched for '{search_query}'."),
            }

        # Pattern 0E: "in (chrome|brave|edge|firefox) search (for|about)? <query>"
        m_in_browser = re.match(
            r"^(?:in|on|using|with)\s+(chrome|brave|edge|firefox|browser|google\s+chrome)\s+(?:search(?:\s+(?:for|about))?|look\s+up|find|open)\s+(.+)$",
            low
        )
        if m_in_browser:
            target_browser = m_in_browser.group(1).strip()
            query_str = m_in_browser.group(2).strip()
            logger.info(f"[ROUTER] Browser-scoped search: '{query_str}' in {target_browser}")
            res = open_web_or_search(query=query_str, browser=target_browser)
            return {
                "handled": True,
                "tool": "open_web_or_search",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Searched '{query_str}' in {target_browser.title()}."),
            }

        # Pattern 0F: "play <video/song> on youtube (in chrome|in brave)?"
        m_play_yt = re.match(
            r"^(?:please\s*)?(?:play|watch|listen\s+to)\s+(.+?)(?:\s+(?:on|in)\s+youtube)?(?:\s+(?:in|on|using|with)\s+(chrome|brave|edge|firefox))?$",
            low
        )
        if m_play_yt and ("youtube" in low or any(w in low for w in ("play ", "watch ", "listen to "))):
            track_name = m_play_yt.group(1).strip()
            custom_browser = m_play_yt.group(2)
            if track_name and not track_name.startswith(("settings", "volume", "music app", "game")):
                logger.info(f"[ROUTER] YouTube media play command: '{track_name}'")
                res = open_web_or_search(query=track_name, site_target="youtube", browser=custom_browser)
                return {
                    "handled": True,
                    "tool": "open_web_or_search",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Playing '{track_name}' on YouTube."),
                }

        # Pattern 0G: "open/new terminal in (vscode|vs code|visual studio code)"
        m_vscode_term = re.match(
            r"^(?:please\s*)?(?:open|launch|start|new|create|show)\s+(?:a\s+)?(?:new\s+)?(?:integrated\s+)?terminal\s+(?:in|inside|on)\s+(?:vs\s*code|vscode|visual\s*studio\s*code)$",
            low
        )
        if not m_vscode_term:
            m_vscode_term = re.match(
                r"^(?:please\s*)?(?:open|launch|start|new)\s+(?:vs\s*code|vscode|visual\s*studio\s*code)\s+(?:integrated\s+)?terminal$",
                low
            )
        if m_vscode_term:
            logger.info(f"[ROUTER] Direct Fast Lane: open VS Code terminal")
            from plugins.manager import plugin_manager
            vscode_plugin = plugin_manager.plugins.get("vscode")
            if vscode_plugin and hasattr(vscode_plugin, "open_terminal"):
                success = vscode_plugin.open_terminal(cleaned)
            else:
                from computer_use.window_manager import window_manager
                window_manager.focus_window("Visual Studio Code") or window_manager.focus_window("Code")
                import time, pyautogui
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "shift", "`")
                success = True
            return {
                "handled": True,
                "tool": "vscode.open_terminal",
                "method": "fast_lane",
                "success": success,
                "message": "Opened integrated terminal in VS Code.",
            }

        # Reject complex multi-step & open-ended agent tasks (e.g. "create folder and inside create a python script with a function")
        if re.search(
            r"\b(?:and\s+(?:type|send|message|tell|write|read|check|create|make|generate|put|add|code|build|run|execute|save))\b"
            r"|\b(?:inside\s+it\s+(?:create|make|write|put|add|generate))\b"
            r"|\b(?:in\s+it\s+(?:create|make|write|put|add|generate))\b"
            r"|\b(?:with\s+(?:a\s+)?(?:hello\s+world|function|class|code|script|content))\b"
            r"|\b(?:saying|send\s+(?:a\s+)?message)\b"
            r"|\b(?:and\s+then\s+(?:create|make|write|open|send))\b",
            low,
        ):
            logger.info(f"[ROUTER] Command contains multi-step / generative actions -> routing to AGENT LANE")
            return None

        # ─── 1. Active Window Aware Navigation & Settings ───
        # Matches: "go to system", "switch to bluetooth", "go to performance tab", "open wifi settings", "go to sound"
        m_nav = re.match(r"^(?:please\s*)?(?:go\s+to|switch\s+to|open|select|click|navigate\s+to)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+tab|\s+page|\s+section)?$", low)
        if m_nav:
            target_nav = m_nav.group(1).strip()
            # Check active window context
            from computer_use.window_manager import window_manager
            from computer_use.actions import computer_actions
            active_win = window_manager.get_active_window()
            active_title = (active_win.get("title") or "").lower()

            # Case A: Active window is Settings (or command explicitly requests a known setting)
            if "settings" in active_title or target_nav in SETTINGS_PAGES or any(f"{k} settings" in low for k in SETTINGS_PAGES.keys()) or "setting" in low:
                clean_target = re.sub(r"\b(?:settings|page|app|tab)\b", "", target_nav).strip()
                if not clean_target:
                    clean_target = "system"
                
                # If target is in SETTINGS_PAGES or active window is Settings
                if clean_target in SETTINGS_PAGES or "settings" in active_title:
                    logger.info(f"[ROUTER] Active window is Settings / target '{clean_target}' in SETTINGS_PAGES -> open_settings")
                    res = open_settings(clean_target)
                    # Also attempt UI element click if Settings window is visible
                    try:
                        computer_actions.click_element(clean_target)
                    except Exception:
                        pass
                    return {
                        "handled": True,
                        "tool": "open_settings",
                        "method": "fast_lane",
                        "success": res.get("success", False),
                        "details": res,
                        "message": res.get("message", f"Navigated to {clean_target.title()} Settings."),
                    }

            # Case B: Active window is Task Manager
            if "task manager" in active_title:
                clean_target = re.sub(r"\b(?:tab|page)\b", "", target_nav).strip()
                if clean_target in ("performance", "processes", "startup", "app history", "users", "details", "services"):
                    logger.info(f"[ROUTER] Active window is Task Manager -> switching to '{clean_target}'")
                    clicked = computer_actions.click_element(clean_target)
                    return {
                        "handled": True,
                        "tool": "switch_tab",
                        "method": "fast_lane",
                        "success": clicked,
                        "message": f"Switched to {clean_target.title()} tab in Task Manager.",
                    }

            # Case C: Direct click / select UI element in active window
            if low.startswith(("click ", "select ")):
                logger.info(f"[ROUTER] Attempting direct UI click on active window element: '{target_nav}'")
                clicked = computer_actions.click_element(target_nav)
                if clicked:
                    return {
                        "handled": True,
                        "tool": "click_element",
                        "method": "fast_lane",
                        "success": True,
                        "message": f"Clicked '{target_nav}' in active window.",
                    }

        # Standalone "settings" or "open settings" fallback
        if re.search(r"\b(?:settings|windows settings)\b", low):
            logger.info(f"[ROUTER] Command classified as FAST: open_settings")
            res = open_settings(low)
            return {
                "handled": True,
                "tool": "open_settings",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", "Opened Windows Settings."),
            }

        # ─── 2. Rename File / Folder ───
        if re.search(r"\b(?:rename|change\s+(?:the\s+)?name\s+of)\b", low):
            old_name, new_name, base_dir = self._extract_rename_params(cleaned)
            if old_name and new_name:
                logger.info(f"[ROUTER] Command classified as FAST: rename_item ('{old_name}' -> '{new_name}')")
                res = rename_item(old_name, new_name, base_directory=base_dir)
                return {
                    "handled": True,
                    "tool": "rename_item",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Renamed '{old_name}' to '{new_name}'."),
                }

        # ─── 3. Delete File / Folder ───
        if re.search(r"^(?:please\s*)?(?:delete|remove|erase)\s+(?:the\s+)?(?:file|folder|directory)\b", low):
            target_path = self._extract_delete_params(cleaned)
            if target_path:
                logger.info(f"[ROUTER] Command classified as FAST: delete_file ('{target_path}')")
                res = delete_file(target_path)
                return {
                    "handled": True,
                    "tool": "delete_file",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Deleted '{target_path}'."),
                }

        # ─── 4. Folder Creation ───
        if re.search(r"\b(?:create|make|new|add)\s+(?:a\s+)?(?:new\s+)?(?:[a-zA-Z0-9_\-\.]+\s+)?(?:folder|directory)\b|\b(?:folder|directory)\s+(?:named|called)\b", low):
            name, path = self._extract_folder_params(cleaned)
            if name and path:
                logger.info(f"[ROUTER] Command classified as FAST: create_folder")
                res = create_folder(path=path, name=name)
                return {
                    "handled": True,
                    "tool": "create_folder",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Created folder '{name}'."),
                }

        # ─── 5. File Creation ───
        if re.search(r"\b(?:create|make|new|add)\s+(?:a\s+)?(?:new\s+)?(?:[a-zA-Z0-9_\-\.]+\s+)?(?:text\s+)?(?:file|document)\b", low):
            name, path = self._extract_file_params(cleaned)
            if name and path:
                logger.info(f"[ROUTER] Command classified as FAST: create_file")
                res = create_file(path=path, name=name)
                return {
                    "handled": True,
                    "tool": "create_file",
                    "method": "fast_lane",
                    "success": res.get("success", False),
                    "details": res,
                    "message": res.get("message", f"Created file '{name}'."),
                }

        # ─── 6. Directory Listing ───
        m_list = re.search(r"\b(?:list|show|view|what\s+is\s+in|what\s+files\s+are\s+in)\s+(?:files\s+in|directory|contents\s+of)?\s*(.+)$", low)
        if m_list and any(w in low for w in ("list", "show files", "what files")):
            target_str = m_list.group(1).strip()
            path = resolve_path(target_str)
            logger.info(f"[ROUTER] Command classified as FAST: list_directory")
            res = list_directory(path)
            return {
                "handled": True,
                "tool": "list_directory",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Listed files in {path}."),
            }

        # ─── 7. Path / Folder Opening ───
        # "open downloads", "open downloads folder", "open my desktop", "open d drive", "open folder called test on desktop", "open test folder"
        # Skip if the user wants to open in vscode/code editor — let the plugin lane handle that
        if not re.search(r"\b(?:vscode|vs\s*code|code\s*editor)\b", low):
            m_open_path = re.match(
                r"^(?:please\s*)?(?:open|show|explore)\s+(?:my\s+)?(?:the\s+)?(?:folder\s+(?:called\s+|named\s+)?|directory\s+(?:called\s+|named\s+)?)?"
                r"([a-zA-Z0-9_\-\s\:\/\\]+?)(?:\s+(?:folder|directory))?$",
                low
            )
            if m_open_path:
                cand_folder = m_open_path.group(1).strip()
                # Detect drive letters dynamically (a: through z:)
                has_drive_letter = bool(re.search(r"\b[a-z]\s*(?:drive|colon)\b|\bdrive\s+[a-z]\b|\b[a-z]:", low, re.IGNORECASE))
                # If the candidate clearly targets a folder, drive, or contains folder keywords
                _FOLDER_KEYWORDS = (
                    "folder", "directory", "drive", "downloads", "desktop", "documents",
                    "pictures", "music", "videos", "this pc", "my computer", "home",
                    "user", "temp", "recycle bin", "appdata", "program files",
                )
                is_folder_intent = has_drive_letter or any(w in low for w in _FOLDER_KEYWORDS)
                if is_folder_intent:
                    logger.info(f"[ROUTER] Command classified as FAST: open_path -> '{cand_folder}'")
                    res = open_path(cand_folder)
                    if res.get("success"):
                        return {
                            "handled": True,
                            "tool": "open_path",
                            "method": "fast_lane",
                            "success": True,
                            "details": res,
                            "message": res.get("message", f"Opened {res.get('path', 'folder')}."),
                        }

        # ─── 8. Default Web Search & YouTube / Popular Sites Navigation ───
        # "open youtube", "open github", "open chatgpt", "search python tutorials on google", "search lofi music on youtube"
        m_open_site = re.match(r"^(?:please\s*)?(?:open|launch|go\s+to)\s+(?:the\s+)?(youtube|github|chatgpt|openai|reddit|twitter|wikipedia|gmail|linkedin|netflix|spotify)\b", low)
        if m_open_site:
            site_name = m_open_site.group(1).strip()
            logger.info(f"[ROUTER] Command classified as FAST: open_web_or_search ({site_name})")
            res = open_web_or_search(query="", site_target=site_name)
            return {
                "handled": True,
                "tool": "open_web_or_search",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", f"Opened {site_name.title()}."),
            }

        search_query, search_site = self._extract_search_params(cleaned)
        if search_query:
            logger.info(f"[ROUTER] Command classified as FAST: open_web_or_search ('{search_query}')")
            res = open_web_or_search(query=search_query, site_target=search_site)
            return {
                "handled": True,
                "tool": "open_web_or_search",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": res.get("message", "Searched web."),
            }

        # ─── 9. System Controls (Volume, Lock, Screenshot, Window State) ───
        system_keywords = {
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
            "press enter": "enter",
            "hit enter": "enter",
            "press tab": "tab",
            "hit tab": "tab",
        }
        for phrase, sys_cmd in system_keywords.items():
            if re.search(rf"\b{re.escape(phrase)}\b", low):
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

        # ─── 10. Dictation / Typing ───
        m_type = re.match(r'^(?:please\s*)?(?:can\s+you\s*)?(?:type\s+that|type\s+out|type|write\s+that|write\s+out|write)\s+(.+)$', cleaned, re.IGNORECASE)
        if m_type:
            typed_text = m_type.group(1).strip()
            from computer_use.system_tools import type_text
            logger.info(f"[ROUTER] Command classified as FAST: type_text")
            res = type_text(typed_text)
            return {
                "handled": True,
                "tool": "type_text",
                "method": "fast_lane",
                "success": res.get("success", False),
                "details": res,
                "message": f"Typed text.",
            }

        # ─── 11. Direct Single App Launching ───
        # "open chrome", "open notepad", "open calculator", "open task manager", "open vs code", "open antigravity in my computer"
        m_open_app = re.match(r'^(?:please\s*)?(?:open|launch|start)\s+(?:the\s+)?([a-zA-Z0-9\s\+\#\.\-]+?)(?:\s+(?:in|on|from|inside)\s+(?:my\s+|this\s+)?(?:computer|conputer|pc|laptop|machine|system|device))?$', low)
        if m_open_app:
            app_cand = m_open_app.group(1).strip()
            # Guard: real app names are 1-4 words max; longer phrases are compound commands → Agent Lane
            if len(app_cand.split()) > 4:
                return None
            # If candidate is a special folder handled above, let open_path handle it
            if app_cand not in ("downloads", "desktop", "documents", "pictures", "music", "videos", "this pc"):
                res = open_application(app_cand)
                if res.get("success"):
                    logger.info(f"[ROUTER] Fast Lane successfully launched application: {app_cand}")
                    return {
                        "handled": True,
                        "tool": "open_application",
                        "method": "fast_lane",
                        "success": True,
                        "details": res,
                        "message": res.get("message", f"Launched '{app_cand}'."),
                    }
                # If Windows app launch failed, do NOT block: fall through to Plugin Lane & LLM Lane!
                logger.info(f"[ROUTER] '{app_cand}' not a standalone OS app, passing to Plugin & Agent Lanes.")
                return None

        return None

fast_lane_router = FastLaneRouter()

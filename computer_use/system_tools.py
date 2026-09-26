import os
import re
import shutil
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("PRIVACY68.SystemTools")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical Windows Settings Map (ms-settings: URIs)
# ─────────────────────────────────────────────────────────────────────────────

SETTINGS_PAGES: Dict[str, str] = {
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "wi-fi": "ms-settings:network-wifi",
    "network": "ms-settings:network",
    "ethernet": "ms-settings:network-ethernet",
    "airplane": "ms-settings:network-airplanemode",
    "display": "ms-settings:display",
    "resolution": "ms-settings:display",
    "sound": "ms-settings:sound",
    "volume": "ms-settings:sound",
    "audio": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "background": "ms-settings:personalization-background",
    "themes": "ms-settings:themes",
    "colors": "ms-settings:colors",
    "lock screen": "ms-settings:lockscreen",
    "lockscreen": "ms-settings:lockscreen",
    "privacy": "ms-settings:privacy",
    "camera": "ms-settings:privacy-webcam",
    "webcam": "ms-settings:privacy-webcam",
    "microphone": "ms-settings:privacy-microphone",
    "mic": "ms-settings:privacy-microphone",
    "apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "accounts": "ms-settings:accounts",
    "sign in": "ms-settings:signinoptions",
    "time": "ms-settings:dateandtime",
    "date": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "gaming": "ms-settings:gaming-gamedvr",
    "storage": "ms-settings:storagesense",
    "battery": "ms-settings:batterysaver",
    "power": "ms-settings:powersleep",
    "troubleshoot": "ms-settings:troubleshoot",
    "device": "ms-settings:bluetooth",
    "devices": "ms-settings:connecteddevices",
    "mouse": "ms-settings:mousetouchpad",
    "keyboard": "ms-settings:devices-typing",
    "windows update": "ms-settings:windowsupdate",
    "update": "ms-settings:windowsupdate",
    "system": "ms-settings:system",
    "about": "ms-settings:about",
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. Dynamic Windows Special Path Resolvers (OneDrive & Registry Safe)
# ─────────────────────────────────────────────────────────────────────────────

def get_shell_folders() -> Dict[str, str]:
    """Dynamically resolves real Windows special folders from User Shell Folders registry
    (handling OneDrive redirection, relocated user directories, etc.)."""
    folders = {
        "desktop": os.path.expanduser("~/Desktop"),
        "documents": os.path.expanduser("~/Documents"),
        "downloads": os.path.expanduser("~/Downloads"),
        "pictures": os.path.expanduser("~/Pictures"),
        "images": os.path.expanduser("~/Pictures"),
        "music": os.path.expanduser("~/Music"),
        "videos": os.path.expanduser("~/Videos"),
        "home": os.path.expanduser("~"),
        "user": os.path.expanduser("~"),
    }
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        ) as key:
            reg_map = {
                "Desktop": ["desktop"],
                "Personal": ["documents"],
                "{374DE290-123F-4565-9164-39C4925E467B}": ["downloads"],
                "{7D83EE9B-2244-4E70-B1F5-5393042AF1E4}": ["downloads"],
                "My Pictures": ["pictures", "images"],
                "My Music": ["music"],
                "My Video": ["videos"],
            }
            for reg_name, aliases in reg_map.items():
                try:
                    val, _ = winreg.QueryValueEx(key, reg_name)
                    expanded = os.path.expandvars(val)
                    if os.path.exists(expanded):
                        for a in aliases:
                            folders[a] = expanded
                except Exception:
                    pass
    except Exception:
        pass
    return folders

SHELL_FOLDERS = get_shell_folders()

def get_desktop_path() -> str:
    """Returns the user's active, visible Desktop path (OneDrive-aware)."""
    return get_shell_folders().get("desktop", os.path.expanduser("~/Desktop"))

def get_documents_path() -> str:
    """Returns the user's active Documents path (OneDrive-aware)."""
    return get_shell_folders().get("documents", os.path.expanduser("~/Documents"))

def get_downloads_path() -> str:
    """Returns the user's Downloads path."""
    return get_shell_folders().get("downloads", os.path.expanduser("~/Downloads"))

def get_pictures_path() -> str:
    """Returns the user's Pictures path."""
    return get_shell_folders().get("pictures", os.path.expanduser("~/Pictures"))

def resolve_path(location_str: str, default_root: Optional[str] = None) -> str:
    """
    Resolves a natural language location string or path into an absolute file system path.
    Supports:
      - Absolute paths: 'D:\\Projects', 'E:\\my_code\\test'
      - Drive letters: 'd drive', 'on e drive', 'c:'
      - Special folders: 'desktop', 'documents', 'downloads', 'pictures'
      - Relative clauses: 'inside projects folder on e drive'
    """
    if not location_str or not location_str.strip():
        return default_root or get_desktop_path()

    cleaned = location_str.strip().strip("'\"")

    # 1. Direct absolute path check (e.g. 'D:\\Projects' or 'C:/Users/...')
    if re.match(r'^[a-zA-Z]:[\\/]', cleaned):
        return os.path.abspath(cleaned)

    # 2. Extract drive letter if present
    base = None
    sub_phrase = cleaned

    dm = re.search(r'\b([a-zA-Z])\s*(?:drive|colon)\b|\bdrive\s+([a-zA-Z])\b|\b([a-zA-Z]):', cleaned, re.IGNORECASE)
    if dm:
        drive_letter = (dm.group(1) or dm.group(2) or dm.group(3) or "").upper()
        base = f"{drive_letter}:\\"
        sub_phrase = re.sub(r'\b[a-zA-Z]\s*(?:drive|colon)\b|\bdrive\s+[a-zA-Z]\b|\b[a-zA-Z]:', ' ', sub_phrase, flags=re.IGNORECASE)
    else:
        # Check against known special shell folder names
        shell_map = get_shell_folders()
        for key, p in shell_map.items():
            if re.search(rf'\b{re.escape(key)}\b', cleaned, re.IGNORECASE):
                base = p
                sub_phrase = re.sub(rf'\b{re.escape(key)}\b', ' ', sub_phrase, flags=re.IGNORECASE)
                break

    if base is None:
        base = default_root or get_desktop_path()

    # Clean sub_phrase: remove trailing conjunctions/sentences (e.g. "and create a python script...")
    sub_clean = re.split(r"\b(?:and\s+|then\s+|with\s+|having\s+|for\s+)\b", sub_phrase, maxsplit=1, flags=re.IGNORECASE)[0]
    # Remove noise wrapper words & action verbs
    sub_clean = re.sub(r"\b(?:open|show|explore|navigate\s+to|go\s+to|please|folder|directory|my|the|called|named|this\s+pc|drive|colon)\b", " ", sub_clean, flags=re.IGNORECASE)
    sub_clean = re.sub(r"\b(?:in|on|to|at|into|inside|under)\b", " ", sub_clean, flags=re.IGNORECASE)
    sub_clean = re.sub(r"\s+", " ", sub_clean).strip(" .!?,_-'\"")

    # If sub_clean is an existing folder or valid directory identifier
    if sub_clean:
        clean_parts = [p.strip(" .!?,_-'\"") for p in re.split(r'[/\\]+', sub_clean) if p.strip(" .!?,_-'\"")]
        if clean_parts:
            valid_parts = clean_parts[:3]  # Max 3 nested directory segments
            return os.path.join(base, *valid_parts)

    return base


# ─────────────────────────────────────────────────────────────────────────────
# 2. Generic Desktop & File System Tools
# ─────────────────────────────────────────────────────────────────────────────

def create_folder(path: str, name: str) -> Dict[str, Any]:
    """
    Generic tool to create a folder at target path and verify existence.
    """
    resolved_dir = resolve_path(path)
    clean_name = name.strip(" .!?-_/\\")
    target_path = os.path.join(resolved_dir, clean_name)

    if os.path.exists(target_path):
        logger.info(f"[FAST] create_folder: Folder already exists at '{target_path}'")
        return {
            "success": True,
            "created": False,
            "already_exists": True,
            "path": target_path,
            "message": f"The '{clean_name}' folder already exists at {resolved_dir}."
        }

    try:
        os.makedirs(target_path, exist_ok=True)
        verified = os.path.exists(target_path) and os.path.isdir(target_path)
        logger.info(f"[FAST] create_folder path={resolved_dir} name={clean_name} verification={'SUCCESS' if verified else 'FAILED'}")
        return {
            "success": verified,
            "created": verified,
            "already_exists": False,
            "path": target_path,
            "message": f"Created folder '{clean_name}' at {resolved_dir} successfully."
        }
    except Exception as e:
        logger.error(f"[FAST] create_folder error: {e}")
        return {
            "success": False,
            "created": False,
            "error": str(e),
            "message": f"Failed to create folder '{clean_name}': {e}"
        }

def create_file(path: str, name: str, content: str = "") -> Dict[str, Any]:
    """
    Generic tool to create a text file at target path and verify existence.
    """
    resolved_dir = resolve_path(path)
    clean_name = name.strip(" .!?-_/\\")

    # Guard: name with no file extension and no content is probably a folder request
    if "." not in clean_name and not content:
        logger.warning(f"[FAST] create_file: no extension, no content for '{clean_name}' — redirecting to create_folder")
        return create_folder(path=path, name=clean_name)

    target_path = os.path.join(resolved_dir, clean_name)

    try:
        os.makedirs(resolved_dir, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        verified = os.path.exists(target_path) and os.path.isfile(target_path)
        logger.info(f"[FAST] create_file path={resolved_dir} name={clean_name} verification={'SUCCESS' if verified else 'FAILED'}")
        return {
            "success": verified,
            "created": verified,
            "path": target_path,
            "message": f"Created file '{clean_name}' at {resolved_dir} successfully."
        }
    except Exception as e:
        logger.error(f"[FAST] create_file error: {e}")
        return {
            "success": False,
            "created": False,
            "error": str(e),
            "message": f"Failed to create file '{clean_name}': {e}"
        }

def delete_file(path: str, force: bool = False) -> Dict[str, Any]:
    """
    Generic tool to delete a file or folder safely.
    """
    target = resolve_path(path)
    if not os.path.exists(target):
        return {"success": False, "error": "Path does not exist", "message": f"Cannot delete: '{path}' does not exist."}

    # Safety check: avoid deleting root directories or user profile root
    user_home = os.path.expanduser("~").lower()
    norm_target = os.path.abspath(target).lower()
    if norm_target in {user_home, "c:\\", "d:\\", "e:\\", get_desktop_path().lower(), get_documents_path().lower()}:
        logger.warning(f"Prevented deletion of protected root path: {target}")
        return {"success": False, "error": "Protected path", "message": "Cannot delete protected system/root directories."}

    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        verified = not os.path.exists(target)
        logger.info(f"[FAST] delete_file path={target} verification={'SUCCESS' if verified else 'FAILED'}")
        return {"success": verified, "path": target, "message": f"Deleted '{target}' successfully."}
    except Exception as e:
        logger.error(f"[FAST] delete_file error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to delete '{target}': {e}"}

def open_path(path: str) -> Dict[str, Any]:
    """
    Opens any directory or file in Windows File Explorer or associated default app.
    Searches common user directories if a relative folder name is specified.
    """
    target = resolve_path(path)
    if not os.path.exists(target):
        # If the resolved target is a drive root (e.g. F:\) that doesn't exist, report clearly
        if re.match(r'^[A-Z]:\\?$', target):
            return {"success": False, "error": "Drive not found",
                    "message": f"Drive '{target}' is not available or not connected."}

        # Extract folder name candidate
        clean_name = os.path.basename(target).strip(" .!?,_-'\"")
        candidates = [
            get_desktop_path(),
            get_documents_path(),
            get_downloads_path(),
            os.path.expanduser("~"),
        ]
        found_target = None
        for root in candidates:
            cand_path = os.path.join(root, clean_name)
            if os.path.exists(cand_path):
                found_target = cand_path
                break
        
        if found_target:
            target = found_target
        else:
            # Only auto-create if the parent directory exists (don't create on non-existent drives)
            parent = os.path.dirname(target)
            if os.path.exists(parent):
                try:
                    os.makedirs(target, exist_ok=True)
                    logger.info(f"[FAST] open_path created missing folder at: {target}")
                except Exception:
                    return {"success": False, "error": "Path does not exist", "message": f"Folder or path '{path}' does not exist."}
            else:
                return {"success": False, "error": "Path does not exist", "message": f"Folder or path '{path}' does not exist."}

    try:
        os.startfile(target)
        logger.info(f"[FAST] open_path path={target} verification=SUCCESS")
        return {"success": True, "path": target, "message": f"Opened '{target}'."}
    except Exception as e:
        logger.error(f"[FAST] open_path error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to open '{target}': {e}"}

def list_directory(path: str) -> Dict[str, Any]:
    """
    Lists the contents of a directory.
    """
    target = resolve_path(path)
    if not os.path.exists(target):
        return {"success": False, "error": "Path does not exist", "items": []}
    if not os.path.isdir(target):
        return {"success": False, "error": "Target is not a directory", "items": []}

    try:
        entries = os.listdir(target)
        items = []
        for e in entries:
            full = os.path.join(target, e)
            items.append({
                "name": e,
                "is_dir": os.path.isdir(full),
                "size_bytes": os.path.getsize(full) if os.path.isfile(full) else 0
            })
        logger.info(f"[FAST] list_directory path={target} count={len(items)} verification=SUCCESS")
        return {
            "success": True,
            "path": target,
            "count": len(items),
            "items": items,
            "message": f"Found {len(items)} items in '{target}'."
        }
    except Exception as e:
        logger.error(f"[FAST] list_directory error: {e}")
        return {"success": False, "error": str(e), "items": []}

def verify_path_exists(path: str) -> Dict[str, Any]:
    """
    Verifies whether a file or directory exists on disk.
    """
    target = resolve_path(path)
    exists = os.path.exists(target)
    is_dir = os.path.isdir(target) if exists else False
    is_file = os.path.isfile(target) if exists else False
    return {
        "success": exists,
        "exists": exists,
        "path": target,
        "is_dir": is_dir,
        "is_file": is_file,
        "message": f"Path '{target}' {'exists' if exists else 'does not exist'}."
    }

def rename_item(source_name_or_path: str, new_name: str, base_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    Generic tool to rename a file or folder safely.
    Supports absolute paths or fuzzy searching by name in base_directory (defaults to Desktop).
    """
    import difflib
    clean_new_name = new_name.strip(" .!?-_/\\")
    if not clean_new_name:
        return {"success": False, "error": "Invalid new name", "message": "New name cannot be empty."}

    # 1. Check if source is directly an existing path
    resolved_src = resolve_path(source_name_or_path, default_root=base_directory)
    target_src = resolved_src if os.path.exists(resolved_src) else None

    # 2. Fuzzy search in base_directory if not directly found
    if not target_src:
        search_dir = resolve_path(base_directory) if base_directory else get_desktop_path()
        if os.path.exists(search_dir) and os.path.isdir(search_dir):
            try:
                entries = os.listdir(search_dir)
                low_src = source_name_or_path.lower().strip()
                best_match, best_score = None, 0.0
                for entry in entries:
                    low_entry = entry.lower()
                    score = difflib.SequenceMatcher(None, low_src, low_entry).ratio()
                    if low_src in low_entry or low_entry.startswith(low_src):
                        score = max(score, 0.85)
                    if score > best_score:
                        best_score, best_match = score, os.path.join(search_dir, entry)
                if best_score >= 0.65:
                    target_src = best_match
            except Exception as e:
                logger.debug(f"Error scanning directory for rename: {e}")

    if not target_src or not os.path.exists(target_src):
        return {
            "success": False,
            "error": "Source not found",
            "message": f"Could not find file or folder '{source_name_or_path}' to rename."
        }

    # Ensure source extension is preserved for files if new name doesn't specify one
    if os.path.isfile(target_src):
        _, old_ext = os.path.splitext(target_src)
        _, new_ext = os.path.splitext(clean_new_name)
        if old_ext and not new_ext:
            clean_new_name = f"{clean_new_name}{old_ext}"

    parent_dir = os.path.dirname(target_src)
    target_dst = os.path.join(parent_dir, clean_new_name)

    if os.path.exists(target_dst) and target_dst.lower() != target_src.lower():
        return {
            "success": False,
            "error": "Destination exists",
            "message": f"An item named '{clean_new_name}' already exists in {parent_dir}."
        }

    try:
        shutil.move(target_src, target_dst)
        verified = os.path.exists(target_dst)
        logger.info(f"[FAST] rename_item src={target_src} dst={target_dst} verification={'SUCCESS' if verified else 'FAILED'}")
        return {
            "success": verified,
            "old_path": target_src,
            "new_path": target_dst,
            "message": f"Renamed '{os.path.basename(target_src)}' to '{clean_new_name}' successfully."
        }
    except Exception as e:
        logger.error(f"[FAST] rename_item error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to rename: {e}"}

def move_item(source_path: str, destination_dir: str, base_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    Generic tool to move a file or folder to a target directory.
    """
    resolved_src = resolve_path(source_path, default_root=base_directory)
    resolved_dst_dir = resolve_path(destination_dir)

    if not os.path.exists(resolved_src):
        return {"success": False, "error": "Source does not exist", "message": f"Source path '{source_path}' does not exist."}

    try:
        os.makedirs(resolved_dst_dir, exist_ok=True)
        shutil.move(resolved_src, resolved_dst_dir)
        final_path = os.path.join(resolved_dst_dir, os.path.basename(resolved_src))
        verified = os.path.exists(final_path)
        logger.info(f"[FAST] move_item src={resolved_src} dst={final_path} verification={'SUCCESS' if verified else 'FAILED'}")
        return {
            "success": verified,
            "source": resolved_src,
            "destination": final_path,
            "message": f"Moved '{os.path.basename(resolved_src)}' to '{resolved_dst_dir}'."
        }
    except Exception as e:
        logger.error(f"[FAST] move_item error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to move '{source_path}': {e}"}

def open_settings(page_name: str = "") -> Dict[str, Any]:
    """
    Opens Windows Settings directly using ms-settings: deep links.
    """
    clean = page_name.lower().strip(" .!?,_-")
    if not clean or clean in ("settings", "windows settings", "system settings", "settings app"):
        target_uri = "ms-settings:"
        label = "Windows Settings"
    else:
        target_uri = "ms-settings:"
        label = clean
        # Match longest key first
        sorted_keys = sorted(SETTINGS_PAGES.keys(), key=lambda k: -len(k))
        for key in sorted_keys:
            if re.search(rf"\b{re.escape(key)}\b", clean, re.IGNORECASE):
                target_uri = SETTINGS_PAGES[key]
                label = f"{key.title()} Settings"
                break

    try:
        subprocess.Popen(f"start {target_uri}", shell=True)
        logger.info(f"[FAST] open_settings uri={target_uri} label={label}")
        return {
            "success": True,
            "uri": target_uri,
            "label": label,
            "message": f"Opened {label}."
        }
    except Exception as e:
        logger.error(f"[FAST] open_settings error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to open {label}: {e}"}

def open_web_or_search(query: str = "", site_target: Optional[str] = None, browser: Optional[str] = None) -> Dict[str, Any]:
    """
    Universal default web & search launcher.
    Opens websites (YouTube, GitHub, ChatGPT, Reddit, etc.) or performs queries across platforms in the default/active browser.
    """
    import urllib.parse
    import webbrowser

    clean_query = query.strip(" .!?, \t\n")
    target_site = (site_target or "").lower().strip()

    # Known popular direct websites
    KNOWN_DOMAINS = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "chatgpt": "https://chatgpt.com",
        "openai": "https://chatgpt.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "wikipedia": "https://www.wikipedia.org",
        "gmail": "https://mail.google.com",
        "linkedin": "https://www.linkedin.com",
        "netflix": "https://www.netflix.com",
        "spotify": "https://open.spotify.com",
        "amazon": "https://www.amazon.com",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "whatsapp web": "https://web.whatsapp.com",
        "duckduckgo": "https://duckduckgo.com",
        "bing": "https://www.bing.com",
        "twitch": "https://www.twitch.tv",
    }

    # Platform search URL templates
    SEARCH_TEMPLATES = {
        "youtube": ("https://www.youtube.com/results?search_query={q}", "YouTube"),
        "google": ("https://www.google.com/search?q={q}", "Google"),
        "reddit": ("https://www.reddit.com/search/?q={q}", "Reddit"),
        "github": ("https://github.com/search?q={q}", "GitHub"),
        "wikipedia": ("https://en.wikipedia.org/wiki/Special:Search?search={q}", "Wikipedia"),
        "amazon": ("https://www.amazon.com/s?k={q}", "Amazon"),
        "twitter": ("https://twitter.com/search?q={q}", "Twitter"),
        "x": ("https://x.com/search?q={q}", "X"),
        "duckduckgo": ("https://duckduckgo.com/?q={q}", "DuckDuckGo"),
        "bing": ("https://www.bing.com/search?q={q}", "Bing"),
    }

    # 1. Check if target_site is specified or detectable in the query
    detected_site = target_site
    if not detected_site:
        for site_key in SEARCH_TEMPLATES:
            if re.search(rf"\b(?:on\s+{site_key}|in\s+{site_key}|{site_key}\s+for)\b", clean_query, flags=re.IGNORECASE):
                detected_site = site_key
                break

    # 2. Extract search term without the site marker
    search_term = clean_query
    if detected_site:
        search_term = re.sub(rf"\b(?:on\s+{detected_site}|in\s+{detected_site}|{detected_site}\s+for|{detected_site})\b", "", search_term, flags=re.IGNORECASE).strip()
    search_term = re.sub(r"^(?:search(?:\s+(?:for|about|on))?|look\s+up|google|find|play|listen\s+to|watch)\s+", "", search_term, flags=re.IGNORECASE).strip()
    search_term = search_term.strip(" .!?,_-'\"")

    # 3. Determine final URL
    final_url = ""
    action_desc = ""

    # Case A: Direct URL (starts with http://, https:// or contains domain like .com, .org, .io)
    if clean_query.startswith(("http://", "https://")):
        final_url = clean_query
        action_desc = f"Opened {clean_query}"
    elif re.match(r"^[a-zA-Z0-9\-\.]+\.(?:com|org|net|io|dev|ai|edu|gov|in|co|tv|app|me)(?:/[^\s]*)?$", clean_query):
        final_url = f"https://{clean_query}"
        action_desc = f"Opened {final_url}"

    # Case B: Platform search (e.g. YouTube, Reddit, GitHub, Wikipedia)
    elif detected_site in SEARCH_TEMPLATES:
        template, site_name = SEARCH_TEMPLATES[detected_site]
        if search_term:
            encoded = urllib.parse.quote_plus(search_term)
            final_url = template.format(q=encoded)
            action_desc = f"Searched {site_name} for '{search_term}'"
        else:
            final_url = KNOWN_DOMAINS.get(detected_site, f"https://www.{detected_site}.com")
            action_desc = f"Opened {site_name}"

    # Case C: Known direct website name without search term (e.g. "open youtube", "open chatgpt")
    elif clean_query.lower() in KNOWN_DOMAINS:
        final_url = KNOWN_DOMAINS[clean_query.lower()]
        action_desc = f"Opened {clean_query.title()}"

    # Case D: General web search query (Google)
    else:
        term = search_term if search_term else clean_query
        encoded = urllib.parse.quote_plus(term)
        final_url = f"https://www.google.com/search?q={encoded}"
        action_desc = f"Searched Google for '{term}'"

    # 4. Launch browser
    browser_name = (browser or "").lower().strip()
    if browser_name in ("google chrome", "chrome browser"):
        browser_name = "chrome"
    elif browser_name in ("brave browser",):
        browser_name = "brave"
    elif browser_name in ("microsoft edge", "edge browser"):
        browser_name = "msedge"
    elif browser_name == "edge":
        browser_name = "msedge"

    try:
        if browser_name:
            subprocess.Popen(f'start {browser_name} "{final_url}"', shell=True)
        else:
            # Check if running browser exists (Brave or Chrome or Edge), otherwise default webbrowser
            try:
                task_list = subprocess.check_output('tasklist /FI "STATUS eq RUNNING"', shell=True, text=True).lower()
                if "brave.exe" in task_list:
                    subprocess.Popen(f'start brave "{final_url}"', shell=True)
                elif "chrome.exe" in task_list:
                    subprocess.Popen(f'start chrome "{final_url}"', shell=True)
                elif "msedge.exe" in task_list:
                    subprocess.Popen(f'start msedge "{final_url}"', shell=True)
                else:
                    webbrowser.open(final_url)
            except Exception:
                webbrowser.open(final_url)

        logger.info(f"[FAST] open_web_or_search url={final_url} desc={action_desc}")
        return {
            "success": True,
            "url": final_url,
            "message": action_desc
        }
    except Exception as e:
        logger.error(f"[FAST] open_web_or_search error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to open web search: {e}"}

def open_application(name: str) -> Dict[str, Any]:
    """
    Opens any Windows application by name (Task Manager, Calculator, Notepad, Chrome, VS Code, etc.).
    """
    from computer_use.launcher import app_launcher
    success = app_launcher.launch(name)
    logger.info(f"[FAST] open_application app={name} verification={'SUCCESS' if success else 'FAILED'}")
    return {
        "success": success,
        "app_name": name,
        "message": f"Launched '{name}'." if success else f"Could not find or launch application '{name}'."
    }

def get_active_window() -> Dict[str, Any]:
    """
    Returns information about the currently focused foreground window.
    """
    from computer_use.window_manager import window_manager
    return window_manager.get_active_window()

def observe_window() -> Dict[str, Any]:
    """
    Captures active window information and visible UI controls.
    """
    from computer_use.observer import desktop_observer
    return desktop_observer.observe(inspect_controls=True)

def find_ui_element(name: str, control_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Searches for an interactive UI element by name / control type in the active window.
    """
    from computer_use.observer import desktop_observer
    elem = desktop_observer.find_active_element(name=name, control_type=control_type)
    if elem:
        return {"success": True, "found": True, "element": elem}
    return {"success": False, "found": False, "element": None, "message": f"Element '{name}' not found."}

def click_element(name: str, control_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Finds and clicks a UI element by name in the active window.
    """
    from computer_use.actions import computer_actions
    success = computer_actions.click_element(name, control_type=control_type)
    return {
        "success": success,
        "element": name,
        "message": f"Clicked '{name}'." if success else f"Could not click '{name}'."
    }

def type_text(text: str, target_field: Optional[str] = None) -> Dict[str, Any]:
    """
    Types text into the active control or specified field.
    """
    from computer_use.actions import computer_actions
    success = computer_actions.type_text(text, target_field_name=target_field)
    return {
        "success": success,
        "text": text,
        "message": f"Typed text into active field." if success else "Failed to type text."
    }

def press_key(key: str) -> Dict[str, Any]:
    """
    Sends a keyboard key press (e.g. 'enter', 'tab', 'escape', 'space').
    """
    from computer_use.actions import computer_actions
    success = computer_actions.press_key(key)
    return {
        "success": success,
        "key": key,
        "message": f"Pressed '{key}' key." if success else f"Failed to press key '{key}'."
    }

def verify_window(name: str) -> Dict[str, Any]:
    """
    Verifies whether a specific window title or application is open and active.
    """
    from computer_use.window_manager import window_manager
    is_open = window_manager.is_window_open(name)
    is_active = window_manager.is_window_active(name)
    return {
        "success": is_open,
        "is_open": is_open,
        "is_active": is_active,
        "name": name,
        "message": f"Window '{name}' is {'open' if is_open else 'not open'}."
    }

def system_action(command: str, text: str = "") -> Dict[str, Any]:
    """
    Executes standard Windows OS system commands (volume, lock, screenshot, window state).
    """
    import pyautogui
    pyautogui.FAILSAFE = False
    cmd = command.lower().strip()
    try:
        if cmd in ("volume_up", "volume up", "increase volume", "louder"):
            for _ in range(5):
                pyautogui.press("volumeup")
            return {"success": True, "command": "volume_up", "message": "Increased volume."}
        elif cmd in ("volume_down", "volume down", "decrease volume", "quieter"):
            for _ in range(5):
                pyautogui.press("volumedown")
            return {"success": True, "command": "volume_down", "message": "Decreased volume."}
        elif cmd in ("volume_mute", "mute", "unmute", "mute volume"):
            pyautogui.press("volumemute")
            return {"success": True, "command": "volume_mute", "message": "Toggled volume mute."}
        elif cmd in ("lock", "lock_screen", "lock computer", "lock the computer"):
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "command": "lock", "message": "Locked computer."}
        elif cmd in ("screenshot", "take screenshot", "take a screenshot"):
            save_dir = get_pictures_path()
            os.makedirs(save_dir, exist_ok=True)
            filename = f"Screenshot_{int(time.time())}.png"
            file_path = os.path.join(save_dir, filename)
            pyautogui.screenshot(file_path)
            return {"success": True, "command": "screenshot", "path": file_path, "message": f"Screenshot saved to {file_path}."}
        elif cmd in ("close_window", "close this window", "close current window", "close active window", "close app"):
            pyautogui.hotkey("alt", "f4")
            return {"success": True, "command": "close_window", "message": "Closed active window."}
        elif cmd in ("maximize", "maximize_window", "maximize this window", "maximize window", "full screen"):
            pyautogui.hotkey("win", "up")
            return {"success": True, "command": "maximize", "message": "Maximized active window."}
        elif cmd in ("minimize", "minimize_window", "minimize this window", "minimize window"):
            pyautogui.hotkey("win", "down")
            return {"success": True, "command": "minimize", "message": "Minimized active window."}
        elif cmd in ("enter", "press enter", "hit enter"):
            pyautogui.press("enter")
            return {"success": True, "command": "enter", "message": "Pressed Enter."}
        elif cmd in ("tab", "press tab", "hit tab"):
            pyautogui.press("tab")
            return {"success": True, "command": "tab", "message": "Pressed Tab."}
        else:
            return {"success": False, "error": f"Unknown system command '{command}'"}
    except Exception as e:
        logger.error(f"[FAST] system_action error: {e}")
        return {"success": False, "error": str(e), "message": f"Failed to execute system command: {e}"}

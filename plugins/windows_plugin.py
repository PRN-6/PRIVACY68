import logging
import os
import re
import shutil
import difflib
import subprocess
from typing import Callable, Dict, List, Optional, Tuple
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugin.Windows")

try:
    from computer_use.system_tools import SETTINGS_PAGES
except ImportError:
    # Fallback if computer_use is not available
    SETTINGS_PAGES = {
        "bluetooth": "ms-settings:bluetooth",
        "wifi": "ms-settings:network-wifi",
        "network": "ms-settings:network",
        "ethernet": "ms-settings:network-ethernet",
        "airplane": "ms-settings:network-airplanemode",
        "display": "ms-settings:display",
        "resolution": "ms-settings:display",
        "sound": "ms-settings:sound",
        "volume": "ms-settings:sound",
        "notifications": "ms-settings:notifications",
        "background": "ms-settings:personalization-background",
        "themes": "ms-settings:themes",
        "colors": "ms-settings:colors",
        "lock screen": "ms-settings:lockscreen",
        "privacy": "ms-settings:privacy",
        "camera": "ms-settings:privacy-webcam",
        "microphone": "ms-settings:privacy-microphone",
        "apps": "ms-settings:appsfeatures",
        "default apps": "ms-settings:defaultapps",
        "accounts": "ms-settings:accounts",
        "sign in": "ms-settings:signinoptions",
        "time": "ms-settings:dateandtime",
        "language": "ms-settings:regionlanguage",
        "gaming": "ms-settings:gaming-gamedvr",
        "storage": "ms-settings:storagesense",
        "battery": "ms-settings:batterysaver",
        "troubleshoot": "ms-settings:troubleshoot",
        "device": "ms-settings:bluetooth",
        "mouse": "ms-settings:mousetouchpad",
        "keyboard": "ms-settings:devices-typing",
        "power": "ms-settings:powersleep",
        "system": "ms-settings:system",
    }

# Well-known special app launches that aren't in Start Menu search
SPECIAL_APPS = {
    "control panel": "control.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "file explorer": "explorer.exe",
    "this pc": "explorer.exe",
    "my computer": "explorer.exe",
    "snipping tool": "ms-snippingtool:",
    "task manager": "taskmgr.exe",
}

# Helper to dynamically find real Windows User Shell Folders (OneDrive, custom user paths, etc.)
def _get_shell_folders() -> Dict[str, str]:
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

# Root folder keywords -> real absolute paths
ROOT_PATHS = _get_shell_folders()

# Words that shouldn't end up as part of a name/path
STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "to", "at", "into", "inside", "under",
    "folder", "directory", "file", "please", "and", "with", "from", "for",
    "desktop", "documents", "downloads", "pictures", "music", "videos", "home",
    "drive", "new", "called", "named", "as", "it", "me", "my",
})


class WindowsPlugin(BasePlugin):
    """
    Windows Automation plugin: file/folder management, app launching,
    and Windows Settings page navigation. Self-contained and auto-registered.
    """
    id = "windows"
    name = "Windows Automation"
    icon = "🗔"
    description = "Windows file and system automation: create/rename/move/delete files and folders, open applications, and open Windows Settings pages."
    version = "1.0.0"
    author = "PRIVACY68 Core"
    is_builtin = True

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "windows.open_settings": self.open_settings,
            "windows.open_app": self.open_app,
            "windows.create_folder": self.create_folder,
            "windows.create_file": self.create_file,
            "windows.rename": self.rename,
            "windows.move": self.move,
            "windows.delete": self.delete,
            "windows.open_location": self.open_location,
            "windows.taskmgr_performance": self.taskmgr_performance,
            "windows.taskmgr_processes": self.taskmgr_processes,
            "windows.taskmgr_startup": self.taskmgr_startup,
            "windows.taskmgr_app_history": self.taskmgr_app_history,
            "windows.taskmgr_users": self.taskmgr_users,
            "windows.taskmgr_details": self.taskmgr_details,
            "windows.taskmgr_services": self.taskmgr_services,
            "windows.taskmgr_end_task": self.taskmgr_end_task,
            "windows.taskmgr_run_task": self.taskmgr_run_task,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "windows.open_settings": [
                "open settings",
                "open windows settings",
                "open system settings",
                "open settings app",
                "open windows settings page",
                "open bluetooth settings",
                "open wifi settings",
                "open display settings",
                "open sound settings",
                "open privacy settings",
                "open network settings",
                "open apps settings",
                "go to system",
                "go to bluetooth",
                "go to wifi",
                "go to sound",
                "go to display",
                "go to network",
                "go to apps",
                "go to battery",
                "go to storage",
                "go to update",
                "system tab",
                "bluetooth tab",
                "wifi tab",
                "sound tab",
                "display tab",
            ],
            "windows.open_app": [
                "open calculator",
                "open task manager",
                "open file explorer",
                "open this pc",
                "open control panel",
                "open terminal",
                "open command prompt",
                "open powershell",
                "open snipping tool",
                "open ms paint",
                "open ms word",
                "open excel",
                "open camera",
                "open an application",
                "open application",
                "open app",
                "launch an application",
            ],
            "windows.taskmgr_performance": [
                "go to performance",
                "go to performance tab",
                "switch to performance",
                "switch to performance tab",
                "open performance tab",
                "performance tab",
                "show performance",
                "performance in task manager",
                "go to performance in task manager",
                "open performance",
                "task manager performance",
            ],
            "windows.taskmgr_processes": [
                "go to processes",
                "go to processes tab",
                "switch to processes",
                "switch to processes tab",
                "processes tab",
                "show processes",
                "processes in task manager",
                "go to processes in task manager",
                "task manager processes",
            ],
            "windows.taskmgr_startup": [
                "go to startup",
                "go to startup apps",
                "switch to startup",
                "startup apps tab",
                "startup tab",
                "show startup apps",
                "task manager startup",
            ],
            "windows.taskmgr_app_history": [
                "go to app history",
                "switch to app history",
                "app history tab",
                "show app history",
            ],
            "windows.taskmgr_users": [
                "go to users",
                "users tab",
                "switch to users",
                "task manager users",
            ],
            "windows.taskmgr_details": [
                "go to details",
                "details tab",
                "switch to details",
                "task manager details",
            ],
            "windows.taskmgr_services": [
                "go to services",
                "services tab",
                "switch to services",
                "task manager services",
            ],
            "windows.taskmgr_end_task": [
                "end task",
                "end selected task",
                "kill selected task",
            ],
            "windows.taskmgr_run_task": [
                "run new task",
                "create new task",
            ],
            "windows.create_folder": [
                "create folder", "make folder", "create a folder",
                "make a folder", "new folder", "create directory",
                "make a new folder", "create a new folder",
                "can you create a folder", "can you make a folder",
                "create a folder on desktop", "create folder on desktop",
                "make a folder on desktop", "create a new folder on desktop",
                "create a folder inside documents", "create a folder in documents",
                "create a folder inside the documents", "create a folder in the documents",
                "create a folder on documents", "create folder inside documents",
                "make a folder inside documents", "make a folder inside the documents",
                "can you create a folder inside documents", "can you create a folder inside the documents",
                "can you create a folder in documents", "can you create a folder on desktop",
                "create a folder inside downloads", "create a folder in downloads",
                "create a folder inside pictures", "create a folder in pictures",
                "create a folder named", "create folder named", "create a folder called",
                "make a folder named", "make a folder called",
            ],
            "windows.create_file": [
                "create file", "make file", "create a file",
                "make a file", "create new file", "create a new file",
                "create a text file", "create a document",
                "can you create a file", "can you make a file",
                "create a file on desktop", "create file on desktop",
                "create a file in documents", "create a file inside documents",
                "create a file inside the documents", "create a file in the documents",
                "can you create a file inside documents", "can you create a file on desktop",
                "create a file named", "create file named", "create a file called",
            ],
            "windows.rename": [
                "rename file", "rename folder", "rename",
                "rename the file", "rename the folder",
                "change the name of the file",
                "change the name of the folder",
            ],
            "windows.move": [
                "move file", "move folder", "move this file",
                "move this folder", "move the file", "move the folder",
                "move to desktop", "move to documents",
                "move a file to a folder",
            ],
            "windows.delete": [
                "delete file", "delete folder", "delete the file",
                "delete the folder", "remove file", "remove folder",
                "erase file", "erase folder",
            ],
            "windows.open_location": [
                "open folder", "open the folder", "open file location",
                "open the file location", "open in explorer",
                "open in file explorer", "show in explorer",
                "open location in explorer", "open folder in vscode",
                "open folder in code editor",
                "open folder in file explorer", "show folder in explorer",
                "open this folder in explorer", "open this in file explorer",
                "open project folder", "open the project folder",
                "open projects folder in explorer",
                "open folder in vs code",
                "open c drive", "open d drive", "open e drive",
                "open f drive", "open g drive",
                "open c drive in explorer", "open d drive in explorer",
                "open e drive in explorer",
                "open downloads in explorer", "open documents in explorer",
                "open desktop in explorer", "open pictures in explorer",
                "open home folder", "open user folder",
                "open my home folder", "open my user folder",
                "explore folder", "explore the folder",
                "browse folder", "browse files",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "windows.open_settings": "- windows.open_settings: Open a Windows Settings page (e.g. 'open bluetooth settings', 'open wifi settings').",
            "windows.open_app": "- windows.open_app: Launch any application installed on the PC by name (e.g. 'open calculator', 'open discord', 'open telegram').",
            "windows.taskmgr_performance": "- windows.taskmgr_performance: Switch to the Performance tab in Task Manager to view CPU, GPU, Memory, and Disk stats (e.g. 'go to performance').",
            "windows.taskmgr_processes": "- windows.taskmgr_processes: Switch to the Processes tab in Task Manager (e.g. 'go to processes').",
            "windows.taskmgr_startup": "- windows.taskmgr_startup: Switch to the Startup Apps tab in Task Manager (e.g. 'go to startup').",
            "windows.taskmgr_app_history": "- windows.taskmgr_app_history: Switch to the App History tab in Task Manager (e.g. 'go to app history').",
            "windows.taskmgr_users": "- windows.taskmgr_users: Switch to the Users tab in Task Manager (e.g. 'go to users').",
            "windows.taskmgr_details": "- windows.taskmgr_details: Switch to the Details tab in Task Manager (e.g. 'go to details').",
            "windows.taskmgr_services": "- windows.taskmgr_services: Switch to the Services tab in Task Manager (e.g. 'go to services').",
            "windows.taskmgr_end_task": "- windows.taskmgr_end_task: End the currently selected task or process in Task Manager.",
            "windows.taskmgr_run_task": "- windows.taskmgr_run_task: Open the Run New Task dialog in Task Manager.",
            "windows.create_folder": "- windows.create_folder: Create a new folder, optionally in a location (e.g. 'create folder agent testing in projects folder on e drive', 'make folder personal stuff on desktop').",
            "windows.create_file": "- windows.create_file: Create a new (empty text) file, optionally in a location (e.g. 'create file todo notes on desktop').",
            "windows.rename": "- windows.rename: Rename an existing file or folder (e.g. 'rename folder reports to monthly reports').",
            "windows.move": "- windows.move: Move a file or folder to another location (e.g. 'move reports.pdf to documents', 'move the project folder into the projects folder').",
            "windows.delete": "- windows.delete: Delete a file or folder (e.g. 'delete the file notes.txt from desktop').",
            "windows.open_location": "- windows.open_location: Open a folder or file's location in Explorer or VS Code (e.g. 'open the projects folder in explorer', 'open folder in vscode').",
        }

    # ────────────────────────── Parsing Helpers ──────────────────────────

    @staticmethod
    def _normalize_name(text: str) -> str:
        """Cleans a name/phrase by removing trigger words and punctuation."""
        cleaned = re.sub(
            r"\b(?:please|create|make|add|the|a|an|folder|directory|file|"
            r"new\s+(?:folder|directory|file)|"
            r"rename|move|delete|remove|erase|open|launch|start|named|called|app|"
            r"application|program|me|for|from|with|into|inside|on|to|in|at|as)\b",
            " ", text, flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .!?,_-")
        return cleaned

    def _extract_name(self, text: str) -> str:
        """Extracts the object name out of a creation command."""
        quoted = re.search(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted.group(1).strip()
        
        # Check for explicit name patterns: "name it as X", "named X", "called X", "name X"
        m_name = re.search(
            r"\b(?:name\s+it\s+as|named\s+as|name\s+it|named|called|with\s+name)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|on|to|at|inside|into|under)\b|$)",
            text, flags=re.IGNORECASE
        )
        if m_name:
            cand = m_name.group(1).strip(" .!?,_-")
            # If the extracted candidate is not empty and not purely stop words
            if cand and not all(w.lower() in STOP_WORDS for w in cand.split()):
                return cand

        # Drop the trailing location clause if present ("... on the desktop")
        head = re.split(r"\b(?:on|in|to|at|under|inside|into)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
        return self._normalize_name(head)

    def _resolve_location(self, text: str, default_root: Optional[str] = None
                          ) -> Tuple[str, str]:
        """Finds (base_root, sub_path) from location words in the text.

        e.g. "e drive inside projects folder" -> ("E:", "projects")
             "documents"                       -> (~/Documents, "")
             "on the desktop"                  -> (~/Desktop, "")
        """
        if default_root is None:
            default_root = ROOT_PATHS.get("desktop", os.path.expanduser("~/Desktop"))

        # Strip explicit "name it as X" / "named X" clauses so they aren't parsed as sub-folders
        clean_text = re.sub(
            r"\b(?:name\s+it\s+as|named\s+as|name\s+it|named|called|with\s+name)\s+[a-zA-Z0-9_\-\.\s]+",
            " ", text, flags=re.IGNORECASE
        )

        m = re.search(
            r"\b(?:in|on|to|at|inside|into|under)\s+(.+)$",
            clean_text, flags=re.IGNORECASE,
        )
        loc_phrase = (m.group(1) if m else "").strip()

        base = None
        # Drive letter first ("e drive", "drive e", "e:", "e: drive")
        dm = re.search(
            r"\b([a-z])\s*(?:drive|colon)\b|\bdrive\s+([a-z])\b|\b([a-z]):",
            loc_phrase, flags=re.IGNORECASE,
        )
        if dm:
            drive = (dm.group(1) or dm.group(2) or dm.group(3) or "").upper()
            base = f"{drive}:\\"
            loc_phrase = re.sub(
                r"\b[a-z]\s*(?:drive|colon)\b|\bdrive\s+[a-z]\b|\b[a-z]:",
                " ", loc_phrase, flags=re.IGNORECASE,
            )
        else:
            # Known root folder keyword
            for key, path in ROOT_PATHS.items():
                if re.search(rf"\b{re.escape(key)}\b", loc_phrase, re.IGNORECASE):
                    base = os.path.expanduser(path)
                    loc_phrase = re.sub(
                        rf"\b{re.escape(key)}\b", " ", loc_phrase, flags=re.IGNORECASE)
                    break

        if base is None:
            base = default_root

        # Remaining words form a sub-path ("inside projects folder" -> projects)
        words = [
            w for w in re.split(r"[\s,]+", loc_phrase)
            if w and w.lower() not in STOP_WORDS
        ]
        sub_path = os.path.join(*words) if words else ""
        if sub_path:
            sub_path = sub_path.strip(" .!?-_\\/")
        return base, sub_path

    def _resolve_path(self, text: str, default_root: Optional[str] = None) -> str:
        r"""Resolves 'base\sub_path' from location words into one absolute path."""
        base, sub = self._resolve_location(text, default_root)
        if sub:
            return os.path.join(base, sub)
        return base

    def find_object(self, base: str, name: str, is_dir: Optional[bool] = None) -> Optional[str]:
        """Fuzzy-matches name against first-level entries in base."""
        try:
            entries = os.listdir(base)
        except OSError:
            return None

        best_path, best_score = None, 0.0
        for entry in entries:
            full = os.path.join(base, entry)
            if is_dir is not None and os.path.isdir(full) != is_dir:
                continue
            low_entry = entry.lower()
            low_name = name.lower()
            score = difflib.SequenceMatcher(None, low_name, low_entry).ratio()
            if low_name in low_entry or low_entry.startswith(low_name):
                score = max(score, 0.85)
            if score > best_score:
                best_score, best_path = score, full
        if best_score >= 0.65:
            return best_path
        return None

    # ────────────────────────── Action Implementations ──────────────────────────

    def open_settings(self, text: str) -> bool:
        logger.info(f"Plugin Action: Opening Windows Settings page for '{text}'")
        low = text.strip(" .!?, ")
        if not low or low.lower() in ("settings", "windows settings", "system settings", "settings app"):
            low = "system"
        for key, uri in SETTINGS_PAGES.items():
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                try:
                    subprocess.Popen(f"start {uri}", shell=True)
                    logger.info(f"Opened Settings page: {uri}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to open settings '{uri}': {e}")
                    return False
        try:
            subprocess.Popen("start ms-settings:", shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")
            return False

    def open_app(self, text: str) -> bool:
        query = self._normalize_name(text).strip()
        logger.info(f"Plugin Action: Opening application '{query}'")
        if not query:
            return False

        low = text.lower()
        # 1. Known special apps
        for key, launch in SPECIAL_APPS.items():
            if key in low:
                try:
                    if launch.startswith("ms-"):
                        subprocess.Popen(f"start {launch}", shell=True)
                    else:
                        subprocess.Popen(f"start {launch}", shell=True)
                    logger.info(f"Launched special app: {key}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to launch special app '{key}': {e}")
                    return False

        # 2. Search Start Menu (handles UWP + classic apps) and launch best match
        safe = query.replace("'", "''")
        ps = (
            "$app = Get-StartApps | Where-Object {{ $_.Name -like '*{0}*' }} "
            "| Select-Object -First 1; "
            "if ($app) {{ if ($app.AppID -like '*\\*' -or $app.AppID -like '*.exe') "
            "{{ Start-Process $app.AppID }} "
            "else {{ explorer.exe ('shell:AppsFolder\\' + $app.AppID) }} }}\n"
        ).format(safe)
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"App launch command failed: {result.stderr.strip()}")
                return False
            logger.info(f"Launched app matching '{query}'")
            return True
        except Exception as e:
            logger.error(f"Failed to launch application '{query}': {e}")
            return False

    def create_folder(self, text: str) -> bool:
        name = self._extract_name(text)
        if not name:
            logger.warning("No folder name detected.")
            return False
        target = self._resolve_path(text)
        path = os.path.join(target, name)
        logger.info(f"Plugin Action: Creating folder '{path}'")
        try:
            os.makedirs(path, exist_ok=True)
            logger.info(f"Folder created: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create folder '{path}': {e}")
            return False

    def create_file(self, text: str) -> bool:
        name = self._extract_name(text)
        if not name:
            logger.warning("No file name detected.")
            return False
        target = self._resolve_path(text)
        path = os.path.join(target, name)
        logger.info(f"Plugin Action: Creating file '{path}'")
        try:
            os.makedirs(target, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("")
            logger.info(f"File created: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create file '{path}': {e}")
            return False

    def rename(self, text: str) -> bool:
        logger.info(f"Plugin Action: Rename request '{text}'")
        # "rename <old> to <new>"
        parts = re.split(r"\s+(?:to|into)\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            return False
        old_phrase, new_phrase = parts

        # Which type is being renamed?
        want_dir = None
        if re.search(r"\bfolder\b|\bdirectory\b", old_phrase, re.IGNORECASE):
            want_dir = True
        elif re.search(r"\bfile\b", old_phrase, re.IGNORECASE):
            want_dir = False

        old_name = self._normalize_name(old_phrase)
        # New name = everything before a trailing location clause
        new_head = re.split(r"\b(?:on|in|at|under|to)\b", new_phrase, maxsplit=1, flags=re.IGNORECASE)[0]
        new_name = self._normalize_name(new_head).strip(" .!?-_/\\")
        if not old_name or not new_name:
            return False

        base = self._resolve_path(text)
        src = self.find_object(base, old_name, is_dir=want_dir)
        if not src:
            logger.warning(f"Could not find '{old_name}' under {base}")
            return False
        dst = os.path.join(os.path.dirname(src), new_name)
        try:
            os.rename(src, dst)
            logger.info(f"Renamed '{src}' -> '{dst}'")
            return True
        except Exception as e:
            logger.error(f"Failed to rename '{src}': {e}")
            return False

    def move(self, text: str) -> bool:
        logger.info(f"Plugin Action: Move request '{text}'")
        # "move <what> to <where>"
        parts = re.split(r"\s+(?:to|into|inside)\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            return False
        target_phrase, dest_phrase = parts

        want_dir = None
        if re.search(r"\bfolder\b|\bdirectory\b", target_phrase, re.IGNORECASE):
            want_dir = True
        elif re.search(r"\bfile\b", target_phrase, re.IGNORECASE):
            want_dir = False

        src_name = self._normalize_name(target_phrase)
        if not src_name:
            return False

        # Source: perhaps given explicitly ("from downloads"), else default root
        src_loc = ""
        fm = re.search(r"\bfrom\s+(.+)$", target_phrase, re.IGNORECASE)
        if fm:
            src_loc = fm.group(1)
            src_name = self._normalize_name(target_phrase[:fm.start()])
        src_base = self._resolve_location(src_loc)[0]
        src = self.find_object(src_base, src_name, is_dir=want_dir)
        if not src:
            logger.warning(f"Could not find '{src_name}' under {src_base}")
            return False

        dest = self._resolve_path(dest_phrase)
        try:
            os.makedirs(dest, exist_ok=True)
            final = shutil.move(src, dest)
            logger.info(f"Moved '{src}' -> '{final}'")
            return True
        except Exception as e:
            logger.error(f"Failed to move '{src}' to '{dest}': {e}")
            return False

    def delete(self, text: str) -> bool:
        logger.info(f"Plugin Action: Delete request '{text}'")
        want_dir = None
        if re.search(r"\bfolder\b|\bdirectory\b", text, re.IGNORECASE):
            want_dir = True
        elif re.search(r"\bfile\b", text, re.IGNORECASE):
            want_dir = False

        name = self._normalize_name(text)
        if not name:
            return False

        base = self._resolve_path(text)
        # Safety: never delete the location root itself
        if name.lower() in {os.path.basename(base).lower(), "this pc"} or not self.find_object:
            pass
        target = self.find_object(base, name, is_dir=want_dir)
        if not target or os.path.abspath(target) == os.path.abspath(base):
            logger.warning(f"Delete target not found or unsafe: '{name}' under {base}")
            return False

        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
                logger.info(f"Deleted folder: {target}")
            else:
                os.remove(target)
                logger.info(f"Deleted file: {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete '{target}': {e}")
            return False

    def open_location(self, text: str) -> bool:
        logger.info(f"Plugin Action: Open location request '{text}'")
        low = text.lower()
        open_in_vscode = bool(re.search(r"\b(vscode|vs\s*code|code\s*editor)\b", low))

        # --- Resolve the actual path ---
        # First try drive letter detection on the FULL text (not just after prepositions)
        dm = re.search(
            r"\b([a-z])\s*(?:drive|colon)\b|\bdrive\s+([a-z])\b|\b([a-z]):",
            low, flags=re.IGNORECASE,
        )
        if dm:
            drive = (dm.group(1) or dm.group(2) or dm.group(3) or "").upper()
            actual = f"{drive}:\\"
            # Check if there's a sub-path after the drive reference
            remaining = re.sub(
                r"\b[a-z]\s*(?:drive|colon)\b|\bdrive\s+[a-z]\b|\b[a-z]:",
                " ", low, flags=re.IGNORECASE,
            )
            remaining = re.sub(
                r"\b(?:open|show|explore|in|on|to|at|inside|into|under|the|my|folder|directory|file\s*explorer|explorer|location|please)\b",
                " ", remaining, flags=re.IGNORECASE,
            ).strip(" .!?,_-")
            remaining = re.sub(r"\s+", " ", remaining).strip()
            if remaining:
                sub_parts = [p.strip() for p in remaining.split() if p.strip()]
                if sub_parts:
                    actual = os.path.join(actual, *sub_parts[:3])
        else:
            # Check for known root folders in the full text
            found_root = False
            for key, path in ROOT_PATHS.items():
                if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                    actual = os.path.expanduser(path)
                    found_root = True
                    break
            if not found_root:
                # Fall back to plugin's own resolve
                actual = self._resolve_path(text)
                name = self._normalize_name(text)
                if name and os.path.isdir(actual):
                    found = self.find_object(actual, name)
                    if found:
                        actual = found

        if open_in_vscode:
            try:
                subprocess.Popen(f'code "{actual}"', shell=True)
                logger.info(f"Opened in VS Code: {actual}")
                return True
            except Exception as e:
                logger.error(f"Failed to open in VS Code: {e}")
                return False

        try:
            subprocess.Popen(f'explorer "{actual}"', shell=True)
            logger.info(f"Opened in Explorer: {actual}")
            return True
        except Exception as e:
            logger.error(f"Failed to open in Explorer: {e}")
            return False

    # ────────────────────────── Task Manager & Active Window Navigation ──────────────────────────

    def _ensure_taskmgr_focused(self) -> bool:
        """
        Ensures Task Manager is running and focused in the foreground.
        Uses window_manager (UIA stack) for focus detection and control.
        If already active: returns True immediately.
        If running in background: restores and focuses window.
        If not open: launches taskmgr.exe and waits for UI to initialize.
        """
        import time
        from computer_use.window_manager import window_manager

        if window_manager.is_window_active("Task Manager") or window_manager.is_window_active("taskmgr"):
            return True

        if window_manager.focus_window("Task Manager") or window_manager.focus_window("taskmgr"):
            time.sleep(0.15)
            return True

        # Launch Task Manager if not already open
        try:
            logger.info("Task Manager not running, launching taskmgr.exe...")
            subprocess.Popen("start taskmgr.exe", shell=True)
            for _ in range(15):
                time.sleep(0.2)
                if window_manager.focus_window("Task Manager") or window_manager.focus_window("taskmgr"):
                    time.sleep(0.5)  # Wait for UI components to finish loading
                    return True
            return True
        except Exception as e:
            logger.error(f"Failed to launch Task Manager: {e}")
            return False

    def _navigate_taskmgr_tab(self, tab_name: str, access_char: str, tab_digit: int) -> bool:
        """
        Navigates to a specific tab in Task Manager using UIA element selection.
        Primary:  UIA TabItem select() via pywinauto (computer_use.actions)
        Fallback: pyautogui hotkey (Alt+access_char, Ctrl+digit)
        """
        import time
        from computer_use.window_manager import window_manager
        from computer_use.actions import computer_actions

        if not self._ensure_taskmgr_focused():
            return False

        window_manager.focus_window("Task Manager")
        time.sleep(0.15)
        logger.info(f"Task Manager: Switching to tab '{tab_name}' (UIA select)")

        # 1. Primary: UIA — find TabItem by name and call .select()
        if computer_actions.select_tab(tab_name):
            return True

        # 2. Fallback: pyautogui hotkeys (no ctypes/VK codes)
        try:
            import pyautogui
            pyautogui.hotkey("alt", access_char.lower())
            time.sleep(0.08)
            pyautogui.hotkey("ctrl", str(tab_digit))
        except Exception:
            pass

        return True

    def taskmgr_performance(self, text: str = "") -> bool:
        """Switches to the Performance tab in Task Manager (UIA select / Ctrl+2 fallback)."""
        logger.info("Plugin Action: Task Manager -> Performance Tab")
        return self._navigate_taskmgr_tab("Performance", "e", 2)

    def taskmgr_processes(self, text: str = "") -> bool:
        """Switches to the Processes tab in Task Manager (UIA select / Ctrl+1 fallback)."""
        logger.info("Plugin Action: Task Manager -> Processes Tab")
        return self._navigate_taskmgr_tab("Processes", "p", 1)

    def taskmgr_startup(self, text: str = "") -> bool:
        """Switches to the Startup apps tab in Task Manager (UIA select / Ctrl+4 fallback)."""
        logger.info("Plugin Action: Task Manager -> Startup Apps Tab")
        return self._navigate_taskmgr_tab("Startup apps", "s", 4)

    def taskmgr_app_history(self, text: str = "") -> bool:
        """Switches to the App history tab in Task Manager (UIA select / Ctrl+3 fallback)."""
        logger.info("Plugin Action: Task Manager -> App History Tab")
        return self._navigate_taskmgr_tab("App history", "a", 3)

    def taskmgr_users(self, text: str = "") -> bool:
        """Switches to the Users tab in Task Manager (UIA select / Ctrl+5 fallback)."""
        logger.info("Plugin Action: Task Manager -> Users Tab")
        return self._navigate_taskmgr_tab("Users", "u", 5)

    def taskmgr_details(self, text: str = "") -> bool:
        """Switches to the Details tab in Task Manager (UIA select / Ctrl+6 fallback)."""
        logger.info("Plugin Action: Task Manager -> Details Tab")
        return self._navigate_taskmgr_tab("Details", "d", 6)

    def taskmgr_services(self, text: str = "") -> bool:
        """Switches to the Services tab in Task Manager (UIA select / Ctrl+7 fallback)."""
        logger.info("Plugin Action: Task Manager -> Services Tab")
        return self._navigate_taskmgr_tab("Services", "v", 7)

    def taskmgr_end_task(self, text: str = "") -> bool:
        """Ends the currently selected task in Task Manager via UIA or Delete key."""
        logger.info("Plugin Action: Task Manager -> End Task")
        if not self._ensure_taskmgr_focused():
            return False
        try:
            import pyautogui
            pyautogui.press("delete")
        except Exception:
            pass
        return True

    def taskmgr_run_task(self, text: str = "") -> bool:
        """Opens the Run New Task dialog in Task Manager (Alt+N)."""
        logger.info("Plugin Action: Task Manager -> Run New Task")
        if not self._ensure_taskmgr_focused():
            return False
        try:
            import pyautogui
            pyautogui.hotkey("alt", "n")
        except Exception:
            pass
        return True
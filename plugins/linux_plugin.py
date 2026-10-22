"""
Linux operating-system automation plugin.

This is the Linux counterpart of `plugins/windows_plugin.py`. It exposes the
SAME action names (`windows.*`) so the command catalogue, the trained intent
model and the Ollama tool specifications keep working unchanged on Linux —
only the implementation behind them differs.

Everything here is built on `core.platform`, which already knows how to talk
to X11/Wayland, PipeWire/PulseAudio, the freedesktop settings applications
and the standard shell utilities. The plugin therefore degrades gracefully:
when a helper tool is not installed, the action reports failure instead of
crashing the assistant.
"""

import difflib
import logging
import os
import re
import shutil
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

from core.platform import (
    IS_LINUX,
    desktop_path,
    documents_path,
    downloads_path,
    open_settings as platform_open_settings,
    pictures_path,
    shell_folders,
)
from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugin.Linux")


# ── Linux equivalents of the Windows Settings pages ─────────────────────────
LINUX_SETTINGS_PAGES: Dict[str, str] = {
    "bluetooth": "bluetooth",
    "wifi": "network",
    "wi-fi": "network",
    "network": "network",
    "ethernet": "network",
    "airplane": "network",
    "display": "display",
    "resolution": "display",
    "sound": "sound",
    "volume": "sound",
    "audio": "sound",
    "notifications": "notifications",
    "background": "background",
    "themes": "appearance",
    "appearance": "appearance",
    "colors": "appearance",
    "lock screen": "screen-lock",
    "lockscreen": "screen-lock",
    "privacy": "privacy",
    "camera": "privacy",
    "webcam": "privacy",
    "microphone": "privacy",
    "mic": "privacy",
    "apps": "applications",
    "default apps": "default-applications",
    "accounts": "user-accounts",
    "sign in": "user-accounts",
    "time": "datetime",
    "date": "datetime",
    "language": "language",
    "storage": "storage",
    "battery": "power",
    "power": "power",
    "troubleshoot": "diagnostics",
    "device": "bluetooth",
    "devices": "bluetooth",
    "mouse": "mouse",
    "keyboard": "keyboard",
    "update": "software-updates",
    "windows update": "software-updates",
    "system": "system",
    "about": "system",
    "startup apps": "startup-applications",
    "startup": "startup-applications",
    "default browser": "default-applications",
    "printers": "printers",
    "printer": "printers",
    "accessibility": "universal-access",
    "multitasking": "workspaces",
    "hotspot": "sharing",
    "mobile hotspot": "sharing",
    "sharing": "sharing",
    "online accounts": "online-accounts",
    "user accounts": "user-accounts",
    "date and time": "datetime",
    "region and language": "language",
}

# Applications that have a dedicated binary or .desktop entry.
SPECIAL_APPS: Dict[str, str] = {
    "calculator": "gnome-calculator",
    "text editor": "gedit",
    "notepad": "gedit",
    "paint": "pinta",
    "image viewer": "eog",
    "photos": "shotwell",
    "camera": "cheese",
    "clocks": "gnome-clocks",
    "calendar": "gnome-calendar",
    "music": "rhythmbox",
    "videos": "totem",
    "movies": "totem",
    "files": "nautilus",
    "file manager": "nautilus",
    "terminal": "gnome-terminal",
    "console": "gnome-terminal",
    "system monitor": "gnome-system-monitor",
    "task manager": "gnome-system-monitor",
    "disks": "gnome-disks",
    "software": "gnome-software",
    "app store": "gnome-software",
    "help": "yelp",
    "screenshot": "gnome-screenshot",
    "screen recorder": "gnome-screen-recorder",
    "fonts": "gnome-font-viewer",
    "remmina": "remmina",
    "dconf editor": "dconf-editor",
    "archive manager": "file-roller",
    "text editor": "gedit",
}

# Administrative / diagnostic tools.
SYSTEM_TOOLS: Dict[str, str] = {
    "system monitor": "gnome-system-monitor",
    "task manager": "gnome-system-monitor",
    "processes": "gnome-system-monitor",
    "disks": "gnome-disks",
    "disk usage": "baobab",
    "storage analyzer": "baobab",
    "system information": "gnome-system-monitor",
    "hardware": "gnome-system-monitor",
    "network tools": "gnome-nm-connection-editor",
    "firewall": "gufw",
    "users": "gnome-system-monitor",
    "startup applications": "gnome-session-properties",
    "keyboard settings": "gnome-control-center keyboard",
    "printers": "gnome-printers",
    "fonts": "gnome-font-viewer",
    "logs": "gnome-logs",
    "journal": "gnome-logs",
}

#: Power / session actions.
SYSTEM_ACTIONS: Dict[str, List[str]] = {
    "lock pc": ["loginctl", "lock-session"],
    "lock screen": ["loginctl", "lock-session"],
    "log off": ["loginctl", "terminate-user", ""],
    "logoff": ["loginctl", "terminate-user", ""],
    "sign out": ["loginctl", "terminate-user", ""],
    "sleep": ["systemctl", "suspend"],
    "standby": ["systemctl", "suspend"],
    "suspend": ["systemctl", "suspend"],
    "hibernate": ["systemctl", "hibernate"],
    "restart": ["systemctl", "reboot"],
    "reboot": ["systemctl", "reboot"],
    "restart pc": ["systemctl", "reboot"],
    "shutdown": ["systemctl", "poweroff"],
    "shut down": ["systemctl", "poweroff"],
    "turn off pc": ["systemctl", "poweroff"],
}

#: Volume intent patterns.
VOLUME_PATTERNS: Dict[str, str] = {
    "mute": "mute",
    "unmute": "unmute",
    "silence": "mute",
    "volume up": "up",
    "increase volume": "up",
    "turn up the volume": "up",
    "turn up volume": "up",
    "louder": "up",
    "volume down": "down",
    "decrease volume": "down",
    "turn down the volume": "down",
    "turn down volume": "down",
    "lower the volume": "down",
    "quieter": "down",
    "volume": "up",
}

#: Default browser candidates per vendor.
DEFAULT_BROWSER: Dict[str, str] = {
    "chrome": "google-chrome.desktop",
    "google chrome": "google-chrome.desktop",
    "brave": "brave-browser.desktop",
    "brave browser": "brave-browser.desktop",
    "edge": "microsoft-edge.desktop",
    "firefox": "firefox.desktop",
}


def _run(cmd: List[str], timeout: float = 10.0) -> Tuple[int, str]:
    """Runs a command and returns (returncode, stdout)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:
        logger.debug(f"_run failed for {cmd}: {e}")
        return 1, ""


def _spawn(cmd: List[str]) -> bool:
    """Starts a detached process."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.debug(f"_spawn failed for {cmd}: {e}")
        return False


class LinuxPlugin(BasePlugin):
    """
    Linux Automation plugin: file/folder management, app launching,
    system settings navigation and session control.
    """

    id = "linux"
    name = "Linux Automation"
    icon = "🐧"
    description = (
        "Linux file and system automation: create/rename/move/delete files and "
        "folders, open applications, open system settings pages and control the "
        "session (lock, suspend, reboot, shutdown)."
    )
    version = "1.0.0"
    author = "PRIVACY68 Core"
    is_builtin = True
    category = "System"
    plugin_type = "System & Automation"

    supported_platforms = ("linux",)

    # ────────────────────────── Action catalogue ──────────────────────────
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
            "windows.control_panel": self.control_panel,
            "windows.open_system_tool": self.open_system_tool,
            "windows.system_action": self.system_action,
            "windows.volume_control": self.volume_control,
            "windows.brightness": self.brightness,
            "windows.system_info": self.system_info,
            "windows.empty_recycle_bin": self.empty_recycle_bin,
            "windows.open_run": self.open_run,
            "windows.screenshot": self.screenshot,
            "windows.show_desktop": self.show_desktop,
            "windows.window_control": self.window_control,
            "windows.clipboard_clear": self.clipboard_clear,
            "windows.toggle_connectivity": self.toggle_connectivity,
            "windows.set_default_browser": self.set_default_browser,
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
                "open settings", "open system settings", "open linux settings",
                "open control center", "open the settings app", "system settings",
            ],
            "windows.open_app": [
                "open application", "open app", "launch application", "launch app",
                "open program", "run application", "start application",
            ],
            "windows.create_folder": [
                "create folder", "make folder", "create a new folder",
                "create directory", "make a directory", "new folder",
            ],
            "windows.create_file": [
                "create file", "make file", "create a new file", "new text file",
            ],
            "windows.rename": [
                "rename file", "rename folder", "rename this file", "rename this folder",
                "change the name of", "rename",
            ],
            "windows.move": [
                "move file", "move folder", "move this file", "move to",
                "move this folder to", "transfer file",
            ],
            "windows.delete": [
                "delete file", "delete folder", "delete this file", "delete this folder",
                "remove file", "remove folder", "trash this", "send to trash",
            ],
            "windows.open_location": [
                "open downloads", "open desktop", "open documents", "open pictures",
                "open home folder", "open file manager", "open files", "open my computer",
            ],
            "windows.control_panel": [
                "control panel", "open control panel", "system configuration",
            ],
            "windows.open_system_tool": [
                "open system tool", "open system monitor", "open task manager",
                "open disk usage", "open processes", "open system information",
            ],
            "windows.system_action": [
                "lock the pc", "lock the computer", "lock screen", "lock my computer",
                "sign out", "log out", "log off", "sleep", "suspend", "hibernate",
                "restart the pc", "restart the computer", "restart", "reboot the pc",
                "reboot", "restart my pc", "shut down the pc", "shutdown",
                "shut down", "turn off pc", "cancel shutdown",
            ],
            "windows.volume_control": [
                "volume up", "volume down", "mute", "unmute", "louder", "quieter",
                "increase volume", "decrease volume", "toggle mute",
            ],
            "windows.brightness": [
                "brightness up", "brightness down", "increase brightness",
                "decrease brightness", "make the screen brighter", "dim the screen",
            ],
            "windows.system_info": [
                "system information", "system info", "battery level", "battery status",
                "disk space", "disk usage", "memory usage", "ram usage", "cpu usage",
                "ip address", "my ip", "uptime", "operating system version",
                "linux version", "os version", "wifi network",
            ],
            "windows.empty_recycle_bin": [
                "empty recycle bin", "empty trash", "clear trash", "empty the trash",
            ],
            "windows.open_run": [
                "open run", "open run dialog", "run command", "execute command",
            ],
            "windows.screenshot": [
                "take a screenshot", "take screenshot", "capture screen", "screenshot",
            ],
            "windows.show_desktop": [
                "show desktop", "minimize all", "minimize all windows",
            ],
            "windows.window_control": [
                "maximize window", "maximize this window", "maximize",
                "minimize window", "minimize this window", "minimize",
                "restore window", "close window", "close this window", "close app",
            ],
            "windows.clipboard_clear": [
                "clear clipboard", "empty clipboard", "wipe clipboard",
            ],
            "windows.toggle_connectivity": [
                "toggle connectivity", "turn wifi on", "turn wifi off",
                "toggle wifi", "toggle network", "airplane mode",
            ],
            "windows.set_default_browser": [
                "set default browser", "change default browser", "default browser",
            ],
            "windows.taskmgr_performance": ["task manager performance", "performance tab"],
            "windows.taskmgr_processes": ["task manager processes", "processes tab"],
            "windows.taskmgr_startup": ["task manager startup", "startup apps tab"],
            "windows.taskmgr_app_history": ["task manager app history", "app history tab"],
            "windows.taskmgr_users": ["task manager users", "users tab"],
            "windows.taskmgr_details": ["task manager details", "details tab"],
            "windows.taskmgr_services": ["task manager services", "services tab"],
            "windows.taskmgr_end_task": ["end task", "kill selected task"],
            "windows.taskmgr_run_task": ["run new task", "run task"],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "windows.open_settings": "- windows.open_settings: Open a Linux system settings page (bluetooth, network, sound, display, privacy, ...).",
            "windows.open_app": "- windows.open_app: Launch a Linux desktop application by name (e.g. 'open Firefox', 'launch VS Code').",
            "windows.create_folder": "- windows.create_folder: Create a new folder in a given location.",
            "windows.create_file": "- windows.create_file: Create a new text file in a given location.",
            "windows.rename": "- windows.rename: Rename a file or folder.",
            "windows.move": "- windows.move: Move a file or folder to another location.",
            "windows.delete": "- windows.delete: Delete a file or folder permanently.",
            "windows.open_location": "- windows.open_location: Open a well-known location such as Downloads, Desktop or Documents.",
            "windows.control_panel": "- windows.control_panel: Open the desktop configuration panel.",
            "windows.open_system_tool": "- windows.open_system_tool: Open a Linux system tool (system monitor, disk usage, logs).",
            "windows.system_action": "- windows.system_action: Lock, suspend, sign out, restart or shut down the machine, or cancel a pending shutdown.",
            "windows.volume_control": "- windows.volume_control: Raise, lower, mute or unmute the system volume.",
            "windows.brightness": "- windows.brightness: Increase or decrease the screen brightness.",
            "windows.system_info": "- windows.system_info: Report battery, disk, memory, CPU, network or uptime information.",
            "windows.empty_recycle_bin": "- windows.empty_recycle_bin: Empty the user's trash.",
            "windows.open_run": "- windows.open_run: Run a command or open the application launcher.",
            "windows.screenshot": "- windows.screenshot: Capture the screen and save it to the Pictures folder.",
            "windows.show_desktop": "- windows.show_desktop: Minimise every window and show the desktop.",
            "windows.window_control": "- windows.window_control: Maximize, minimize, restore or close the active window.",
            "windows.clipboard_clear": "- windows.clipboard_clear: Clear the clipboard.",
            "windows.toggle_connectivity": "- windows.toggle_connectivity: Toggle the Wi-Fi or network connection.",
            "windows.set_default_browser": "- windows.set_default_browser: Choose the default web browser.",
        }

    # ────────────────────────── Helpers ──────────────────────────
    def _normalize_name(self, text: str) -> str:
        """Strips filler words from a spoken file or folder name."""
        cleaned = re.sub(
            r"^\s*(?:please\s*)?(?:can\s+you\s+)?(?:create|make|new|open|"
            r"delete|remove|rename|move|copy)?\s*(?:a\s+)?(?:new\s+)?"
            r"(?:file|folder|directory|text file|document)?\s*(?:named|called)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^\s*(?:on|in|to|from|inside|under|at)\s+", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" .!?,_'\"")

    def _resolve_path(self, text: str) -> str:
        """Resolves the target directory of a file/folder command."""
        from computer_use.system_tools import resolve_path

        return resolve_path(text, default_root=desktop_path())

    def _extract_name(self, text: str) -> str:
        """Extracts the new file or folder name from an utterance."""
        match = re.search(
            r"\b(?:named|called)\s+(.+)$", text, flags=re.IGNORECASE
        )
        if match:
            return match.group(1).strip(" .!?,_'\"")

        cleaned = self._normalize_name(text)
        cleaned = re.sub(
            r"\s+(?:on|in|to|from|inside|under|at)\s+.*$", "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\s+(?:and|then|with)\s+.*$", "", cleaned, flags=re.IGNORECASE
        )
        return cleaned.strip(" .!?,_'\"")

    def find_object(self, base: str, name: str, is_dir: Optional[bool] = None) -> Optional[str]:
        """Fuzzy-matches a name against the first-level entries of `base`."""
        try:
            entries = os.listdir(base)
        except OSError:
            return None

        best_path, best_score = None, 0.0
        low_name = name.lower()
        for entry in entries:
            full = os.path.join(base, entry)
            if is_dir is not None and os.path.isdir(full) != is_dir:
                continue
            low_entry = entry.lower()
            score = difflib.SequenceMatcher(None, low_name, low_entry).ratio()
            if low_name in low_entry or low_entry.startswith(low_name):
                score = max(score, 0.85)
            if score > best_score:
                best_score, best_path = score, full
        if best_score >= 0.65:
            return best_path
        return None

    # ────────────────────────── Action implementations ──────────────────────────
    def open_settings(self, text: str) -> bool:
        """Opens the desktop settings application on the requested page."""
        logger.info(f"Plugin Action: Opening system settings page for '{text}'")
        low = text.strip(" .!?, ").lower()
        page = ""
        for key in sorted(LINUX_SETTINGS_PAGES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low):
                page = LINUX_SETTINGS_PAGES[key]
                break
        ok = platform_open_settings(page)
        if not ok:
            logger.warning("Plugin Action: no settings application is available")
        return ok

    def open_app(self, text: str) -> bool:
        """Launches a desktop application by name."""
        from computer_use.launcher import app_launcher

        query = self._normalize_name(text).strip()
        logger.info(f"Plugin Action: Opening application '{query}'")
        if not query:
            return False

        low = text.lower()
        for key, launch in SPECIAL_APPS.items():
            if key in low and shutil.which(launch):
                if _spawn([launch]):
                    logger.info(f"Launched special app: {key}")
                    return True

        return app_launcher.launch(query)

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
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("")
            return True
        except Exception as e:
            logger.error(f"Failed to create file '{path}': {e}")
            return False

    def rename(self, text: str) -> bool:
        """Renames a file or folder: 'rename <old> to <new>'."""
        logger.info(f"Plugin Action: Rename request '{text}'")
        parts = re.split(r"\s+(?:to|into)\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            return False
        old_phrase, new_phrase = parts

        want_dir = None
        if re.search(r"\bfolder\b|\bdirectory\b", old_phrase, re.IGNORECASE):
            want_dir = True
        elif re.search(r"\bfile\b", old_phrase, re.IGNORECASE):
            want_dir = False

        old_name = self._normalize_name(old_phrase)
        new_head = re.split(
            r"\b(?:on|in|at|under|to)\b", new_phrase, maxsplit=1, flags=re.IGNORECASE
        )[0]
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
        """Moves a file or folder: 'move <what> to <where>'."""
        logger.info(f"Plugin Action: Move request '{text}'")
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

        src_loc = ""
        fm = re.search(r"\bfrom\s+(.+)$", target_phrase, re.IGNORECASE)
        if fm:
            src_loc = fm.group(1)
            src_name = self._normalize_name(target_phrase[: fm.start()])

        from computer_use.system_tools import resolve_path

        src_base = resolve_path(src_loc, default_root=desktop_path()) if src_loc else desktop_path()
        src = self.find_object(src_base, src_name, is_dir=want_dir)
        if not src:
            logger.warning(f"Could not find '{src_name}' under {src_base}")
            return False

        dest = resolve_path(dest_phrase, default_root=desktop_path())
        try:
            os.makedirs(dest, exist_ok=True)
            final = shutil.move(src, dest)
            logger.info(f"Moved '{src}' -> '{final}'")
            return True
        except Exception as e:
            logger.error(f"Failed to move '{src}' to '{dest}': {e}")
            return False

    def delete(self, text: str) -> bool:
        """Deletes a file or folder."""
        logger.info(f"Plugin Action: Delete request '{text}'")
        want_dir = None
        if re.search(r"\bfolder\b|\bdirectory\b", text, re.IGNORECASE):
            want_dir = True
        elif re.search(r"\bfile\b", text, re.IGNORECASE):
            want_dir = False

        name = self._extract_name(text)
        if not name:
            return False

        base = self._resolve_path(text)
        target = self.find_object(base, name, is_dir=want_dir)
        if not target:
            logger.warning(f"Could not find '{name}' under {base}")
            return False

        # Never delete a whole home directory or a system root.
        protected = {
            os.path.expanduser("~"),
            desktop_path(),
            documents_path(),
            downloads_path(),
            "/", "/usr", "/etc", "/var", "/home", "/root",
        }
        if os.path.abspath(target) in protected or os.path.abspath(target) == os.path.abspath(base):
            logger.warning(f"Refusing to delete protected path '{target}'")
            return False

        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            logger.info(f"Deleted '{target}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete '{target}': {e}")
            return False

    def open_location(self, text: str) -> bool:
        """Opens a well-known location such as Downloads or Documents."""
        from core.platform import open_path

        low = text.lower()
        folders = shell_folders()
        target = None
        for key in ("downloads", "desktop", "documents", "pictures", "music", "videos", "home"):
            if key in low and key in folders:
                target = folders[key]
                break
        if not target:
            target = desktop_path()
        return open_path(target)

    def control_panel(self, text: str) -> bool:
        """Opens the desktop configuration panel."""
        logger.info(f"Plugin Action: Opening control panel for '{text}'")
        return platform_open_settings("")

    def open_system_tool(self, text: str) -> bool:
        """Opens a Linux system tool."""
        logger.info(f"Plugin Action: Opening system tool for '{text}'")
        low = text.lower()
        for key in sorted(SYSTEM_TOOLS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low):
                cmd = SYSTEM_TOOLS[key].split()
                if shutil.which(cmd[0]):
                    return _spawn(cmd)
        # Fall back to the system monitor.
        if shutil.which("gnome-system-monitor"):
            return _spawn(["gnome-system-monitor"])
        logger.warning(f"No matching system tool for '{text}'")
        return False

    def system_action(self, text: str) -> bool:
        """Lock, suspend, sign out, restart or shut down the machine."""
        logger.info(f"Plugin Action: System action '{text}'")
        low = text.lower()

        if re.search(r"\b(cancel|abort)\b", low):
            _run(["systemctl", "cancel"])
            _run(["shutdown", "-c"])
            logger.info("Cancelled pending shutdown/restart")
            return True

        for key in sorted(SYSTEM_ACTIONS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low):
                cmd = list(SYSTEM_ACTIONS[key])
                if not cmd[-1]:
                    cmd[-1] = os.environ.get("USER", "")
                if not shutil.which(cmd[0]):
                    logger.warning(f"Command '{cmd[0]}' is not available")
                    return False
                if _spawn(cmd):
                    logger.info(f"Ran system action: {' '.join(cmd)}")
                    return True
                return False

        logger.warning(f"No matching system action for '{text}'")
        return False

    def volume_control(self, text: str) -> bool:
        """Raises, lowers, mutes or unmutes the system volume."""
        from core.platform import volume_down, volume_mute, volume_up

        logger.info(f"Plugin Action: Volume control '{text}'")
        low = text.lower()
        intent = None
        for key in sorted(VOLUME_PATTERNS, key=len, reverse=True):
            if key in low:
                intent = VOLUME_PATTERNS[key]
                break
        if intent is None:
            return False

        if intent == "mute":
            return volume_mute()
        if intent == "unmute":
            # `volume_mute` toggles, so check the current state first.
            return volume_mute()
        if intent == "up":
            return volume_up()
        if intent == "down":
            return volume_down()
        return False

    def brightness(self, text: str) -> bool:
        """Increases or decreases the screen brightness."""
        logger.info(f"Plugin Action: Brightness '{text}'")
        low = text.lower()
        up = bool(re.search(r"\b(up|increase|raise|brighter|higher)\b", low))
        down = bool(re.search(r"\b(down|decrease|lower|dimmer|dim)\b", low))
        if not up and not down:
            return False

        steps = 10
        number = re.search(r"\b(\d{1,3})\b", low)
        if number:
            steps = max(1, min(100, int(number.group(1))))

        for binary, args in (
            ("brightnessctl", ["brightnessctl", "set"]),
            ("xbacklight", ["xbacklight", "-inc"]),
        ):
            if not shutil.which(binary):
                continue
            if binary == "brightnessctl":
                value = f"{steps}%" if up else f"-{steps}%"
                code, _ = _run([binary, "set", value], timeout=5)
            else:
                amount = f"{steps}" if up else f"-{steps}"
                code, _ = _run([binary, amount], timeout=5)
            if code == 0:
                return True
        logger.warning("No brightness utility (brightnessctl / xbacklight) available")
        return False

    def system_info(self, text: str) -> bool:
        """Reports read-only system information to the log and the HUD."""
        logger.info(f"Plugin Action: System information '{text}'")
        low = text.lower()
        report = ""

        if "battery" in low:
            code, out = _run(["upower", "-i", "$(upower -e | grep BAT | head -1)"], timeout=6)
            if code != 0 or not out.strip():
                code, out = _run(["cat", "/sys/class/power_supply/BAT0/capacity"], timeout=4)
                out = f"Battery capacity: {out.strip()}%" if code == 0 else ""
            report = out.strip()
        elif "disk" in low or "storage" in low:
            code, out = _run(["df", "-h", "/"], timeout=6)
            report = out.strip()
        elif "memory" in low or "ram" in low:
            code, out = _run(["free", "-h"], timeout=5)
            report = out.strip()
        elif "cpu" in low or "processor" in low:
            code, out = _run(["lscpu"], timeout=6)
            report = "\n".join(out.strip().splitlines()[:12])
        elif "ip address" in low or low.strip() in ("ip", "my ip"):
            code, out = _run(["hostname", "-I"], timeout=5)
            report = f"IP addresses: {out.strip()}"
        elif "uptime" in low:
            code, out = _run(["uptime", "-p"], timeout=5)
            report = out.strip()
        elif "wifi" in low or "wi-fi" in low:
            code, out = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi"], timeout=6)
            report = out.strip()
        else:
            from core.platform import os_release

            code, out = _run(["uname", "-a"], timeout=5)
            release = os_release()
            report = f"{release}\n{out.strip()}".strip()

        if report:
            logger.info(f"System information:\n{report}")
            return True
        return False

    def empty_recycle_bin(self, text: str) -> bool:
        """Empties the user's trash folder."""
        logger.info("Plugin Action: Emptying the trash")
        trash = os.path.join(
            os.path.expanduser("~"), ".local", "share", "Trash", "files"
        )
        if not os.path.isdir(trash):
            logger.info("Trash folder does not exist — nothing to empty")
            return True
        try:
            for entry in os.listdir(trash):
                path = os.path.join(trash, entry)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            return True
        except Exception as e:
            logger.error(f"Failed to empty the trash: {e}")
            return False

    def open_run(self, text: str) -> bool:
        """Opens the application launcher / runs a command."""
        logger.info(f"Plugin Action: Open run '{text}'")
        from computer_use.launcher import app_launcher

        query = self._normalize_name(text).strip()
        if not query:
            for binary in ("xfce4-appfinder", "gnome-shell-extension-app-search", "krunner"):
                if shutil.which(binary):
                    return _spawn([binary])
            return False
        return app_launcher.launch(query)

    def screenshot(self, text: str) -> bool:
        """Captures the screen and saves it to the Pictures folder."""
        from core.platform import take_screenshot

        logger.info("Plugin Action: Taking screenshot")
        path = take_screenshot()
        if not path:
            logger.warning("No screenshot utility available")
            return False
        logger.info(f"Screenshot saved to {path}")
        return True

    def show_desktop(self, text: str) -> bool:
        """Minimises every window to show the desktop."""
        logger.info("Plugin Action: Show desktop")
        if shutil.which("wmctrl"):
            code, _ = _run(["wmctrl", "-k"], timeout=5)
            if code == 0:
                return True
        try:
            import pyautogui

            pyautogui.hotkey("super", "d")
            return True
        except Exception as e:
            logger.debug(f"show_desktop fallback failed: {e}")
            return False

    def window_control(self, text: str) -> bool:
        """Maximizes, minimizes, restores or closes the active window."""
        from computer_use.window_manager import window_manager

        logger.info(f"Plugin Action: Window control '{text}'")
        low = text.lower()

        if "maximi" in low or "full screen" in low or "zoom" in low:
            return window_manager.maximize_window()
        if "minimi" in low:
            return window_manager.minimize_window()
        if "restore" in low or "unmaximi" in low or "un-maximi" in low:
            return window_manager.restore_window()
        if "close" in low:
            return window_manager.close_window()
        return False

    def clipboard_clear(self, text: str) -> bool:
        """Clears the clipboard."""
        logger.info("Plugin Action: Clearing the clipboard")
        for cmd in (
            ["wl-copy", "--clear"],
            ["xclip", "-selection", "clipboard", "/dev/null"],
            ["xsel", "--clipboard", "--input", "/dev/null"],
        ):
            if not shutil.which(cmd[0]):
                continue
            try:
                if cmd[0] == "xsel":
                    with open(os.devnull, "w", encoding="utf-8"):
                        pass
                    code, _ = _run(cmd, timeout=4)
                else:
                    code, _ = _run(cmd, timeout=4)
                if code == 0:
                    return True
            except Exception as e:
                logger.debug(f"clipboard_clear failed with {cmd[0]}: {e}")
        logger.warning("No clipboard utility (wl-copy / xclip / xsel) available")
        return False

    def toggle_connectivity(self, text: str) -> bool:
        """Toggles the Wi-Fi or network connection."""
        logger.info(f"Plugin Action: Toggle connectivity '{text}'")
        if not shutil.which("nmcli"):
            logger.warning("NetworkManager (nmcli) is not available")
            return False

        low = text.lower()
        current = _run(["nmcli", "-t", "radio", "wifi"], timeout=6)[1].strip()
        enabled = current.endswith("enabled")

        if re.search(r"\bturn\s+on\b|\benable\b", low) and not enabled:
            return _run(["nmcli", "radio", "wifi", "on"], timeout=6)[0] == 0
        if re.search(r"\bturn\s+off\b|\bdisable\b", low) and enabled:
            return _run(["nmcli", "radio", "wifi", "off"], timeout=6)[0] == 0

        # Plain "toggle" flips the current state.
        return _run(["nmcli", "radio", "wifi", "off" if enabled else "on"], timeout=6)[0] == 0

    def set_default_browser(self, text: str) -> bool:
        """Sets the default web browser."""
        logger.info(f"Plugin Action: Set default browser '{text}'")
        if not shutil.which("xdg-settings"):
            logger.warning("xdg-settings is not available")
            return False

        low = text.lower()
        desktop_file = ""
        for key, candidate in DEFAULT_BROWSER.items():
            if key in low:
                desktop_file = candidate
                break
        if not desktop_file:
            return False

        code, _ = _run(["xdg-settings", "set", "default-web-browser", desktop_file], timeout=6)
        return code == 0

    # ────────────────────────── System monitor shortcuts ──────────────────────────
    def _open_system_monitor(self) -> bool:
        """Opens the system monitor and gives it the keyboard focus."""
        from computer_use.window_manager import window_manager

        if not self._ensure_taskmgr_focused():
            return False
        return window_manager.focus_window("system monitor") or window_manager.focus_window(
            "gnome-system-monitor"
        )

    def _ensure_taskmgr_focused(self) -> bool:
        """Brings the system monitor to the foreground, launching it if needed."""
        from computer_use.window_manager import window_manager

        if window_manager.is_window_open("system monitor") or window_manager.is_window_open(
            "gnome-system-monitor"
        ):
            window_manager.focus_window("system monitor")
            return True
        return self.open_system_tool("system monitor")

    def taskmgr_performance(self, text: str = "") -> bool:
        """Opens the system monitor on the resources tab."""
        logger.info("Plugin Action: System monitor -> Resources")
        return self._open_system_monitor()

    def taskmgr_processes(self, text: str = "") -> bool:
        """Opens the system monitor on the processes tab."""
        logger.info("Plugin Action: System monitor -> Processes")
        return self._open_system_monitor()

    def taskmgr_startup(self, text: str = "") -> bool:
        """Opens the startup applications settings."""
        logger.info("Plugin Action: Startup applications")
        return self.open_system_tool("startup applications")

    def taskmgr_app_history(self, text: str = "") -> bool:
        """Opens the system monitor on the resources tab."""
        logger.info("Plugin Action: System monitor -> Resources")
        return self._open_system_monitor()

    def taskmgr_users(self, text: str = "") -> bool:
        """Opens the system monitor on the resources tab."""
        logger.info("Plugin Action: System monitor -> Resources")
        return self._open_system_monitor()

    def taskmgr_details(self, text: str = "") -> bool:
        """Opens the system monitor on the processes tab."""
        logger.info("Plugin Action: System monitor -> Processes")
        return self._open_system_monitor()

    def taskmgr_services(self, text: str = "") -> bool:
        """Opens the system monitor on the services view."""
        logger.info("Plugin Action: System monitor -> Services")
        return self._open_system_monitor()

    def taskmgr_end_task(self, text: str = "") -> bool:
        """Ends the currently selected process in the system monitor."""
        logger.info("Plugin Action: System monitor -> End task")
        if not self._ensure_taskmgr_focused():
            return False
        try:
            import pyautogui

            pyautogui.press("delete")
        except Exception as e:
            logger.debug(f"taskmgr_end_task: {e}")
        return True

    def taskmgr_run_task(self, text: str = "") -> bool:
        """Opens the run dialog of the system monitor."""
        logger.info("Plugin Action: System monitor -> Run new task")
        if not self._ensure_taskmgr_focused():
            return False
        try:
            import pyautogui

            pyautogui.hotkey("ctrl", "n")
        except Exception as e:
            logger.debug(f"taskmgr_run_task: {e}")
        return True

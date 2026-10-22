import logging
import os
import re
import shutil
import subprocess
from typing import Dict, Optional

from core.platform import IS_MACOS, IS_WINDOWS

logger = logging.getLogger("PRIVACY68.ComputerUse.Launcher")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Platform specific application tables
# ─────────────────────────────────────────────────────────────────────────────

# Standard Windows Built-In Application Launch Targets
WINDOWS_SYSTEM_APPS: Dict[str, Dict[str, str]] = {
    "task manager": {"cmd": "taskmgr.exe", "window_title": "Task Manager"},
    "calculator": {"cmd": "calc.exe", "protocol": "calculator:", "window_title": "Calculator"},
    "notepad": {"cmd": "notepad.exe", "window_title": "Notepad"},
    "paint": {"cmd": "mspaint.exe", "window_title": "Paint"},
    "snipping tool": {"protocol": "ms-snippingtool:", "cmd": "SnippingTool.exe", "window_title": "Snipping Tool"},
    "control panel": {"cmd": "control.exe", "window_title": "Control Panel"},
    "command prompt": {"cmd": "cmd.exe", "window_title": "Command Prompt"},
    "powershell": {"cmd": "powershell.exe", "window_title": "Windows PowerShell"},
    "terminal": {"cmd": "wt.exe", "window_title": "Terminal"},
    "file explorer": {"cmd": "explorer.exe", "window_title": "File Explorer"},
    "word": {"cmd": "winword.exe", "window_title": "Word"},
    "excel": {"cmd": "excel.exe", "window_title": "Excel"},
    "powerpoint": {"cmd": "powerpnt.exe", "window_title": "PowerPoint"},
    "spotify": {"protocol": "spotify:", "cmd": "spotify.exe", "window_title": "Spotify"},
    "settings": {"protocol": "ms-settings:", "cmd": "ms-settings:", "window_title": "Settings"},
    "camera": {"protocol": "microsoft.windows.camera:", "window_title": "Camera"},
    "photos": {"protocol": "ms-photos:", "window_title": "Photos"},
    "clock": {"protocol": "ms-clock:", "window_title": "Clock"},
    "store": {"protocol": "ms-windows-store:", "window_title": "Microsoft Store"},
    "maps": {"protocol": "bingmaps:", "window_title": "Maps"},
    "mail": {"protocol": "mailto:", "window_title": "Mail"},
    "feedback hub": {"protocol": "feedback-hub:", "window_title": "Feedback Hub"},
    "xbox": {"protocol": "xbox:", "window_title": "Xbox"},
    "device manager": {"cmd": "devmgmt.msc", "window_title": "Device Manager"},
    "disk management": {"cmd": "diskmgmt.msc", "window_title": "Disk Management"},
    "event viewer": {"cmd": "eventvwr.msc", "window_title": "Event Viewer"},
    "resource monitor": {"cmd": "resmon.exe", "window_title": "Resource Monitor"},
    "system information": {"cmd": "msinfo32.exe", "window_title": "System Information"},
    "registry editor": {"cmd": "regedit.exe", "window_title": "Registry Editor"},
    "disk cleanup": {"cmd": "cleanmgr.exe", "window_title": "Disk Cleanup"},
    "remote desktop": {"cmd": "mstsc.exe", "window_title": "Remote Desktop Connection"},
    "on screen keyboard": {"cmd": "osk.exe", "window_title": "On-Screen Keyboard"},
    "magnifier": {"cmd": "magnify.exe", "window_title": "Magnifier"},
    "character map": {"cmd": "charmap.exe", "window_title": "Character Map"},
    "sound recorder": {"protocol": "ms-callrecording:", "window_title": "Sound Recorder"},
    "sticky notes": {"protocol": "ms-stickynotes:", "window_title": "Sticky Notes"},
    "weather": {"protocol": "msnweather:", "window_title": "Weather"},
    "alarms": {"protocol": "ms-clock:", "window_title": "Clock"},
}

# Linux equivalents — resolved through PATH or the installed .desktop files.
LINUX_SYSTEM_APPS: Dict[str, Dict[str, str]] = {
    "task manager": {"cmd": "gnome-system-monitor", "window_title": "System Monitor"},
    "system monitor": {"cmd": "gnome-system-monitor", "window_title": "System Monitor"},
    "calculator": {"cmd": "gnome-calculator", "window_title": "Calculator"},
    "notepad": {"cmd": "gedit", "window_title": "Text Editor"},
    "text editor": {"cmd": "gedit", "window_title": "Text Editor"},
    "paint": {"cmd": "pinta", "window_title": "Paint"},
    "control panel": {"cmd": "gnome-control-center", "window_title": "Settings"},
    "settings": {"cmd": "gnome-control-center", "window_title": "Settings"},
    "command prompt": {"cmd": "gnome-terminal", "window_title": "Terminal"},
    "terminal": {"cmd": "gnome-terminal", "window_title": "Terminal"},
    "file explorer": {"cmd": "nautilus", "window_title": "Files"},
    "file manager": {"cmd": "nautilus", "window_title": "Files"},
    "files": {"cmd": "nautilus", "window_title": "Files"},
    "spotify": {"cmd": "spotify", "window_title": "Spotify"},
    "camera": {"cmd": "cheese", "window_title": "Cheese"},
    "photos": {"cmd": "shotwell", "window_title": "Photos"},
    "clock": {"cmd": "gnome-clocks", "window_title": "Clocks"},
    "store": {"cmd": "gnome-software", "window_title": "Software"},
    "maps": {"cmd": "gnome-maps", "window_title": "Maps"},
    "mail": {"cmd": "thunderbird", "window_title": "Thunderbird"},
    "screen recorder": {"cmd": "gnome-screen-recorder", "window_title": "Screen Recorder"},
    "vlc": {"cmd": "vlc", "window_title": "VLC media player"},
    "word processor": {"cmd": "libreoffice", "window_title": "LibreOffice Writer"},
    "spreadsheet": {"cmd": "libreoffice", "window_title": "LibreOffice Calc"},
    "presentation": {"cmd": "libreoffice", "window_title": "LibreOffice Impress"},
}

# macOS equivalents.
MACOS_SYSTEM_APPS: Dict[str, Dict[str, str]] = {
    "task manager": {"cmd": "Activity Monitor", "window_title": "Activity Monitor"},
    "calculator": {"cmd": "Calculator", "window_title": "Calculator"},
    "notepad": {"cmd": "TextEdit", "window_title": "TextEdit"},
    "text editor": {"cmd": "TextEdit", "window_title": "TextEdit"},
    "settings": {"cmd": "System Settings", "window_title": "System Settings"},
    "terminal": {"cmd": "Terminal", "window_title": "Terminal"},
    "file explorer": {"cmd": "Finder", "window_title": "Finder"},
    "file manager": {"cmd": "Finder", "window_title": "Finder"},
    "mail": {"cmd": "Mail", "window_title": "Mail"},
    "maps": {"cmd": "Maps", "window_title": "Maps"},
    "photos": {"cmd": "Photos", "window_title": "Photos"},
    "clock": {"cmd": "Clock", "window_title": "Clock"},
    "store": {"cmd": "App Store", "window_title": "App Store"},
    "camera": {"cmd": "Photo Booth", "window_title": "Photo Booth"},
    "voice memos": {"cmd": "Voice Memos", "window_title": "Voice Memos"},
}


def _system_apps() -> Dict[str, Dict[str, str]]:
    """Returns the built-in application table for the host platform."""
    if IS_WINDOWS:
        return WINDOWS_SYSTEM_APPS
    if IS_MACOS:
        return MACOS_SYSTEM_APPS
    return LINUX_SYSTEM_APPS


# Alias resolution mapping — maps genuine synonyms to canonical names
APP_ALIASES: Dict[str, str] = {
    # Task Manager
    "taskmanager": "task manager",
    "task mgr": "task manager",
    "taskmgr": "task manager",
    "system monitor": "task manager",
    "activity monitor": "task manager",
    # Calculator
    "calc": "calculator",
    # Notepad
    "note pad": "notepad",
    "text editor": "notepad",
    "gedit": "notepad",
    # Browsers
    "google chrome": "chrome",
    "brave browser": "brave",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "mozilla firefox": "firefox",
    "chromium": "chrome",
    # VS Code
    "vscode": "vs code",
    "visual studio code": "vs code",
    "code": "vs code",
    "code editor": "vs code",
    # Paint
    "ms paint": "paint",
    "microsoft paint": "paint",
    "pinta": "paint",
    # Snipping Tool
    "snip": "snipping tool",
    "screenshot tool": "snipping tool",
    "screen capture": "snipping tool",
    # Terminal / Command Line
    "windows terminal": "terminal",
    "cmd": "command prompt",
    "command line": "command prompt",
    "power shell": "powershell",
    "gnome terminal": "terminal",
    "konsole": "terminal",
    "xterm": "terminal",
    # File Explorer
    "explorer": "file explorer",
    "files": "file explorer",
    "my computer": "file explorer",
    "this pc": "file explorer",
    "file manager": "file explorer",
    "nautilus": "file explorer",
    # Communication & Social
    "whats app": "whatsapp",
    "whats": "whatsapp",
    "microsoft teams": "teams",
    "ms teams": "teams",
    # Office Suite
    "ms word": "word",
    "microsoft word": "word",
    "winword": "word",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "spreadsheet": "excel",
    "ppt": "powerpoint",
    "ms powerpoint": "powerpoint",
    "power point": "powerpoint",
    "presentation": "powerpoint",
    "ms outlook": "outlook",
    "email": "outlook",
    "one note": "onenote",
    "libreoffice writer": "word processor",
    "libreoffice calc": "spreadsheet",
    "libreoffice impress": "presentation",
    # Media & Entertainment
    "music": "spotify",
    "vlc player": "vlc",
    "media player": "vlc",
    # System & Settings
    "microsoft store": "store",
    "app store": "store",
    "gnome software": "store",
    "windows settings": "settings",
    "system settings": "settings",
    "control panel": "settings",
    "timer": "clock",
    "notes": "sticky notes",
    # System Utilities
    "system info": "system information",
    "regedit": "registry editor",
    "osk": "on screen keyboard",
    # Dev & Creative Tools
    "anti gravity": "antigravity",
    "andtygravity": "antigravity",
    "anti-gravity": "antigravity",
    "antigravity ide": "antigravity",
}

_PREFIX_RE = re.compile(r"\b(open|launch|start|switch\s+to|app|the|program|an)\b", re.IGNORECASE)
_LOCATION_RE = re.compile(
    r"\b(in|on|from|inside)\s+(?:my\s+|this\s+)?(?:computer|conputer|pc|laptop|machine|system|device)\b",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


class AppLauncher:
    """
    Deterministic & Alias-Aware Application Launcher.

    Launches system tools and user installed applications reliably without
    depending on hardcoded file paths. The lookup strategy differs per
    platform: the Windows registry and Start Menu on Windows, the installed
    `.desktop` entries on Linux and the application bundle on macOS.
    """

    _exe_cache: Dict[str, Optional[str]] = {}

    @classmethod
    def resolve_app_name(cls, raw_name: str) -> str:
        """Normalizes voice command text to a standard application name."""
        clean = _PREFIX_RE.sub(" ", raw_name.lower().strip())
        clean = _LOCATION_RE.sub(" ", clean)
        clean = _WHITESPACE_RE.sub(" ", clean).strip(" .!?,_-")
        return APP_ALIASES.get(clean, clean)

    @classmethod
    def _find_app_exe(cls, canonical_name: str) -> Optional[str]:
        """Looks up the executable path with caching via Registry, common paths, and PATH."""
        if canonical_name in cls._exe_cache:
            return cls._exe_cache[canonical_name]

        exe_names = {
            "chrome": ["chrome.exe", "google-chrome", "chromium", "chromium-browser"],
            "brave": ["brave.exe", "brave-browser"],
            "msedge": ["msedge.exe", "microsoft-edge"],
            "firefox": ["firefox.exe", "firefox"],
            "vs code": ["Code.exe", "code.cmd", "code"],
            "notepad": ["notepad.exe", "gedit", "gnome-text-editor"],
            "spotify": ["spotify.exe", "Spotify.exe", "spotify"],
            "discord": ["Discord.exe", "discord"],
            "vlc": ["vlc.exe", "vlc"],
            "whatsapp": ["whatsapp.exe", "whatsapp"],
        }.get(canonical_name, [f"{canonical_name}.exe", canonical_name, canonical_name.replace(" ", "-")])

        path = cls._find_app_exe_platform(canonical_name, exe_names)
        cls._exe_cache[canonical_name] = path
        return path

    @classmethod
    def _find_app_exe_platform(cls, canonical_name: str, exe_names: list) -> Optional[str]:
        """Platform specific executable resolution."""
        if IS_WINDOWS:
            return cls._find_app_exe_windows(canonical_name, exe_names)
        # POSIX: an executable of the same name on PATH is the primary route.
        for exe in exe_names:
            found = shutil.which(exe)
            if found and os.path.exists(found):
                return found
        return None

    @classmethod
    def _find_app_exe_windows(cls, canonical_name: str, exe_names: list) -> Optional[str]:
        """Registry, standard folders and PATH lookup on Windows."""
        import winreg

        # 1. Check App Paths registry (HKLM & HKCU)
        for exe in exe_names:
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            cleaned_val = val.strip('"')
                            if os.path.exists(cleaned_val):
                                return cleaned_val
                except Exception as e:
                    logger.debug(f"_find_app_exe: {e}")

        # 2. Check standard installation directories
        common_dirs = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        ]
        for p in common_dirs:
            if os.path.exists(p):
                p_low = p.lower()
                if (
                    (canonical_name == "chrome" and "chrome.exe" in p_low)
                    or (canonical_name == "brave" and "brave.exe" in p_low)
                    or (canonical_name in ("edge", "msedge") and "msedge.exe" in p_low)
                    or (canonical_name == "vs code" and "code.exe" in p_low)
                ):
                    return p

        # 3. Check PATH
        for exe in exe_names:
            w = shutil.which(exe)
            if w and os.path.exists(w):
                return w
        return None

    def launch(self, app_name: str) -> bool:
        """
        Launches an application by name or alias.
        If already open, brings it to foreground.
        """
        canonical = self.resolve_app_name(app_name)
        logger.info(f"Launcher: Launching '{app_name}' (resolved to '{canonical}')")

        from computer_use.window_manager import window_manager

        # 1. If window already exists, restore and focus it
        if window_manager.focus_window(canonical):
            logger.info(f"Launcher: Brought existing '{canonical}' window to foreground.")
            return True

        # 2. Check known system applications
        if canonical in _system_apps():
            info = _system_apps()[canonical]
            try:
                if "protocol" in info and self._launch_protocol(info["protocol"]):
                    return True
                if "cmd" in info:
                    self._spawn(info["cmd"])
                    logger.info(f"Launcher: Launched system app via '{info['cmd']}'")
                    return True
            except Exception as e:
                logger.error(f"Launcher: Failed to launch system app '{canonical}': {e}")

        # 3. Direct executable resolution (Chrome, Brave, VS Code, Edge, etc.)
        exe_path = self._find_app_exe(canonical)
        if exe_path:
            try:
                subprocess.Popen([exe_path])
                logger.info(f"Launcher: Launched '{canonical}' via direct executable '{exe_path}'")
                return True
            except Exception as e:
                logger.warning(f"Launcher: Failed to launch direct exe '{exe_path}': {e}")

        # 4. The installed-application index: every application the user has
        #    on this machine is here, so no plugin is needed to open it.
        from core.apps import app_index

        entry = app_index.find(canonical)
        if entry and entry.launch():
            return True

        # 5. Last resort: the protocol handler of the platform.
        if canonical == "whatsapp" and IS_WINDOWS:
            return self._launch_protocol("whatsapp:")
        if canonical == "chrome":
            return self._spawn("google-chrome") or self._spawn("chromium") or self._spawn("chrome")
        if canonical == "brave":
            return self._spawn("brave-browser") or self._spawn("brave")
        if canonical == "vs code":
            return self._spawn("code")

        return False

    def launch_and_wait(self, app_name: str, timeout: float = 4.0) -> bool:
        """Launches application and waits until its window appears and gains focus."""
        import time

        canonical = self.resolve_app_name(app_name)
        success = self.launch(canonical)
        if not success:
            return False

        from computer_use.window_manager import window_manager

        start_time = time.time()
        while time.time() - start_time < timeout:
            if window_manager.is_window_open(canonical):
                window_manager.focus_window(canonical)
                time.sleep(0.15)
                return True
            time.sleep(0.2)

        return window_manager.is_window_open(canonical)

    @staticmethod
    def _spawn(command: str) -> bool:
        """Starts a detached process, resolving the binary on PATH first."""
        binary = shutil.which(command)
        try:
            if binary:
                subprocess.Popen(
                    [binary],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            elif IS_WINDOWS:
                subprocess.Popen(f'start "" "{command}"', shell=True)
            else:
                subprocess.Popen(
                    [command],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            return True
        except Exception as e:
            logger.debug(f"_spawn failed for '{command}': {e}")
            return False

    @staticmethod
    def _launch_protocol(uri: str) -> bool:
        """Opens a URI through the desktop's default handler."""
        try:
            if IS_WINDOWS:
                subprocess.Popen(f'start "" "{uri}"', shell=True)
            else:
                subprocess.Popen(
                    ["xdg-open", uri],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            return True
        except Exception:
            return False

app_launcher = AppLauncher()

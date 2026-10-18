import logging
import os
import re
import shutil
import subprocess
import time
import winreg
from typing import Dict, List, Optional

logger = logging.getLogger("PRIVACY68.ComputerUse.Launcher")

# Standard Windows Built-In Application Launch Targets
KNOWN_SYSTEM_APPS: Dict[str, Dict[str, str]] = {
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

# Alias resolution mapping — maps genuine synonyms to canonical names
APP_ALIASES: Dict[str, str] = {
    # Task Manager
    "taskmanager": "task manager",
    "task mgr": "task manager",
    "taskmgr": "task manager",
    # Calculator
    "calc": "calculator",
    # Notepad
    "note pad": "notepad",
    "text editor": "notepad",
    # Browsers
    "google chrome": "chrome",
    "brave browser": "brave",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "mozilla firefox": "firefox",
    # VS Code
    "vscode": "vs code",
    "visual studio code": "vs code",
    "code": "vs code",
    "code editor": "vs code",
    # Paint
    "ms paint": "paint",
    "microsoft paint": "paint",
    # Snipping Tool
    "snip": "snipping tool",
    "screenshot tool": "snipping tool",
    "screen capture": "snipping tool",
    # Terminal / Command Line
    "windows terminal": "terminal",
    "cmd": "command prompt",
    "command line": "command prompt",
    "power shell": "powershell",
    # File Explorer
    "explorer": "file explorer",
    "files": "file explorer",
    "my computer": "file explorer",
    "this pc": "file explorer",
    "file manager": "file explorer",
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
    # Media & Entertainment
    "music": "spotify",
    "vlc player": "vlc",
    "media player": "vlc",
    # System & Settings
    "microsoft store": "store",
    "app store": "store",
    "windows settings": "settings",
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
    Deterministic & Alias-Aware Windows Application Launcher.
    Launches system tools and user installed applications reliably
    without depending on hardcoded file paths.
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
            "chrome": ["chrome.exe"],
            "brave": ["brave.exe"],
            "msedge": ["msedge.exe"],
            "firefox": ["firefox.exe"],
            "vs code": ["Code.exe", "code.cmd"],
            "notepad": ["notepad.exe"],
            "spotify": ["spotify.exe", "Spotify.exe"],
            "discord": ["Discord.exe"],
            "vlc": ["vlc.exe"],
        }.get(canonical_name, [f"{canonical_name}.exe"])

        # 1. Check App Paths registry (HKLM & HKCU)
        for exe in exe_names:
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            cleaned_val = val.strip('"')
                            if os.path.exists(cleaned_val):
                                cls._exe_cache[canonical_name] = cleaned_val
                                return cleaned_val
                except Exception:
                    pass

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
            r"E:\Microsoft VS Code\Code.exe",
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
                    cls._exe_cache[canonical_name] = p
                    return p

        # 3. Check PATH
        for exe in exe_names:
            w = shutil.which(exe)
            if w and os.path.exists(w):
                cls._exe_cache[canonical_name] = w
                return w

        cls._exe_cache[canonical_name] = None
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
        if canonical in KNOWN_SYSTEM_APPS:
            info = KNOWN_SYSTEM_APPS[canonical]
            try:
                if "protocol" in info and self._launch_protocol(info["protocol"]):
                    return True
                if "cmd" in info:
                    subprocess.Popen(f"start {info['cmd']}", shell=True)
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

        # 4. Fallback shell start commands
        if canonical == "chrome":
            try:
                subprocess.Popen("start chrome", shell=True)
                return True
            except Exception:
                pass

        elif canonical == "brave":
            try:
                subprocess.Popen("start brave", shell=True)
                return True
            except Exception:
                pass

        elif canonical == "vs code":
            try:
                subprocess.Popen("code", shell=True)
                return True
            except Exception:
                pass

        elif canonical == "whatsapp":
            try:
                subprocess.Popen("start whatsapp:", shell=True)
                return True
            except Exception:
                pass

        # 5. Search Windows Start Menu (UWP & Win32 installed apps)
        return self._launch_from_start_menu(canonical)

    def launch_and_wait(self, app_name: str, timeout: float = 4.0) -> bool:
        """Launches application and waits until its window appears and gains focus."""
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
    def _launch_protocol(uri: str) -> bool:
        try:
            subprocess.Popen(f"start {uri}", shell=True)
            return True
        except Exception:
            return False

    @staticmethod
    def _launch_from_start_menu(query: str) -> bool:
        """Finds and launches an app from Windows Start Menu Apps index."""
        safe_query = query.replace("'", "''")
        ps_cmd = (
            f"$app = Get-StartApps | Where-Object {{ $_.Name -like '*{safe_query}*' }} | Select-Object -First 1; "
            f"if ($app) {{ "
            f"  if ($app.AppID -like '*\\*' -or $app.AppID -like '*.exe') {{ Start-Process $app.AppID }} "
            f"  else {{ explorer.exe ('shell:AppsFolder\\' + $app.AppID) }}; "
            f"  exit 0; "
            f"}} else {{ exit 1 }}"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=8
            )
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Launcher: Start Menu search failed for '{query}': {e}")
            return False


app_launcher = AppLauncher()

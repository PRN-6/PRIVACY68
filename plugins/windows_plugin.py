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
    "account": "ms-settings:accounts",
    "sign in options": "ms-settings:signinoptions",
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

# Deep Windows Settings pages not covered by the base map
EXTRA_SETTINGS_PAGES = {
    "update": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "windows update history": "ms-settings:windowsupdate-history",
    "optional update": "ms-settings:windowsupdate-optional",
    "recovery": "ms-settings:recovery",
    "reset this pc": "ms-settings:recovery",
    "reset": "ms-settings:recovery",
    "about": "ms-settings:about",
    "system info": "ms-settings:about",
    "system information settings": "ms-settings:about",
    "printers": "ms-settings:printers",
    "printer": "ms-settings:printers",
    "printers and scanners": "ms-settings:printers",
    "accessibility": "ms-settings:easeofaccess",
    "ease of access": "ms-settings:easeofaccess",
    "magnifier settings": "ms-settings:easeofaccess-magnifier",
    "narrator settings": "ms-settings:easeofaccess-narrator",
    "start menu": "ms-settings:start",
    "optional updates": "ms-settings:windowsupdate-optional",
    "update history": "ms-settings:windowsupdate-history",
    "power and sleep": "ms-settings:powersleep",
    "notifications and actions": "ms-settings:notifications",
    "accounts": "ms-settings:accounts",
    "sync": "ms-settings:syncsettings",
    "default browser": "ms-settings:defaultapps",
    "default apps": "ms-settings:defaultapps",
    "default programs": "ms-settings:defaultapps",
    "clipboard": "ms-settings:clipboard",
    "startup": "ms-settings:startupapps",
    "startup apps": "ms-settings:startupapps",
    "start": "ms-settings:start",
    "taskbar": "ms-settings:taskbar",
    "multitasking": "ms-settings:multitasking",
    "window snapping": "ms-settings:multitasking-windows",
    "snap windows": "ms-settings:multitasking-windows",
    "desktop": "ms-settings:multitasking-desk",
    "hotspot": "ms-settings:mobilehotspot",
    "mobile hotspot": "ms-settings:mobilehotspot",
    "data usage": "ms-settings:datausage",
    "vpn": "ms-settings:vpn",
    "nearby sharing": "ms-settings:nearbyshare",
    "sharing": "ms-settings:nearbyshare",
    "optional features": "ms-settings:optionalfeatures",
    "indexing": "ms-settings:indexingoptions",
    "indexed locations": "ms-settings:indexingoptions",
    "search indexing": "ms-settings:indexingoptions",
    "memory": "ms-settings:memory",
    "maps": "ms-settings:maps",
    "email accounts": "ms-settings:emailandaccounts",
    "your info": "ms-settings:yourinfo",
    "sync settings": "ms-settings:syncsettings",
    "find my device": "ms-settings:findmydevice",
    "family": "ms-settings:family",
    "night light": "ms-settings:nightlight",
    "advanced display": "ms-settings:displayadvanced",
    "scale and layout": "ms-settings:displayadvanced",
    "screen brightness": "ms-settings:display",
    "volume mixer": "ms-settings:sound-volumemixer",
    "audio": "ms-settings:sound",
    "focus assist": "ms-settings:quietmode",
    "do not disturb": "ms-settings:quietmode",
    "dnd": "ms-settings:quietmode",
    "usage": "ms-settings:usage",
    "screen time": "ms-settings:usage",
    "battery saver": "ms-settings:batterysaver",
    "power saving": "ms-settings:batterysaver",
    "power usage": "ms-settings:usage",
    "sleep": "ms-settings:powersleep",
    "screen saver": "ms-settings:screensaver",
    "desktop background": "ms-settings:personalization-background",
    "lock screen": "ms-settings:lockscreen",
    "language": "ms-settings:regionlanguage",
    "region": "ms-settings:regionlanguage",
    "speech": "ms-settings:speech",
    "typing": "ms-settings:typing",
    "privacy and security": "ms-settings:privacy",
    "windows security": "windowsdefender:",
    "security": "windowsdefender:",
    "antivirus": "windowsdefender:",
    "firewall": "control.exe /name Microsoft.WindowsFirewall",
    "webcam": "ms-settings:privacy-webcam",
    "location": "ms-settings:privacy-location",
    "advertising": "ms-settings:privacy-advertising",
    "diagnostics": "ms-settings:privacy-diagnostics",
    "game bar": "ms-settings:gaming-gamebar",
    "captures": "ms-settings:gaming-captures",
    "xbox": "ms-settings:gaming-xbox",
    "storage sense": "ms-settings:storagesense",
    "troubleshoot": "ms-settings:troubleshoot",
    "activation": "ms-settings:activation",
    "phone link": "ms-settings:mobilelink",
}

ALL_SETTINGS_PAGES = {**SETTINGS_PAGES, **EXTRA_SETTINGS_PAGES}

# Control Panel pages (.cpl / control.exe targets)
CONTROL_PANEL_PAGES = {
    "power options": "powercfg.cpl",
    "power plan": "powercfg.cpl",
    "power": "powercfg.cpl",
    "network connections": "ncpa.cpl",
    "network": "ncpa.cpl",
    "internet options": "inetcpl.cpl",
    "internet properties": "inetcpl.cpl",
    "network and sharing center": "control.exe /name Microsoft.NetworkAndSharingCenter",
    "sharing center": "control.exe /name Microsoft.NetworkAndSharingCenter",
    "sound": "mmsys.cpl",
    "sounds": "mmsys.cpl",
    "playback devices": "mmsys.cpl",
    "recording devices": "mmsys.cpl",
    "user accounts": "netplwiz",
    "user accounts control panel": "netplwiz",
    "accounts": "netplwiz",
    "date and time": "timedate.cpl",
    "region and language": "intl.cpl",
    "region": "intl.cpl",
    "keyboard": "main.cpl",
    "mouse": "main.cpl",
    "printers": "control.exe /name Microsoft.DevicesAndPrinters",
    "printers and scanners": "control.exe /name Microsoft.DevicesAndPrinters",
    "programs and features": "appwiz.cpl",
    "programs": "appwiz.cpl",
    "uninstall a program": "appwiz.cpl",
    "uninstall programs": "appwiz.cpl",
    "administrative tools": "control.exe /name Microsoft.AdministrativeTools",
    "file explorer options": "control.exe /name Microsoft.FileExplorerOptions",
    "folder options": "control.exe /name Microsoft.FileExplorerOptions",
    "fonts": "control.exe /name Microsoft.Fonts",
    "color management": "color.cpl",
    "indexing options": "control.exe /name Microsoft.IndexingOptions",
    "sync center": "control.exe /name Microsoft.SyncCenter",
    "credential manager": "control.exe /name Microsoft.CredentialManager",
    "security center": "control.exe /name Microsoft.SecurityCenter",
    "troubleshooting": "control.exe /name Microsoft.Troubleshooting",
    "backup and restore": "control.exe /name Microsoft.BackupAndRestoreCenter",
    "system restore": "control.exe /name Microsoft.SystemRestore",
    "windows firewall": "control.exe /name Microsoft.WindowsFirewall",
    "windows update": "control.exe /name Microsoft.Update",
    "default programs": "control.exe /name Microsoft.DefaultPrograms",
    "personalization": "control.exe /name Microsoft.Personalization",
    "mail": "mail.exe",
    "dial up networking": "control.exe /name Microsoft.DialupNetworking",
}

# Legacy MMC/exe system tools keyed by spoken name
SYSTEM_TOOLS = {
    "device manager": "devmgmt.msc",
    "task scheduler": "taskschd.msc",
    "services": "services.msc",
    "service manager": "services.msc",
    "event viewer": "eventvwr.msc",
    "system configuration": "msconfig",
    "msconfig": "msconfig",
    "system information": "msinfo32",
    "computer management": "compmgmt.msc",
    "local users and groups": "lusrmgr.msc",
    "performance monitor": "perfmon.msc",
    "resource monitor": "resmon",
    "disk management": "diskmgmt.msc",
    "disk cleanup": "cleanmgr",
    "defragment and optimize drives": "dfrgui.exe",
    "defragment": "dfrgui.exe",
    "registry editor": "regedit",
    "windows memory diagnostic": "mdsched",
    "group policy editor": "gpedit.msc",
    "windows powershell": "powershell",
    "character map": "charmap",
    "steps recorder": "psr",
    "on screen keyboard": "osk",
    "magnifier": "magnify",
    "narrator": "narrator",
    "voice recorder": "soundrecorder:",
    "media player": "wmplayer",
    "sticky notes": "ms-sticky-notes:",
    "alarms and clock": "ms-clock:",
    "clock app": "ms-clock:",
    "weather": "ms-weather:",
    "photos": "microsoft.windows.photos:",
    "camera app": "microsoft.windows.camera:",
    "microsoft store": "ms-windows-store:",
    "store": "ms-windows-store:",
    "feedback hub": "ms-feedbackhub:",
    "xbox app": "xbox:",
    "movies and tv": "filmsandtv:",
    "mail and calendar": "outlookmail:",
    "windows settings": "ms-settings:",
    "calculator app": "calc",
    "notepad": "notepad",
    "paint app": "mspaint",
    "device pairing": "control.exe /name Microsoft.DevicesAndPrinters",
}

# Full-system power/session commands
SYSTEM_ACTIONS = {
    "cancel": "shutdown /a",
    "cancel shutdown": "shutdown /a",
    "abort shutdown": "shutdown /a",
    "lock": "rundll32.exe user32.dll,LockWorkStation",
    "lock pc": "rundll32.exe user32.dll,LockWorkStation",
    "lock screen": "rundll32.exe user32.dll,LockWorkStation",
    "log off": "shutdown /l",
    "logoff": "shutdown /l",
    "sign out": "shutdown /l",
    "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    "standby": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    "hibernate": "shutdown /h",
    "restart": "shutdown /r /t 3",
    "reboot": "shutdown /r /t 3",
    "restart pc": "shutdown /r /t 3",
    "shutdown": "shutdown /s /t 3",
    "shut down": "shutdown /s /t 3",
    "turn off pc": "shutdown /s /t 3",
}

# Read-only system information queries
SYSTEM_INFO_QUERIES = {
    "battery": "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | Format-List",
    "battery level": "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | Format-List",
    "power plan": "powercfg /getactivescheme",
    "disk space": "Get-Volume | Select-Object DriveLetter, SizeRemaining, Size | Format-Table -AutoSize",
    "disk usage": "Get-Volume | Select-Object DriveLetter, SizeRemaining, Size | Format-Table -AutoSize",
    "storage": "Get-Volume | Select-Object DriveLetter, SizeRemaining, Size | Format-Table -AutoSize",
    "memory": "Get-CimInstance Win32_OperatingSystem | Select-Object @{n='FreeGB';e={[math]::Round($_.FreePhysicalMemory/1MB,2)}}, @{n='TotalGB';e={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}} | Format-List",
    "ram": "Get-CimInstance Win32_ComputerSystem | Select-Object @{n='TotalRAM_GB';e={[math]::Round($_.TotalPhysicalMemory/1GB,2)}} | Format-List",
    "cpu": "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, MaxClockSpeed | Format-List",
    "processor": "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, MaxClockSpeed | Format-List",
    "gpu": "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion | Format-List",
    "graphics": "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion | Format-List",
    "ip address": "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*'} | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize",
    "ip": "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*'} | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize",
    "uptime": "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime",
    "windows version": "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List",
    "os version": "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List",
    "wifi network": "netsh wlan show interfaces | Select-String -Pattern 'SSID|Signal|State'",
    "wi-fi network": "netsh wlan show interfaces | Select-String -Pattern 'SSID|Signal|State'",
    "system info": "Get-ComputerInfo | Select-Object CsName, WindowsProductName, WindowsVersion, OsBuildNumber | Format-List",
    "computer name": "$env:COMPUTERNAME",
    "hostname": "$env:COMPUTERNAME",
    "monitor": "Get-CimInstance -Namespace root\\wmi -Class WmiMonitorID | ForEach-Object { ($_.UserFriendlyName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join '' }",
}

# Volume control intents
VOLUME_PATTERNS = {
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

# Default browser candidates per vendor
DEFAULT_BROWSER = {
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "mozilla firefox": "firefox.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
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
    category = "System"
    plugin_type = "System & Automation"

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
                "open clipboard settings",
                "open accessibility settings",
                "open printer settings",
                "open recovery settings",
                "open windows update settings",
                "open account settings",
                "open volume mixer settings",
                "open activation settings",
                "open start menu settings",
                "open mobile hotspot settings",
                "open multitasking settings",
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
            "windows.control_panel": [
                "open control panel", "open the control panel",
                "show control panel", "open control panel settings",
                "open control panel for power options",
                "open control panel for network connections",
                "open control panel for sound",
                "open control panel for user accounts",
                "open power options", "show power options",
                "open network connections", "open internet options",
                "open network and sharing center", "open sharing center",
                "open sound settings control panel", "open user accounts",
                "open date and time settings", "open region settings",
                "open folder options", "open file explorer options",
                "open fonts", "open index options", "open indexing options",
                "open credential manager", "open color management",
                "open programs and features", "open uninstall programs",
                "open system restore", "open backup and restore",
                "open troubleshooting", "open default programs",
                "open personalization", "open mail control panel",
            ],
            "windows.open_system_tool": [
                "open device manager", "open task scheduler",
                "open services", "open service manager",
                "open event viewer", "open system configuration",
                "open msconfig", "open system information",
                "open computer management", "open local users and groups",
                "open performance monitor", "open resource monitor",
                "open disk management", "open disk cleanup",
                "open registry editor", "open memory diagnostic",
                "open group policy editor", "open character map",
                "open steps recorder", "open on screen keyboard",
                "open magnifier", "open narrator", "open voice recorder",
                "open media player", "open sticky notes",
                "open alarms and clock", "open weather app",
                "open photos", "open camera app", "open microsoft store",
                "open store", "open feedback hub", "open notepad",
                "open paint app", "open calculator app",
            ],
            "windows.system_action": [
                "lock the pc", "lock my pc", "lock the screen",
                "lock this computer", "lock computer",
                "sign out", "log off", "log out", "sign me out",
                "put the pc to sleep", "sleep the pc", "go to sleep",
                "hibernate", "hibernate the pc",
                "restart the pc", "restart the computer", "restart",
                "reboot the pc", "reboot", "restart my pc",
                "shut down the pc", "shutdown the pc", "shut down",
                "shutdown", "turn off the pc", "turn off my pc",
                "cancel shutdown", "abort shutdown", "cancel restart",
            ],
            "windows.volume_control": [
                "mute", "mute the volume", "mute audio", "silence the audio",
                "unmute", "unmute the volume", "unmute audio",
                "volume up", "turn up the volume", "increase the volume",
                "raise the volume", "make it louder", "louder",
                "volume down", "turn down the volume", "decrease the volume",
                "lower the volume", "make it quieter", "quieter",
                "set volume", "change volume",
            ],
            "windows.brightness": [
                "increase brightness", "brightness up", "make it brighter",
                "decrease brightness", "brightness down", "dim the screen",
                "lower the brightness", "set brightness", "adjust brightness",
            ],
            "windows.system_info": [
                "check battery", "battery level", "how much battery",
                "how much storage", "check disk space", "storage left",
                "how much ram", "how much memory", "check memory",
                "what is my ip", "show ip address", "check ip address",
                "system uptime", "how long has the pc been on",
                "windows version", "check windows version",
                "what is my wifi network", "which wifi am i on",
                "cpu info", "check the processor", "graphics card",
                "what is my computer name", "check the monitor",
                "check the power plan",
            ],
            "windows.empty_recycle_bin": [
                "empty the recycle bin", "empty recycle bin",
                "clear the recycle bin", "clear recycle bin",
                "delete everything in the recycle bin",
                "empty the trash",
            ],
            "windows.open_run": [
                "open run dialog", "open the run box", "show run dialog",
                "open run and type", "run a command", "run command",
                "run this command", "open run",
            ],
            "windows.screenshot": [
                "take a screenshot", "take screenshot", "capture the screen",
                "capture screen", "screenshot this", "snip the screen",
                "take a snip", "snip", "screen capture",
            ],
            "windows.show_desktop": [
                "show desktop", "show the desktop", "minimize all windows",
                "minimise all windows", "go to the desktop", "desktop please",
                "show my desktop",
            ],
            "windows.window_control": [
                "minimize the window", "minimise the window",
                "maximize the window", "maximise the window", "maximize this window",
                "close the window", "close this window",
                "snap the window left", "snap window to the left",
                "snap the window right", "snap window to the right",
                "snap the window", "snap window",
            ],
            "windows.clipboard_clear": [
                "clear the clipboard", "empty the clipboard",
                "wipe the clipboard", "clear clipboard",
            ],
            "windows.toggle_connectivity": [
                "turn on wifi", "turn on wi fi", "enable wifi", "enable wi fi",
                "turn off wifi", "turn off wi fi", "disable wifi", "disable wi fi",
                "switch on wifi", "switch off wifi",
                "turn on bluetooth", "enable bluetooth",
                "turn off bluetooth", "disable bluetooth",
                "toggle wifi", "toggle bluetooth",
            ],
            "windows.set_default_browser": [
                "set default browser", "change default browser",
                "make chrome the default browser", "make edge the default browser",
                "set chrome as default browser", "set edge as default browser",
                "set firefox as default browser",
                "make firefox the default browser", "default browser",
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
            "windows.control_panel": "- windows.control_panel: Open a Control Panel page (e.g. 'open control panel', 'open power options', 'open network connections', 'open internet options', 'open programs and features', 'open folder options').",
            "windows.open_system_tool": "- windows.open_system_tool: Open a Windows administrative tool (e.g. 'open device manager', 'open task scheduler', 'open services', 'open event viewer', 'open disk management', 'open registry editor').",
            "windows.system_action": "- windows.system_action: Lock, sleep, hibernate, sign out, restart or shut down Windows, or cancel a pending shutdown (e.g. 'lock the pc', 'shut down the pc', 'restart my pc').",
            "windows.volume_control": "- windows.volume_control: Mute, unmute, or raise/lower system volume (e.g. 'mute', 'volume up', 'turn down the volume').",
            "windows.brightness": "- windows.brightness: Raise, lower or set the screen brightness (e.g. 'increase brightness', 'set brightness to 60').",
            "windows.system_info": "- windows.system_info: Report PC information such as battery level, disk space, RAM, IP address, uptime, Windows version, or Wi-Fi network (e.g. 'how much battery is left', 'check disk space', 'what is my ip').",
            "windows.empty_recycle_bin": "- windows.empty_recycle_bin: Permanently clear the Recycle Bin (e.g. 'empty the recycle bin').",
            "windows.open_run": "- windows.open_run: Open the Run dialog and optionally type a command into it (e.g. 'open run and type notepad').",
            "windows.screenshot": "- windows.screenshot: Take a screenshot or open the screen snipping overlay (e.g. 'take a screenshot', 'snip the screen').",
            "windows.show_desktop": "- windows.show_desktop: Minimize all windows and reveal the desktop (e.g. 'show desktop', 'minimize all windows').",
            "windows.window_control": "- windows.window_control: Control the active window - minimize, maximize, close, or snap it left/right (e.g. 'snap the window left', 'close the window').",
            "windows.clipboard_clear": "- windows.clipboard_clear: Erase the current clipboard contents (e.g. 'clear the clipboard').",
            "windows.toggle_connectivity": "- windows.toggle_connectivity: Turn Wi-Fi or Bluetooth on/off (e.g. 'turn on wifi', 'disable bluetooth').",
            "windows.set_default_browser": "- windows.set_default_browser: Change the default web browser (e.g. 'set chrome as default browser', 'make edge the default browser').",
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
        for key in sorted(ALL_SETTINGS_PAGES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                uri = ALL_SETTINGS_PAGES[key]
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

        # 2. Known Windows system tools / legacy admin apps (reliable, no Start Menu)
        for key, launch in sorted(SYSTEM_TOOLS.items(), key=lambda kv: len(kv[0]), reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                try:
                    subprocess.Popen(f"start {launch}", shell=True)
                    logger.info(f"Launched system tool: {launch}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to launch system tool '{launch}': {e}")
                    return False

        # 3. Search Start Menu (handles UWP + classic apps) and launch best match
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

    # ────────────────────────── Windows System Control ──────────────────────────

    def _ps(self, script: str, timeout: int = 25) -> Tuple[bool, str]:
        """Runs a PowerShell snippet and returns (ok, output)."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, timeout=timeout,
            )
        except Exception as e:
            logger.error(f"PowerShell execution failed: {e}")
            return False, ""
        if result.returncode != 0:
            logger.error(f"PowerShell error: {result.stderr.strip()}")
            return False, result.stderr.strip()
        return True, result.stdout.strip()

    def control_panel(self, text: str) -> bool:
        """Opens a Control Panel page, defaulting to the Control Panel root."""
        logger.info(f"Plugin Action: Opening Control Panel for '{text}'")
        low = text.lower()
        for key in sorted(CONTROL_PANEL_PAGES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                target = CONTROL_PANEL_PAGES[key]
                try:
                    subprocess.Popen(f"start {target}", shell=True)
                    logger.info(f"Opened Control Panel page: {target}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to open Control Panel '{target}': {e}")
                    return False
        try:
            subprocess.Popen("start control.exe", shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to open Control Panel: {e}")
            return False

    def open_system_tool(self, text: str) -> bool:
        """Opens a Windows administrative tool (MMC snap-in or legacy exe)."""
        logger.info(f"Plugin Action: Opening system tool for '{text}'")
        low = text.lower()
        for key in sorted(SYSTEM_TOOLS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                target = SYSTEM_TOOLS[key]
                try:
                    subprocess.Popen(f"start {target}", shell=True)
                    logger.info(f"Launched system tool: {target}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to launch system tool '{target}': {e}")
                    return False
        logger.warning(f"No matching system tool for '{text}'")
        return False

    def system_action(self, text: str) -> bool:
        """Lock/sleep/hibernate/sign out/restart/shut down, or cancel a pending shutdown."""
        logger.info(f"Plugin Action: System action '{text}'")
        low = text.lower()
        if re.search(r"\b(cancel|abort)\b", low):
            self._ps("shutdown /a")
            logger.info("Cancelled pending shutdown/restart")
            return True
        for key in sorted(SYSTEM_ACTIONS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                cmd = SYSTEM_ACTIONS[key]
                try:
                    subprocess.Popen(cmd, shell=True)
                    logger.info(f"Ran system action: {cmd}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to run system action '{cmd}': {e}")
                    return False
        logger.warning(f"No matching system action for '{text}'")
        return False

    def volume_control(self, text: str) -> bool:
        """Mutes/unmutes or raises/lowers the system volume."""
        logger.info(f"Plugin Action: Volume control '{text}'")
        low = text.lower()
        intent = None
        for key in sorted(VOLUME_PATTERNS, key=len, reverse=True):
            if key in low:
                intent = VOLUME_PATTERNS[key]
                break
        if intent is None:
            return False
        steps = 10
        num = re.search(r"\b(\d{1,3})\b", low)
        if num:
            steps = max(1, min(50, int(num.group(1))))
        single = intent in ("mute", "unmute")
        try:
            import pyautogui
            pyautogui.press(
                {"up": "volumeup", "down": "volumedown",
                 "mute": "volumemute", "unmute": "volumemute"}[intent],
                presses=1 if single else steps, interval=0.03,
            )
            return True
        except Exception:
            pass
        vkey = {"up": 175, "down": 174, "mute": 173, "unmute": 173}[intent]
        script = (
            "$ws = New-Object -ComObject WScript.Shell; "
            + "; ".join(["$ws.SendKeys([char]" + str(vkey) + ")"] * (1 if single else min(steps, 20)))
        )
        ok, _ = self._ps(script)
        return ok

    def brightness(self, text: str) -> bool:
        """Raises, lowers, or sets the display brightness (percent)."""
        logger.info(f"Plugin Action: Brightness '{text}'")
        low = text.lower()
        _, out = self._ps("(Get-CimInstance -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
        current = int(out.strip()) if out.strip().isdigit() else 50
        explicit = re.search(r"\b(\d{1,3})\b", low)
        if explicit and re.search(r"\b(to|by)\b", low):
            target = int(explicit.group(1))
        elif re.search(r"\b(increase|raise|up|brighter|higher|more)\b", low):
            target = current + 10
        elif re.search(r"\b(decrease|lower|down|dim|reduce|less)\b", low):
            target = current - 10
        else:
            target = current
        target = max(0, min(100, target))
        script = (
            "$m = Get-CimInstance -Namespace root/WMI -Class WmiMonitorBrightnessMethods; "
            f"if ($m) {{ $m.WmiSetBrightness(1, {target}) }}"
        )
        ok, _ = self._ps(script)
        logger.info(f"Brightness: {current}% -> {target}%")
        return ok

    def system_info(self, text: str) -> bool:
        """Reports read-only system information (battery, disk, RAM, IP, uptime...)."""
        logger.info(f"Plugin Action: System info query '{text}'")
        low = text.lower()
        for key in sorted(SYSTEM_INFO_QUERIES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", low, re.IGNORECASE):
                ok, out = self._ps(SYSTEM_INFO_QUERIES[key])
                if ok:
                    logger.info(f"System info [{key}]:\n{out}")
                return ok
        logger.warning(f"No matching system info query for '{text}'")
        return False

    def empty_recycle_bin(self, text: str = "") -> bool:
        """Permanently clears the Recycle Bin."""
        logger.info("Plugin Action: Emptying Recycle Bin")
        ok, _ = self._ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
        return ok

    def open_run(self, text: str) -> bool:
        """Opens the Run dialog (Win+R), optionally typing a command into it."""
        import time
        logger.info(f"Plugin Action: Open Run dialog for '{text}'")
        cmd = re.sub(
            r"^\s*(?:please\s+)?(?:open\s+)?(?:the\s+)?run(?:\s+(?:dialog|box|command|window))?"
            r"\s*(?:and\s+)?(?:type|enter|run|open|with)\s+",
            "", text, flags=re.IGNORECASE,
        ).strip(" .!?,:\"'")
        try:
            import pyautogui
            pyautogui.hotkey("win", "r")
            time.sleep(0.5)
            if cmd:
                pyautogui.typewrite(cmd, interval=0.01)
                time.sleep(0.2)
                pyautogui.press("enter")
            return True
        except Exception as e:
            logger.error(f"Failed to open Run dialog: {e}")
            return False

    def screenshot(self, text: str) -> bool:
        """Opens the snip overlay for a region, or the full Snipping Tool."""
        logger.info(f"Plugin Action: Screenshot '{text}'")
        if re.search(r"\b(region|partial|select|crop|area|snip)\b", text.lower()):
            try:
                import pyautogui
                pyautogui.hotkey("win", "shift", "s")
                return True
            except Exception:
                pass
        try:
            subprocess.Popen("start ms-snippingtool:", shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to start Snipping Tool: {e}")
            return False

    def show_desktop(self, text: str = "") -> bool:
        """Minimizes all windows to reveal the desktop."""
        logger.info("Plugin Action: Show Desktop")
        try:
            import pyautogui
            pyautogui.hotkey("win", "d")
            return True
        except Exception:
            return self._ps("(New-Object -ComObject Shell.Application).MinimizeAll()")[0]

    def window_control(self, text: str) -> bool:
        """Minimizes, maximizes, closes, or snaps the active window."""
        logger.info(f"Plugin Action: Window control '{text}'")
        low = text.lower()
        keys = None
        if re.search(r"\b(minimi[sz]e)\b", low):
            keys = ("win", "down")
        elif re.search(r"\b(maximi[sz]e)\b", low):
            keys = ("win", "up")
        elif re.search(r"\bleft\b", low) and re.search(r"\b(snap|side|align)\b", low):
            keys = ("win", "left")
        elif re.search(r"\bright\b", low) and re.search(r"\b(snap|side|align)\b", low):
            keys = ("win", "right")
        elif re.search(r"\bclose\b", low):
            keys = ("alt", "f4")
        if not keys:
            return False
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error(f"Failed window control {keys}: {e}")
            return False

    def clipboard_clear(self, text: str = "") -> bool:
        """Erases the clipboard contents."""
        logger.info("Plugin Action: Clearing clipboard")
        ok, _ = self._ps("Set-Clipboard -Value ''")
        return ok

    def toggle_connectivity(self, text: str) -> bool:
        """Turns Wi-Fi or Bluetooth on/off."""
        logger.info(f"Plugin Action: Connectivity toggle '{text}'")
        low = text.lower()
        want_on = bool(re.search(r"\b(on|enable[ds]?|switch\s+on|turn\s+on|start)\b", low))
        want_off = bool(re.search(r"\b(off|disable[ds]?|switch\s+off|turn\s+off|stop)\b", low))
        if re.search(r"\b(bluetooth|bt)\b", low) and not re.search(r"\bwi[\s-]?fi\b", low):
            if not (want_on or want_off):
                return False
            verb = "Enable" if want_on else "Disable"
            script = (
                "$d = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object -First 1; "
                f"if ($d) {{ {verb}-PnpDevice -InputObject $d.InstanceId -Confirm:$false }}"
            )
            ok, out = self._ps(script)
            if ok:
                logger.info(f"Bluetooth {verb}d")
                return True
            logger.warning("PnP toggle unavailable, opening Bluetooth settings instead")
            subprocess.Popen("start ms-settings:bluetooth", shell=True)
            return True
        if re.search(r"\b(wi[\s-]?fi|wlan|wireless|internet)\b", low):
            if not (want_on or want_off):
                return False
            state = "enabled" if want_on else "disabled"
            ok, out = self._ps(
                'netsh interface set interface name="Wi-Fi" admin=' + state
            )
            if ok:
                logger.info(f"Wi-Fi set to {state}")
                return True
            logger.warning("Wi-Fi toggle failed, opening Wi-Fi settings instead")
            subprocess.Popen("start ms-settings:network-wifi", shell=True)
            return True
        return False

    def set_default_browser(self, text: str) -> bool:
        """Opens the Default Apps Settings page filtered to the requested browser."""
        logger.info(f"Plugin Action: Set default browser '{text}'")
        low = text.lower()
        known = None
        for key in sorted(DEFAULT_BROWSER, key=len, reverse=True):
            if key in low:
                known = key
                break
        try:
            subprocess.Popen("start ms-settings:defaultapps", shell=True)
            logger.info(f"Opened Default Apps settings (browser: {known or 'unspecified'})")
            return True
        except Exception as e:
            logger.error(f"Failed to open Default Apps settings: {e}")
            return False
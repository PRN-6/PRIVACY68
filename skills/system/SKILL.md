---
name: system
description: "Windows OS system controls: audio volume, mute, app launching, screenshot capture, lock screen, and clipboard."
keywords: ["system", "volume", "mute", "unmute", "sound", "audio", "screenshot", "lock", "windows", "app", "launch", "clipboard", "process", "processes", "tasklist", "taskkill", "task manager"]
metadata:
  openclaw:
    emoji: "💻"
    requires: { bins: [] }
---

# Windows System Control Skill Guide

Use this skill for controlling volume, taking desktop screenshots, launching applications, locking the PC, or accessing clipboard.

## Audio & Volume Controls
```python
import subprocess

def toggle_mute():
    # Toggle master audio mute using WScript shell key 173
    subprocess.run(["powershell", "-c", "(New-Object -ComObject Wscript.Shell).SendKeys([char]173)"], check=False)
    print("Toggled audio mute.")

def volume_up():
    subprocess.run(["powershell", "-c", "(New-Object -ComObject Wscript.Shell).SendKeys([char]175)"], check=False)
    print("Volume increased.")

def volume_down():
    subprocess.run(["powershell", "-c", "(New-Object -ComObject Wscript.Shell).SendKeys([char]174)"], check=False)
    print("Volume decreased.")
```

## Desktop Screenshot Capture
```python
import os
from pathlib import Path
from PIL import ImageGrab

def take_screenshot(filename: str = "screenshot.png"):
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    save_path = desktop / filename
    img = ImageGrab.grab()
    img.save(str(save_path))
    print(f"Screenshot saved to: {save_path}")

take_screenshot()
```

## Locking Workstation
```python
import ctypes

def lock_screen():
    ctypes.windll.user32.LockWorkStation()
    print("Windows workstation locked.")

lock_screen()
```

## Launching Any Windows App
```python
from services.system import system_service
system_service.launch_app("notepad")
print("Launched application.")
```

## Closing Applications & Windows
```python
from services.system import system_service

# Close specific application cleanly
system_service.close_app("notepad")

# Or close the currently active / focused foreground window cleanly
system_service.close_active_window()
```

## Virtual Desktop Navigation
```python
from services.system import system_service

# Navigate directly to Desktop 1, 2, 3, 4, 5, etc.
system_service.switch_to_desktop(2)

# Navigate to next or previous desktop
system_service.switch_next_desktop()
system_service.switch_previous_desktop()

# Create or close a virtual desktop
system_service.create_virtual_desktop()
system_service.close_virtual_desktop()

# Open Windows Task View (view all desktops)
system_service.show_task_view()
```

## Clipboard Management
```python
import subprocess

def get_clipboard() -> str:
    res = subprocess.run(["powershell", "-c", "Get-Clipboard"], capture_output=True, text=True, check=False)
    return res.stdout.strip()

def set_clipboard(text: str):
    subprocess.run(["powershell", "-c", f"Set-Clipboard -Value @'\n{text}\n'@"], check=False)
    print("Copied text to clipboard.")
```

## Process Management & Task Termination
```python
import subprocess

def list_running_processes(filter_name: str = ""):
    cmd = ["tasklist"]
    if filter_name:
        cmd.extend(["/fi", f"imagename eq {filter_name}*"])
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    print(res.stdout)

def kill_process(process_name: str):
    subprocess.run(["taskkill", "/f", "/im", process_name], check=False)
    print(f"Terminated process: {process_name}")
```


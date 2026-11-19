---
name: system
description: "Windows OS system controls: audio volume, mute, app launching, screenshot capture, lock screen, and clipboard."
keywords: ["system", "volume", "mute", "unmute", "sound", "audio", "screenshot", "lock", "windows", "app", "launch", "clipboard"]
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


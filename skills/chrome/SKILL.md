---
name: chrome
description: "Google Chrome browser automation: launch, open URLs, incognito mode, user profiles, and tab management."
keywords: ["chrome", "google chrome", "chrome browser", "incognito", "web", "browser", "new tab"]
metadata:
  openclaw:
    emoji: "🌐"
    requires: { bins: ["chrome.exe"] }
---

# Google Chrome Skill Guide

Use this skill when any developer or user asks to open Google Chrome, navigate to websites, search in Chrome, open incognito windows, or manage Chrome profiles.

## Binary Path Discovery on Windows
Google Chrome installs to:
* `C:\Program Files\Google\Chrome\Application\chrome.exe`
* `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
* `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe`

## Command-Line Recipes
```bash
# Open URL
chrome.exe "https://github.com"

# Open Incognito Window
chrome.exe --incognito "https://duckduckgo.com"

# Launch with specific profile
chrome.exe --profile-directory="Default" "https://google.com"

# Remote debugging
chrome.exe --remote-debugging-port=9222
```

## Python Automation Pattern in PRIVACY68
```python
import os
import subprocess
import webbrowser

def find_chrome_exe() -> str:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""

def open_chrome(url: str = "https://www.google.com", incognito: bool = False, profile: str = ""):
    exe = find_chrome_exe()
    if exe:
        cmd = [exe]
        if incognito:
            cmd.append("--incognito")
        if profile:
            cmd.append(f"--profile-directory={profile}")
        cmd.append(url)
        subprocess.Popen(cmd)
        print(f"Opened Chrome ({'incognito' if incognito else 'normal'}) to: {url}")
    else:
        webbrowser.open(url)
        print(f"Chrome binary not found; opened default browser to: {url}")

# Example usage
open_chrome("https://github.com")
```


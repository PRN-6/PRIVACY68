---
name: brave
description: "Brave browser automation: ad-blocking navigation, incognito/Tor windows, and web search."
keywords: ["brave", "brave browser", "brave search", "private window", "tor", "web", "new tab"]
metadata:
  openclaw:
    emoji: "🦁"
    requires: { bins: ["brave.exe"] }
---

# Brave Browser Skill Guide

Use this skill when any developer or user asks to open Brave browser, navigate privately, launch Tor windows, or search in Brave.

## Binary Path Discovery on Windows
Brave Browser installs to:
* `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`
* `C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe`
* `%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe`

## Command-Line Recipes
```bash
# Open URL
brave.exe "https://search.brave.com"

# Open Incognito / Private Window
brave.exe --incognito "https://github.com"

# Open Private Window with Tor
brave.exe --tor "https://check.torproject.org"
```

## Python Automation Pattern in PRIVACY68
```python
import os
import subprocess
import webbrowser

def find_brave_exe() -> str:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""

def open_brave(url: str = "https://search.brave.com", incognito: bool = False, tor: bool = False):
    exe = find_brave_exe()
    if exe:
        cmd = [exe]
        if incognito:
            cmd.append("--incognito")
        if tor:
            cmd.append("--tor")
        cmd.append(url)
        subprocess.Popen(cmd)
        print(f"Opened Brave to: {url}")
    else:
        webbrowser.open(url)
        print(f"Brave binary not found; opened default browser to: {url}")

# Example usage
open_brave("https://search.brave.com")
```


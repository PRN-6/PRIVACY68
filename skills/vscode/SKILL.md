---
name: vscode
description: "Universal VS Code and developer workspace orchestrator for dynamically discovering project directories, launching VS Code, and managing files across any developer workstation."
keywords: ["vscode", "code", "project", "workspace", "folder", "open project", "editor", "ide", "launch project"]
metadata:
  emoji: "💻"
  requires: { bins: ["code"] }
---

# Universal VS Code & Workspace Skill Guide

Use this skill when any developer asks to open a project, directory, or workspace in Visual Studio Code.
Never hardcode fixed drive letters or user paths. Always discover paths dynamically.

## 1. Universal Project Discovery Pattern (Works on ANY machine)
```python
import os
import shutil
import string
import subprocess
from pathlib import Path

def find_project_path(project_name: str) -> Path | None:
    # 1. Search current working directory first
    cwd = Path.cwd()
    if project_name.lower() in cwd.name.lower():
        return cwd
    if (cwd / project_name).is_dir():
        return cwd / project_name

    # 2. Collect candidate base search folders across all accessible Windows drives
    search_dirs = []
    
    # User profile & common developer locations
    home = Path.home()
    user_candidates = ["projects", "dev", "code", "source/repos", "workspace", "work", "git", "Documents", "Desktop"]
    for sub in user_candidates:
        p = home / sub
        if p.exists() and p.is_dir():
            search_dirs.append(p)

    # Check OneDrive-redirected folders if active
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer") or ""
    if onedrive:
        for sub in ["Desktop", "Documents", "projects"]:
            od_p = Path(onedrive) / sub
            if od_p.exists() and od_p.is_dir():
                search_dirs.append(od_p)

    # Scan root developer directories on all active drive letters (C:, D:, E:, etc.)
    for letter in string.ascii_uppercase:
        drive_root = Path(f"{letter}:/")
        if drive_root.exists():
            for folder_name in ["projects", "dev", "code", "workspace", "source", "repos"]:
                dp = drive_root / folder_name
                if dp.exists() and dp.is_dir() and dp not in search_dirs:
                    search_dirs.append(dp)

    # Search for matching project folder
    target_low = project_name.strip().lower()
    
    # A. Exact match
    for base in search_dirs:
        exact = base / project_name
        if exact.exists() and exact.is_dir():
            return exact

    # B. Case-insensitive / substring match (1 level deep)
    for base in search_dirs:
        try:
            for item in base.iterdir():
                if item.is_dir() and target_low in item.name.lower():
                    return item
        except (PermissionError, OSError):
            continue

    return None
```

## 2. Universal VS Code Binary Resolution
Developers may have VS Code installed in User AppData, Program Files, or standalone:
```python
def get_vscode_executable() -> str:
    # Check if 'code' is on system PATH
    found = shutil.which("code") or shutil.which("code.cmd")
    if found:
        return found

    # Fallback to standard installation paths on Windows
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")

    common_paths = [
        Path(local_appdata) / "Programs/Microsoft VS Code/bin/code.cmd",
        Path(program_files) / "Microsoft VS Code/bin/code.cmd",
        Path(program_files_x86) / "Microsoft VS Code/bin/code.cmd",
        Path("C:/Program Files/Microsoft VS Code/bin/code.cmd"),
    ]
    for p in common_paths:
        if p.exists():
            return str(p)

    return "code"  # Default invocation
```

## 3. Launching
```python
vscode_bin = get_vscode_executable()
target_dir = find_project_path(project_name)

if target_dir:
    subprocess.Popen([vscode_bin, str(target_dir)], shell=True)
    print(f"Successfully opened '{target_dir.name}' in VS Code ({target_dir})")
else:
    # If project not found, open current directory as fallback
    subprocess.Popen([vscode_bin, "."], shell=True)
    print(f"Project '{project_name}' not found. Opened current workspace in VS Code.")
```

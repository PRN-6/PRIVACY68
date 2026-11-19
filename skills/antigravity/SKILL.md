---
name: antigravity
description: "Antigravity IDE & AI workspace orchestrator: launch Antigravity IDE, open project folders, initialize Python virtual environments, and manage developer workspaces."
keywords: ["antigravity", "antigravity ide", "antigravity-ide", "open in antigravity", "agy", "create project", "virtual environment", "venv", "new project"]
metadata:
  openclaw:
    emoji: "🚀"
    requires: { bins: ["Antigravity IDE.exe"] }
---

# Google Antigravity IDE Skill Guide

Use this skill whenever the user asks to open a project or directory in Antigravity IDE, or asks to create a new project with a virtual environment and launch it in Antigravity.

> IMPORTANT: Do NOT open the Python 'import antigravity' XKCD comic link. Always launch the actual Antigravity IDE application executable on the machine.

## Antigravity IDE Discovery on Windows
Antigravity IDE installs to:
* `%LOCALAPPDATA%\Programs\Antigravity IDE\_\Antigravity IDE.exe`
* `%LOCALAPPDATA%\Programs\Antigravity IDE\_\bin\antigravity-ide.cmd`
* `%ProgramFiles%\Antigravity IDE\_\Antigravity IDE.exe`

## Python Automation Recipe
```python
import os
import subprocess
import sys
import venv
from pathlib import Path

def find_antigravity_exe() -> str | None:
    local_app = os.environ.get("LOCALAPPDATA", "")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = [
        os.path.join(local_app, r"Programs\Antigravity IDE\_\Antigravity IDE.exe"),
        os.path.join(local_app, r"Programs\Antigravity IDE\_\bin\antigravity-ide.cmd"),
        os.path.join(prog_files, r"Antigravity IDE\_\Antigravity IDE.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def setup_project_and_launch(project_name: str, base_dir: Path, with_venv: bool = True):
    proj_dir = base_dir / project_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created project folder: {proj_dir}")

    if with_venv:
        venv_dir = proj_dir / ".venv"
        print(f"Initializing virtual environment at: {venv_dir}")
        venv.create(str(venv_dir), with_pip=True)
        print("Virtual environment created.")

    exe = find_antigravity_exe()
    if exe:
        subprocess.Popen([exe, str(proj_dir)])
        print(f"Opened {proj_dir} in Antigravity IDE.")
    else:
        os.startfile(str(proj_dir))
        print(f"Opened {proj_dir} in File Explorer.")
```


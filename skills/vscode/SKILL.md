---
name: vscode
description: "VS Code and developer workspace orchestrator for finding projects, launching directories in VS Code, and spinning up dev servers."
keywords: ["vscode", "code", "project", "workspace", "folder", "open project", "editor", "ide"]
metadata:
  emoji: "💻"
  requires: { bins: ["code"] }
---

# VS Code & Workspace Skill Guide

Use this skill when the developer asks to open projects, folders, or workspaces in Visual Studio Code.

## Locating Developer Projects on Windows
Scan standard developer directories:
- `D:/projects`
- `C:/projects`
- `%USERPROFILE%/projects`
- `%USERPROFILE%/source/repos`
- `%USERPROFILE%/Documents`
- `%USERPROFILE%/Desktop`

## Opening in VS Code
- **Open folder in VS Code**: `code "<folder_path>"`
- **Open file at line number**: `code -g "<file_path>:<line_number>"`
- **Open in new window**: `code -n "<folder_path>"`

## How to Execute in Python
```python
import subprocess
from pathlib import Path

# Launch VS Code with folder path:
subprocess.Popen(["code", str(project_folder)], shell=True)
print(f"Opened project '{project_name}' in VS Code at {project_folder}")
```


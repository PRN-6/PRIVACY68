---
name: git
description: "Local Git version control operations: status, diff, add, commit, branch, checkout, log, stash, and pull/push."
keywords: ["git", "commit", "branch", "diff", "checkout", "stash", "status", "log", "merge", "push", "pull", "repo", "rebase"]
metadata:
  openclaw:
    emoji: "🌿"
    requires: { bins: ["git"] }
---

# Git Version Control Skill Guide

Use this skill for all local Git repository management. For remote GitHub PRs, issues, and CI runs, use the `github` skill (`gh`).

## Common Git CLI Commands
```bash
git status --short
git diff
git log --oneline -n 10
git checkout -b <branch_name>
git add -A && git commit -m "<message>"
git push -u origin <branch_name>
git pull --rebase
git stash && git stash pop
```

## Python Automation Pattern in PRIVACY68
```python
import os
import subprocess

def resolve_repo_dir(target_name: str = "PRIVACY68") -> str:
    if os.path.exists(".git"):
        return os.getcwd()
    candidates = [
        rf"D:\projects\{target_name}",
        os.path.join(os.path.expanduser("~"), "projects", target_name),
    ]
    for p in candidates:
        if os.path.exists(os.path.join(p, ".git")):
            return p
    return os.getcwd()

def run_git(*args, repo_dir: str = None):
    cwd = repo_dir or resolve_repo_dir()
    cmd = ["git", *args]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    output = res.stdout.strip() or res.stderr.strip()
    repo_label = f"[{os.path.basename(cwd)}] " if cwd else ""
    if res.returncode == 0:
        print(f"{repo_label}{output}" if output else f"{repo_label}Working directory is clean (nothing to commit).")
    else:
        print(f"{repo_label}Error: {output or 'Not a git repository.'}")
    return res.returncode == 0

# Check git status
run_git("status", "--short")
```


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
import subprocess

def run_git(*args):
    cmd = ["git", *args]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = res.stdout.strip() or res.stderr.strip()
    print(output or f"Git command '{' '.join(args)}' completed.")
    return res.returncode == 0

# Check git status
run_git("status", "--short")
```


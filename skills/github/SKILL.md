---
name: github
description: "Universal GitHub CLI and Git operations for issues, PRs, checks, CI logs, comments, reviews, releases, and repository status across any repository."
keywords: ["github", "gh", "pr", "pull request", "issue", "repo", "commit", "ci", "checks", "branch", "push", "diff", "pulls", "issues"]
metadata:
  emoji: "🐙"
  requires: { bins: ["gh", "git"] }
---

# Universal GitHub Skill Guide

Use this skill when any developer asks to manage GitHub repositories, issues, pull requests, CI checks, or branches.
Never assume a specific repository owner or name. Always resolve from current Git working directory or user request.

## 1. Dynamic Repository & Token Resolution
```python
import os
import shutil
import subprocess

def get_current_repo() -> str | None:
    try:
        res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False)
        url = res.stdout.strip()
        # Parse owner/repo from https://github.com/owner/repo.git or git@github.com:owner/repo.git
        import re
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        return match.group(1) if match else None
    except Exception:
        return None

def get_auth_env() -> dict:
    env = os.environ.copy()
    # Check if a PAT is available from PRIVACY68 Windows Credential Manager or .env
    token = None
    try:
        from plugins.github_plugin import GitHubPlugin
        token = GitHubPlugin().get_token()
    except Exception:
        pass
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    return env
```

## 2. Pull Request Operations (Any Repo)
```bash
# List PRs for current repo (or specify --repo owner/repo)
gh pr list --limit 10

# View PR details or checks
gh pr view <number_or_branch>
gh pr checks <number_or_branch>
gh pr diff <number_or_branch>

# Create a PR
gh pr create --title "<title>" --body "<body>"
```

## 3. Issue Tracking Operations
```bash
# List open issues
gh issue list --state open --limit 15

# View issue details & comments
gh issue view <issue_number>

# Create an issue
gh issue create --title "<title>" --body "<body>"
```

## 4. CI/CD Run Logs & Debugging
```bash
# List latest workflow runs
gh run list --limit 5

# View logs for a failed run
gh run view <run_id> --log-failed

# Rerun failed jobs
gh run rerun <run_id> --failed
```

## 5. Universal Execution Pattern in Python
```python
import subprocess
env = get_auth_env()
res = subprocess.run(["gh", "pr", "list", "--limit", "10"], capture_output=True, text=True, env=env, check=False)
if res.returncode == 0:
    print(res.stdout.strip() or "No open PRs found.")
else:
    # If gh is not authenticated or not installed, provide helpful diagnostics
    print(f"GitHub Error: {res.stderr.strip() or 'Command failed.'}")
```

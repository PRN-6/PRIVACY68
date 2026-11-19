---
name: github
description: "GitHub CLI and Git operations for issues, PRs, checks, CI logs, comments, reviews, releases, and repository status."
keywords: ["github", "gh", "pr", "pull request", "issue", "repo", "commit", "ci", "checks", "branch", "push", "diff"]
metadata:
  emoji: "🐙"
  requires: { bins: ["gh", "git"] }
---

# GitHub Skill Guide

Use `gh` CLI commands to interact with GitHub. Use `git` for local branch, commit, push, and diff operations.

## Pull Requests (PRs)
- **List PRs**: `gh pr list --limit 10`
- **View PR details**: `gh pr view <number_or_url>`
- **View PR Diff**: `gh pr diff <number_or_url>`
- **Check CI/Build Status**: `gh pr checks <number>`
- **Create PR**: `gh pr create --title "<title>" --body "<body>"`

## Issues
- **List Open Issues**: `gh issue list --state open`
- **View Issue**: `gh issue view <number>`
- **Create Issue**: `gh issue create --title "<title>" --body "<body>"`
- **Close Issue**: `gh issue close <number> --comment "<comment>"`

## CI/CD Workflow Runs
- **List recent runs**: `gh run list --limit 5`
- **View failed CI logs**: `gh run view <run_id> --log-failed`
- **Rerun failed CI**: `gh run rerun <run_id> --failed`

## Git Local Operations
- **Status**: `git status --short`
- **Diff**: `git diff`
- **Push**: `git push origin <branch>`

## How to Execute in Python
Use `subprocess.run(["gh", ...], capture_output=True, text=True, check=False)` and print the command output cleanly so the user receives it.


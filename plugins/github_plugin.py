import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.GitHubPlugin")

_CREDENTIAL_TARGET = "PRIVACY68/GitHub/PersonalAccessToken"
_GITHUB_API = "https://api.github.com"


class GitHubPlugin(BasePlugin):
    """GitHub account and current-project integration using a Windows-stored PAT."""

    def __init__(self, repo_path: Optional[str] = None):
        super().__init__()
        self.id = "github"
        self.name = "GitHub"
        self.version = "1.0.0"
        self.description = "Manage GitHub repositories, issues, pull requests, and this project's Git branch."
        self.icon = "🐙"
        self.category = "Developer"
        self.plugin_type = "GitHub Integration"
        self.is_builtin = True
        self.repo_path = os.path.abspath(repo_path or os.path.join(os.path.dirname(__file__), os.pardir))

    def _credential_manager(self):
        if os.name != "nt":
            raise RuntimeError("GitHub token storage requires Windows Credential Manager.")
        try:
            import win32cred
        except ImportError as exc:
            raise RuntimeError("Windows Credential Manager is unavailable; install the project Windows dependencies.") from exc
        return win32cred

    def get_token(self) -> Optional[str]:
        win32cred = self._credential_manager()
        try:
            credential = win32cred.CredRead(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC)
        except Exception as exc:
            if getattr(exc, "winerror", None) == 1168:
                return None
            raise RuntimeError("Could not read the GitHub credential from Windows Credential Manager.") from exc

        secret = credential.get("CredentialBlob")
        if isinstance(secret, bytes):
            return secret.decode("utf-8")
        if isinstance(secret, str):
            return secret
        raise RuntimeError("The saved GitHub credential has an unsupported format.")

    def connect(self, token: str) -> Dict[str, Any]:
        token = token.strip()
        if not token or len(token) > 500:
            return {"success": False, "message": "Enter a valid GitHub personal access token."}

        user = self._api_request("GET", "/user", token=token)
        win32cred = self._credential_manager()
        try:
            win32cred.CredWrite({
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": _CREDENTIAL_TARGET,
                "UserName": user["login"],
                "CredentialBlob": token.encode("utf-8"),
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            }, 0)
        except Exception as exc:
            raise RuntimeError("GitHub sign-in succeeded, but Windows Credential Manager could not save the token.") from exc
        return {"success": True, "message": f"Connected to GitHub as {user['login']}.", "login": user["login"]}

    def disconnect(self) -> Dict[str, Any]:
        win32cred = self._credential_manager()
        try:
            win32cred.CredDelete(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
        except Exception as exc:
            if getattr(exc, "winerror", None) != 1168:
                raise RuntimeError("Could not remove the GitHub credential from Windows Credential Manager.") from exc
        return {"success": True, "message": "GitHub token removed from Windows Credential Manager."}

    def get_connection_status(self) -> Dict[str, Any]:
        token = self.get_token()
        if not token:
            return {"connected": False, "login": ""}
        user = self._api_request("GET", "/user", token=token)
        return {"connected": True, "login": user["login"]}

    def _api_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None,
                     query: Optional[Dict[str, str]] = None, token: Optional[str] = None) -> Any:
        token = token or self.get_token()
        if not token:
            raise RuntimeError("Connect a GitHub account in the Plugins dashboard first.")
        url = f"{_GITHUB_API}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, method=method, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PRIVACY68",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(detail).get("message", "")
            except (json.JSONDecodeError, AttributeError):
                message = ""
            if exc.code == 401:
                raise RuntimeError("GitHub rejected the token. Reconnect with a valid personal access token.") from exc
            if exc.code == 403:
                raise RuntimeError(f"GitHub denied this action. Check token permissions or rate limits. {message}".strip()) from exc
            if exc.code == 404:
                raise RuntimeError("GitHub could not find that repository or resource; check its name and token access.") from exc
            raise RuntimeError(f"GitHub API request failed ({exc.code}): {message or exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not connect to GitHub: {exc.reason}") from exc
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _run_git(self, *args: str, timeout: int = 30, extra_env: Optional[Dict[str, str]] = None):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, **(extra_env or {})},
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Git is not installed or is not available on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Git command timed out: git {' '.join(args)}") from exc
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or "Git command failed."
            raise RuntimeError(message)
        return result.stdout.strip()

    def current_repository(self) -> str:
        remote = self._run_git("remote", "get-url", "origin")
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if not match:
            raise RuntimeError("The current project's origin remote is not a GitHub repository.")
        return match.group(1)

    def parse_command(self, text: str):
        """Translate a small, explicit set of GitHub requests into plugin actions."""
        low = text.strip().lower()
        if not re.search(r"\b(github|git)\b", low):
            return None

        branch_match = re.search(
            r"\bbranch(?:\s+(?:is|named|called|ok|okay))?\s+([A-Za-z0-9][A-Za-z0-9._/-]{0,199})",
            text,
            re.IGNORECASE,
        )
        repo_match = re.search(r"\brepo(?:sitory)?\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text, re.IGNORECASE)

        if re.search(r"\b(delete|remove|close|merge|fork|release|workflow)\b", low):
            return {"action": "unsupported", "kwargs": {}, "requires_confirmation": False}
        if re.search(r"\b(push|upload)\b", low):
            branch = branch_match.group(1).rstrip(".,!?") if branch_match else None
            return {
                "action": "push",
                "kwargs": {"branch": branch},
                "requires_confirmation": True,
                "description": f"push the current project branch{f' {branch}' if branch else ''} to GitHub",
            }
        if re.search(r"\b(status|changes|diff)\b", low):
            return {"action": "status", "kwargs": {}, "requires_confirmation": False}
        if re.search(r"\b(create|open|file)\b", low) and re.search(r"\bissue\b", low):
            title_match = re.search(r"\btitle\s+(.+?)(?=\s+\bbody\b|$)", text, re.IGNORECASE)
            body_match = re.search(r"\bbody\s+(.+)$", text, re.IGNORECASE)
            return {
                "action": "create_issue",
                "kwargs": {
                    "title": title_match.group(1).strip(" \"'") if title_match else "",
                    "body": body_match.group(1).strip(" \"'") if body_match else "",
                    "repo": repo_match.group(1) if repo_match else None,
                },
                "requires_confirmation": True,
                "description": "create a GitHub issue",
            }
        if re.search(r"\b(create|open)\b", low) and re.search(r"\b(pull request|pr)\b", low):
            title_match = re.search(r"\btitle\s+(.+?)(?=\s+\b(?:head|base|body)\b|$)", text, re.IGNORECASE)
            head_match = re.search(r"\bhead\s+([A-Za-z0-9][A-Za-z0-9._/-]*)", text, re.IGNORECASE)
            base_match = re.search(r"\bbase\s+([A-Za-z0-9][A-Za-z0-9._/-]*)", text, re.IGNORECASE)
            body_match = re.search(r"\bbody\s+(.+)$", text, re.IGNORECASE)
            return {
                "action": "create_pull_request",
                "kwargs": {
                    "title": title_match.group(1).strip(" \"'") if title_match else "",
                    "head": head_match.group(1) if head_match else "",
                    "base": base_match.group(1) if base_match else "",
                    "body": body_match.group(1).strip(" \"'") if body_match else "",
                    "repo": repo_match.group(1) if repo_match else None,
                },
                "requires_confirmation": True,
                "description": "create a GitHub pull request",
            }
        if re.search(r"\b(issues|issue)\b", low):
            return {"action": "list_issues", "kwargs": {"repo": repo_match.group(1) if repo_match else None},
                    "requires_confirmation": False}
        if re.search(r"\b(pull requests|pull request|prs)\b", low):
            return {"action": "list_pull_requests", "kwargs": {"repo": repo_match.group(1) if repo_match else None},
                    "requires_confirmation": False}
        if re.search(r"\b(repositories|repos)\b", low):
            return {"action": "list_repositories", "kwargs": {}, "requires_confirmation": False}
        if re.search(
            r"\b(push|pull|upload|commit|branch|status|diff|changes|repositories|repository|repos|issues?|pull requests?|prs?|"
            r"delete|remove|close|merge|fork|release|workflow)\b",
            low,
        ):
            return {"action": "unsupported", "kwargs": {}, "requires_confirmation": False}
        return None

    def repository_status(self) -> Dict[str, Any]:
        branch = self._run_git("branch", "--show-current")
        status = self._run_git("status", "--short", "--branch")
        diff = self._run_git("diff", "--stat")
        staged_diff = self._run_git("diff", "--cached", "--stat")
        return {
            "repository": self.current_repository(),
            "branch": branch,
            "status": status or "Working tree clean.",
            "diff": "\n".join(part for part in (diff, staged_diff) if part) or "No unstaged or staged diff.",
        }

    def push(self, branch: Optional[str] = None) -> Dict[str, Any]:
        current_branch = self._run_git("branch", "--show-current")
        branch = branch or current_branch
        if not branch or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch):
            raise RuntimeError("A valid local branch name is required to push.")
        if branch != current_branch:
            raise RuntimeError(f"The checked-out branch is '{current_branch}', not '{branch}'. Check out the requested branch first.")
        working_tree = self._run_git("status", "--porcelain")
        if working_tree:
            raise RuntimeError("The working tree has uncommitted changes. Review and commit them in VS Code, then retry the push.")
        token = self.get_token()
        if not token:
            raise RuntimeError("Connect a GitHub account in the Plugins dashboard before pushing.")
        remote = self._run_git("remote", "get-url", "origin")
        if not re.match(r"https://github\.com/", remote, re.IGNORECASE):
            raise RuntimeError("GitHub token pushes require an HTTPS GitHub origin remote.")

        helper_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".cmd", prefix="privacy68-git-auth-", delete=False,
                                             encoding="ascii", newline="\r\n") as helper:
                helper.write('@echo off\r\n')
                helper.write('echo %* | findstr /i "Username" >nul\r\n')
                helper.write('if not errorlevel 1 (\r\n')
                helper.write('  echo x-access-token\r\n')
                helper.write(') else (\r\n')
                helper.write('  echo %PRIVACY68_GITHUB_TOKEN%\r\n')
                helper.write(')\r\n')
                helper_path = helper.name
            output = self._run_git(
                "-c", "credential.helper=",
                "push", "origin", branch,
                timeout=120,
                extra_env={
                    "PRIVACY68_GITHUB_TOKEN": token,
                    "GIT_ASKPASS": helper_path,
                    "GIT_TERMINAL_PROMPT": "0",
                },
            )
        finally:
            if helper_path and os.path.exists(helper_path):
                os.remove(helper_path)
        return {"message": f"Pushed branch '{branch}' to GitHub.", "output": output}

    def list_repositories(self):
        repositories = self._api_request("GET", "/user/repos", query={"sort": "updated", "per_page": "30"})
        return [
            {"name": repo["full_name"], "private": repo["private"], "url": repo["html_url"]}
            for repo in repositories
        ]

    def list_issues(self, repo: Optional[str] = None):
        repo = repo or self.current_repository()
        issues = self._api_request("GET", f"/repos/{repo}/issues", query={"state": "open", "per_page": "30"})
        return [
            {"number": item["number"], "title": item["title"], "url": item["html_url"]}
            for item in issues if "pull_request" not in item
        ]

    def create_issue(self, title: str, body: str = "", repo: Optional[str] = None):
        if not title.strip():
            raise RuntimeError("An issue title is required.")
        repo = repo or self.current_repository()
        issue = self._api_request("POST", f"/repos/{repo}/issues", {"title": title.strip(), "body": body})
        return {"message": f"Created issue #{issue['number']}: {issue['title']}", "url": issue["html_url"]}

    def list_pull_requests(self, repo: Optional[str] = None):
        repo = repo or self.current_repository()
        pulls = self._api_request("GET", f"/repos/{repo}/pulls", query={"state": "open", "per_page": "30"})
        return [
            {"number": item["number"], "title": item["title"], "url": item["html_url"]}
            for item in pulls
        ]

    def create_pull_request(self, title: str, head: str, base: str, body: str = "",
                            repo: Optional[str] = None):
        if not title.strip() or not head.strip() or not base.strip():
            raise RuntimeError("A pull request title, head branch, and base branch are required.")
        repo = repo or self.current_repository()
        pull = self._api_request("POST", f"/repos/{repo}/pulls", {
            "title": title.strip(),
            "head": head.strip(),
            "base": base.strip(),
            "body": body,
        })
        return {"message": f"Created pull request #{pull['number']}: {pull['title']}", "url": pull["html_url"]}

    def perform(self, action: str, **kwargs) -> Dict[str, Any]:
        if action == "status":
            return {"success": True, "message": "Current project status.", "details": self.repository_status()}
        if action == "push":
            return {"success": True, **self.push(kwargs.get("branch"))}
        if action == "list_repositories":
            return {"success": True, "message": "GitHub repositories.", "details": self.list_repositories()}
        if action == "list_issues":
            return {"success": True, "message": "Open GitHub issues.", "details": self.list_issues(kwargs.get("repo"))}
        if action == "create_issue":
            return {"success": True, **self.create_issue(kwargs.get("title", ""), kwargs.get("body", ""), kwargs.get("repo"))}
        if action == "list_pull_requests":
            return {"success": True, "message": "Open pull requests.", "details": self.list_pull_requests(kwargs.get("repo"))}
        if action == "create_pull_request":
            return {"success": True, **self.create_pull_request(
                kwargs.get("title", ""),
                kwargs.get("head", ""),
                kwargs.get("base", ""),
                kwargs.get("body", ""),
                kwargs.get("repo"),
            )}
        raise ValueError(f"Unsupported GitHub action: {action}")

    def execute(self, action: str, **kwargs) -> bool:
        try:
            self.perform(action, **kwargs)
            return True
        except (RuntimeError, ValueError) as exc:
            logger.warning("GitHub action %s failed: %s", action, exc)
            return False

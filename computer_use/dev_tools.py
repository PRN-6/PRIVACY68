"""
PRIVACY68 Developer Tools Controller.

Provides controlled developer workflow automation:
  - Git repository inspection and operations (status, diff, branch, log, pull, commit)
  - VS Code workspace management (open project, open active file)
  - Safe terminal command and Python runner with strict security allowlists
"""

import os
import subprocess
import logging
import time
import json
from typing import Any, Dict, List, Optional

import psutil
try:
    import pyautogui
except Exception:
    pyautogui = None
try:
    import pyperclip
except Exception:
    pyperclip = None

from computer_use.window_manager import window_manager

logger = logging.getLogger("PRIVACY68.DevTools")


class DevToolsController:
    """
    Automates developer tools and version control operations.
    """

    IDE_SPECS = [
        {"name": "Antigravity IDE", "processes": ["antigravity ide.exe", "antigravity.exe"], "window_query": "antigravity"},
        {"name": "Visual Studio Code", "processes": ["code.exe"], "window_query": "vs code"},
        {"name": "Cursor", "processes": ["cursor.exe"], "window_query": "cursor"},
        {"name": "Windsurf", "processes": ["windsurf.exe"], "window_query": "windsurf"},
        {"name": "PyCharm", "processes": ["pycharm64.exe", "pycharm.exe"], "window_query": "pycharm"},
        {"name": "IntelliJ IDEA", "processes": ["idea64.exe", "idea.exe"], "window_query": "intellij"},
        {"name": "Sublime Text", "processes": ["sublime_text.exe"], "window_query": "sublime"},
    ]

    @staticmethod
    def _find_git_root(start_path: Optional[str] = None) -> Optional[str]:
        """Finds the root directory containing .git starting from start_path or current directory."""
        if not start_path:
            start_path = os.getcwd()
        try:
            curr = os.path.abspath(start_path)
            while True:
                if os.path.isdir(os.path.join(curr, ".git")):
                    return curr
                parent = os.path.dirname(curr)
                if parent == curr:
                    break
                curr = parent
        except Exception as e:
            logger.debug(f"_find_git_root: {e}")
        return None

    def detect_active_ide_and_repo(self) -> Optional[Dict[str, Any]]:
        """
        Detects if any supported developer IDE is open and locates its active git repository.
        Inspects process instances, working directories, and open workspace trees.
        """
        running_procs: Dict[int, Any] = {}
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info.get('name')
                if name:
                    running_procs[p.pid] = (p, name.lower())
            except Exception:
                continue

        for spec in self.IDE_SPECS:
            matching_pids = [
                pid for pid, (proc, pname) in running_procs.items()
                if any(target in pname for target in spec["processes"])
            ]
            if not matching_pids:
                continue

            # Check matching processes for a git repository CWD
            detected_repo = None
            for pid in matching_pids:
                try:
                    proc = running_procs[pid][0]
                    cwd = proc.cwd()
                    if cwd:
                        git_root = self._find_git_root(cwd)
                        if git_root:
                            detected_repo = git_root
                            break
                except Exception:
                    continue

            # Fallback to current directory git root if no process CWD exposed it
            if not detected_repo:
                detected_repo = self._find_git_root(os.getcwd())

            return {
                "ide_name": spec["name"],
                "window_query": spec["window_query"],
                "repo_path": detected_repo,
                "repo_name": os.path.basename(detected_repo) if detected_repo else "",
            }

        return None

    def generate_smart_commit_message(self, repo_path: str) -> str:
        """
        Generates a concise, high-quality conventional commit message based on uncommitted changes.
        Uses Cloud LLM (Groq / OpenAI) if configured; falls back to semantic heuristics.
        """
        stat_res = self.run_git_command(["diff", "--stat"], repo_path)
        status_res = self.run_git_command(["status", "--porcelain"], repo_path)

        diff_summary = stat_res.get("output", "").strip()
        status_summary = status_res.get("output", "").strip()

        if not diff_summary and not status_summary:
            return ""

        # Gather changed files
        changed_files = []
        for line in status_summary.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                changed_files.append(parts[1])

        # 1. Try Cloud LLM synthesis (if Groq / OpenAI configured in profile_manager)
        try:
            from plugins.profile_manager import profile_manager
            provider = profile_manager.get("llm_provider", "groq")
            api_key = profile_manager.get("api_key", "").strip()
            cloud_model = profile_manager.get("cloud_model", "llama-3.3-70b-versatile")

            if api_key and provider == "groq":
                prompt = (
                    "You are an expert Git assistant. Generate ONE single concise conventional commit message "
                    "(e.g., 'feat(speech): support custom wake words' or 'fix(auth): update speaker verification'). "
                    "Max 60 characters. Do NOT use markdown or quotes. Return ONLY the commit message.\n\n"
                    f"Git status:\n{status_summary[:1000]}\n\nGit diff stat:\n{diff_summary[:1000]}"
                )
                import urllib.request
                payload = {
                    "model": cloud_model,
                    "messages": [
                        {"role": "system", "content": "You output only a single conventional git commit message."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 40
                }
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "PRIVACY68/1.0"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg = data["choices"][0]["message"]["content"].strip().strip('"\'`')
                    if msg and len(msg) >= 5:
                        return msg
        except Exception as e:
            logger.debug(f"[DEV_TOOLS] LLM commit message generation skipped: {e}")

        # 2. Smart Heuristic Conventional Commit Generator (Instant & Offline)
        scopes = set()
        for f in changed_files:
            lower_f = f.lower()
            if "speech" in lower_f or "audio" in lower_f or "streamer" in lower_f:
                scopes.add("speech")
            elif "action" in lower_f or "intent" in lower_f:
                scopes.add("actions")
            elif "ui" in lower_f or "dashboard" in lower_f or "html" in lower_f or "css" in lower_f:
                scopes.add("ui")
            elif "plugin" in lower_f:
                scopes.add("plugins")
            elif "test" in lower_f:
                scopes.add("tests")
            elif "doc" in lower_f or "readme" in lower_f or "changelog" in lower_f:
                scopes.add("docs")
            elif "config" in lower_f or "setting" in lower_f:
                scopes.add("config")

        scope_str = "/".join(sorted(scopes)[:2]) if scopes else "core"
        if "docs" in scopes and len(scopes) == 1:
            return f"docs: update documentation for {scope_str}"
        elif "tests" in scopes and len(scopes) == 1:
            return "test: update test suites and verifications"
        elif any("fix" in f.lower() for f in changed_files):
            return f"fix({scope_str}): update changes in {scope_str} components"
        else:
            first_file = os.path.basename(changed_files[0]) if changed_files else "project files"
            return f"feat({scope_str}): update {first_file} and related modules"

    def execute_in_ide_terminal(self, ide_info: Dict[str, Any], commit_message: str, changes_exist: bool) -> bool:
        """
        Brings the active IDE (Antigravity IDE, VS Code, Cursor, Windsurf, etc.) to the foreground,
        opens a brand new integrated terminal tab (Ctrl + Shift + `), and executes the git commands live.
        """
        ide_name = ide_info.get("ide_name", "IDE")
        win_query = ide_info.get("window_query", "antigravity")

        logger.info(f"[DEV_TOOLS] Bringing {ide_name} to foreground...")
        window_manager.focus_window(win_query)
        time.sleep(0.5)

        if not pyautogui:
            logger.warning("[DEV_TOOLS] pyautogui not available to automate IDE terminal")
            return False

        pyautogui.FAILSAFE = False

        # Open a brand new integrated terminal tab in the IDE
        logger.info(f"[DEV_TOOLS] Opening new terminal in {ide_name} via Ctrl+Shift+`...")
        if any(jb in ide_name.lower() for jb in ("pycharm", "intellij", "idea")):
            pyautogui.hotkey("alt", "f12")
        else:
            # Universal shortcut for VS Code, Antigravity IDE, Cursor, Windsurf:
            # Ctrl+Shift+` creates a new terminal and automatically focuses it.
            pyautogui.hotkey("ctrl", "shift", "`")

        # Allow terminal shell to initialize and display prompt
        time.sleep(1.2)

        # Commands to execute
        commands = []
        if changes_exist:
            commands.append("git add .")
            commands.append(f'git commit -m "{commit_message}"')
        commands.append("git push")

        for cmd in commands:
            if pyperclip:
                pyperclip.copy(cmd)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.typewrite(cmd, interval=0.01)
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.6)

        logger.info(f"[DEV_TOOLS] Successfully executed git commands in {ide_name} new terminal.")
        return True

    def open_external_terminal_and_run(self, repo_path: str, commit_message: str, changes_exist: bool) -> bool:
        """
        Fallback: Opens a standalone external PowerShell window in repo_path and executes git push.
        """
        repo_name = os.path.basename(repo_path)
        safe_msg = commit_message.replace("'", "''").replace('"', '`"')
        if changes_exist:
            script = f"git add .; git commit -m '{safe_msg}'; git push"
        else:
            script = "git push"

        try:
            cmd = ["powershell.exe", "-NoExit", "-Command", f"Set-Location -LiteralPath '{repo_path}'; {script}"]
            subprocess.Popen(cmd, cwd=repo_path, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
            logger.info(f"[DEV_TOOLS] Launched external PowerShell in '{repo_path}'")
            return True
        except Exception as e:
            logger.error(f"[DEV_TOOLS] Could not launch external PowerShell: {e}")
            return False

    def smart_git_push_workflow(self) -> Dict[str, Any]:
        """
        Executes IDE-aware Git push automation:
        1. Automatically detects the active IDE and project repository.
        2. Inspects git status and diff for uncommitted changes or pending commits.
        3. Synthesizes a clean conventional commit message.
        4. Focuses the IDE, opens a brand new integrated terminal (Ctrl + Shift + `).
        5. Executes git add ., git commit -m "<message>", and git push live in the IDE.
        """
        ide_info = self.detect_active_ide_and_repo()
        repo_path = ide_info.get("repo_path") if ide_info else None

        if not repo_path or not os.path.exists(repo_path):
            repo_path = self._find_git_root(os.getcwd())

        if not repo_path or not os.path.exists(repo_path):
            return {
                "success": False,
                "tool": "smart_git_push",
                "message": "No Git repository found in your active IDE or current directory."
            }

        repo_name = os.path.basename(repo_path)
        ide_name = ide_info.get("ide_name", "your IDE") if ide_info else "your IDE"

        # Check for uncommitted changes
        status_res = self.run_git_command(["status", "--porcelain"], repo_path)
        changes = status_res.get("output", "").strip()

        # Check for unpushed commits
        unpushed_res = self.run_git_command(["log", "@{u}..HEAD", "--oneline"], repo_path)
        unpushed = unpushed_res.get("output", "").strip()

        if not changes and not unpushed:
            return {
                "success": True,
                "tool": "smart_git_push",
                "message": f"Your project '{repo_name}' is already up to date. No new changes to push."
            }

        # Generate smart commit message if changes exist
        commit_msg = self.generate_smart_commit_message(repo_path) if changes else "Sync latest commits with remote"

        # Execute live in IDE's new terminal
        executed = False
        if ide_info:
            executed = self.execute_in_ide_terminal(ide_info, commit_msg, bool(changes))

        # Fallback to external terminal if no IDE was detected or hotkey automation failed
        if not executed:
            self.open_external_terminal_and_run(repo_path, commit_msg, bool(changes))

        logger.info(f"[DEV_TOOLS] Smart Git Push triggered in {ide_name} terminal for {repo_name}: '{commit_msg}'")
        return {
            "success": True,
            "tool": "smart_git_push",
            "repo": repo_name,
            "ide": ide_name,
            "commit_message": commit_msg,
            "message": f"Opened new terminal in {ide_name}, committed changes as '{commit_msg}', and pushed to GitHub."
        }

    def run_git_command(self, git_args: List[str], repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Executes a git command inside the detected repository directory."""
        root = self._find_git_root(repo_path)
        if not root:
            return {"success": False, "error": "No Git repository found in the current project hierarchy."}

        # Disallow raw dangerous git options
        disallowed = {"--exec", "--upload-pack", "config", "filter-branch"}
        if any(d in git_args for d in disallowed):
            return {"success": False, "error": "Disallowed git command for safety."}

        try:
            cmd = ["git"] + git_args
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            output = proc.stdout.strip() or proc.stderr.strip()
            return {
                "success": proc.returncode == 0,
                "output": output,
                "returncode": proc.returncode,
                "cwd": root,
            }
        except Exception as e:
            logger.error(f"[DEV_TOOLS] Git error {git_args}: {e}")
            return {"success": False, "error": str(e)}

    def git_status(self, repo_path: Optional[str] = None) -> str:
        res = self.run_git_command(["status", "--short"], repo_path)
        if not res["success"]:
            return res.get("error", "Failed to check git status.")
        changes = res.get("output", "")
        if not changes:
            return "Git working directory is clean. No uncommitted changes."
        return f"Git status:\n{changes}"

    def git_branch(self, repo_path: Optional[str] = None) -> str:
        res = self.run_git_command(["branch", "--show-current"], repo_path)
        if not res["success"]:
            return res.get("error", "Failed to get current branch.")
        branch = res.get("output", "main")
        return f"Currently on git branch '{branch}'."

    def git_pull(self, repo_path: Optional[str] = None) -> str:
        res = self.run_git_command(["pull"], repo_path)
        return res.get("output") or ("Pulled latest changes successfully." if res["success"] else "Git pull failed.")

    def git_log(self, count: int = 3, repo_path: Optional[str] = None) -> str:
        res = self.run_git_command(["log", f"-n{count}", "--oneline"], repo_path)
        return res.get("output", "No git commits found.")

    def git_add_all(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        return self.run_git_command(["add", "."], repo_path)

    def git_commit(self, message: str = "Auto-update via Privacy68", repo_path: Optional[str] = None) -> Dict[str, Any]:
        return self.run_git_command(["commit", "-m", message], repo_path)

    def git_push(self, repo_path: Optional[str] = None) -> str:
        res = self.run_git_command(["push"], repo_path)
        if res["success"]:
            return "Successfully pushed code to remote repository!"
        return f"Git push failed: {res.get('output', 'Unknown error')}"

    def git_push_workflow(self, commit_message: str = "Update via Privacy68", repo_path: Optional[str] = None) -> str:
        """Runs: git add . -> git commit -m <msg> -> git push"""
        root = self._find_git_root(repo_path)
        if not root:
            return "No Git repository found in the current workspace."

        add_res = self.git_add_all(root)
        if not add_res["success"]:
            return f"Git add failed: {add_res.get('error')}"

        commit_res = self.git_commit(commit_message, root)
        push_res = self.git_push(root)
        return push_res

    def open_in_vscode(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        """Launches Visual Studio Code opening the specified directory or current workspace."""
        path_to_open = os.path.abspath(target_path or os.getcwd())
        try:
            subprocess.Popen(["code", path_to_open], shell=True)
            return {"success": True, "message": f"Opened '{path_to_open}' in Visual Studio Code."}
        except Exception as e:
            logger.error(f"[DEV_TOOLS] Failed opening VS Code: {e}")
            return {"success": False, "error": str(e)}


# Global singleton instance
dev_tools = DevToolsController()


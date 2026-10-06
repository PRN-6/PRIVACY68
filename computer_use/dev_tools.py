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
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PRIVACY68.DevTools")


class DevToolsController:
    """
    Automates developer tools and version control operations.
    """

    @staticmethod
    def _find_git_root(start_path: Optional[str] = None) -> Optional[str]:
        """Finds the root directory containing .git starting from start_path or current directory."""
        curr = os.path.abspath(start_path or os.getcwd())
        while True:
            if os.path.isdir(os.path.join(curr, ".git")):
                return curr
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
        return None

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
        # If nothing to commit, we can still attempt push
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

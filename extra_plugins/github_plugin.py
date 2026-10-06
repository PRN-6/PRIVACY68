"""
PRIVACY68 GitHub Automation Plugin.

Provides native voice integration with GitHub:
  - Open GitHub dashboard & notifications
  - Search GitHub repositories, code, and issues
  - View Pull Requests, Trending repos, and Issues
  - Open new repository creator
  - Git repository push / sync integration
"""

import logging
import re
import urllib.parse
import webbrowser
from typing import Callable, Dict, List

from plugins.base_plugin import BasePlugin
from computer_use.dev_tools import dev_tools

logger = logging.getLogger("PRIVACY68.Plugin.GitHub")


class GitHubPlugin(BasePlugin):
    id = "github"
    name = "GitHub Manager"
    icon = "🐙"
    description = "Manage GitHub repositories, search code, check notifications, PRs, and trending projects."
    version = "1.0.0"
    author = "Privacy68 Team"
    category = "Developer Tools"
    plugin_type = "Developer Automation"

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "github.open": self.open_github,
            "github.notifications": self.open_notifications,
            "github.pull_requests": self.open_pull_requests,
            "github.issues": self.open_issues,
            "github.trending": self.open_trending,
            "github.search": self.search_github,
            "github.create_repo": self.create_new_repo,
            "github.my_repositories": self.open_my_repositories,
            "github.push": self.push_current_repo,
            "github.status": self.check_repo_status,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "github.open": [
                "open github",
                "launch github",
                "go to github",
                "start github",
            ],
            "github.notifications": [
                "open github notifications",
                "check github notifications",
                "github notifications",
                "show my notifications on github",
            ],
            "github.pull_requests": [
                "open pull requests",
                "show my pull requests",
                "open github pull requests",
                "github prs",
            ],
            "github.issues": [
                "open github issues",
                "show github issues",
                "my github issues",
            ],
            "github.trending": [
                "open github trending",
                "show trending repositories",
                "what is trending on github",
                "github trending",
            ],
            "github.search": [
                "search github for",
                "search on github",
                "find repo on github",
                "look up on github",
            ],
            "github.create_repo": [
                "create new repository on github",
                "new github repo",
                "create repo on github",
            ],
            "github.my_repositories": [
                "open my repositories on github",
                "show my repos on github",
                "my github repos",
            ],
            "github.push": [
                "push to github",
                "push my code to github",
                "push repo to github",
            ],
            "github.status": [
                "github status",
                "check github repo status",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "github.open": "Opens GitHub homepage or dashboard in the default browser.",
            "github.notifications": "Opens GitHub notifications inbox.",
            "github.pull_requests": "Opens user pull requests overview on GitHub.",
            "github.issues": "Opens GitHub issues page.",
            "github.trending": "Opens trending GitHub repositories for the day/week.",
            "github.search": "Searches GitHub for repositories, topics, libraries, or code.",
            "github.create_repo": "Opens the GitHub new repository creation page.",
            "github.my_repositories": "Opens the current user's repositories list on GitHub.",
            "github.push": "Stages, commits, and pushes current workspace code to remote GitHub origin.",
            "github.status": "Checks current local Git repository branch and uncommitted changes.",
        }

    def open_github(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening GitHub home")
        return webbrowser.open("https://github.com")

    def open_notifications(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening notifications")
        return webbrowser.open("https://github.com/notifications")

    def open_pull_requests(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening pull requests")
        return webbrowser.open("https://github.com/pulls")

    def open_issues(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening issues")
        return webbrowser.open("https://github.com/issues")

    def open_trending(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening trending")
        return webbrowser.open("https://github.com/trending")

    def open_my_repositories(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening user repositories")
        return webbrowser.open("https://github.com?tab=repositories")

    def create_new_repo(self, text: str = "") -> bool:
        logger.info("[GITHUB] Opening new repo page")
        return webbrowser.open("https://github.com/new")

    def search_github(self, text: str) -> bool:
        query = re.sub(r"^(?:please\s*)?(?:search\s+(?:on\s+)?github\s+(?:for|about)?|find\s+(?:on\s+)?github\s+(?:for|about)?|look\s+up\s+on\s+github\s+)\s*", "", text, flags=re.IGNORECASE).strip()
        if not query:
            query = "machine learning"
        encoded = urllib.parse.quote(query)
        url = f"https://github.com/search?q={encoded}&type=repositories"
        logger.info(f"[GITHUB] Searching GitHub for: '{query}'")
        return webbrowser.open(url)

    def push_current_repo(self, text: str = "") -> bool:
        logger.info("[GITHUB] Triggering git push workflow")
        msg = dev_tools.git_push_workflow(commit_message="Updated via Privacy68 voice assistant")
        logger.info(f"[GITHUB] Push result: {msg}")
        return True

    def check_repo_status(self, text: str = "") -> bool:
        logger.info("[GITHUB] Checking repo status")
        status = dev_tools.git_status()
        logger.info(f"[GITHUB] Status:\n{status}")
        return True

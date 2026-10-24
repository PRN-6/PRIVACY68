import os
import unittest
from unittest.mock import Mock, patch

from plugins.github_plugin import GitHubPlugin


class TestGitHubPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = GitHubPlugin(repo_path="C:\\repo")

    def test_parse_push_includes_explicit_branch_and_confirmation(self):
        result = self.plugin.parse_command(
            "push my code to github; this is the branch ok feat/function-calling-architecture"
        )

        self.assertEqual(result["action"], "push")
        self.assertEqual(result["kwargs"]["branch"], "feat/function-calling-architecture")
        self.assertTrue(result["requires_confirmation"])

    def test_unsupported_github_operations_do_not_fall_through_to_agent(self):
        result = self.plugin.parse_command("close this GitHub issue")

        self.assertEqual(result["action"], "unsupported")

    def test_parse_status_and_read_only_api_requests(self):
        self.assertEqual(self.plugin.parse_command("check git status")["action"], "status")
        self.assertEqual(self.plugin.parse_command("list my GitHub repositories")["action"], "list_repositories")
        self.assertEqual(self.plugin.parse_command("show GitHub issues")["action"], "list_issues")
        self.assertEqual(self.plugin.parse_command("show pull requests on GitHub")["action"], "list_pull_requests")

    def test_parse_issue_creation_requires_title_and_confirmation(self):
        result = self.plugin.parse_command("create GitHub issue title Fix login body Login fails")

        self.assertEqual(result["action"], "create_issue")
        self.assertEqual(result["kwargs"]["title"], "Fix login")
        self.assertEqual(result["kwargs"]["body"], "Login fails")
        self.assertTrue(result["requires_confirmation"])

    def test_parse_pull_request_creation_captures_branches(self):
        result = self.plugin.parse_command(
            "create GitHub pull request title Add feature head feat/demo base main body Summary"
        )

        self.assertEqual(result["kwargs"]["title"], "Add feature")
        self.assertEqual(result["kwargs"]["head"], "feat/demo")
        self.assertEqual(result["kwargs"]["base"], "main")

    def test_connect_validates_token_and_saves_in_credential_manager(self):
        credential_manager = Mock()
        credential_manager.CRED_TYPE_GENERIC = 1
        credential_manager.CRED_PERSIST_LOCAL_MACHINE = 2
        with patch.object(self.plugin, "_api_request", return_value={"login": "tester"}) as request:
            with patch.object(self.plugin, "_credential_manager", return_value=credential_manager):
                result = self.plugin.connect("github_pat_example")

        self.assertTrue(result["success"])
        request.assert_called_once_with("GET", "/user", token="github_pat_example")
        saved = credential_manager.CredWrite.call_args.args[0]
        self.assertEqual(saved["CredentialBlob"], b"github_pat_example")
        self.assertEqual(saved["TargetName"], "PRIVACY68/GitHub/PersonalAccessToken")

    def test_connect_does_not_save_a_token_if_github_rejects_it(self):
        credential_manager = Mock()
        with patch.object(self.plugin, "_api_request", side_effect=RuntimeError("bad token")):
            with patch.object(self.plugin, "_credential_manager", return_value=credential_manager):
                with self.assertRaisesRegex(RuntimeError, "bad token"):
                    self.plugin.connect("github_pat_invalid")

        credential_manager.CredWrite.assert_not_called()

    def test_api_request_requires_saved_token(self):
        with patch.object(self.plugin, "get_token", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Connect a GitHub account"):
                self.plugin._api_request("GET", "/user")

    def test_repository_status_reports_current_branch_and_changes(self):
        with patch.object(
            self.plugin,
            "_run_git",
            side_effect=["feat/demo", "## feat/demo\n M app.py", " app.py | 1 +", ""],
        ):
            with patch.object(self.plugin, "current_repository", return_value="owner/repo"):
                result = self.plugin.repository_status()

        self.assertEqual(result["branch"], "feat/demo")
        self.assertEqual(result["repository"], "owner/repo")
        self.assertIn("M app.py", result["status"])
        self.assertIn("app.py", result["diff"])

    def test_push_does_not_accept_a_different_branch(self):
        with patch.object(self.plugin, "_run_git", return_value="main"):
            with self.assertRaisesRegex(RuntimeError, "not 'feat/demo'"):
                self.plugin.push("feat/demo")

    def test_push_uses_temporary_askpass_without_putting_token_in_arguments(self):
        token = "github_pat_secret"
        with patch.object(self.plugin, "get_token", return_value=token):
            with patch.object(
                self.plugin,
                "_run_git",
                side_effect=["feat/demo", "", "https://github.com/owner/repo.git", "Everything up-to-date"],
            ) as run_git:
                result = self.plugin.push()

        args, kwargs = run_git.call_args
        self.assertNotIn(token, repr(args))
        self.assertEqual(kwargs["extra_env"]["PRIVACY68_GITHUB_TOKEN"], token)
        askpass_path = kwargs["extra_env"]["GIT_ASKPASS"]
        self.assertFalse(os.path.exists(askpass_path))
        self.assertIn("feat/demo", result["message"])

    def test_push_refuses_uncommitted_changes(self):
        with patch.object(self.plugin, "_run_git", side_effect=["feat/demo", " M app.py"]):
            with self.assertRaisesRegex(RuntimeError, "uncommitted changes"):
                self.plugin.push()

    def test_issue_creation_requires_a_title(self):
        with self.assertRaisesRegex(RuntimeError, "title is required"):
            self.plugin.create_issue("  ")


if __name__ == "__main__":
    unittest.main()

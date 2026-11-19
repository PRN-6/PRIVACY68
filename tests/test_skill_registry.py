import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from skills.skill_registry import SkillRegistry, skill_registry


class TestSkillRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = SkillRegistry()

    def test_builtin_skills_loaded(self):
        skills = self.registry.list_skills()
        skill_names = [s["name"].lower() for s in skills]
        self.assertIn("github", skill_names)
        self.assertIn("vscode", skill_names)
        self.assertIn("docker", skill_names)

    def test_github_skill_matching(self):
        matches = self.registry.find_matching_skills("check why the CI failed on PR 55")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["name"].lower(), "github")

    def test_vscode_skill_matching(self):
        matches = self.registry.find_matching_skills("open my project PRIVACY68 in vs code")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["name"].lower(), "vscode")

    def test_docker_skill_matching(self):
        matches = self.registry.find_matching_skills("show all running docker containers")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["name"].lower(), "docker")

    def test_build_prompt_context_includes_skill_body(self):
        context = self.registry.build_skill_prompt_context("check github pr 42 status")
        self.assertIn("DEVELOPER SKILL KNOWLEDGE", context)
        self.assertIn("GITHUB", context)
        self.assertIn("gh pr", context)

    def test_agent_brain_injects_skill_context(self):
        from actions.agent_brain import agent_brain
        with patch.object(agent_brain, "_call_single_model", return_value="print('test')") as mock_call:
            agent_brain._get_code_from_llm("open my project chat in vs code")
            messages = mock_call.call_args[0][1]
            sys_msg = messages[0]["content"]
            self.assertIn("DEVELOPER SKILL KNOWLEDGE", sys_msg)
            self.assertIn("VSCODE", sys_msg)


if __name__ == "__main__":
    unittest.main()


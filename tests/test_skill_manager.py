import os
import shutil
import tempfile
import unittest
from actions.skill_manager import SkillManager


class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = SkillManager(storage_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_preseeded_skills_exist(self):
        skills = self.mgr.list_skills()
        skill_ids = [s["id"] for s in skills]
        self.assertIn("organize_downloads", skill_ids)
        self.assertIn("take_screenshot", skill_ids)
        self.assertIn("system_performance_diagnostics", skill_ids)

    def test_extract_keywords(self):
        keywords = self.mgr.extract_keywords("Please organize the downloads folder for me")
        self.assertIn("organize", keywords)
        self.assertIn("downloads", keywords)
        self.assertIn("folder", keywords)
        self.assertNotIn("the", keywords)
        self.assertNotIn("for", keywords)
        self.assertNotIn("me", keywords)

    def test_find_matching_skill_exact_phrase(self):
        match = self.mgr.find_matching_skill("organize downloads")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], "organize_downloads")

    def test_find_matching_skill_partial_phrase(self):
        match = self.mgr.find_matching_skill("can you please organize downloads right now")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], "organize_downloads")

    def test_find_matching_skill_screenshot(self):
        match = self.mgr.find_matching_skill("take a screenshot")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], "take_screenshot")

    def test_learn_new_skill_and_recall(self):
        code = "import os\nprint('custom automated work')\n"
        learned = self.mgr.learn_skill(
            trigger_command="backup project files",
            code=code,
            description="Backs up project files to archive directory"
        )
        self.assertIsNotNone(learned)
        self.assertEqual(learned["id"], "backup_project_files")
        self.assertEqual(learned["code"], code)

        # Recall the newly learned skill
        recalled = self.mgr.find_matching_skill("backup project files")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled["id"], "backup_project_files")

    def test_record_execution_increments_count(self):
        match = self.mgr.find_matching_skill("organize downloads")
        initial_count = match.get("success_count", 0)
        self.mgr.record_execution("organize_downloads", success=True)
        updated = self.mgr.skills["organize_downloads"]
        self.assertEqual(updated["success_count"], initial_count + 1)

    def test_record_execution_updates_refined_code(self):
        new_code = "print('refined self-healed code')\n"
        self.mgr.record_execution("organize_downloads", success=True, refined_code=new_code)
        updated = self.mgr.skills["organize_downloads"]
        self.assertEqual(updated["code"], new_code)

    def test_delete_skill(self):
        self.mgr.learn_skill(
            trigger_command="temporary task test",
            code="print('temp')\n",
            description="Temporary"
        )
        self.assertIn("temporary_task_test", self.mgr.skills)
        deleted = self.mgr.delete_skill("temporary_task_test")
        self.assertTrue(deleted)
        self.assertNotIn("temporary_task_test", self.mgr.skills)


if __name__ == "__main__":
    unittest.main()


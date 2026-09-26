import os
import sys
import unittest
import tempfile
import shutil

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from computer_use.system_tools import (
    create_folder,
    create_file,
    rename_item,
    delete_file,
    move_item,
    open_settings,
    open_web_or_search,
    SETTINGS_PAGES,
)
from actions.fast_lane import fast_lane_router
from plugins.manager import plugin_manager


class TestInbuiltAutomation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="privacy68_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_settings_pages_catalog(self):
        """Verifies settings pages dictionary has canonical entries."""
        self.assertIn("bluetooth", SETTINGS_PAGES)
        self.assertIn("wifi", SETTINGS_PAGES)
        self.assertIn("sound", SETTINGS_PAGES)
        self.assertIn("display", SETTINGS_PAGES)
        self.assertIn("network", SETTINGS_PAGES)
        self.assertIn("windows update", SETTINGS_PAGES)

    def test_file_and_folder_operations(self):
        """Verifies create, rename, and delete operations."""
        # 1. Create folder
        folder_res = create_folder(path=self.test_dir, name="test_folder")
        self.assertTrue(folder_res.get("success"))
        folder_path = os.path.join(self.test_dir, "test_folder")
        self.assertTrue(os.path.isdir(folder_path))

        # 2. Create file
        file_res = create_file(path=folder_path, name="sample.txt", content="Hello Privacy68")
        self.assertTrue(file_res.get("success"))
        file_path = os.path.join(folder_path, "sample.txt")
        self.assertTrue(os.path.isfile(file_path))

        # 3. Rename file
        rename_res = rename_item(source_name_or_path="sample.txt", new_name="renamed_sample.txt", base_directory=folder_path)
        self.assertTrue(rename_res.get("success"))
        new_file_path = os.path.join(folder_path, "renamed_sample.txt")
        self.assertTrue(os.path.isfile(new_file_path))
        self.assertFalse(os.path.isfile(file_path))

        # 4. Delete file
        delete_res = delete_file(new_file_path)
        self.assertTrue(delete_res.get("success"))
        self.assertFalse(os.path.exists(new_file_path))

    def test_fast_lane_settings_routing(self):
        """Verifies fast lane correctly parses and triggers settings commands."""
        for phrase in [
            "open settings", "open bluetooth settings", "open wifi settings", "open display settings",
            "Go to system", "go to bluetooth", "go to sound tab", "switch to display",
        ]:
            res = fast_lane_router.try_execute_fast(phrase)
            self.assertIsNotNone(res, f"Failed on '{phrase}'")
            self.assertEqual(res.get("tool"), "open_settings")
            self.assertTrue(res.get("handled"))

    def test_fast_lane_rename_routing(self):
        """Verifies fast lane parses rename commands."""
        # Create a file in test_dir
        create_file(path=self.test_dir, name="old_doc.txt", content="test")
        cmd = f"rename file old_doc.txt to final_doc.txt in {self.test_dir}"
        res = fast_lane_router.try_execute_fast(cmd)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("tool"), "rename_item")
        self.assertTrue(res.get("success"))
        self.assertTrue(os.path.isfile(os.path.join(self.test_dir, "final_doc.txt")))

    def test_fast_lane_web_and_youtube_routing(self):
        """Verifies fast lane handles direct websites, search queries, and compound browsing commands."""
        # 1. Direct website
        yt_res = fast_lane_router.try_execute_fast("open youtube")
        self.assertIsNotNone(yt_res)
        self.assertEqual(yt_res.get("tool"), "open_web_or_search")
        self.assertTrue(yt_res.get("success"))
        self.assertIn("youtube.com", yt_res.get("details", {}).get("url", ""))

        gh_res = fast_lane_router.try_execute_fast("open github")
        self.assertIsNotNone(gh_res)
        self.assertEqual(gh_res.get("tool"), "open_web_or_search")
        self.assertTrue(gh_res.get("success"))
        self.assertIn("github.com", gh_res.get("details", {}).get("url", ""))

        # 2. General search query
        search_res = fast_lane_router.try_execute_fast("search machine learning algorithms on google")
        self.assertIsNotNone(search_res)
        self.assertEqual(search_res.get("tool"), "open_web_or_search")
        self.assertTrue(search_res.get("success"))
        self.assertIn("google.com/search", search_res.get("details", {}).get("url", ""))

        # 3. Compound: "open chrome and search for youtube"
        c1 = fast_lane_router.try_execute_fast("open chrome and search for youtube")
        self.assertIsNotNone(c1)
        self.assertEqual(c1.get("tool"), "open_web_or_search")
        self.assertTrue(c1.get("success"))
        self.assertIn("youtube.com", c1.get("details", {}).get("url", ""))

        # 4. Compound: "open chrome and go to reddit.com"
        c2 = fast_lane_router.try_execute_fast("open chrome and go to reddit.com")
        self.assertIsNotNone(c2)
        self.assertEqual(c2.get("tool"), "open_web_or_search")
        self.assertTrue(c2.get("success"))
        self.assertIn("reddit.com", c2.get("details", {}).get("url", ""))

        # 5. Compound: "open youtube and search for lofi beats"
        c3 = fast_lane_router.try_execute_fast("open youtube and search for lofi beats")
        self.assertIsNotNone(c3)
        self.assertEqual(c3.get("tool"), "open_web_or_search")
        self.assertTrue(c3.get("success"))
        self.assertIn("youtube.com/results?search_query=lofi+beats", c3.get("details", {}).get("url", ""))

        # 6. Compound: "play believer on youtube"
        c4 = fast_lane_router.try_execute_fast("play believer on youtube")
        self.assertIsNotNone(c4)
        self.assertEqual(c4.get("tool"), "open_web_or_search")
        self.assertTrue(c4.get("success"))
        self.assertIn("youtube.com/results?search_query=believer", c4.get("details", {}).get("url", ""))

        # 7. Scoped: "in chrome search for python tutorials"
        c5 = fast_lane_router.try_execute_fast("in chrome search for python tutorials")
        self.assertIsNotNone(c5)
        self.assertEqual(c5.get("tool"), "open_web_or_search")
        self.assertTrue(c5.get("success"))

        # 8. Direct platform web search verification
        web_res = open_web_or_search(query="quantum computing", site_target="wikipedia")
        self.assertTrue(web_res.get("success"))
        self.assertIn("wikipedia.org", web_res.get("url", ""))

    def test_fast_lane_system_controls(self):
        """Verifies fast lane matches system control keywords."""
        for cmd in ["volume up", "volume down", "mute volume"]:
            res = fast_lane_router.try_execute_fast(cmd)
            self.assertIsNotNone(res)
            self.assertEqual(res.get("tool"), "system_action")
            self.assertTrue(res.get("success"))

    def test_plugin_system_integration(self):
        """Verifies plugin system loads plugins cleanly without interfering with core."""
        plugins = plugin_manager.get_all_plugins()
        self.assertGreater(len(plugins), 0)
        plugin_ids = [p.id for p in plugins]
        self.assertIn("chrome", plugin_ids)
        self.assertIn("windows", plugin_ids)


if __name__ == "__main__":
    unittest.main()

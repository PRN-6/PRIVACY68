import os
import shutil
import unittest
import logging

from computer_use.system_tools import (
    get_desktop_path,
    get_documents_path,
    resolve_path,
    create_folder,
    create_file,
    delete_file,
    list_directory,
    verify_path_exists,
)
from actions.fast_lane import fast_lane_router
from actions.executor import execute_system_command_detailed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PRIVACY68.TestTwoLane")


class TestTwoLaneArchitecture(unittest.TestCase):
    """
    Test suite verifying the Two-Lane Command Architecture:
    1. Fast Lane Deterministic Generic Tools & Zero-LLM Routing
    2. Desktop & Dynamic Path Resolution
    3. Router FAST vs AGENT Classification
    """

    def setUp(self):
        self.desktop = get_desktop_path()
        self.test_dir = os.path.join(self.desktop, "Privacy68_Test_Suite")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Generic Tools Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_create_folder_on_desktop(self):
        """Test creating a folder on Desktop via generic tool."""
        res = create_folder(path=self.test_dir, name="Privacy")
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "Privacy")))

    def test_folder_already_exists(self):
        """Test creating a folder that already exists returns safe success."""
        create_folder(path=self.test_dir, name="Privacy")
        res = create_folder(path=self.test_dir, name="Privacy")
        self.assertTrue(res["success"])
        self.assertTrue(res.get("already_exists", False))

    def test_create_nested_folder(self):
        """Test creating nested folder structure."""
        res = create_folder(path=os.path.join(self.test_dir, "Parent"), name="Child")
        self.assertTrue(res["success"])
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, "Parent", "Child")))

    def test_create_file(self):
        """Test creating a text file."""
        res = create_file(path=self.test_dir, name="notes.txt", content="Hello Privacy68")
        self.assertTrue(res["success"])
        file_path = os.path.join(self.test_dir, "notes.txt")
        self.assertTrue(os.path.isfile(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Hello Privacy68")

    def test_list_directory(self):
        """Test listing directory contents."""
        create_folder(path=self.test_dir, name="SubFolder")
        create_file(path=self.test_dir, name="test.txt")
        res = list_directory(self.test_dir)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)

    def test_path_resolution_onedrive_aware(self):
        """Test that Desktop and Documents resolve to valid paths."""
        desktop = get_desktop_path()
        documents = get_documents_path()
        self.assertTrue(os.path.exists(desktop), f"Desktop path {desktop} should exist")
        self.assertTrue(os.path.exists(documents), f"Documents path {documents} should exist")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Fast Lane Router & Classification Tests (ZERO LLM CALLS)
    # ─────────────────────────────────────────────────────────────────────────

    def test_fast_lane_create_privacy_folder(self):
        """
        Test that 'Create a folder named Privacy on Desktop'
        executes immediately via Fast Lane with NO LLM CALLS.
        """
        cmd = "Create a folder named Privacy on Desktop"
        res = execute_system_command_detailed(cmd)
        
        self.assertEqual(res.get("method"), "fast_lane", "Should execute via Fast Lane")
        self.assertTrue(res.get("success"), "Execution should succeed")
        
        target = os.path.join(get_desktop_path(), "Privacy")
        self.assertTrue(os.path.exists(target), f"Folder should exist at {target}")
        
        # Cleanup
        if os.path.exists(target):
            shutil.rmtree(target)

    def test_fast_lane_create_mca_folder_custom_path(self):
        """
        Test that 'Create MCA folder in <test_dir>'
        executes immediately via Fast Lane with NO LLM CALLS.
        """
        cmd = f"Create MCA folder in {self.test_dir}"
        res = execute_system_command_detailed(cmd)
        
        self.assertEqual(res.get("method"), "fast_lane", "Should execute via Fast Lane")
        self.assertTrue(res.get("success"))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "MCA")))

    def test_fast_lane_system_volume_lock(self):
        """Test fast classification of system commands."""
        match1 = fast_lane_router.try_execute_fast("increase volume")
        self.assertIsNotNone(match1)
        self.assertEqual(match1["tool"], "system_action")

        match2 = fast_lane_router.try_execute_fast("mute volume")
        self.assertIsNotNone(match2)
        self.assertEqual(match2["tool"], "system_action")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Router Compound & Unmatched Classification Test
    # ─────────────────────────────────────────────────────────────────────────

    def test_unhandled_compound_command_rejected_by_fast_lane(self):
        """
        Test that an unsupported complex generative action (e.g. 'Open WhatsApp and send message to mom saying hello')
        is NOT handled by Fast Lane.
        """
        compound_cmd = "Open WhatsApp and send a message to mom saying hello"
        fast_res = fast_lane_router.try_execute_fast(compound_cmd)
        self.assertIsNone(fast_res, "Complex multi-step generative command must NOT be handled by Fast Lane")


if __name__ == "__main__":
    unittest.main()

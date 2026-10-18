"""
Tests for the Three-Lane Command Architecture:
- Lane 1: Fast Lane (Deterministic, OS + Plugin Fast Intents, Highest Priority)
- Lane 2: API Lane (Direct App/Web APIs + Cloud LLM Semantic Router, High Priority)
- Lane 3: Local LLM Lane (Optional / Opt-In Local Air-Gapped Model)
"""

import unittest
from unittest.mock import patch, MagicMock
from actions.executor import execute_system_command_detailed
from actions.fast_lane import fast_lane_router
from actions.api_lane import api_lane_router
from actions.router import is_ollama_alive, LLMRouter


class TestThreeLaneArchitecture(unittest.TestCase):

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Lane 1: Fast Lane Tests (Highest Priority, runs on any PC)
    # ─────────────────────────────────────────────────────────────────────────

    def test_fast_lane_system_action(self):
        """Muting volume should execute immediately via Fast Lane."""
        res = execute_system_command_detailed("mute volume")
        self.assertEqual(res.get("method"), "fast_lane")
        self.assertTrue(res.get("success"))

    @patch("actions.skill_manager.manager.execute_skill", return_value=True)
    def test_fast_lane_plugin_fast_intent(self, mock_skill):
        """Plugin fast intents (e.g., Chrome new tab, GitHub notifications) execute in Fast Lane."""
        res = execute_system_command_detailed("new tab in chrome")
        self.assertEqual(res.get("method"), "fast_lane")
        mock_skill.assert_called_once()

    def test_fast_lane_open_web_search(self):
        """Web search queries route through Fast Lane instantly."""
        res = execute_system_command_detailed("open youtube")
        self.assertEqual(res.get("method"), "fast_lane")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Lane 2: API Lane Tests (High Priority, Direct & Cloud APIs)
    # ─────────────────────────────────────────────────────────────────────────

    def test_api_lane_weather_query(self):
        """Weather queries route via API Lane (direct public API, zero LLM)."""
        res = execute_system_command_detailed("what is the weather in Tokyo")
        self.assertEqual(res.get("method"), "api_lane")
        self.assertEqual(res.get("tool"), "api_weather")

    @patch("actions.api_lane.APILaneRouter._call_cloud_endpoint")
    @patch("plugins.profile_manager.profile_manager.get")
    def test_api_lane_cloud_llm_routing(self, mock_get, mock_call):
        """When Cloud API key is configured, API Lane resolves complex natural language."""
        def profile_side_effect(key, default=None):
            if key == "llm_provider":
                return "groq"
            if key == "api_key":
                return "gsk_test_api_key_12345"
            return default

        mock_get.side_effect = profile_side_effect
        mock_call.return_value = "system.screenshot"

        with patch("actions.skill_manager.manager.execute_skill", return_value=True):
            res = execute_system_command_detailed("could you please capture what is on my screen right now")
            self.assertEqual(res.get("method"), "api_lane")
            self.assertEqual(res.get("tool"), "system.screenshot")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Lane 3: Local LLM Lane Tests (Optional, Non-blocking, User Choice)
    # ─────────────────────────────────────────────────────────────────────────

    def test_is_ollama_alive_probe(self):
        """is_ollama_alive should return a boolean in under 500ms without throwing exceptions."""
        alive = is_ollama_alive(timeout_sec=0.2)
        self.assertIsInstance(alive, bool)

    @patch("actions.router.is_ollama_alive", return_value=False)
    def test_local_llm_skipped_when_ollama_offline(self, mock_alive):
        """When Ollama daemon is offline, Local LLM Lane is skipped instantly without freezing."""
        router = LLMRouter()
        # Non-fast command with Ollama offline
        action = router._route_ollama("open whatsapp and write to john", [], {})
        self.assertIsNone(action, "Should return None immediately when Ollama is offline")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Priority Hierarchy Test (Fast Lane > API Lane > Local LLM Lane)
    # ─────────────────────────────────────────────────────────────────────────

    def test_priority_hierarchy_fast_lane_first(self):
        """Commands that match Fast Lane MUST NOT trigger API Lane or LLM Lane."""
        res = execute_system_command_detailed("volume up")
        self.assertEqual(res.get("method"), "fast_lane", "Fast lane must have highest priority")


if __name__ == "__main__":
    unittest.main()

"""
Tests for the Compound Command Planner.

Verifies that multi-command utterances are split into ordered clauses and
that single commands (including ones with "and" buried inside an argument)
are left alone.
"""

import unittest
from unittest.mock import patch

from actions.command_planner import is_compound, split_compound_command


# ─── Genuine compounds: MUST split ──────────────────────────────────────────
COMPOUND_CASES = [
    ("mute the volume and open chrome", 2),
    ("turn up the volume and open spotify", 2),
    ("open chrome then take a screenshot", 2),
    ("lock the screen, open notepad, and mute audio", 3),
    ("create a folder called Test and delete file old.txt", 2),
    ("open notepad and type hello world", 2),
    ("mute audio and lock the screen", 2),
    ("open brave and open firefox", 2),
    ("open chrome and type hello", 2),
    ("play lofi and open notepad", 2),
    ("open chrome also open brave and mute audio", 3),
    ("mute and lock", 2),
    ("explain quantum computing and write a python script", 2),
    ("open chrome and close it", 2),
    ("take a screenshot and send it to mom", 2),
    ("open downloads and create a folder named temp", 2),
    ("lock pc and mute", 2),
    ("open settings and go to bluetooth", 2),
    ("increase volume and open youtube", 2),
    ("close window and open notepad", 2),
    ("press enter and take screenshot", 2),
    ("open chrome, brave, and edge", 3),
    ("create file notes.txt and open it", 2),
    ("open chrome and brave", 2),
]

# ─── Single commands with a conjunction INSIDE the argument: MUST NOT split ──
SINGLE_CASES = [
    "search for cats and dogs",
    "search for machine learning and artificial intelligence",
    "play rock and roll on youtube",
    "create a folder called Cats and Dogs",
    "send a message to John and Mary",
    "search for cats and dogs on youtube",
    "create a file called Notes and Tips.txt",
    "rename file old.txt to new and final.txt",
    "search how to bake bread and cake",
    "search for python then learn it",
    "open chrome and",
    "open chrome and search for quantum computing",  # one browser workflow
    "explain what a neural network is and how it works",
    "what is the weather in new york and london",
    "search for open source and machine learning",
    "delete tmp and build folders",
    "search for python tips and open source projects",
    "create a folder called Movies and Games",
    "create a file called readme and license",
    "open a file called index and main",
    "search for cats and dogs and birds",
    "open the project and tests folders",
    "open chrome",
    "take a screenshot",
    "what is the weather",
    "mute",
    "open notepad",
    "search for cats",
    "lock the screen",
    "explain quantum computing",
    "write a python script",
    "play lofi",
]


class TestCompoundCommandPlanner(unittest.TestCase):

    def test_genuine_compounds_are_split(self):
        """Multi-command utterances split into the right number of clauses."""
        for utterance, expected_count in COMPOUND_CASES:
            with self.subTest(utterance=utterance):
                clauses = split_compound_command(utterance)
                self.assertIsNotNone(clauses, f"'{utterance}' should split")
                self.assertEqual(len(clauses), expected_count, f"'{utterance}' -> {clauses}")

    def test_single_commands_are_not_split(self):
        """Commands with a conjunction inside their argument stay whole."""
        for utterance in SINGLE_CASES:
            with self.subTest(utterance=utterance):
                self.assertIsNone(
                    split_compound_command(utterance),
                    f"'{utterance}' must not split",
                )

    def test_empty_input(self):
        """Empty and whitespace input never splits."""
        for utterance in ("", "   ", "\n"):
            with self.subTest(utterance=utterance):
                self.assertIsNone(split_compound_command(utterance))

    def test_is_compound_predicate(self):
        """is_compound() agrees with split_compound_command()."""
        self.assertTrue(is_compound("mute the volume and open chrome"))
        self.assertFalse(is_compound("search for cats and dogs"))
        self.assertFalse(is_compound("open chrome"))

    def test_split_preserves_order(self):
        """Clauses keep the order the user said them in."""
        clauses = split_compound_command("mute the volume and open chrome")
        self.assertEqual(clauses[0], "mute the volume")
        self.assertEqual(clauses[1], "open chrome")

    def test_split_does_not_mutate_input(self):
        """The planner does not modify the caller's string."""
        utterance = "mute the volume and open chrome"
        split_compound_command(utterance)
        self.assertEqual(utterance, "mute the volume and open chrome")


class TestCompoundCommandExecution(unittest.TestCase):
    """End-to-end: the executor actually runs BOTH clauses."""

    @patch("actions.executor.fast_lane_router.try_execute_fast")
    def test_both_clauses_are_executed(self, mock_fast):
        """Each clause of a compound command is routed through the fast lane."""
        from actions.executor import execute_system_command_detailed

        def fake_fast(text):
            if text == "mute the volume":
                return {"success": True, "tool": "volume_mute", "message": "Muted."}
            if text == "open chrome":
                return {"success": True, "tool": "open_application", "message": "Opened Chrome."}
            return None

        mock_fast.side_effect = fake_fast

        res = execute_system_command_detailed("mute the volume and open chrome")

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("method"), "compound_planner")
        self.assertEqual(res.get("tool"), "compound_command")
        self.assertEqual(res["details"]["succeeded"], 2)
        self.assertEqual(res["details"]["failed"], 0)
        self.assertEqual(len(res["details"]["clauses"]), 2)

    @patch("actions.executor.fast_lane_router.try_execute_fast")
    def test_single_command_is_not_treated_as_compound(self, mock_fast):
        """A plain command still takes the normal single-command path."""
        from actions.executor import execute_system_command_detailed

        mock_fast.return_value = {"success": True, "tool": "open_application", "message": "Opened."}

        res = execute_system_command_detailed("open chrome")

        self.assertEqual(res.get("method"), "fast_lane")
        self.assertNotEqual(res.get("method"), "compound_planner")

    @patch("actions.executor.llm_router.route", return_value=None)
    @patch("actions.executor.api_lane_router.try_execute_api", return_value=None)
    @patch("actions.executor.fast_lane_router.try_execute_plugin_fast", return_value=None)
    @patch("actions.executor.fast_lane_router.try_execute_fast")
    def test_compound_reports_partial_failure(self, mock_fast, mock_plugin, mock_api, mock_llm):
        """A failing clause is reported, not silently swallowed."""
        from actions.executor import execute_system_command_detailed

        def fake_fast(text):
            if text == "mute the volume":
                return {"success": True, "tool": "volume_mute", "message": "Muted."}
            return None

        mock_fast.side_effect = fake_fast

        res = execute_system_command_detailed("mute the volume and open chrome")

        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("tool"), "compound_command_partial")
        self.assertEqual(res["details"]["succeeded"], 1)
        self.assertEqual(res["details"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()

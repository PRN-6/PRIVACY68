import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from actions.agent_brain import AgentBrain


class TestAgentBrain(unittest.TestCase):
    def setUp(self):
        self.brain = AgentBrain()

    @patch("actions.agent_brain.litellm.completion")
    def test_get_code_from_llm_removes_python_fence(self, completion):
        completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="```python\nprint('ok')\n```"))]
        )

        self.assertEqual(self.brain._get_code_from_llm("say hello"), "print('ok')")
        completion.assert_called_once()

    @patch("actions.agent_brain.subprocess.run")
    def test_generate_and_execute_returns_success_and_stdout(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "print('ok')"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )
        with patch.object(self.brain, "_get_code_from_llm", return_value="print('ok')"):
            result = self.brain.generate_and_execute("say hello")

        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "ok\n")
        self.assertEqual(result["method"], "agentic_engine")
        self.assertEqual(self.brain.last_code, "print('ok')")
        run.assert_called_once()

    @patch("actions.agent_brain.subprocess.run")
    def test_generate_and_execute_reports_execution_error(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "raise RuntimeError('bad')"],
            returncode=1,
            stdout="",
            stderr="RuntimeError: bad",
        )
        with patch.object(self.brain, "_get_code_from_llm", return_value="raise RuntimeError('bad')"):
            result = self.brain.generate_and_execute("do something")

        self.assertFalse(result["success"])
        self.assertIn("RuntimeError: bad", result["message"])

    @patch("actions.agent_brain.subprocess.run")
    def test_empty_generated_code_is_not_executed(self, run):
        with patch.object(self.brain, "_get_code_from_llm", return_value=""):
            result = self.brain.generate_and_execute("do something")

        self.assertFalse(result["success"])
        self.assertEqual(result["method"], "agentic_brain")
        run.assert_not_called()

    def test_generation_exception_is_returned_as_failure(self):
        self.brain.last_code = "stale prior code"
        with patch.object(self.brain, "_get_code_from_llm", side_effect=RuntimeError("LLM unavailable")):
            result = self.brain.generate_and_execute("do something")

        self.assertFalse(result["success"])
        self.assertIn("LLM unavailable", result["message"])
        self.assertEqual(self.brain.last_code, "")
        self.assertEqual(self.brain.last_reasoning, "Analyzing request: do something")


if __name__ == "__main__":
    unittest.main()

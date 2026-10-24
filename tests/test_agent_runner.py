import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from actions.agent_runner import execute_agent_script, run_agent_code


class TestAgentRunner(unittest.TestCase):
    def test_source_run_uses_python_subprocess(self):
        with patch("actions.agent_runner.subprocess.run") as run:
            expected = subprocess.CompletedProcess(["python", "-c"], 0, "ok\n", "")
            run.return_value = expected

            result = run_agent_code("print('ok')")

        self.assertIs(result, expected)
        self.assertEqual(run.call_args.args[0][-2:], ["-c", "print('ok')"])
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertTrue(run.call_args.kwargs["text"])

    def test_frozen_run_uses_internal_executable_runner(self):
        def run_child(command, **kwargs):
            self.assertEqual(command[1], "--run-agent-script")
            self.assertTrue(os.path.isfile(command[2]))
            self.assertEqual(
                execute_agent_script(command[2], command[3]),
                0,
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("actions.agent_runner.sys.frozen", True, create=True):
            with patch("actions.agent_runner.subprocess.run", side_effect=run_child):
                result = run_agent_code("print('frozen output')")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "frozen output\n")
        self.assertEqual(result.stderr, "")

    def test_internal_runner_captures_script_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "agent_script.py")
            result_path = os.path.join(temp_dir, "result.json")
            with open(script_path, "w", encoding="utf-8") as script:
                script.write("print('before failure')\nraise RuntimeError('broken')")

            returncode = execute_agent_script(script_path, result_path)

            with open(result_path, encoding="utf-8") as result_file:
                result = json.load(result_file)

        self.assertEqual(returncode, 1)
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["stdout"], "before failure\n")
        self.assertIn("RuntimeError: broken", result["stderr"])


if __name__ == "__main__":
    unittest.main()

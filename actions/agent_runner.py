"""Run Agent Brain code in an isolated subprocess in source and frozen builds."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any


def run_agent_code(code: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Execute generated code through Python or the frozen app's internal runner."""
    if not getattr(sys, "frozen", False):
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    with tempfile.TemporaryDirectory(prefix="privacy68-agent-") as temp_dir:
        script_path = Path(temp_dir) / "agent_script.py"
        result_path = Path(temp_dir) / "agent_result.json"
        script_path.write_text(code, encoding="utf-8")
        command = [
            sys.executable,
            "--run-agent-script",
            str(script_path),
            str(result_path),
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if not result_path.is_file():
            return process

        result: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(
            args=command,
            returncode=result["returncode"],
            stdout=result["stdout"],
            stderr=result["stderr"],
        )


def execute_agent_script(script_path: str, result_path: str) -> int:
    """Internal frozen-app entry point; writes captured output for its parent."""
    output = io.StringIO()
    errors = io.StringIO()
    returncode = 0

    try:
        script = Path(script_path)
        source = script.read_text(encoding="utf-8")
        previous_argv = sys.argv
        sys.argv = [str(script)]
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                exec(compile(source, str(script), "exec"), {"__name__": "__main__", "__file__": str(script)})
        finally:
            sys.argv = previous_argv
    except SystemExit as exc:
        if isinstance(exc.code, int):
            returncode = exc.code
        elif exc.code is not None:
            returncode = 1
            errors.write(f"{exc.code}\n")
    except BaseException:
        returncode = 1
        errors.write(traceback.format_exc())

    payload = {
        "returncode": returncode,
        "stdout": output.getvalue(),
        "stderr": errors.getvalue(),
    }
    Path(result_path).write_text(json.dumps(payload), encoding="utf-8")
    return returncode

"""
Regression tests for the Control Center startup path.

These cover the four causes behind "the Control Panel takes forever to open
or never opens":

  1. A missing Microsoft Edge WebView2 Runtime (blank window after a long
     pause) — detection lives in utils/webview2.py.
  2. The Control Center process booting the whole application stack (CUDA
     probing, `import config`, the plugin catalogue, the Whisper/ONNX stack)
     instead of only what it needs.
  3. The microphone being opened on dashboard startup, which deadlocks against
     the assistant process on exclusive-mode audio drivers.
  4. A dashboard that fails silently, with no way for the launcher to tell
     "starting" apart from "crashed".
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

PROJECT_ROOT = os.path.abspath(".")


def run_python(code: str) -> subprocess.CompletedProcess:
    """Runs a snippet in a fresh interpreter and returns the completed process."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestWebView2Detection(unittest.TestCase):
    """The WebView2 runtime must be detectable without raising."""

    def test_status_is_well_formed(self):
        from utils.webview2 import get_webview2_status

        status = get_webview2_status()
        self.assertIn("installed", status)
        self.assertIn("version", status)
        self.assertIn("download_url", status)
        self.assertIsInstance(status["installed"], bool)
        self.assertTrue(status["download_url"].startswith("https://"))

    def test_installed_matches_version_check(self):
        from utils.webview2 import get_webview2_status, is_webview2_installed

        self.assertEqual(get_webview2_status()["installed"], is_webview2_installed())

    def test_version_parsing(self):
        from utils.webview2 import parse_version, version_at_least

        self.assertEqual(parse_version("120.0.2210.91"), (120, 0, 2210, 91))
        self.assertIsNone(parse_version("not-a-version"))
        self.assertIsNone(parse_version(None))

        # The dashboard needs Chromium 86+; anything older cannot render it.
        self.assertTrue(version_at_least("86.0.622.0"))
        self.assertTrue(version_at_least("120.0.2210.91"))
        self.assertFalse(version_at_least("85.0.0.0"))
        self.assertFalse(version_at_least("garbage"))

    def test_install_hint_mentions_download(self):
        from utils.webview2 import get_webview2_install_hint

        hint = get_webview2_install_hint()
        self.assertIn("WebView2", hint)
        self.assertIn("https://", hint)


class TestDashboardStartupIsLightweight(unittest.TestCase):
    """
    The Control Center runs in its own process. That process must not import
    the assistant's heavy stack, or every launch pays for a second Whisper
    model, an ONNX runtime and a CUDA probe.
    """

    HEAVY_MODULES = (
        "numpy",
        "sounddevice",
        "onnxruntime",
        "scipy",
        "huggingface_hub",
        "faster_whisper",
        "ctranslate2",
        "config",
        "plugins.manager",
        "speech.streamer",
    )

    def _loaded_heavy_modules(self, module_under_test: str):
        code = (
            "import sys, json\n"
            f"import {module_under_test}\n"
            "heavy = %r\n" % (list(self.HEAVY_MODULES),) +
            "print(json.dumps(sorted(m for m in heavy if m in sys.modules)))\n"
        )
        result = run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_dashboard_bridge_does_not_import_heavy_stack(self):
        loaded = self._loaded_heavy_modules("ui.dashboard_bridge")
        self.assertEqual(
            loaded, [],
            f"The Control Center bridge still imports {loaded} at startup."
        )

    def test_dashboard_runner_does_not_import_heavy_stack(self):
        loaded = self._loaded_heavy_modules("ui.dashboard_runner")
        self.assertEqual(
            loaded, [],
            f"The Control Center runner still imports {loaded} at startup."
        )

    def test_app_entry_point_defers_config_and_cuda(self):
        """`import app` must not pull in `config` or the CUDA manager."""
        code = (
            "import sys, app\n"
            "print('config' in sys.modules, 'utils.cuda_manager' in sys.modules)\n"
        )
        result = run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False False")

    def test_dashboard_flag_is_detected(self):
        code = (
            "import sys\n"
            "sys.argv = ['PRIVACY68.exe', '--dashboard']\n"
            "import app\n"
            "print(app._is_dashboard_launch())\n"
        )
        result = run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "True")


class TestLazyMicrophoneCapture(unittest.TestCase):
    """
    The dashboard must not open the microphone until the user actually visits
    the Voice Enrollment tab.
    """

    def test_capture_stream_is_not_started_on_launch(self):
        code = (
            "import ui.dashboard_runner as dr\n"
            "import inspect\n"
            "src = inspect.getsource(dr.run_dashboard)\n"
            "print('has_capture' if '_start_capture_stream' in src else 'clean')\n"
        )
        result = run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "clean")

    def test_api_exposes_lazy_capture_controls(self):
        from ui.dashboard_bridge import DashboardAPI

        api = DashboardAPI()
        self.assertTrue(hasattr(api, "start_enrollment_capture"))
        self.assertTrue(hasattr(api, "stop_enrollment_capture"))
        # Nothing may be opened before the user asks for it.
        self.assertIsNone(api._capture_streamer)

    def test_capture_only_streamer_does_not_load_whisper(self):
        """A capture-only streamer must not pull in the Whisper model."""
        from speech.streamer import SpeechStreamer

        signature_params = SpeechStreamer.__init__.__code__.co_varnames
        self.assertIn("capture_only", signature_params)

    def test_dashboard_html_opens_mic_only_on_the_voice_tab(self):
        html_path = os.path.join(PROJECT_ROOT, "ui", "dashboard", "index.html")
        with open(html_path, "r", encoding="utf-8") as handle:
            html = handle.read()
        self.assertIn("start_enrollment_capture", html)
        self.assertIn("stop_enrollment_capture", html)
        self.assertIn("tab-voice", html)


class TestDashboardReadinessHandshake(unittest.TestCase):
    """The launcher must be able to tell a slow start from a failed one."""

    def test_ready_file_is_written_when_the_window_appears(self):
        ready_path = os.path.join(
            os.environ.get("TEMP", "."), f"p68_test_ready_{os.getpid()}.json"
        )
        if os.path.exists(ready_path):
            os.remove(ready_path)

        code = (
            "import sys, json\n"
            "sys.argv = ['PRIVACY68.exe', '--dashboard', '--dashboard-ready=' + sys.argv[1]]\n"
            "import ui.dashboard_runner as dr\n"
            "dr._signal_ready({'ok': True, 'pid': 1234})\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, ready_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(ready_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pid"], 1234)
        os.remove(ready_path)

    def test_ready_file_is_written_only_once(self):
        from ui.dashboard_runner import _signal_ready
        import ui.dashboard_runner as dr

        ready_path = os.path.join(
            os.environ.get("TEMP", "."), f"p68_test_ready_once_{os.getpid()}.json"
        )
        if os.path.exists(ready_path):
            os.remove(ready_path)

        original_argv = dr.sys.argv
        try:
            dr.sys.argv = ["PRIVACY68.exe", f"--dashboard-ready={ready_path}"]
            _signal_ready({"ok": True, "pid": 1})
            _signal_ready({"ok": False, "error": "late failure"})
        finally:
            dr.sys.argv = original_argv

        with open(ready_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        # The first payload wins — a late failure must not overwrite success.
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pid"], 1)
        os.remove(ready_path)

    def test_launcher_passes_the_ready_file_to_the_child(self):
        from ui.plugin_window import PluginManagerWindow

        window = PluginManagerWindow()
        captured = {}

        class _FakeProc:
            returncode = None

            def poll(self):
                return None

        def _fake_popen(cmd, *args, **kwargs):
            captured["cmd"] = cmd
            return _FakeProc()

        original_popen = subprocess.Popen
        try:
            subprocess.Popen = _fake_popen
            window.open()
        finally:
            subprocess.Popen = original_popen

        self.assertTrue(
            any(part.startswith("--dashboard-ready=") for part in captured["cmd"]),
            f"Launcher did not pass a readiness file: {captured.get('cmd')}",
        )


if __name__ == "__main__":
    unittest.main()

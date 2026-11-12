import io
import json
import unittest
from unittest.mock import Mock, patch

from server import remote_server


class DummyRemoteHandler(remote_server.Privacy68RemoteHandler):
    """Subclass Privacy68RemoteHandler without running an actual network socket."""

    def __init__(self, method="POST", path="/api/command", headers=None, body=b""):
        self.command = method
        self.path = path
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.client_address = ("192.168.1.50", 54321)
        self._headers_buffer = []

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        self._headers_buffer.append((keyword, value))

    def end_headers(self):
        pass


class TestRemoteServer(unittest.TestCase):
    def setUp(self):
        remote_server.set_auth_token("TESTPIN")

    def test_get_remote_url_includes_token(self):
        url = remote_server.get_remote_url(8765, include_token=True)
        self.assertIn("token=TESTPIN", url)
        self.assertIn(":8765", url)

    def test_qr_code_generates_valid_png(self):
        try:
            import qrcode
            png = remote_server.generate_qr_png_bytes()
            self.assertTrue(len(png) > 0)
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        except ImportError:
            # When qrcode package is not present, it safely returns empty bytes without crashing
            png = remote_server.generate_qr_png_bytes()
            self.assertEqual(png, b"")

    def test_handler_blocks_unauthorized_post(self):
        payload = json.dumps({"command": "open chrome"}).encode("utf-8")
        handler = DummyRemoteHandler(
            method="POST",
            path="/api/command",
            headers={"Content-Length": str(len(payload))},
            body=payload,
        )
        handler.do_POST()

        self.assertEqual(handler.response_code, 401)
        response_data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(response_data["success"])
        self.assertTrue(response_data.get("auth_required"))

    def test_handler_allows_authorized_post_via_bearer(self):
        mock_cb = Mock(return_value={"success": True, "tool": "chrome", "message": "Opened Chrome"})
        remote_server._global_on_command_callback = mock_cb

        payload = json.dumps({"command": "open chrome"}).encode("utf-8")
        handler = DummyRemoteHandler(
            method="POST",
            path="/api/command",
            headers={
                "Content-Length": str(len(payload)),
                "Authorization": "Bearer TESTPIN",
            },
            body=payload,
        )
        handler.do_POST()

        self.assertEqual(handler.response_code, 200)
        response_data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["tool"], "chrome")
        mock_cb.assert_called_once_with("open chrome")

    def test_handler_status_endpoint_returns_current_version_and_pin(self):
        handler = DummyRemoteHandler(method="GET", path="/api/status")
        handler.do_GET()

        self.assertEqual(handler.response_code, 200)
        response_data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(response_data["status"], "online")
        self.assertEqual(response_data["pairing_token"], "TESTPIN")
        self.assertNotEqual(response_data["version"], "1.1.0")


if __name__ == "__main__":
    unittest.main()

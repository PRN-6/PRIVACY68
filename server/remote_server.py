import os
import sys
import json
import socket
import logging
import threading
import mimetypes
import io
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

logger = logging.getLogger("PRIVACY68.RemoteServer")

IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR = sys._MEIPASS if IS_FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "server", "static")

# Threaded HTTP Server
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def get_local_ip() -> str:
    """Discovers the primary LAN IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually send packets, just resolves local outbound interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def get_remote_url(port: int = 8765) -> str:
    """Returns the full accessible URL for the mobile web client."""
    ip = get_local_ip()
    return f"http://{ip}:{port}"


def generate_qr_png_bytes(url: str) -> bytes:
    """Generates PNG bytes for the connection QR code."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#06B6D4", back_color="#0D1117")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        logger.warning(f"Could not generate QR code PNG: {e}")
        return b""


_global_on_command_callback = None
_global_server_port = 8765

class Privacy68RemoteHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving the Mobile Remote Web App and REST API endpoints.
    """
    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed_path = self.path.split("?")[0]

        # 1. API: Server & PC Status
        if parsed_path == "/api/status":
            local_ip = get_local_ip()
            self._send_json({
                "status": "online",
                "app": "PRIVACY68",
                "version": "1.0.0",
                "pc_name": socket.gethostname(),
                "local_ip": local_ip,
                "port": _global_server_port,
                "remote_url": f"http://{local_ip}:{_global_server_port}"
            })
            return

        # 2. API: QR Code
        if parsed_path == "/api/qr":
            url = get_remote_url(_global_server_port)
            qr_bytes = generate_qr_png_bytes(url)
            if qr_bytes:
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(qr_bytes)))
                self.send_header("Cache-Control", "no-cache")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(qr_bytes)
            else:
                self._send_json({"error": "Failed to generate QR code"}, 500)
            return

        # 3. API: Quick Action Presets
        if parsed_path == "/api/quick-actions":
            actions = [
                {"id": "chrome", "label": "Open Chrome", "icon": "🌐", "command": "open chrome", "category": "Apps"},
                {"id": "brave", "label": "Open Brave", "icon": "🦁", "command": "open brave", "category": "Apps"},
                {"id": "whatsapp", "label": "WhatsApp", "icon": "💬", "command": "open whatsapp", "category": "Apps"},
                {"id": "youtube", "label": "YouTube", "icon": "▶️", "command": "open youtube", "category": "Media"},
                {"id": "playpause", "label": "Play / Pause", "icon": "⏯️", "command": "play music", "category": "Media"},
                {"id": "nexttrack", "label": "Next Track", "icon": "⏭️", "command": "next track", "category": "Media"},
                {"id": "volup", "label": "Volume Up", "icon": "🔊", "command": "volume up", "category": "Media"},
                {"id": "voldown", "label": "Volume Down", "icon": "🔉", "command": "volume down", "category": "Media"},
                {"id": "mute", "label": "Mute / Unmute", "icon": "🔇", "command": "mute volume", "category": "Media"},
                {"id": "screenshot", "label": "Screenshot", "icon": "📸", "command": "take screenshot", "category": "System"},
                {"id": "lock", "label": "Lock PC", "icon": "🔒", "command": "lock screen", "category": "System"},
                {"id": "newtab", "label": "New Tab", "icon": "➕", "command": "new tab", "category": "Browser"},
                {"id": "closetab", "label": "Close Tab", "icon": "❌", "command": "close tab", "category": "Browser"},
            ]
            self._send_json({"actions": actions})
            return

        # 4. Serve Static Files (Mobile Web App)
        rel_path = parsed_path.lstrip("/")
        if not rel_path or rel_path == "remote":
            rel_path = "index.html"

        file_path = os.path.join(STATIC_DIR, rel_path)
        # Security: prevent directory traversal
        if not os.path.abspath(file_path).startswith(os.path.abspath(STATIC_DIR)):
            self.send_error(403, "Access Denied")
            return

        if os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "application/octet-stream"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(content)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                logger.error(f"Error serving static file {file_path}: {e}")
                self.send_error(500, "Internal Server Error")
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed_path = self.path.split("?")[0]

        if parsed_path == "/api/command":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json({"success": False, "message": "No command payload"}, 400)
                return

            try:
                post_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(post_body)
                command_text = payload.get("command", "").strip()

                if not command_text:
                    self._send_json({"success": False, "message": "Empty command string"}, 400)
                    return

                logger.info(f"📱 Remote Mobile Command Received: '{command_text}'")

                if _global_on_command_callback:
                    # Execute on PC via Privacy68 Core
                    result = _global_on_command_callback(command_text)
                    if isinstance(result, dict):
                        self._send_json({
                            "success": result.get("success", False),
                            "tool": result.get("tool", "unknown"),
                            "method": result.get("method", "fast_lane"),
                            "message": result.get("message", f"Executed {command_text}"),
                            "command": command_text
                        })
                    else:
                        self._send_json({
                            "success": bool(result),
                            "tool": "executed",
                            "method": "core",
                            "message": f"Command '{command_text}' executed",
                            "command": command_text
                        })
                else:
                    self._send_json({"success": False, "message": "No executor configured on server"}, 500)

            except json.JSONDecodeError:
                self._send_json({"success": False, "message": "Invalid JSON"}, 400)
            except Exception as e:
                logger.error(f"Error handling remote command: {e}", exc_info=True)
                self._send_json({"success": False, "message": str(e)}, 500)
            return

        self.send_error(404, "Unknown API endpoint")

    def log_message(self, format, *args):
        """Redirect HTTP server logging to Privacy68's logger (debug level)."""
        logger.debug(f"{self.address_string()} - - {format % args}")


class RemoteServerManager:
    """
    Manages the lifecycle of the Privacy68 Mobile Web Remote Server.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.httpd = None
        self.server_thread = None
        self.is_running = False

    def start(self, on_command_callback) -> str:
        """
        Starts the remote HTTP server in a background daemon thread.
        Returns the accessible remote web URL.
        """
        global _global_on_command_callback, _global_server_port

        if self.is_running:
            return get_remote_url(self.port)

        _global_on_command_callback = on_command_callback
        _global_server_port = self.port


        try:
            self.httpd = ThreadedHTTPServer((self.host, self.port), Privacy68RemoteHandler)
            self.is_running = True
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()

            url = get_remote_url(self.port)
            logger.info(f"📱 PRIVACY68 Mobile Web Remote Server is active at: {url}")
            logger.info(f"📱 Connect your phone on the same Wi-Fi network and open: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to start Mobile Web Remote Server on {self.host}:{self.port}: {e}")
            self.is_running = False
            return ""

    def stop(self):
        """Stops the remote server."""
        if self.httpd and self.is_running:
            logger.info("Stopping PRIVACY68 Mobile Web Remote Server...")
            self.is_running = False
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception as e:
                logger.warning(f"Error closing remote server: {e}")


# Global instance
_server_manager = RemoteServerManager()

def start_remote_server(on_command_callback, host: str = "0.0.0.0", port: int = 8765) -> str:
    global _server_manager
    _server_manager.host = host
    _server_manager.port = port
    return _server_manager.start(on_command_callback)

def stop_remote_server():
    global _server_manager
    _server_manager.stop()

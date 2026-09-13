import sys
import os
import urllib.request
import json
import time

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.remote_server import start_remote_server, stop_remote_server
from actions.executor import execute_system_command_detailed

def test_remote_server():
    print("1. Starting Remote Server on port 8799...", flush=True)
    url = start_remote_server(on_command_callback=execute_system_command_detailed, port=8799)
    print(f"Server started at: {url}", flush=True)
    time.sleep(0.5)

    try:
        # 1. Status API
        print("2. Testing GET /api/status...", flush=True)
        with urllib.request.urlopen("http://127.0.0.1:8799/api/status") as res:
            status_data = json.loads(res.read().decode())
            print(f"-> Status response: {status_data}", flush=True)
            assert status_data["status"] == "online"
            assert "local_ip" in status_data

        # 2. Quick Actions API
        print("3. Testing GET /api/quick-actions...", flush=True)
        with urllib.request.urlopen("http://127.0.0.1:8799/api/quick-actions") as res:
            actions_data = json.loads(res.read().decode())
            print(f"-> Quick Actions loaded: {len(actions_data.get('actions', []))} presets", flush=True)
            assert len(actions_data.get("actions", [])) > 0

        # 3. Static Web App Index
        print("4. Testing GET / (Static Web App)...", flush=True)
        with urllib.request.urlopen("http://127.0.0.1:8799/") as res:
            html = res.read().decode("utf-8")
            print(f"-> HTML served length: {len(html)} bytes", flush=True)
            assert "<title>PRIVACY68 Mobile Remote</title>" in html

        # 4. QR Code API
        print("5. Testing GET /api/qr...", flush=True)
        with urllib.request.urlopen("http://127.0.0.1:8799/api/qr") as res:
            qr_bytes = res.read()
            print(f"-> QR code image bytes: {len(qr_bytes)} bytes", flush=True)
            assert len(qr_bytes) > 0

        # 5. POST /api/command Dispatch
        print("6. Testing POST /api/command with fast routing...", flush=True)
        req = urllib.request.Request(
            "http://127.0.0.1:8799/api/command",
            data=json.dumps({"command": "open chrome"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            cmd_res = json.loads(res.read().decode("utf-8"))
            print(f"-> Command result: {cmd_res}", flush=True)
            assert cmd_res["command"] == "open chrome"
            assert cmd_res["tool"] == "open_chrome" or cmd_res["success"] is True

        print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===", flush=True)

    finally:
        print("Stopping Remote Server...", flush=True)
        stop_remote_server()

if __name__ == "__main__":
    test_remote_server()

"""Build the PRIVACY68 Windows application bundle with PyInstaller."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    if sys.platform != "win32":
        print("The PRIVACY68 desktop bundle must be built on Windows.")
        return 1

    required_paths = (
        ROOT / "assets" / "models" / "speaker_model.onnx",
        ROOT / "assets" / "icon.ico",
        ROOT / "ui" / "dashboard" / "index.html",
        ROOT / "privacy68.spec",
    )
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    if missing:
        print("Cannot build PRIVACY68; required files are missing:")
        for path in missing:
            print(f"  - {path}")
        return 1

    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(ROOT / "privacy68.spec"),
    ]
    print("Building PRIVACY68 one-folder application bundle...")
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        print("PyInstaller failed; review the build output above.")
        return result.returncode

    executable = ROOT / "dist" / "PRIVACY68" / "PRIVACY68.exe"
    if not executable.is_file():
        print(f"PyInstaller completed but the executable was not found: {executable}")
        return 1

    print(f"Application bundle created: {ROOT / 'dist' / 'PRIVACY68'}")
    print("Run PRIVACY68.exe to start the assistant or PRIVACY68.exe --dashboard to open the Control Center.")
    print("The configured Agent Brain model/provider is not bundled and may need separate setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

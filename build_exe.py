"""
build_exe.py — Builds the standalone PRIVACY68 application.

Windows produces dist/PRIVACY68/PRIVACY68.exe, which installer.iss wraps
into a setup program. Linux produces dist/PRIVACY68/PRIVACY68, a folder the
user can copy anywhere (see build.sh, which also makes a tarball).

Usage:
    python build_exe.py                 # slim build
    python build_exe.py --bundle-cuda   # Windows only: ship the CUDA DLLs
"""

import os
import shutil
import subprocess
import sys

APP_VERSION = "1.4.1"
IS_WINDOWS = sys.platform.startswith("win")

#: The folders that are shipped next to the executable.
DATA_DIRS = ["plugins", "extra_plugins", "actions", "core", "computer_use",
             "speech", "server", "ui", "utils", "assets"]


def _cuda_datas():
    """The CUDA libraries to bundle — Windows only, and only on request."""
    if not IS_WINDOWS or "--bundle-cuda" not in sys.argv:
        return []

    print("[*] Full offline CUDA bundling enabled via --bundle-cuda")
    datas = []
    venv_nvidia = os.path.join(".venv", "Lib", "site-packages", "nvidia")
    if not os.path.isdir(venv_nvidia):
        return datas
    for package in ("cublas", "cudnn", "cuda_nvrtc"):
        bin_path = os.path.join(venv_nvidia, package, "bin")
        if os.path.isdir(bin_path):
            datas.append(f"--add-data={bin_path};nvidia/{package}/bin")
            print(f"[+] Added bundled CUDA package: {package}")
    return datas


def build():
    print("=" * 50)
    print(f"   PRIVACY68 v{APP_VERSION} Standalone Build Pipeline  ")
    print("=" * 50)

    sep = os.pathsep
    add_data = [f"--add-data={d}{sep}{d}" for d in DATA_DIRS if os.path.isdir(d)]
    if os.path.isfile("config.py"):
        add_data.append(f"--add-data=config.py{sep}.")

    # A stale build folder locks files on Windows and only slows Linux down.
    shutil.rmtree("build", ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name=PRIVACY68",
    ]
    if IS_WINDOWS:
        # A .ico file is only understood by the Windows bootloader.
        cmd += ["--icon=assets\\icon.ico", "--hidden-import=pystray._win32"]
        if os.path.isfile("version_info.txt"):
            cmd.append("--version-file=version_info.txt")
    else:
        cmd.append("--hidden-import=pystray._xorg")

    cmd += add_data + [
        "--collect-all=faster_whisper",
        "--collect-all=ctranslate2",
        "--collect-all=sounddevice",
        "--collect-all=pystray",
        "--collect-all=PIL",
        "--collect-all=webview",
        "--collect-all=pyautogui",
        "--collect-all=qrcode",
        "--collect-all=sklearn",
        "--hidden-import=scipy.special.cython_special",
        "app.py",
    ] + _cuda_datas()

    print("\n[+] Compiling PRIVACY68 with PyInstaller...")
    subprocess.run(cmd, check=True)

    print("\n" + "=" * 50)
    print(f" [OK] Build Successful! PRIVACY68 v{APP_VERSION}")
    print(" Output directory: dist/PRIVACY68/")
    if IS_WINDOWS:
        print(" Distribute by zipping 'dist/PRIVACY68' or running installer.iss")
    else:
        print(" Distribute with build.sh, which also creates a tarball")
    print("=" * 50)


if __name__ == "__main__":
    build()

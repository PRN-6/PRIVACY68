import os
import sys
import subprocess

APP_VERSION = "1.4.1"

def build():
    print("=" * 50)
    print(f"   PRIVACY68 v{APP_VERSION} Standalone EXE Build Pipeline  ")
    print("=" * 50)

    # Check for optional CUDA bundling flag
    bundle_cuda = "--bundle-cuda" in sys.argv
    nvidia_bin_datas = []
    
    if bundle_cuda:
        print("[*] Full offline CUDA bundling enabled via --bundle-cuda")
        venv_nvidia = os.path.join(".venv", "Lib", "site-packages", "nvidia")
        if os.path.isdir(venv_nvidia):
            for pkg in ["cublas", "cudnn", "cuda_nvrtc"]:
                bin_path = os.path.join(venv_nvidia, pkg, "bin")
                if os.path.isdir(bin_path):
                    nvidia_bin_datas.append(f"--add-data={bin_path};nvidia/{pkg}/bin")
                    print(f"[+] Added bundled CUDA package: {pkg}")
    else:
        print("[*] Building Slim Lightweight Package (CUDA downloaded on-demand in-app)")

    # Collect data directories that exist
    data_dirs = ["plugins", "extra_plugins", "actions", "computer_use", "speech", "server", "ui", "utils", "assets"]
    add_data_args = []
    for d in data_dirs:
        if os.path.isdir(d):
            add_data_args.append(f"--add-data={d};{d}")
    if os.path.isfile("config.py"):
        add_data_args.append("--add-data=config.py;.")

    # Clean any stale build folders before compiling to prevent Windows file locks
    import shutil
    shutil.rmtree("build", ignore_errors=True)

    # 3. Assemble PyInstaller Build Command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name=PRIVACY68",
        *(["--version-file=version_info.txt"] if os.path.isfile("version_info.txt") else []),
        "--icon=assets\\icon.ico",
    ] + add_data_args + [
        "--collect-all=faster_whisper",
        "--collect-all=ctranslate2",
        "--collect-all=sounddevice",
        "--collect-all=pystray",
        "--collect-all=PIL",
        "--collect-all=webview",
        "--collect-all=pyautogui",
        "--collect-all=qrcode",
        "--collect-all=sklearn",
        "--hidden-import=pystray._win32",
        "--hidden-import=scipy.special.cython_special",
        "app.py"
    ] + nvidia_bin_datas

    print("\n[+] Compiling PRIVACY68 with PyInstaller...")
    subprocess.run(cmd, check=True)

    print("\n" + "=" * 50)
    print(f" [OK] Build Successful! PRIVACY68 v{APP_VERSION}")
    print(" Output directory: dist/PRIVACY68/")
    print(" Distribute by zipping 'dist/PRIVACY68' or running installer.iss")
    print("=" * 50)

if __name__ == "__main__":
    build()

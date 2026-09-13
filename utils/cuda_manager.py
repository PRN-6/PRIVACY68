import os
import sys
import ctypes
import shutil
import logging
import zipfile
import threading
import urllib.request
import json
import subprocess
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("PRIVACY68.CUDAManager")

# User AppData directory for persistent external CUDA runtime storage
APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
APPDATA_CUDA_DIR = os.path.join(APPDATA_DIR, "cuda")
APPDATA_CUDA_BIN = os.path.join(APPDATA_CUDA_DIR, "bin")

# PyPI packages required for ctranslate2 / faster-whisper on CUDA 12 Windows
CUDA_PACKAGES = [
    "nvidia-cublas-cu12",
    "nvidia-cudnn-cu12"
]

_download_state: Dict[str, Any] = {
    "is_downloading": False,
    "progress": 0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "status": "idle",
    "error": None
}
_download_lock = threading.Lock()


def get_gpu_info() -> Dict[str, Any]:
    """Detects if an NVIDIA GPU is present on Windows."""
    info = {
        "has_nvidia_gpu": False,
        "gpu_name": "None",
        "total_memory": "0 MB",
        "free_memory": "0 MB",
        "driver_version": "None"
    }

    # Method 1: Check driver DLL
    try:
        ctypes.WinDLL("nvcuda.dll")
        info["has_nvidia_gpu"] = True
    except OSError:
        pass

    # Method 2: Detailed query via nvidia-smi
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            info["has_nvidia_gpu"] = True
            info["gpu_name"] = parts[0] if len(parts) > 0 else "NVIDIA GPU"
            info["total_memory"] = parts[1] if len(parts) > 1 else "?"
            info["free_memory"] = parts[2] if len(parts) > 2 else "?"
            info["driver_version"] = parts[3] if len(parts) > 3 else "?"
    except Exception:
        pass

    return info


def get_candidate_cuda_dirs() -> List[str]:
    """Returns candidate directories where CUDA 12 runtime DLLs may reside."""
    candidates = [
        APPDATA_CUDA_BIN,
        APPDATA_CUDA_DIR,
    ]

    # Frozen exe relative dirs
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for pkg in ["cublas", "cudnn", "cuda_nvrtc"]:
        candidates.append(os.path.join(base_dir, "nvidia", pkg, "bin"))
        candidates.append(os.path.join(os.path.dirname(base_dir), "nvidia", pkg, "bin"))

    # Virtual environment site-packages
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_nvidia = os.path.join(project_root, ".venv", "Lib", "site-packages", "nvidia")
    for pkg in ["cublas", "cudnn", "cuda_nvrtc"]:
        candidates.append(os.path.join(venv_nvidia, pkg, "bin"))

    # Running interpreter's site-packages (covers venv AND system installs, incl. pip nvidia-* wheels)
    try:
        import sysconfig
        import site
        site_pkgs = set()
        for key in ("purelib", "platlib"):
            p = sysconfig.get_paths().get(key)
            if p:
                site_pkgs.add(p)
        _getsitepackages = getattr(site, "getsitepackages", None)
        if callable(_getsitepackages):
            try:
                site_pkgs.update(_getsitepackages())
            except Exception:
                pass
        for sp in site_pkgs:
            if not sp:
                continue
            for pkg in ["cublas", "cudnn", "cuda_nvrtc"]:
                candidates.append(os.path.join(sp, "nvidia", pkg, "bin"))
    except Exception:
        pass
    finally:
        pass

    # System CUDA toolkit path fallback
    cuda_path_env = os.environ.get("CUDA_PATH", "")
    if cuda_path_env and os.path.isdir(os.path.join(cuda_path_env, "bin")):
        candidates.append(os.path.join(cuda_path_env, "bin"))

    return [c for c in candidates if os.path.isdir(c)]


def find_cuda_dlls() -> List[str]:
    """Locates any existing CUDA 12 runtime DLLs on the machine."""
    found_dlls = []
    for d in get_candidate_cuda_dirs():
        try:
            for f in os.listdir(d):
                if f.lower().endswith(".dll") and ("cublas" in f.lower() or "cudnn" in f.lower() or "nvrtc" in f.lower()):
                    found_dlls.append(os.path.join(d, f))
        except Exception:
            continue
    return found_dlls


def register_cuda_dlls() -> bool:
    """
    Registers CUDA runtime directories with Windows DLL loader and PATH.
    Returns True if at least one valid CUDA directory was registered.
    """
    valid_dirs = get_candidate_cuda_dirs()
    registered = False
    for d in valid_dirs:
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(d)
            if d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            registered = True
        except Exception as e:
            logger.debug(f"Could not register DLL dir {d}: {e}")
    return registered


def get_cuda_status() -> Dict[str, Any]:
    """Provides a complete health and acceleration status summary."""
    gpu = get_gpu_info()
    dlls = find_cuda_dlls()
    has_dlls = len(dlls) > 0
    is_ready = gpu["has_nvidia_gpu"] and has_dlls

    return {
        "has_gpu": gpu["has_nvidia_gpu"],
        "gpu_name": gpu["gpu_name"],
        "total_memory": gpu["total_memory"],
        "free_memory": gpu["free_memory"],
        "driver_version": gpu["driver_version"],
        "has_cuda_dlls": has_dlls,
        "dll_count": len(dlls),
        "is_ready": is_ready,
        "cuda_appdata_dir": APPDATA_CUDA_DIR,
        "download_url": "https://pypi.org/project/nvidia-cublas-cu12/",
        "download_state": get_download_progress()
    }


def get_download_progress() -> Dict[str, Any]:
    """Returns thread-safe current download state."""
    with _download_lock:
        return dict(_download_state)


def _get_wheel_url(package_name: str) -> Optional[str]:
    """Queries PyPI JSON API to get the official Windows AMD64 wheel URL."""
    try:
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        req = urllib.request.Request(api_url, headers={"User-Agent": "SANA-Assistant-Installer/1.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for file_info in data.get("urls", []):
                filename = file_info.get("filename", "")
                if "win_amd64" in filename and filename.endswith(".whl"):
                    return file_info.get("url")
    except Exception as e:
        logger.warning(f"Could not query PyPI for {package_name}: {e}")
    return None


def start_cuda_runtime_download(
    on_complete: Optional[Callable[[bool, str], None]] = None
) -> Dict[str, Any]:
    """
    Starts asynchronous download and extraction of CUDA 12 runtime DLLs
    into AppData/PRIVACY68/cuda/bin.
    """
    global _download_state
    with _download_lock:
        if _download_state["is_downloading"]:
            return {"success": False, "message": "Download is already in progress."}
        _download_state = {
            "is_downloading": True,
            "progress": 0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "status": "Starting download...",
            "error": None
        }

    def _worker():
        global _download_state
        try:
            os.makedirs(APPDATA_CUDA_BIN, exist_ok=True)

            # Step 1: Check if local env already has the DLLs (instant copy)
            local_copied = 0
            local_bin_dirs = []
            for d in get_candidate_cuda_dirs():
                if "lib\\site-packages" in d.replace("/", "\\").lower() and os.path.isdir(d):
                    local_bin_dirs.append(d)
            for local_bin in local_bin_dirs:
                for fname in os.listdir(local_bin):
                    if fname.lower().endswith(".dll"):
                        src = os.path.join(local_bin, fname)
                        dst = os.path.join(APPDATA_CUDA_BIN, fname)
                        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                            continue
                        shutil.copy2(src, dst)
                        local_copied += 1

            if local_copied >= 10:
                logger.info(f"Copied {local_copied} CUDA DLLs from local environment.")
                register_cuda_dlls()
                with _download_lock:
                    _download_state["is_downloading"] = False
                    _download_state["progress"] = 100
                    _download_state["status"] = "CUDA 12 Runtime installed successfully!"
                    _download_state["error"] = None
                if on_complete:
                    on_complete(True, "CUDA runtime installed successfully!")
                return

            # Step 2: Fetch PyPI Wheel URLs for cuBLAS and cuDNN
            with _download_lock:
                _download_state["status"] = "Resolving CUDA runtime packages from PyPI..."

            package_urls = []
            for pkg in CUDA_PACKAGES:
                w_url = _get_wheel_url(pkg)
                if w_url:
                    package_urls.append((pkg, w_url))
                else:
                    raise RuntimeError(f"Could not locate Windows download URL for {pkg}")

            # Step 3: Download & Extract Each Wheel (Whl is standard Zip format)
            total_pkgs = len(package_urls)
            for idx, (pkg_name, url) in enumerate(package_urls):
                with _download_lock:
                    _download_state["status"] = f"Downloading {pkg_name} ({idx + 1}/{total_pkgs})..."

                temp_whl = os.path.join(APPDATA_DIR, f"{pkg_name}_temp.whl")
                req = urllib.request.Request(url, headers={"User-Agent": "SANA-Assistant/1.1"})

                with urllib.request.urlopen(req, timeout=30) as response, open(temp_whl, "wb") as out_file:
                    pkg_size = response.length or (400 * 1024 * 1024)
                    downloaded = 0
                    chunk_size = 1024 * 128  # 128 KB chunks

                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)

                        overall_pct = int(((idx + (downloaded / pkg_size)) / total_pkgs) * 90)
                        dl_mb = round(downloaded / (1024 * 1024), 1)

                        with _download_lock:
                            _download_state["progress"] = overall_pct
                            _download_state["downloaded_mb"] = dl_mb
                            _download_state["total_mb"] = round(pkg_size / (1024 * 1024), 1)

                # Extract DLLs directly into APPDATA_CUDA_BIN
                with _download_lock:
                    _download_state["status"] = f"Extracting {pkg_name} DLLs..."

                with zipfile.ZipFile(temp_whl, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        fname = os.path.basename(member)
                        if fname.lower().endswith(".dll"):
                            src = zip_ref.open(member)
                            dst_file = os.path.join(APPDATA_CUDA_BIN, fname)
                            with open(dst_file, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                # Cleanup temp file
                try:
                    os.remove(temp_whl)
                except Exception:
                    pass

            # Register DLLs immediately into runtime
            register_cuda_dlls()

            with _download_lock:
                _download_state["is_downloading"] = False
                _download_state["progress"] = 100
                _download_state["status"] = "CUDA 12 Runtime successfully installed! Ready."
                _download_state["error"] = None

            logger.info("CUDA runtime successfully downloaded, extracted and registered.")
            if on_complete:
                on_complete(True, "CUDA runtime installed successfully!")

        except Exception as e:
            logger.error(f"CUDA runtime download failed: {e}", exc_info=True)
            with _download_lock:
                _download_state["is_downloading"] = False
                _download_state["status"] = "Download failed"
                _download_state["error"] = str(e)
            if on_complete:
                on_complete(False, str(e))

    thread = threading.Thread(target=_worker, daemon=True, name="CUDADownloadWorker")
    thread.start()
    return {"success": True, "message": "Download started in background."}

"""
PRIVACY68 CUDA & Acceleration Manager.
Detects host NVIDIA GPU and safely registers existing CUDA runtime paths if available.
Local model downloads and wheel compilation have been removed in favor of cloud APIs.
"""

import os
import sys
import ctypes
import logging
import subprocess
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("PRIVACY68.CUDAManager")

APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
APPDATA_CUDA_DIR = os.path.join(APPDATA_DIR, "cuda")
APPDATA_CUDA_BIN = os.path.join(APPDATA_CUDA_DIR, "bin")


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

    # Method 2: Query via nvidia-smi
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            info["has_nvidia_gpu"] = True
            info["gpu_name"] = parts[0] if len(parts) > 0 else "NVIDIA GPU"
            info["total_memory"] = parts[1] if len(parts) > 1 else "?"
            info["free_memory"] = parts[2] if len(parts) > 2 else "?"
            info["driver_version"] = parts[3] if len(parts) > 3 else "?"
    except Exception as e:
        logger.debug(f"get_gpu_info: {e}")

    return info


def get_candidate_cuda_dirs() -> List[str]:
    """Returns directories where local CUDA runtime DLLs may reside."""
    candidates = [
        APPDATA_CUDA_BIN,
        APPDATA_CUDA_DIR,
    ]

    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for pkg in ["cublas", "cudnn", "cuda_nvrtc"]:
        candidates.append(os.path.join(base_dir, "nvidia", pkg, "bin"))
        candidates.append(os.path.join(os.path.dirname(base_dir), "nvidia", pkg, "bin"))

    cuda_path_env = os.environ.get("CUDA_PATH", "")
    if cuda_path_env:
        candidates.append(os.path.join(cuda_path_env, "bin"))

    return [c for c in candidates if os.path.isdir(c)]


def find_cuda_dlls() -> List[str]:
    """Locates any existing CUDA runtime DLLs on the machine."""
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
    """Registers CUDA runtime directories with Windows DLL loader and PATH if present."""
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
    """Provides hardware acceleration status summary."""
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
        "download_url": None,
        "download_state": get_download_progress()
    }


def get_download_progress() -> Dict[str, Any]:
    """Compatibility helper: local model/CUDA downloads are no longer needed."""
    return {
        "is_downloading": False,
        "progress": 100,
        "downloaded_mb": 0.0,
        "total_mb": 0.0,
        "status": "Cloud API / Zero-setup mode active",
        "error": None
    }


def start_cuda_runtime_download(
    on_complete: Optional[Callable[[bool, str], None]] = None
) -> Dict[str, Any]:
    """Compatibility helper: informs user that local CUDA downloads are no longer required."""
    msg = "Cloud API & Google Speech mode is active. No local CUDA download needed."
    if on_complete:
        on_complete(True, msg)
    return {"success": True, "message": msg}

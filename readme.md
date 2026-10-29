# PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)

PRIVACY68 is an offline-first Windows desktop voice assistant with local speech-processing components, a desktop control center, and agentic OS automation. It pairs local Faster-Whisper inference with an Agent Brain powered by Ollama to execute complex desktop tasks safely through generated Python scripts.

**Latest Windows release:** [Download the installer from GitHub Releases](https://github.com/PRN-6/PRIVACY68/releases/latest).

---

## Command Routing Architecture

The assistant uses deterministic shortcut dispatching alongside an LLM-powered Agent Brain:

```text
Voice/Text Command
  -> Command Executor (actions/executor.py)
       ├── Pending Security Confirmation ("yes", "confirm", "cancel")
       ├── Built-in Greeting Shortcuts ("hi", "hello", "good morning")
       ├── Direct App Launch Shortcuts (Chrome, Brave, WhatsApp) -> Native Plugins
       ├── GitHub Integration Plugin -> GitHub REST API & local Git operations
       └── Agent Brain (actions/agent_brain.py)
            ├── LiteLLM Completion Request -> Ollama (http://127.0.0.1:11434)
            ├── Dynamic Windows Path Resolution (OneDrive/Desktop/Downloads)
            ├── Isolated Code Execution (30-second watchdog timeout)
            └── Formatted Results & UI Telemetry to Control Center & Floating HUD
```

---

## System Requirements & Prerequisites

### 1. Hardware Specifications

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **Operating System** | Windows 10 (64-bit, build 19041+) | Windows 11 (64-bit) |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (AVX2 support) | Intel Core i5/i7 / AMD Ryzen 5/7 |
| **System Memory (RAM)** | 4 GB | 8 GB or 16 GB |
| **GPU (Optional)** | None (runs on CPU via `int8`) | NVIDIA GeForce GTX 1650 / RTX 3050+ (6 GB+ VRAM) |
| **Audio Hardware** | Standard USB/3.5mm microphone & speakers | Noise-cancelling microphone |
| **Storage** | 1.5 GB free disk space | 5 GB+ (for local LLMs if stored locally) |

---

### 2. Ollama Subsystem (Required for Agent Brain Automation)

PRIVACY68 uses **Ollama** via LiteLLM as its reasoning engine for desktop automation (opening apps, managing files, adjusting system settings, web navigation, etc.).

* **How to Install**: Download and run the official Windows installer from [ollama.com/download](https://ollama.com/download).
* **Service Requirements**: Ollama must be running as a background service (listens on `http://127.0.0.1:11434`). It usually runs in the Windows system tray.
* **Control Center Integration**: The PRIVACY68 Control Center actively monitors the Ollama service on startup:
  - 🟢 **Online**: Ollama is active; Agent Brain can immediately execute commands.
  - 🟡 **Not Running / Offline**: Ollama is installed on your PC, but the service is stopped. Click **Start Ollama** right in the dashboard to launch it.
  - 🔴 **Not Installed**: Ollama was not found on your system. Click **Download Ollama** to open the installer page.
* **Execution Modes**:
  - **Cloud Proxy (Default `ollama/gemma4:31b-cloud`)**: Ollama acts as a lightweight proxy to Google Cloud's Gemma 4 31B model. Requires zero local GPU VRAM.
  - **100% Offline Local Model (e.g. `qwen2.5:0.5b` or `llama3.2:1b`)**: For completely air-gapped local execution, pull your preferred model:
    ```powershell
    ollama pull qwen2.5:0.5b
    ```
    Then change `self.model = "ollama/qwen2.5:0.5b"` in `actions/agent_brain.py`.

---

### 3. CUDA & GPU Acceleration (Optional, for High-Speed Audio Inference)

PRIVACY68 uses **Faster-Whisper** and Silero neural Voice Activity Detection (VAD) for real-time speech transcription and wake-word gating.

| Compute Mode | Audio Inference Latency | Memory Footprint | Setup Required |
|---|---|---|---|
| **CPU (`cpu / int8`)** | ~350ms – 600ms | ~1.2 GB System RAM | **Zero setup.** Works out of the box on any Windows PC. |
| **GPU (`cuda / float16`)** | ~120ms – 160ms | ~1.4 GB NVIDIA VRAM | NVIDIA GPU + cuBLAS 12 & cuDNN 9 runtime DLLs. |

#### Why the standard NVIDIA CUDA Toolkit is not enough:
Faster-Whisper (built on CTranslate2) requires **CUDA 12 runtime** (`cublas64_12.dll`, `cublasLt64_12.dll`) **AND NVIDIA cuDNN 9** (`cudnn64_9.dll`, `cudnn_ops64_9.dll`). Standard NVIDIA CUDA Toolkit installers (such as CUDA 13.x) have mismatched versions and **never include cuDNN**.

#### Zero-Config One-Click Solution:
You do **not** need to manually search for or install the multi-gigabyte NVIDIA Developer SDK. If an NVIDIA GPU is detected on your PC, the PRIVACY68 dashboard automatically provides a **"Download CUDA (~450MB)"** button under the Hardware card. Clicking it downloads the exact pre-compiled cuBLAS 12 and cuDNN 9 runtime DLLs directly into:
```text
%APPDATA%\PRIVACY68\cuda\bin\
```
Upon restart, PRIVACY68 automatically registers these DLLs and switches the audio pipeline to `cuda / float16` GPU acceleration.

---

## Features

- **Local Speech Recognition**: Faster-Whisper with Silero neural VAD for zero-latency wake word ("Alexa") and command recognition.
- **Agentic Code Execution**: Translates user intent into verified Python automation with an integrated 30-second watchdog timer.
- **Control Center Dashboard**: Modern pywebview control center for managing runtime status, testing microphones, reviewing LLM output, and toggling plugins.
- **Hardware Telemetry**: Real-time monitoring of NVIDIA GPU availability, CUDA runtime readiness, microphone input RMS, and Ollama connectivity.
- **Security Confirmation State Machine**: High-risk actions (file deletion, GitHub branch pushes) are paused and require explicit user confirmation ("yes" / "confirm").
- **Built-in Plugins**: Dedicated controllers for Google Chrome, Brave Browser, WhatsApp, and GitHub.
- **Dynamic User Path Resolution**: Resolves active OneDrive and standard Windows desktop paths dynamically.

---

## Installation & Running from Source

```powershell
# 1. Clone repository
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68

# 2. Create virtual environment with Python 3.11 or 3.12
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Start PRIVACY68
python app.py
```

To open the dashboard directly:
```powershell
python app.py --dashboard
```

---

## Building the Windows Installer

Building a standalone distributable installer uses PyInstaller and Inno Setup 6:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\build.bat
```

This compiles `PRIVACY68.exe` under `dist\PRIVACY68\` and packages an Inno Setup installer under `installer\PRIVACY68-Setup-v1.5.0.exe`.

---

## Unit Testing

Run the full automated test suite (59 unit tests covering command parsing, executor dispatch, security guard, and dashboard bridge):

```powershell
python -m unittest discover tests -v
```

---

## Documentation Links

- [Software Design Specification (SDS)](PRIVACY68_SDS.md)
- [Project Documentation Portal](website/docs.html)
- [Plugin Architecture Guide](website/plugins.html)
- [Security Policy](SECURITY.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [License](LICENSE)

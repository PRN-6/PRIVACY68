# PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)
[![Tests: 85 Passed](https://img.shields.io/badge/tests-85%20passed-brightgreen.svg)](#unit-testing)
[![Version: 1.6.1](https://img.shields.io/badge/version-1.6.1-blue.svg)](https://github.com/PRN-6/PRIVACY68/releases/tag/v1.6.1)

PRIVACY68 is a 100% private Windows desktop AI assistant featuring on-demand Click-to-Speak, a modern minimalist Control Center, multi-provider AI brain orchestration, and agentic OS automation. It pairs zero-key speech recognition (Google Web Speech & Groq Whisper Cloud) with an Agent Brain powered by multi-provider AI APIs (Google Gemini, Groq Llama 3.3, Anthropic Claude, OpenAI, or local Ollama) to execute complex desktop tasks safely through generated, self-correcting Python scripts.

**Latest Windows Release:** [Download PRIVACY68 Installer from GitHub Releases](https://github.com/PRN-6/PRIVACY68/releases/tag/v1.6.1)

---

## What's New in v1.6.1

- **Minimalist Control Center**: Redesigned UI with an icon-free, clean enterprise design system, dark glassmorphism styling, and responsive layout.
- **Multi-Provider Cloud AI Slots**: Seamless simultaneous slots for Google Gemini (Free 1.5/2.0 Flash), Groq Cloud (Free Llama 3.3 70B), Anthropic Claude, OpenAI, and local Ollama with automatic failover.
- **Autonomous Skill Crystallization**: Instant 0ms fast-path replay for learned and verified desktop automation scripts.
- **Mobile Web Remote Server**: Control your desktop from any phone, tablet, or browser on your local Wi-Fi (Port 8765) with live telemetry and quick actions.
- **3-Tier Security Guard**: Strict permission gating with in-memory audit logs (Safe Level 1 auto-execute, Sensitive Level 2 with prompt confirmation, Critical Level 3 blocked).
- **100% Free Push-to-Talk Privacy**: Zero continuous microphone recording; Google Web Speech cloud ASR activates only on demand.
- **85 Unit Tests Passing**: Fully validated test suite covering agent self-healing, command routing, security guard, plugin lifecycle, and dashboard bridges.

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
       ├── Skill Crystallizer -> 0ms fast-path execution of cached automation
       └── Agent Brain (actions/agent_brain.py)
            ├── Multi-Provider AI Routing (Gemini / Groq / Claude / OpenAI / Ollama)
            ├── Automatic Failover on Rate Limits (Groq 429 -> Gemini Fallback)
            ├── Dynamic Windows Path Resolution (OneDrive/Desktop/Downloads)
            ├── Isolated Code Execution with 30-Second Watchdog
            ├── Self-Healing Error Correction Loop (up to 2 retry attempts)
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
| **Audio Hardware** | Standard USB/3.5mm microphone & speakers | Noise-cancelling array microphone |
| **Storage** | 1.5 GB free disk space | 5 GB+ (for local LLMs if stored locally) |

---

### 2. Multi-Provider AI Brain Options

PRIVACY68 offers complete freedom in selecting your reasoning provider:

1. **Free Cloud AI (Zero Setup & Fast)**:
   - **Google Gemini**: Supports Gemini 1.5 Flash and 2.0 Flash with free tier keys from Google AI Studio.
   - **Groq Cloud**: Ultra-fast inference running Llama 3.3 70B Versatile for instant code generation.
2. **Premium Cloud AI**:
   - **Anthropic Claude**: Claude 3.5 Sonnet / Haiku for complex multi-step reasoning.
   - **OpenAI**: GPT-4o / GPT-4o-mini for robust desktop automation.
3. **100% Offline Local Model (Ollama)**:
   - Download the official Windows installer from [ollama.com/download](https://ollama.com/download).
   - Ollama runs locally on `http://127.0.0.1:11434`.
   - The Control Center displays live status (Online, Not Running, or Not Installed) with one-click startup.
   - Run lightweight models locally without internet:
     ```powershell
     ollama pull qwen2.5:0.5b
     ```

---

### 3. CUDA & GPU Acceleration (Optional, for High-Speed Audio Inference)

PRIVACY68 uses **Google Web Speech** (100% free, zero keys required) for high-accuracy speech transcription with zero background listening. For local offline Whisper transcription, GPU acceleration is supported:

| Compute Mode | Audio Inference Latency | Memory Footprint | Setup Required |
|---|---|---|---|
| **CPU (`cpu / int8`)** | ~350ms – 600ms | ~1.2 GB System RAM | **Zero setup.** Works out of the box on any Windows PC. |
| **GPU (`cuda / float16`)** | ~120ms – 160ms | ~1.4 GB NVIDIA VRAM | NVIDIA GPU + cuBLAS 12 & cuDNN 9 runtime DLLs. |

#### Zero-Config One-Click Solution:
If an NVIDIA GPU is detected on your PC, the PRIVACY68 Control Center provides a **"Download CUDA (~450MB)"** button under the Hardware card. Clicking it downloads the exact pre-compiled cuBLAS 12 and cuDNN 9 runtime DLLs directly into:
```text
%APPDATA%\PRIVACY68\cuda\bin\
```
Upon restart, PRIVACY68 automatically registers these DLLs and switches the audio pipeline to `cuda / float16` GPU acceleration.

---

## Core Features

- **Push-to-Talk Privacy**: Zero continuous microphone streaming. Audio capture triggers exclusively when you click 'Click to Speak', eliminating background surveillance.
- **Agentic Code Execution**: Translates user intent into verified Python automation with an integrated 30-second watchdog timer and automatic self-healing.
- **Minimalist Control Center**: Clean pywebview interface for managing runtime status, testing microphones, reviewing LLM output, configuring AI keys, and managing plugins.
- **Mobile Web Remote**: Access and control your assistant from any device on your local Wi-Fi network (Port 8765) with live status and quick action tiles.
- **3-Tier Security Guard**: Strict permission gating (Safe Level 1 auto-execute, Sensitive Level 2 confirmation prompt, Critical Level 3 blocked).
- **GitHub Integration**: Authenticated repository status, issue/PR creation, and branch pushes via Windows Credential Manager.
- **Built-in Plugins**: Native controllers for Google Chrome, Brave Browser, WhatsApp, and GitHub.
- **Dynamic Path Resolution**: Dynamically resolves active OneDrive, Desktop, Downloads, and Documents paths.

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
pip install -r requirements.txt .

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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt .
.\build.bat
```

This compiles `PRIVACY68.exe` under `dist\PRIVACY68\` and packages an Inno Setup installer under `installer\PRIVACY68-Setup-v1.6.1.exe`.

---

## Unit Testing

Run the full automated test suite (85 unit tests covering agent brain failover, execution self-healing, command executor, security guard, GitHub integration, and dashboard bridge):

```powershell
python -m unittest discover tests -v
```

---

## Project Documentation

- [Project Documentation Portal](website/docs.html)
- [About & Architecture](website/about.html)
- [Plugin Architecture Guide](website/plugins.html)
- [Security Policy](SECURITY.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [License](LICENSE)

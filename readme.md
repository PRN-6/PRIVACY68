# PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)
[![Tests: 144 Passed](https://img.shields.io/badge/tests-144%20passed-brightgreen.svg)](#unit-testing)
[![Version: 1.6.4](https://img.shields.io/badge/version-1.6.4-blue.svg)](https://github.com/PRN-6/PRIVACY68/releases/tag/v1.6.4)

PRIVACY68 is a 100% private Windows desktop AI assistant featuring on-demand Click-to-Speak, a modern minimalist Control Center, universal multi-provider AI brain orchestration, and agentic OS automation. It pairs zero-key speech recognition (Google Web Speech) with an Agent Brain powered by universal AI APIs (Google Gemini, Groq LPU, OpenRouter, Anthropic Claude, OpenAI, or local Ollama / LM Studio) to execute complex desktop tasks safely through generated, self-correcting Python scripts.

**Latest Windows Release:** [Download PRIVACY68 Installer v1.6.4 from GitHub Releases](https://github.com/PRN-6/PRIVACY68/releases/tag/v1.6.4)  
**Universal LLM Guide:** [Read Complete Guide to Connecting Any Cloud or Local LLM](docs/UNIVERSAL_LLM_GUIDE.md)

---

## What's New in v1.6.4

- **Telegram Remote Gateway Plugin**: Live global teleoperation from anywhere in the world on 4G/5G mobile data. Send voice notes (transcribed locally via Faster-Whisper), text commands, request live screenshots (`/screenshot`), and inspect system diagnostics (`/status`).
- **Interactive PIN Pairing Security**: Cryptographically generated 6-character ephemeral pairing PIN (`/pair <PIN>`) guarantees that only your verified phone can dispatch commands to your PC.
- **Push-to-Talk Transparent Floating Overlay**: Added a dedicated `"🎙️ Voice Command (Push to Talk)"` option to the Windows System Tray menu. Clicking it summons a sleek, draggable, glassmorphic floating widget allowing users to click and speak commands with instant visual feedback and 100% zero-idle mic privacy.
- **Adaptive Speech Priority with Offline Local Fallback**: Default speech pipeline prioritizes ultra-fast, zero-setup Google Web Speech, seamlessly auto-failing over to on-device Faster-Whisper whenever an internet outage or network disconnect is detected.
- **3-Tier AST Code Safety Guard**: Deep static analysis and regex pattern inspection on all Agent Brain generated Python code before execution, preventing untrusted scripts from performing dangerous OS operations without explicit human confirmation.
- **Compound Command Routing Fix**: Prevented multi-step instructions (`"open notepad and type hello"`, `"open youtube and search..."`) from being prematurely truncated by the app launcher, ensuring compound tasks cleanly reach the Agent Brain.
- **All 7 Built-in Plugins Documented & Tested**: Windows System, Google Chrome, Brave Browser, WhatsApp, Gmail, GitHub, and Telegram Remote Gateway.
- **144 Unit Tests Passing**: Fully validated test suite (100% pass rate in 7.90s) covering all plugins, failover, self-healing, security guard, adaptive speech priority, dual-accent recovery, push-to-talk overlay, and remote gateway flows.

---

## What's New in v1.6.3

- **Gmail Automation Controller**: Native plugin supporting direct browser compose and inbox navigation (`"compose email to ... with subject ... and body ..."`). Supports Google's multi-account `authuser` gateway to route emails directly from your configured Google account.
- **Interactive Click-to-Configure Plugin Drawers**: Clicking any plugin card in the Control Center reveals a configuration drawer with live input boxes (e.g. Gmail sender email, WhatsApp default contact, browser homepage) and one-click test execution buttons.
- **Zero-Latency Natural Language Parsing**: Real-time extraction of email recipients, subjects, and body text without cloud LLM latency.
- **Unified IPC Plugin Settings**: Dashboard bridge supports `set_plugin_setting`, `get_plugin_setting`, and `execute_plugin_action` with profile persistence.
- **107 Unit Tests Passing**: Fully validated test suite (100% pass rate) verifying Gmail parsing, URL generation, multi-account routing, dashboard drawer bridge, and execution safety.

---

## What's New in v1.6.2

- **Universal API & Custom Endpoint Support**: Connect any cloud AI key (Gemini, Groq, OpenRouter, Claude, OpenAI) or any custom OpenAI-compatible endpoint (LM Studio, LocalAI, vLLM, DeepSeek, Mistral).
- **Intra-Provider Model Cascading**: Automatically cascades to sibling models within the same provider on 404/429 errors (e.g. Groq decommissioned model fallback to `openai/gpt-oss-120b`).
- **Autonomous Configuration Healing**: Automatically updates runtime `.env` settings upon failover success to eliminate retry latency on future commands.
- **OpenRouter Free Tier (100+ Free Models)**: Direct first-class support for free open-weights models (`openrouter/google/gemini-2.0-flash-exp:free`, `openrouter/meta-llama/llama-3.3-70b-instruct:free`).
- **Local Ollama Model Chips**: Control Center auto-detects installed local models and displays interactive one-click activation chips.
- **87 Unit Tests Passing**: Fully validated test suite (100% pass rate in 13.9s) covering auto-failover, self-healing, security guard, and skill crystallization.

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
   - **Google Gemini**: Supports `gemini/gemini-3.5-flash` with generous free tier keys from Google AI Studio.
   - **Groq Cloud**: Ultra-fast inference running `groq/openai/gpt-oss-120b` or `qwen3.8-27b` at ~200ms latency.
   - **OpenRouter**: Access 100+ free open-weights models (`openrouter/meta-llama/...:free`, `gemini-2.0-flash-exp:free`).
2. **Premium Cloud AI**:
   - **Anthropic Claude**: Claude 3.5 Sonnet / Haiku for complex multi-step reasoning.
   - **OpenAI**: GPT-4o / GPT-4o-mini for robust desktop automation.
   - **Custom Endpoints**: DeepSeek, Mistral, Together AI via standard OpenAI-compatible base URLs.
3. **100% Offline Local Models (Ollama, LM Studio, LocalAI)**:
   - Run completely offline with zero internet and zero cloud token usage:
   - **Ollama**: Connects to `http://localhost:11434` or remote Ollama server.
   - **LM Studio / LocalAI / vLLM**: Connects to `http://localhost:1234/v1` or custom base URL.
   - Quick one-click model selection right from the Control Center.
   - *For full setup instructions, see the [Universal LLM & API Integration Guide](docs/UNIVERSAL_LLM_GUIDE.md).*

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
- **Built-in Plugins**: 7 native integrations: Windows System, Google Chrome, Brave Browser, WhatsApp, Gmail, GitHub, and Telegram Remote Gateway.
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

This compiles `PRIVACY68.exe` under `dist\PRIVACY68\` and packages an Inno Setup installer under `installer\PRIVACY68-Setup-v1.6.4.exe`.

---

## Unit Testing

Run the full automated test suite (144 unit tests covering agent brain failover, execution self-healing, command executor, Telegram Remote Gateway, Faster-Whisper offline transcription, Gmail automation, security guard, GitHub integration, push-to-talk overlay, and dashboard bridge):

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

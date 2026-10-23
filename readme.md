# 🌌 PRIVACY68 Voice Assistant v1.4.1

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)
[![Privacy First](https://img.shields.io/badge/privacy-100%25%20Local-brightgreen.svg)](#)
[![Release: v1.4.1](https://img.shields.io/badge/release-v1.4.1-blueviolet.svg)](https://github.com/PRN-6/PRIVACY68/releases)

**PRIVACY68** is an ultra-fast, local-first AI voice assistant and autonomous desktop automation engine for Windows. Engineered for extreme speed, 100% zero-cloud voice privacy, and biometric security, it replaces fragmented script-based automation with a professional **Agentic Brain** powered by local LLMs.

---

## 📑 Table of Contents
1. [Architecture Overview: The Agentic Brain](#-architecture-overview-the-agentic-brain)
2. [Speech Engine & Wake Word Recognition](#-speech-engine--wake-word-recognition)
3. [Biometric Voice Authentication (Voice Lock)](#-biometric-voice-authentication-voice-lock)
4. [Control Center Dashboard](#-control-center-dashboard)
5. [Hardware Acceleration & Performance Boost](#-hardware-acceleration--performance-boost)
6. [Complete User Guide & Application Controls](#-complete-user-guide--application-controls)
7. [Voice Command Reference](#-voice-command-reference)
8. [Installation & Developer Setup](#-installation--developer-setup)
9. [Security & Privacy Commitments](#-security--privacy-commitments)

---

## 🧠 Architecture Overview: The Agentic Brain

Unlike traditional voice assistants that rely on fixed "if-then" routing, PRIVACY68 uses an **Agentic Reasoning Engine**. This architecture allows the assistant to reason through a request, plan the necessary steps, and generate executable Python code on-the-fly to automate your OS.

### The Reasoning Flow:
```
 [ Voice/Text Input ] 
          │
 [ Silero Neural VAD ] → [ faster-whisper STT ]
          │
 [ Voice Lock Verification ] (Biometric Gate)
          │
 [ Agentic Brain (Gemma 4 via Ollama) ]
          │
 [ Python Code Generation ] → [ Subprocess Execution ]
          │
 [ OS Automation / Plugin Execution ]
```

### Key Components:
- **Neural Core**: Powered by **Gemma 4 (31B)** via Ollama, providing deep reasoning and high-accuracy code generation.
- **Dynamic Plugin System**: A modular architecture (`plugins/`) allowing the Agent to call specialized controllers for Chrome, WhatsApp, System settings, and more.
- **Zero-Latency Execution**: Generated scripts are executed directly via the system Python interpreter, bypassing slow intermediate layers.
- **Air-Gapped Privacy**: All reasoning happens locally on your machine. No data is sent to the cloud.

---

## 🎙️ Speech Engine & Wake Word Recognition

PRIVACY68 features a high-performance audio pipeline designed for accuracy across diverse environments.

### Core Technology:
1. **STT Engine**: **faster-whisper (CTranslate2)** for near-instant, high-fidelity transcription.
2. **VAD Filter**: **Silero Neural VAD** to eliminate background noise and precisely detect when speech starts and ends.
3. **Phonetic Wake Word Matching**: Uses fuzzy Levenshtein distance and phonetic aliases to ensure the wake word is detected regardless of accent or speed.
4. **Dynamic Normalization**: Automatically adjusts audio levels to ensure consistent trigger reliability across different microphone hardwares.

---

## 🔒 Biometric Voice Authentication (Voice Lock)

PRIVACY68 includes a military-grade biometric verification system powered by **ECAPA-TDNN neural speaker embeddings**.

### How It Works:
- Converts your voice into a unique **512-dimensional acoustic vector**.
- Uses **Cosine Similarity** to compare live speech against your enrolled profile.
- Only the authorized owner can trigger sensitive system commands.

**Enrollment**: Performed via the **Control Center Dashboard** where you record 3 verification samples to create your master voice profile.

---

## 📊 Control Center Dashboard

The **Control Center** is a professional WebView2-based management console that serves as the "window" into the Agent's mind.

- **Neural Command Console**: A real-time terminal where you can type commands and watch the Agent's reasoning process.
- **Reasoning Logs**: View the exact thought process ("The Why") the AI used to decompose your request.
- **Code Viewer**: Inspect the generated Python scripts ("The How") before or after they are executed.
- **System Telemetry**: Live monitoring of CUDA acceleration, mic sensitivity, and LLM status.
- **Profile Management**: Easily update your wake word, user name, and biometric thresholds.

---

## 🚀 Hardware Acceleration & Performance Boost

Engineered to scale from office laptops to high-end gaming rigs.

- **NVIDIA GPU Support**: Full CUDA 12 acceleration for faster-whisper, reducing transcription latency to **~120ms**.
- **CPU Optimization**: Uses **int8 quantization** and AVX-512 instructions for fast performance on Intel/AMD systems without requiring GPU drivers.
- **One-Click CUDA Manager**: Built-in tool to download and configure the NVIDIA cuBLAS/cuDNN runtime DLLs without requiring a full CUDA Toolkit installation.

---

## 🖥️ Complete User Guide & Application Controls

### 1. Windows System Tray
The application docks into the tray for minimal distraction:
- **Right-Click**: Access the Dashboard, toggle Mute, or reload plugins.
- **Tray Color**: Changes dynamically to reflect the assistant's state (Listening, Processing, Success, Error).

### 2. Floating Neon HUD
A transparent, click-through overlay appears during interaction:
- **Cyan Pulse**: Listening.
- **Purple Wave**: AI is reasoning.
- **Green Flash**: Action completed.

### 3. Mobile Web Remote
Control your PC from your phone via a local Wi-Fi server. Scan the QR code in the Dashboard to open the remote interface on any device.

---

## ⌨️ Voice Command Reference

| Category | Spoken Trigger Example | Action |
| :--- | :--- | :--- |
| **Browsing** | *"Privacy68, open Chrome"* | Launches Google Chrome |
| **Communication**| *"Privacy68, open WhatsApp"* | Launches WhatsApp Desktop/Web |
| **System** | *"Privacy68, mute volume"* | Sets master volume to 0% |
| **Security** | *"Privacy68, lock screen"* | Locks Windows workstation |
| **Web Search** | *"Privacy68, search for AI news"*| Searches via Chrome/Brave |
| **Productivity** | *"Privacy68, open VS Code"* | Launches Visual Studio Code |
| **Reasoning** | *"Privacy68, explain black holes"*| Local LLM provides spoken answer |

---

## 🛠️ Installation & Developer Setup

### Prerequisites
- Windows 10/11 (64-bit)
- Python 3.10+
- [Ollama](https://ollama.ai/) (for local LLM reasoning)

### Quick Start
```powershell
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

---

## 🛡️ Security & Privacy Commitments
- **100% Local Audio**: Voice streams never leave your RAM.
- **Zero Cloud Reasoning**: By default, all AI processing happens via Ollama on your local hardware.
- **Local Biometrics**: Your voice embeddings are stored encrypted on your own disk.
- **Open Source**: Fully auditable code under the MIT License.

---

*Crafted for private, instant, and autonomous Windows intelligence.*

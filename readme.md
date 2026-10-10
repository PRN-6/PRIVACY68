# 🌌 PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Privacy First](https://img.shields.io/badge/privacy-100%25%20Local-brightgreen.svg)](#)

PRIVACY68 is a high-performance, locally-hosted AI voice assistant built in Python. Designed for speed and 100% privacy, it uses local neural networks to listen for a customizable wake word (e.g. Privacy68, Nova, Leo, Serena, etc.), transcribe your speech, and execute system commands or query local AI models (via Ollama)—all without sending any voice data to the cloud.

---

## ✨ Features
- **Lightning Fast Transcription**: Powered by `faster-whisper` and NVIDIA CUDA acceleration for near-instant speech-to-text.
- **Customizable Wake Words**: Supports any custom wake word or multi-word combination dynamically.
- **Local AI Brain**: Integrates with `Ollama` for complex query resolution and conversational AI.
- **Continuous Listening**: Runs silently in the background using a dedicated audio thread and `sounddevice`.
- **Smart Voice Activity Detection (VAD)**: Uses `SileroVAD` to perfectly detect when you start and stop speaking, ignoring background noise.
- **Extensible Plugin System**: Easily add new skills (e.g., Open Google Chrome, Send WhatsApp message, Control Volume).
- **Non-Intrusive UI**: Features a Windows System Tray integration (`pystray`), Modern WebView2 Control Center, and a floating HUD overlay for visual feedback.

---

## 🛠️ How It Works

1. **The Wake Word**: The audio stream continuously buffers short chunks of audio. It uses a lightweight Whisper scan to detect the wake word (`"Privacy68"`, `"Nova"`, or your custom chosen name).
2. **Active Listening**: Once awakened, the Neural VAD tracks your voice. It records until you stop speaking.
3. **Transcription**: The recorded audio is normalized and sent to the Whisper AI model to be converted into text.
4. **Execution**: The text is passed to the `ActionExecutor`, which matches it against available plugins or routes it to the Ollama AI for complex reasoning.

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+
- An NVIDIA GPU (Highly recommended for CUDA acceleration, though CPU fallback is supported)
- [Ollama](https://ollama.ai/) installed and running locally
  - Required model: **`qwen2.5:0.5b`** (used for AI intent reasoning and fallback skills)
  - Pull the model before running PRIVACY68:
    ```powershell
    ollama pull qwen2.5:0.5b
    ```

### 1. Clone & Environment Setup
Clone the repository and create a Python virtual environment:
```powershell
git clone https://github.com/yourusername/PRIVACY68.git
cd PRIVACY68
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
Install all required packages from the requirements file:
```powershell
pip install -r requirements.txt
```

*(Note: If you have an NVIDIA GPU, the requirements file automatically installs the necessary `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` libraries for GPU acceleration).*

### 3. Run PRIVACY68
To launch the assistant, simply run:
```powershell
python app.py
```
You will see the PRIVACY68 icon appear in your Windows System Tray. Say *"Privacy68"* or your custom wake word to wake it up!

---

## 📂 Project Structure
- `app.py`: The main entry point that starts the background threads and UI.
- `config.py`: Central configuration for model sizes, thresholds, and device selection.
- `speech/streamer.py`: The core audio engine handling the microphone stream and Whisper transcription.
- `speech/vad.py`: The Voice Activity Detection logic.
- `actions/executor.py`: Routes transcribed text across Fast Lane and Plugin Lane.
- `actions/fast_lane.py`: Instant deterministic Windows OS automation (<5ms, zero LLM overhead).
- `actions/router.py`: TF-IDF Semantic Router for plugin matching.
- `computer_use/`: Low-level Windows OS automation (UIA, window management, app launching, file tools).
- `plugins/`: Directory containing all the executable skills and integrations.
- `ui/`: Contains the System Tray and Floating HUD interfaces.

---

## ⚡ Command Execution Architecture

PRIVACY68 uses an ultra-fast, local execution pipeline designed for privacy, reliability, and zero latency:

```
Privacy68
├── Voice / Wake Word (Faster-Whisper + Silero VAD)
├── Voice Authentication (Biometric Speaker Recognition)
├── Fast Lane (Instant <5ms Deterministic Windows Automation)
├── HUD / Control Center (Neon Click-Through Overlay)
└── Plugin Lane (WhatsApp, Chrome, PPT, Spotify, etc.)
```

### ⚡ Fast Lane vs. 🔌 Plugin Lane

- **Fast Lane (Deterministic / Regex)**: Core desktop actions execute in **< 5ms** with zero LLM overhead:
  - *"Open Chrome"* / *"Open Command Prompt"* / *"Launch VS Code"*
  - *"Volume up"* / *"Mute"* / *"Take a screenshot"* / *"Lock screen"*
  - *"Create a folder named Project on Desktop"*
  - *"Open settings and go to display"*
  - *"Open Chrome and search for YouTube"*
  - *"Play believer on YouTube"*

- **Plugin Lane (Semantic TF-IDF)**: Matches natural phrases against registered plugins:
  - *"Send WhatsApp message to Mom"*
  - *"Play music on Spotify"*
  - *"Next slide"* / *"Previous slide"*

---
*Built with ❤️ for local, private, and instant desktop automation.*
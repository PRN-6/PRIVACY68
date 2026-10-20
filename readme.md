# 🌌 PRIVACY68 Voice Assistant v1.4.0

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)
[![Privacy First](https://img.shields.io/badge/privacy-100%25%20Local-brightgreen.svg)](#)
[![Release: v1.4.0](https://img.shields.io/badge/release-v1.4.0-blueviolet.svg)](https://github.com/PRN-6/PRIVACY68/releases)

**PRIVACY68** is an ultra-fast, local-first AI voice assistant and autonomous desktop automation engine for Windows. Engineered for extreme speed, 100% zero-cloud voice privacy, and biometric security, it combines **faster-whisper (CTranslate2)**, **Silero Neural VAD**, and an intelligent **3-Lane Routing Architecture** to execute desktop automations in under 2 milliseconds.

---

## 📑 Table of Contents
1. [Architecture Overview: The 3-Lane Engine](#-architecture-overview-the-3-lane-engine)
2. [Speech Engine & Wake Word Recognition](#-speech-engine--wake-word-recognition)
3. [Biometric Voice Authentication (Voice Lock)](#-biometric-voice-authentication-voice-lock)
4. [Microphone Setup & Audio Diagnostics](#-microphone-setup--audio-diagnostics)
5. [Hardware Acceleration & Performance Boost](#-hardware-acceleration--performance-boost)
6. [Complete User Guide & Application Controls](#-complete-user-guide--application-controls)
7. [Voice Command Reference](#-voice-command-reference)
8. [Installation & Developer Setup](#-installation--developer-setup)
9. [Configuration Reference (`config.py`)](#-configuration-reference-configpy)

---

## ⚡ Architecture Overview: The 3-Lane Engine

Unlike cloud-dependent voice assistants that transmit your speech to third-party data centers, PRIVACY68 routes every spoken request through an intelligent **3-Lane Decision Engine** designed for speed, privacy, and reasoning depth:

```
                                [ Microphone Stream (16kHz Mono) ]
                                                │
                                     [ Silero Neural VAD ]
                                                │
                                    [ faster-whisper STT ]
                                                │
                          [ Biometric Voice Authentication (512-d) ]
                                                │
                                  ┌─────────────┴─────────────┐
                                  ▼                           ▼
                        (Authorized Master)           (Guest / Rejected)
                                  │                           │
                   ┌──────────────┴──────────────┐       [ Drop / Log ]
                   ▼                             ▼
         [ Fast Lane Classifier ]      [ API / LLM Router ]
                   │                             │
    ┌──────────────┴──────────────┐       ┌──────┴──────┐
    ▼                             ▼       ▼             ▼
[ Lane 1: Fast Lane ]   [ Lane 2: API Lane ]  [ Lane 3: Local LLM Lane ]
  (< 2ms, 0% AI, Local)   (Cloud Reasoning)     (Ollama Air-Gapped)
```

### 🏎️ Lane 1: Fast Lane (Deterministic Execution)
- **Latency**: `< 2ms`
- **AI Overhead**: 0% (Zero LLM inference, zero cloud communication)
- **Engine**: Dual-layer vector classifier (`actions/intent_classifier.py` + `actions/param_extractor.py`) trained to **100% accuracy** on canonical system entities.
- **Handles**: 
  - Direct app launching (*"open chrome"*, *"launch vs code"*, *"open brave"*)
  - System hardware controls (*"volume up"*, *"mute"*, *"lock screen"*, *"take screenshot"*)
  - Windows settings (*"open settings"*, *"bluetooth"*, *"wifi"*, *"display"*)
  - File/folder shortcuts (*"open downloads"*, *"open desktop"*)
  - Rapid media and typing macros (*"type hello world"*, *"next track"*)

### ☁️ Lane 2: API Lane (Cloud Intelligence)
- **Latency**: `~300ms – 1.2s`
- **Engine**: Direct REST integration supporting **OpenAI (`gpt-4o-mini`)**, **Groq (`llama-3.3-70b-versatile`)**, or custom OpenAI-compatible endpoints.
- **Privacy Model**: API keys are stored strictly on your local disk in `user_profile.json` and are only invoked when you request open-ended reasoning, coding questions, or live web search.
- **Handles**:
  - Complex reasoning (*"explain quantum computing in simple terms"*)
  - Code generation and scripting (*"write a python script to parse csv"*)
  - Real-time weather and public IP queries
  - Live Google web search with automated result summarization

### 🔒 Lane 3: Local LLM Lane (Air-Gapped Privacy)
- **Latency**: `~100ms – 400ms` (depending on local GPU/CPU)
- **Engine**: Fully offline, air-gapped **Ollama** integration running local models like `qwen2.5:0.5b` or `llama3.2`.
- **Privacy Model**: 100% offline. Zero bytes leave your local machine (`127.0.0.1:11434`).
- **Handles**:
  - Offline conversational answers and intent decomposition when internet is disconnected.
  - Automatic fallback if Lane 2 cloud providers fail or time out.

---

## 🔗 Compound Command Planner

The 3-lane classifier returns **one** intent for a whole utterance, so a request
containing several commands used to collapse into a single action — the rest
were silently dropped.

The **Compound Command Planner** (`actions/command_planner.py`) splits a
utterance into ordered clauses and runs each one through the normal 3-lane
path:

```
"mute the volume and open chrome"     -> ["mute the volume", "open chrome"]
"lock the screen, open notepad, and mute audio"
                                      -> ["lock the screen", "open notepad", "mute audio"]
"open chrome, brave, and edge"        -> ["open chrome", "open brave", "open edge"]
```

**How it decides** — English commands are imperative and verb-headed, so a
conjunction only separates two commands when *both* sides read as a command on
their own. This is deterministic, needs no LLM, and works offline.

| Rule | Example | Result |
|------|---------|--------|
| Lead verb | *"search for cats and dogs"* | Not split — `dogs` is not a command |
| Lead verb | *"mute the volume and open chrome"* | Split — both sides are commands |
| Name guard | *"create a folder called Cats and Dogs"* | Not split — `Dogs` is part of the name |
| Browser workflow | *"open chrome and search for X"* | Kept as one browser action (one window, one search) |
| Destructive guard | *"delete tmp and build folders"* | Not split — the `and` belongs to the folder name |

Anything the planner is not certain about returns `None` and is handled as a
single command exactly as before — so ordinary commands are never affected.

**Security**: a sensitive clause (file deletion) is still gated behind the
3-tier security model's voice confirmation, even inside a compound command.
The safe clauses run immediately; the destructive one waits for *"yes"*.

---

## 🎙️ Speech Engine & Wake Word Recognition

PRIVACY68 v1.3.0 features a completely overhauled audio pipeline designed to detect wake words accurately across diverse accents, microphone hardware, and background environments.

### Key Upgrades in v1.3.0:
1. **Phonetic Variations & Aliases**:
   - The engine automatically expands your wake word into phonetic equivalents:
     - *"Privacy 68"*, *"Privacy sixty eight"*, *"Privacy sixty-eight"*, *"Privacy six eight"*, *"Privacy 6 8"*, and digit-separated variations.
2. **2-Gram Multi-Word Fuzzy Matching**:
   - Uses sliding-window multi-word Levenshtein distance with a relaxed 80% similarity threshold. This eliminates missed triggers caused by fast speech or regional accents.
3. **Dynamic Peak Normalization**:
   - Every audio frame is automatically normalized against its peak amplitude before reaching Whisper. Quiet voices and budget microphones trigger with the same consistency as studio microphones.
4. **Decoder Priming & Hotwords**:
   - Whisper's beam search decoder is primed with initial prompts (`config.INITIAL_PROMPT`) to bias token probabilities toward *"Privacy 68"* and technical command terms.

---

## 🔒 Biometric Voice Authentication (Voice Lock)

PRIVACY68 includes an optional, military-grade biometric voice verification system powered by **ECAPA-TDNN / CAM++ neural speaker embeddings** (`speech/voice_auth.py`).

### How It Works:
- Converts human vocal tract characteristics into a **512-dimensional acoustic embedding vector**.
- Whenever a wake word is detected, the captured speech segment is compared against your enrolled voice vector using **Cosine Similarity**:
  $$\text{Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$$

### Voice Enrollment Guide:
1. Open the **PRIVACY68 Dashboard** (Right-click tray icon → *Dashboard*).
2. Navigate to the **Voice Profile / Biometrics** panel.
3. Click **"Enroll Master Voice"**.
4. Speak the 3 verification prompts clearly when prompted:
   - *"Privacy68 is my personal private voice assistant."*
   - *"My voice is my password and my identity."*
   - *"Authorize system command execution."*
5. The system averages the embeddings and saves your encrypted profile to `%APPDATA%\PRIVACY68\voice_lock\`.

### Threshold Calibration:
| Threshold | Security Level | Recommended Use Case |
| :--- | :--- | :--- |
| **0.40 – 0.45** | **Relaxed** | Ideal for noisy environments, users with varying vocal tones, or head colds. |
| **0.50 (Default)** | **Balanced** | Recommended for standard daily use. Rejects casual background voices while reliably passing the owner. |
| **0.65 – 0.75** | **Strict** | High security. Only identical vocal pitch and cadence are authorized. |

*Changes to the threshold take effect dynamically in memory without restarting.*

---

## 🎤 Microphone Setup & Audio Diagnostics

To ensure optimal voice detection and minimal latency, follow these best practices for audio configuration:

### 1. Windows Privacy Permissions
Ensure desktop apps are permitted to access your microphone:
- Open **Windows Settings** (`Win + I`) → **Privacy & Security** → **Microphone**.
- Verify **"Microphone access"** is toggled **ON**.
- Verify **"Let desktop apps access your microphone"** is toggled **ON**.

### 2. Audio Device Selection
In [`config.py`](config.py), PRIVACY68 defaults to the system's default recording device at `16000 Hz Mono`:
```python
SAMPLE_RATE = 16000
BLOCK_SIZE  = 1280    # 80ms audio frames
CHANNELS    = 1
```

### 3. Audio Level Diagnostics
You can verify your microphone levels by running the diagnostic test:
```powershell
python -c "import sounddevice as sd; import numpy as np; data = sd.rec(int(16000*3), samplerate=16000, channels=1, dtype='float32'); sd.wait(); print('Peak:', float(np.max(np.abs(data))), 'RMS:', float(np.sqrt(np.mean(data**2))))"
```
- **Healthy Silence**: `RMS < 0.005`, `Peak < 0.015`
- **Healthy Speech**: `RMS > 0.020`, `Peak > 0.080`

If your microphone is too quiet, increase the recording level in **Windows Sound Control Panel** → **Recording** → **Properties** → **Levels** (set to 80–90%).

---

## 🚀 Hardware Acceleration & Performance Boost

PRIVACY68 is engineered to run seamlessly on both high-end gaming rigs and standard office laptops without requiring manual reconfiguration.

### Automatic Hardware Detection
During startup, [`utils/cuda_manager.py`](utils/cuda_manager.py) inspects your system:
- **If an NVIDIA GPU with CUDA is detected**:
  - Device: `cuda`
  - Quantization: `float16`
  - STT Latency: **~120ms – 160ms**
  - VRAM Consumption: **~1.4 GB**
- **If running on Intel / AMD CPU (Normal PC)**:
  - Device: `cpu`
  - Quantization: `int8` (CTranslate2 optimized AVX2/AVX-512 vector instructions)
  - STT Latency: **~350ms – 600ms**
  - System RAM Consumption: **~1.5 GB**
  - **Zero CUDA drivers or toolkits required!**

### One-Click CUDA Runtime Manager
If you have an NVIDIA GPU but don't have the CUDA 12 toolkit installed:
1. Open the **PRIVACY68 Dashboard**.
2. Click the **CUDA Acceleration** card in the system overview.
3. Click **"Download & Register CUDA 12 Runtime"**.
4. PRIVACY68 automatically downloads the official NVIDIA cuBLAS and cuDNN runtime packages and configures DLL paths without requiring admin reboots.

---

## 🖥️ Complete User Guide & Application Controls

### Launching the Application
- **Executable**: Double-click `PRIVACY68.exe` or launch from the Start Menu.
- **From Source**: Run `python app.py` in your terminal.

### 1. Windows System Tray
Upon launching, PRIVACY68 docks into the Windows Notification Area (System Tray):
- **Left-Click**: Toggle the Dashboard Control Center.
- **Right-Click Context Menu**:
  - **Open Dashboard**: Opens the WebView2 settings and management console.
  - **Toggle Mute / Listening**: Pauses or resumes the audio capture loop.
  - **Reload Plugins**: Hot-reloads all plugins in `plugins/` and `extra_plugins/`.
  - **Exit**: Gracefully shuts down audio threads and background services.

### 2. Floating Neon HUD Overlay
When you speak the wake word, a transparent, click-through HUD overlay appears on your desktop:
- **Cyan Pulse**: Wake word detected; listening for your command.
- **Text Stream**: Real-time transcription display.
- **Green Flash**: Fast-lane command successfully executed.
- **Purple Wave**: AI reasoning lane processing response.
- *Click-through enabled (`WS_EX_TRANSPARENT`)*: The HUD never interrupts gaming, coding, or video playback.

### 3. Mobile Web Remote
Control PRIVACY68 from your phone, tablet, or another laptop on the same local Wi-Fi:
1. Open the Dashboard → **Remote Server**.
2. Scan the displayed **QR Code** with your smartphone camera (or visit `http://<your-pc-ip>:8765`).
3. Speak or type commands directly from the mobile browser interface to control your PC across the room!

---

## ⌨️ Voice Command Reference

Here is a quick cheat sheet of commands supported out-of-the-box:

| Category | Spoken Trigger Example | Execution Lane | Action |
| :--- | :--- | :--- | :--- |
| **System Hardware** | *"Privacy68, mute volume"* | Fast Lane (<2ms) | Sets system master volume to 0% |
| **System Hardware** | *"Privacy68, set volume to 75"* | Fast Lane (<2ms) | Adjusts Win32 audio endpoints |
| **System Hardware** | *"Privacy68, take a screenshot"* | Fast Lane (<2ms) | Captures desktop to Pictures/Screenshots |
| **System Hardware** | *"Privacy68, lock screen"* | Fast Lane (<2ms) | Calls Windows `LockWorkStation` |
| **Applications** | *"Privacy68, open Chrome"* | Fast Lane (<2ms) | Launches Google Chrome |
| **Applications** | *"Privacy68, launch VS Code"* | Fast Lane (<2ms) | Launches Visual Studio Code |
| **Applications** | *"Privacy68, open calculator"* | Fast Lane (<2ms) | Launches Windows Calculator |
| **Websites** | *"Privacy68, open YouTube"* | Fast Lane (<2ms) | Opens `youtube.com` in default browser |
| **Websites** | *"Privacy68, open GitHub"* | Fast Lane (<2ms) | Opens `github.com` in default browser |
| **Windows Settings**| *"Privacy68, open bluetooth settings"* | Fast Lane (<2ms) | Opens `ms-settings:bluetooth` |
| **File Management** | *"Privacy68, open downloads"* | Fast Lane (<2ms) | Opens Downloads folder in File Explorer |
| **Compound Browser**| *"Privacy68, play Believer on YouTube"* | Fast Lane / API | Searches and auto-plays video on YouTube |
| **WhatsApp Desktop**| *"Privacy68, send message to Mom"* | Plugin Lane | Resolves contact alias and opens chat |
| **PowerPoint** | *"Privacy68, next slide"* | Plugin Lane | Sends slide navigation keypress |
| **Live Web Search** | *"Privacy68, search latest news on AI"*| API Lane | Queries DuckDuckGo / Google API |
| **AI Reasoning** | *"Privacy68, how do neural networks work?"* | API / Ollama Lane | Delivers synthesized spoken answer |

---

## 🛠️ Installation & Developer Setup

### Prerequisites
- Windows 10 (Build 1809+) or Windows 11 (64-bit)
- Python 3.10 or 3.11
- *(Optional)* NVIDIA GPU with CUDA 12 drivers
- *(Optional for offline LLM)* [Ollama](https://ollama.ai/) with `qwen2.5:0.5b`

### 1. Clone & Environment Setup
```powershell
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run Tests
Ensure all 77 automated tests pass:
```powershell
python -m unittest discover tests
```
Or with pytest:
```powershell
pytest
```

### 4. Build Standalone EXE
To compile the standalone Windows executable:
```powershell
python build_exe.py
```
Or run the complete two-step build and Inno Setup installer script:
```powershell
.\build.bat
```
`build.bat` also syncs `website/downloads/plugins/` from the canonical plugin
sources so the copies served to users on the website never drift. To sync
manually:
```powershell
python sync_website_plugins.py
```

---

## ⚙️ Configuration Reference (`config.py`)

All key parameters can be customized directly in [`config.py`](config.py):

```python
# Speech-to-Text Model
WHISPER_MODEL_SIZE   = "medium.en"      # tiny.en, base.en, small.en, medium.en
WHISPER_DEVICE       = "cuda"           # "cuda" (GPU) or "cpu" (auto-detected)
WHISPER_COMPUTE_TYPE = "float16"        # "float16" for GPU, "int8" for CPU
WHISPER_BEAM_SIZE    = 8                # Higher beam = better transcription accuracy

# Voice Activity Detection (VAD)
VAD_THRESHOLD        = 0.50             # Silero speech detection threshold (0.0 - 1.0)
VAD_IDLE_THRESHOLD   = 0.30             # Lower threshold for wake word scanning
SILENCE_DURATION_CHUNKS = 8             # 8 chunks * 80ms = 0.64s pause after speech
SILENCE_THRESHOLD    = 0.008            # Noise floor RMS gate

# Initial Prompt for Whisper Priming
INITIAL_PROMPT = (
    "Privacy 68, Privacy68, open chrome, launch vs code, mute volume, "
    "take screenshot, lock screen, open youtube, next track, play music."
)
```

---

## 🛡️ Security & Privacy Commitments
- **Zero Cloud Audio Transmission**: Voice streams never leave your RAM. All STT and biometric verification models run strictly in local memory.
- **Encrypted Local Storage**: Voice biometric vectors and cloud API keys are stored strictly on your local disk under `%APPDATA%\PRIVACY68\`.
- **Open Source & Auditable**: Every line of code, automation hook, and router logic is transparent and freely auditable under the MIT License.

---

*Crafted with precision for private, instant, and autonomous Windows intelligence.*
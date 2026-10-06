# Software Requirements Specification (SRS)
## For
# PRIVACY68: Autonomous Offline Voice Assistant & Computer-Use Automation System

**Prepared by:** Adarsh M S  
**USN:** 4JK25MC003  
**Project Guide:** Dr. Bruce Mathew  
**Course:** Master of Computer Applications (MCA)  
**Date:** 05/10/2026  
**Academic Year:** 2026–2027  
**Document Standard:** IEEE Std 830-1998 / ML & Autonomous Systems Reference Format  

---

## Contents
1. **INTRODUCTION**  
   - 1.1 Purpose  
   - 1.2 Intended Audience  
   - 1.3 Scope  
   - 1.4 References  
2. **OVERALL DESCRIPTION**  
   - 2.1 Product Perspective  
   - 2.2 Product Functions  
   - 2.3 User Classes and Characteristics  
   - 2.4 Operating Environment  
   - 2.5 Design and Implementation Constraints  
   - 2.6 Assumptions and Dependencies  
3. **SPECIFIC REQUIREMENTS**  
   - 3.1 Data Requirements  
   - 3.2 Functional Requirements (FR-01 to FR-18)  
   - 3.3 Performance and AI/ML Quality Requirements  
   - 3.4 External Interface Requirements  
   - 3.5 Security, Safety, and Privacy Requirements  
4. **APPENDICES**  
   - 4.1 Glossary  
   - 4.2 System Data Schemas & Architecture Pipeline  

---

## 1. Introduction

### 1.1 Purpose
The purpose of this Software Requirements Specification (SRS) is to define the requirements of **PRIVACY68**, an autonomous, privacy-first desktop voice assistant and Windows computer-use automation system.

The system is designed to provide 100% offline edge-AI voice recognition, biometric speaker authentication ("Voice Lock"), dual-lane command routing (Deterministic Fast Lane + Local LLM Tool Calling), and native Windows UI Automation (UIA) to execute desktop tasks without relying on external cloud APIs or transmitting private user data over the internet.

### 1.2 Intended Audience
The intended audience of this document includes:
- Project guide, faculty members, and MCA academic evaluators.
- Machine learning and Edge-AI developers.
- Windows desktop software and automation developers.
- Users seeking hands-free, privacy-preserving desktop accessibility.
- Future developers extending the modular plugin system.

### 1.3 Scope
**PRIVACY68** provides a comprehensive platform for offline voice assistance and deep operating system automation on Windows. 

The system supports:
- Edge-based real-time speech transcription via quantized neural models (`Faster-Whisper`).
- 256-dimensional neural voiceprint embedding verification for biometric anti-spoofing.
- Dual-Lane hybrid routing architecture:
  - **Lane 1 (Deterministic Fast Lane)**: Sub-5ms regex dispatch for critical OS utilities.
  - **Lane 2 (Local LLM Tool-Calling Lane)**: Contextual intent extraction and plugin action invocation via local Ollama models (`Qwen2.5` / `Llama3.2`).
- Deep Windows UI Automation (UIA) with pattern support (`TogglePattern`, `RangeValuePattern`, `SelectionItemPattern`, `ExpandCollapsePattern`, and `ScrollPattern`).
- Hot-reloadable modular plugin system for applications including Browsers (Chrome, Brave), Developer Tools (VS Code), Productivity Suites (PowerPoint, Notepad), and Messaging (WhatsApp Desktop).
- Local-network mobile web remote controller and desktop dashboard GUI.

### 1.4 References
1. **Faster-Whisper / CTranslate2**: Efficient Transformer inference on CPU/CUDA for Whisper models.
2. **Speaker Verification**: D. Snyder et al., *"X-vectors: Robust DNN Embeddings for Speaker Recognition,"* IEEE ICASSP.
3. **Microsoft UI Automation (UIA)**: Windows Accessibility API Architecture & Pattern Specifications.
4. **Ollama & Function Calling**: Tool-calling schema protocols for local small language models (SLMs).
5. **Silero VAD**: Enterprise-grade Voice Activity Detection for real-time audio chunk segmentation.

---

## 2. Overall Description

### 2.1 Product Perspective
**PRIVACY68** is a self-contained desktop application integrating a frontend dashboard, an asynchronous Python backend, offline neural speech models, an OS-level UIA automation engine, and a local LAN server.

| Component | Technology Stack / Responsibility |
| :--- | :--- |
| **Voice Ingestion & VAD** | PyAudio, SoundDevice, Silero VAD |
| **Speech-to-Text (STT)** | Faster-Whisper (quantized int8/float16 CPU/CUDA) |
| **Biometric Voice Lock** | Resemblyzer / ECAPA-TDNN (256-d Cosine Metric on ONNX) |
| **Hybrid Intent Dispatcher** | Deterministic Fast Lane (Regex) + Local LLM (Ollama Tool Calling) |
| **OS & UI Automation Engine** | Native Windows UIA (`pywinauto` backend), Win32 API, ctypes |
| **Desktop Control Center** | PyWebView, TailwindCSS, Modern HTML5 / JavaScript |
| **Mobile LAN Remote** | FastAPI, WebSocket, Uvicorn |

```
Microphone Audio Stream
          │
          ▼
   [ Silero VAD ] ──► Voice Ingestion (16kHz Mono)
          │
          ▼
 [ Voice Lock Biometrics ] ──► Cosine Similarity >= Threshold?
          │ (Authorized)
          ▼
  [ Faster-Whisper STT ] ──► Transcribed Command String
          │
          ├──────────────────────────────┐
          ▼                              ▼
  [ Lane 1: Fast Lane ]        [ Lane 2: Local LLM Lane ]
  (Regex < 5ms Deterministic)   (Ollama Function/Tool Calling)
          │                              │
          └──────────────┬───────────────┘
                         ▼
             [ Windows UIA Stack ]
   (Toggle, Slider, TabSelect, Scroll, Click)
                         │
                         ▼
        Target Desktop Application / OS State
```

### 2.2 Product Functions
The major functions of PRIVACY68 are:
1. **Continuous Voice Ingestion**: Real-time microphone listening with voice activity detection.
2. **Biometric Speaker Authentication**: Enrolls a 3-sample master voiceprint; rejects foreign speakers and background noise.
3. **Speech Transcription**: Offline neural audio-to-text inference.
4. **Deterministic Fast-Lane Execution**: Instant resolution for window states, volume, media, app launching, and system settings.
5. **Local LLM Tool Routing**: Natural-language parameter extraction and plugin action resolution using Ollama function-calling.
6. **Windows UI Automation (UIA)**: Resolution-independent control over toggles, sliders, tab bars, dropdowns, and menus.
7. **Modular Plugin Architecture**: Hot-reloading of built-in and user-defined Python plugins from `%APPDATA%/PRIVACY68/plugins/`.
8. **Control Center Dashboard**: GUI for visual voice enrollment, sensitivity calibration, and plugin management.
9. **Mobile Remote Controller**: Web-based LAN dashboard for wireless smartphone control.

### 2.3 User Classes and Characteristics

| User Class | Characteristics / Responsibilities |
| :--- | :--- |
| **Owner / Master User** | Enrolls voice profile, configures wake words and thresholds, manages plugins, and executes system automations. |
| **Unverified Speaker** | Any unregistered voice speaking to the microphone; blocked automatically by the Voice Lock biometrics filter. |
| **Plugin Developer** | Creates custom `.py` plugins inheriting from `BasePlugin` to automate third-party software. |

### 2.4 Operating Environment

| Category | Requirement |
| :--- | :--- |
| **Operating System** | Windows 10 or Windows 11 (64-bit) |
| **Hardware** | Intel Core i5 / AMD Ryzen 5 or higher, 8 GB RAM (16 GB recommended), microphone |
| **Optional Accelerators** | NVIDIA GPU with CUDA 11.8+ for real-time acceleration |
| **Programming** | Python 3.10 / 3.11, JavaScript, HTML5, CSS3 |
| **AI / ML Models** | Silero VAD, Faster-Whisper (`small.en`/`base.en`), ECAPA-TDNN ONNX, Ollama (`qwen2.5:0.5b`) |
| **Desktop Shell** | PyWebView, MSHTML/Chromium embedded webview |

### 2.5 Design and Implementation Constraints
- **100% Offline Operation**: Zero dependencies on cloud servers or external speech APIs.
- **Resolution Independence**: Automation must not rely on fixed coordinate screen clicking.
- **Latency Budget**: Fast-lane system actions must execute in under 5ms.
- **Local Resource Footprint**: Whisper and LLM models must run smoothly on consumer hardware.

### 2.6 Assumptions and Dependencies
- The host system has a functional audio capture input device.
- Windows UI Automation service is active and responsive.
- Ollama local server is installed and running on `localhost:11434` for Lane 2 LLM requests.
- The user enrolls their voice profile during initial setup before enabling Voice Lock.

---

## 3. Specific Requirements

### 3.1 Data Requirements

#### 3.1.1 Audio Ingestion Data
- 16,000 Hz sample rate, 16-bit PCM mono audio buffers.
- VAD chunk frames with configurable sensitivity threshold (0.20 to 0.80).

#### 3.1.2 Biometric Data
- 256-dimensional floating-point speaker embedding vectors.
- Centroid calculation across 3 distinct enrollment audio recordings.

#### 3.1.3 Configuration Profile Data
- User preferences stored in `%APPDATA%/PRIVACY68/profile.json` (wake word, thresholds, models, enabled plugins).

#### 3.1.4 Plugin Tool Schemas
- Dynamic Hermes/JSON function-calling schema definitions generated at runtime from enabled plugins.

---

### 3.2 Functional Requirements

| Requirement ID | Module | Description |
| :--- | :--- | :--- |
| **FR-01** | **VAD & Streaming** | The system shall continuously monitor audio input and segment speech frames using Silero VAD with zero cloud streaming. |
| **FR-02** | **Voice Lock Enrollment** | The system shall capture 3 vocal enrollment samples to compute a normalized master speaker centroid embedding. |
| **FR-03** | **Speaker Verification** | The system shall compute the cosine similarity between the incoming speech embedding and the master profile, rejecting similarity scores below the configured threshold (default: 0.50). |
| **FR-04** | **Speech-to-Text** | The system shall transcribe authenticated voice utterances into text using Faster-Whisper. |
| **FR-05** | **Fast-Lane Matching** | The system shall match deterministic system commands (volume, window management, app launch, screenshot, power) using regex in < 5ms. |
| **FR-06** | **LLM Tool Routing** | Unmatched or compound voice queries shall be converted to structured tool calls via local Ollama models with system schema injection. |
| **FR-07** | **UIA Element Discovery** | The system shall dynamically locate controls in the active foreground window accessibility tree by `Name`, `ControlType`, and `AutomationId`. |
| **FR-08** | **UIA Pattern Invocation** | The system shall support `TogglePattern`, `RangeValuePattern`, `SelectionItemPattern`, `ExpandCollapsePattern`, and `ScrollPattern`. |
| **FR-09** | **Fallback Clicking** | If an application element does not implement native invoke patterns, the system shall compute its bounding box center `(cx, cy)` and dispatch a hardware click. |
| **FR-10** | **App Launcher** | The system shall resolve application aliases and launch desktop programs via Windows Registry `App Paths`, `PATH`, and Start Menu shortcuts. |
| **FR-11** | **Plugin Loader** | The system shall automatically discover, register, and instantiate plugins inheriting from `BasePlugin` in both built-in and AppData directories. |
| **FR-12** | **Hot-Reloading** | The system shall support runtime enabling, disabling, and installing of plugins without application restart. |
| **FR-13** | **Browser Automation** | The system shall control Google Chrome and Brave (new tab, close tab, reopen tab, web search, incognito). |
| **FR-14** | **Developer Tool Automation** | The system shall automate Visual Studio Code (terminal toggle, sidebar navigation, code formatting, debugging, git). |
| **FR-15** | **Office & Slides Control** | The system shall control PowerPoint slide transitions, laser pointer mode, and jump to specific slide numbers hands-free. |
| **FR-16** | **Messaging Control** | The system shall automate WhatsApp Desktop, resolving spoken contacts via fuzzy matching and drafting voice messages. |
| **FR-17** | **Control Center UI** | The system shall provide a native PyWebView dashboard displaying system health, live mic waveform, voice enrollment, and categorized plugin filters. |
| **FR-18** | **LAN Mobile Remote** | The system shall host a password-protected local HTTP/WebSocket server allowing mobile browser remote control over Wi-Fi. |

---

### 3.3 Performance and AI/ML Quality Requirements

| Metric | Target Specification | Purpose |
| :--- | :--- | :--- |
| **Fast Lane Latency** | **< 5 ms** | Instant deterministic command execution. |
| **Whisper Transcription Latency** | **< 400 ms** (int8 CPU) / **< 150 ms** (CUDA) | Near real-time speech recognition. |
| **Voice Lock False Acceptance Rate (FAR)** | **< 2.5%** (at 0.65 threshold) | Prevents unauthorized foreign speakers from issuing commands. |
| **Voice Lock False Rejection Rate (FRR)** | **< 4.0%** (at 0.50 threshold) | Minimizes friction for the enrolled owner. |
| **LLM Routing Accuracy** | **> 94.0%** on complex queries | Ensures correct tool selection from available plugin schemas. |
| **UI Automation Resolution** | **100% Resolution Independent** | Functions consistently across 100%, 125%, 150%, and 200% DPI scaling. |

---

### 3.4 External Interface Requirements

#### 3.4.1 User Interfaces
- **Desktop Control Center (`index.html`)**: Dark-mode glassmorphic dashboard with category filter tabs (System, Browser, Messaging, Dev Tools, Productivity, Custom).
- **Voice Calibration Visualizer**: Waveform canvas and real-time audio energy meter.
- **Mobile Remote Web UI**: Touch-optimized interface for smartphone browsers on the local network.

#### 3.4.2 Software Interfaces
| Interface | Protocol / Binding | Description |
| :--- | :--- | :--- |
| **Python ↔ Ollama** | REST HTTP (`127.0.0.1:11434`) | Local LLM inference and tool calling. |
| **Python ↔ PyWinAuto / UIA** | Native Windows COM / Ctypes | Access to the Windows UI Automation tree. |
| **Python ↔ PyWebView** | IPC JS API Bridge | Two-way communication between Python backend and dashboard UI. |
| **FastAPI ↔ Mobile Web** | HTTP / WebSocket | Real-time command streaming from smartphone browser. |

---

### 3.5 Security, Safety, and Privacy Requirements
1. **Zero External Data Transmission**: No voice audio, transcriptions, or credentials leave the host machine.
2. **Encrypted Voiceprint Storage**: Neural embeddings are stored as raw floating-point vectors without invertible audio reconstruction capability.
3. **Execution Guardrails**: Critical system actions (disk cleanup, task killing) enforce explicit confirmation.
4. **Local Network Isolation**: The mobile remote server binds strictly to local IPv4 interfaces (`192.168.x.x` / `127.0.0.1`) with origin validation.

---

## 4. Appendices

### 4.1 Glossary

| Term | Meaning |
| :--- | :--- |
| **VAD** | Voice Activity Detection (separates speech from silence) |
| **STT** | Speech-to-Text (neural acoustic model) |
| **UIA** | Microsoft Windows UI Automation Accessibility Framework |
| **LLM** | Large Language Model (local SLM/LLM for tool calling) |
| **Embedding** | 256-dimensional numerical vector capturing biometric vocal tract features |
| **Fast Lane** | High-speed regex pattern matcher for zero-latency execution |
| **FAR** | False Acceptance Rate |
| **FRR** | False Rejection Rate |

### 4.2 System Configuration Schema

```json
{
  "user_name": "Adarsh",
  "assistant_name": "Privacy68",
  "wake_word": "Alexa",
  "whisper_model": "small.en",
  "wake_threshold": 0.50,
  "voice_lock_enabled": true,
  "voice_lock_threshold": 0.55,
  "llm_model": "qwen2.5:0.5b",
  "plugins_enabled": {
    "system": true,
    "windows": true,
    "chrome": true,
    "brave": true,
    "vscode": true,
    "whatsapp": true,
    "ppt": true
  }
}
```


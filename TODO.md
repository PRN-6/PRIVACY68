# 📋 PRIVACY68 Feature Roadmap & TO-DO List

This document outlines the planned improvements, bug fixes, new plugins, and architectural upgrades for the **PRIVACY68** project.

---

## 🔴 1. Immediate Fixes & High Priority

- [x] **Fix WhatsApp Launch Mechanism & Contact Manager (`whatsapp_plugin.py`)**
  - Robust fallback sequence: Windows Store UWP Package (`shell:AppsFolder`) $\rightarrow$ Standalone EXE (`WhatsApp.exe`) $\rightarrow$ Protocol URI (`whatsapp:`) $\rightarrow$ WhatsApp Web in browser (`https://web.whatsapp.com`).
  - Contact Manager Modal in Dashboard allows adding named contacts with nicknames/aliases and fuzzy matching (`_resolve_contact`) so spoken commands accurately match real WhatsApp chat names.
- [ ] **Text-To-Speech (TTS) Voice Responses**
  - Add offline, low-latency TTS (e.g., `pyttsx3`, `edge-tts`, or `piper-tts`) so Privacy68 can speak back to confirm actions (e.g., *"Opening Chrome"*, *"Volume set to 50%"*).
- [x] **Silero VAD Neural Network Integration**
  - Replace simple energy/RMS thresholding with **Silero VAD (ONNX)** for enterprise-grade speech segmentation.
  - Eliminates false triggers from breathing, keyboard clicks, and background fans while cutting latency when you stop speaking.
- [ ] **Wake-Word Sensitivity & Noise Calibration**
  - Add an automatic ambient noise calibration step on startup to dynamically adjust `SILENCE_THRESHOLD`.
- [ ] **Custom User Wake-Word & Activation Phrases**
  - Allow users to set custom wake words (e.g., *"Hey Jarvis"*, *"Computer"*, *"Hey Privacy68"*, *"Friday"*) via UI settings or config.
  - Support custom regex patterns, phonetic alias expansion, and configurable sensitivity for user-defined awake call commands.
- [x] **Speaker Recognition & Voice Biometrics (Owner-Only Voice Lock)**
  - Integrated SOTA ECAPA-TDNN 512-d (192-d embedding) ONNX model with full Kaldi 80-channel filterbank and CMVN.
  - Energy-based voice activity trimming (`trim_speech`) strips silence from audio so verification evaluates purely vocal tract characteristics.
  - Verification threshold set at `0.65` (owner scores `0.85-0.95`, others score `< 0.45`).
  - Dynamic disk profile reload and secure rejection when no profile is enrolled.
- [x] **Wake-Word & Conversational Command Pipeline**
  - Continuous two-step speech support: saying `"Alexa"` acknowledges the wake word and maintains active listening for 7 seconds so the user can speak their command without getting cut off.
  - Seamless audio buffer handover preserves inline one-breath commands (`"Alexa, open PowerPoint"`).


---

## 🧩 2. New Plugins & Automation Skills

### 🎵 Media & Entertainment
- [ ] **Spotify Plugin (`spotify_plugin.py`)**
  - Commands: *"Play/Pause"*, *"Next track"*, *"Previous track"*, *"Play [song name]"*.
  - Use Windows Media keys or Spotify Local/Web API.
- [ ] **YouTube Direct Search Plugin**
  - Commands: *"Search YouTube for [topic]"*, *"Play lo-fi music on YouTube"*.
  - Auto-open direct search URL and focus video player.

### 💻 System Controls & Utilities
- [ ] **Volume & Brightness Controller**
  - Commands: *"Set volume to 80%"*, *"Mute audio"*, *"Increase brightness"*.
  - Use `pycaw` (Python Core Audio Windows) and `screen-brightness-control`.
- [ ] **Screenshot & Screen Recording Utility**
  - Commands: *"Take a screenshot"*, *"Capture active window"*.
  - Save directly to `%USERPROFILE%/Pictures/Screenshots` and copy to clipboard.
- [ ] **System Health & Battery Stats**
  - Commands: *"Check battery percentage"*, *"How is CPU usage?"*, *"Check available RAM"*.
  - Use `psutil` to query battery and hardware stats.
- [ ] **Windows Window Management**
  - Commands: *"Minimize all windows"*, *"Snap window to left/right"*, *"Switch to next desktop"*, *"Lock computer"*.
- [ ] **Virtual Desktop & Multi-Monitor Workspace Automation (`virtual_desktop_plugin.py`)**
  - Commands: *"Open Chrome in Desktop 2 and search for YouTube"*, *"Move active window to Desktop 2"*, *"Open Spotify on Monitor 2 in background"*.
  - Integrate `pyvda` (Python Virtual Desktop Accessor) to move launched app windows to target Virtual Desktops (e.g., Desktop 2/3) silently without switching the user's active screen.
  - Multi-monitor support: Use Win32 API (`SetWindowPos` with `SWP_NOACTIVATE`) to launch windows onto secondary monitors without stealing window focus.

### 📝 Productivity & Office
- [ ] **Notepad / Quick Notes Plugin (`notepad_plugin.py`)**
  - Integrate user-created Notepad plugin into main release with note-taking support: *"Take note: meeting at 3 PM"*.
- [ ] **Clipboard Manager**
  - Commands: *"Read clipboard"*, *"Clear clipboard"*, *"Save clipboard to notes"*.
- [ ] **Smart Calculator & Unit Converter**
  - Commands: *"What is 15% of 450?"*, *"Convert 50 USD to INR"*, *"What is 100 kilometers in miles?"*.

---

## 🖐️ 3. Multimodal Computer Vision (Hand Gesture Engine)

- [ ] **Real-Time Hand Landmark Tracking (`gesture_service.py`)**
  - Integrate **Google MediaPipe Hands** + **OpenCV** running on CPU (30–60 FPS) with negligible compute overhead.
  - Add optional toggle via voice (*"Privacy68, enable/disable gesture mode"*) or hotkey to conserve resources when camera is unneeded.
- [ ] **Air Gesture Controls:**
  - ✋ **Open Palm $\rightarrow$ ✊ Fist:** Play / Pause active media.
  - 🤏 **Thumb-Index Pinch & Move:** Continuous smooth system volume adjustment.
  - 👈 / 👉 **Horizontal Air Swipe:** Switch active browser tabs or virtual desktops.
  - ✌️ **Two Fingers Point Up/Down:** Smooth document / webpage scrolling.
  - 🤫 **Index Finger to Lips:** Instant audio mute / put Privacy68 to sleep.
- [ ] **HUD Gesture Feedback Overlay:**
  - Display subtle hand tracking skeleton or visual icon on the floating HUD when camera mode is engaged.

---

## 🧠 4. AI & Natural Language Processing (NLP)

- [ ] **Conversation Context & Multi-turn Memory**
  - Remember previous context (e.g., User: *"Search for Paris"*, then: *"What is the weather there?"*).
- [ ] **Live Streaming LLM Responses in HUD**
  - Stream tokens from local Ollama LLM directly onto the floating HUD canvas in real time instead of waiting for full response.
- [ ] **Custom System Prompt Profiles**
  - Allow users to choose AI personality / speed mode (e.g., *Fast Desktop Assistant* vs. *In-depth Conversational Assistant*).

---

## 🎨 5. UI / UX & Web / Audio Presentation

- [ ] **Website Redesign with Tailwind CSS (`website/`)**
  - Refactor custom `styles.css` to Tailwind CSS for modern utility styling, responsive design, and enhanced animations.
- [ ] **Floating HUD Polish & Customization**
  - Add customizable themes (Cyberpunk Neon, Glassmorphism Dark, Minimalist Light).
  - Add adjustable HUD positioning (Top-Center, Bottom-Right, Draggable).
- [ ] **Sound Effects Pack**
  - High-tech audio chimes for: Wake-up, Command Recognized, Action Completed, and Error.
- [ ] **Visualizer Waveform Improvements**
  - Smooth 60 FPS sine-wave or frequency bar visualizer during active listening.

---

## 📦 6. Deployment, Packaging & Distribution

- [ ] **Start with Windows (Auto-Start)**
  - Add optional toggle in System Tray to launch Privacy68 automatically on Windows boot.
- [ ] **Standalone One-Click Installer**
  - Build signed `.exe` installer using `PyInstaller` and `Inno Setup` bundling CUDA DLLs and default models.
- [ ] **Automatic Dependency & Model Downloader**
  - On first run, check if Ollama is running and automatically pull `qwen2.5:0.5b` if missing.


---

## 📱 7. Privacy68 Mobile — Android AI Assistant

> Internet-connected mobile companion to Privacy68 PC. Uses Privacy68's PC as the AI brain over WiFi/mobile data, with on-device fallback for basic offline commands.

### 🏗️ Architecture
- **Online mode:** Android app streams mic audio → Privacy68 PC WebSocket server → Whisper `small.en` transcribes → response sent back → phone executes command
- **Offline mode:** On-device Whisper tiny/base model (ONNX via Whisper.cpp JNI) for basic commands without internet

### 📋 Tasks
- [ ] **Add WebSocket Server to Privacy68 PC (`server/ws_server.py`)**
  - Accept audio stream from Android client over LAN/internet
  - Transcribe using existing Whisper pipeline and return text result
  - Accept remote command execution requests from Android
- [ ] **Android App — Core (`app/`)** *(Kotlin, Android Studio)*
  - Microphone recording and streaming
  - Wake word detection on-device (tiny Whisper ONNX)
  - Connect to Privacy68 PC WebSocket server
  - Floating overlay HUD (like Privacy68's desktop HUD)
- [ ] **Android App — Phone Control**
  - Open apps via Android Intents (*"Open WhatsApp"*, *"Open YouTube"*)
  - Send WhatsApp messages via Intents
  - Control volume, brightness, flashlight
  - Read notifications aloud via Accessibility Service
- [ ] **Android App — Remote PC Control**
  - Send commands to Privacy68 PC over WebSocket (*"Open Chrome on PC"*, *"Lock PC"*)
  - View PC status from phone (CPU, RAM, Privacy68 active/sleeping)
- [ ] **Offline / Online Auto-Switch**
  - Detect internet/LAN availability and seamlessly switch between on-device and PC-powered AI
- [ ] **Android App — UI**
  - Material You design with animated waveform visualizer
  - Dark mode floating assistant overlay

---

## 📅 Roadmap Milestones

| Milestone | Target | Description |
| :--- | :--- | :--- |
| **v1.1** | *Core Polish* | Fix WhatsApp launcher, add pyttsx3 voice feedback, Silero VAD integration, Speaker Recognition (Voice Lock). |
| **v1.2** | *Media & System* | Spotify plugin, Volume/Brightness controls, Screenshot tool. |
| **v1.3** | *Vision Multimodal* | MediaPipe hand gestures (Air swipe, Pinch volume, Play/Pause). |
| **v1.4** | *Intelligence* | Multi-turn conversation memory, streaming HUD text. |
| **v2.0** | *Production Release* | Complete Inno Setup installer with Auto-start and settings GUI. |
| **v3.0** | *Mobile Expansion* | Privacy68 Android app — voice control for phone + remote PC control over internet. |




in the plugin of the whatsapp make a new window for it when they click the whatsapp plugin to configure it then can add their whatsapp contacts in the plugin so that the acuracy of the name when we say open whatsapp and send message to prinson it can detect the chat correctly can we do this?



rerun issun after new voice

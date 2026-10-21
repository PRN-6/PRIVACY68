# 📋 PRIVACY68 Changelog

All notable changes to PRIVACY68 are documented here.
Versioning follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.

---

## [v1.4.1] — 2026-10-21

### ✨ New Features & Improvements

#### 🪟 App-Context Command Routing (`computer_use/app_focus.py`, `actions/fast_lane.py`)
- **Active App Window Context Awareness**: Fast Lane commands automatically resolve context and target the active foreground application (e.g. Chrome, WhatsApp, VS Code, Notepad).
- **Targeted Application Actions**: Context-aware routing for actions like closing tabs, navigating, search, and message sending directly mapped to the currently active application.

#### 💬 Enhanced WhatsApp Desktop Automation (`extra_plugins/whatsapp_plugin.py`, `plugins/base_plugin.py`)
- **Robust Message Automation**: Extended WhatsApp Desktop plugin with improved contact resolution, UI navigation, and message dispatch.
- **Enhanced Plugin Base & Manager**: Improved plugin management lifecycle and hook callbacks.

#### 🔗 Compound Command Planner (`actions/planner.py`)
- **Multi-Command Parsing**: Seamlessly plan and execute multi-intent composite voice utterances sequentially.

---

## [v1.4.0] — 2026-10-19

### ✨ New Features & Ecosystem Upgrades

#### 🔌 Dynamic Plugin Architecture & Hot-Reload (`plugins/manager.py`, `ui/dashboard_bridge.py`)
- **Runtime Plugin Hot-Reload**: Install, enable, disable, and reload plugins dynamically without restarting the assistant.
- **Robust External Plugin Resolution**: Added `sys.path` and `sys.modules` aliasing with MRO-based `BasePlugin` resolution to seamlessly support third-party and custom marketplace plugins.
- **Enhanced Built-In & Marketplace Plugins**: Updated plugins for Google Chrome, Brave, WhatsApp Desktop, GitHub Manager, Notepad, VS Code, and PowerPoint with rich keyboard and window automation.

#### 🛠️ Antigravity IDE Automation & Developer Tools (`computer_use/dev_tools.py`, `actions/executor.py`)
- **Automated IDE DevTools**: Intelligent window detection, foreground elevation, and native terminal execution for Antigravity IDE and VS Code.
- **Voice-Triggered Git Workflow**: Dedicated voice automation to launch terminal sessions, stage, commit, and push changes to GitHub directly from voice command (`"push to GitHub"`).

#### 🎙️ Dynamic Wake Word Engine & Profile Reload (`speech/streamer.py`, `plugins/profile_manager.py`)
- **Dynamic Wake Word Switching**: Switch active wake words (`Jarvis`, `Privacy68`, `Alexa`, `Nova`, `Friday`, etc.) dynamically via dashboard configuration without restarting the application.
- **Phonetic Alias Expansion**: Added comprehensive phonetic alias matching for Jarvis and voice commands to eliminate transcription variances in noisy environments.

---

## [v1.3.0] — 2026-10-18

### ✨ New Features & Architecture Upgrades

#### ⚡ 3-Lane Command Architecture (`actions/router.py`, `actions/fast_lane.py`, `actions/api_lane.py`)
- **Fast Lane (Deterministic)**: 100% local, zero-latency execution for all known system commands, application automations, and media controls without contacting an LLM.
- **API Lane (Cloud Reasoning)**: Fast cloud intelligence using OpenAI or Groq when complex questions, coding tasks, or open-ended reasoning are requested.
- **Local LLM Lane (Private Fallback)**: Full offline privacy via local Ollama models with automatic fallback.

#### 🎯 ML Intent Classification & Parameter Extraction (`actions/intent_classifier.py`, `actions/param_extractor.py`)
- Dedicated machine-learning intent classification pipeline with unified command mapping.
- Dedicated parameter extractor trained to 100% accuracy on standard system entities (applications, URLs, paths, numbers).
- Drastically streamlined Fast Lane codebase (-640 lines of brittle regex) in favor of high-speed vector models.

#### 🎙️ Robust Wake Word & Speech-to-Text (`speech/streamer.py`, `config.py`)
- **Phonetic Alias Matching**: Broad phonetic coverage for *"Privacy 68"*, *"Privacy sixty eight"*, *"Privacy six eight"*, *"Privacy 6 8"*, and digit-separated variations.
- **2-Gram Multi-Word Fuzzy Matching**: Accommodates natural speaking cadence, varied accents, and different microphone responses.
- **Audio Pre-processing Upgrades**: Audio peak normalization, lowered idle-scan RMS threshold (from 0.018 to 0.005), and relaxed VAD gating ensure quiet or low-gain microphones trigger reliably.
- **Whisper Decoder Priming**: Expanded hotwords and initial prompts to prevent Whisper from dropping numeric/alphabetic variations.

#### 📱 Mobile Web Remote Server (`server/remote_server.py`)
- Built-in lightweight local web remote allowing mobile devices on the same Wi-Fi network to control PRIVACY68 with QR code pairing.

---

## [v1.2.0] — 2026-10-12

### ✨ New Features

#### ☁️ Cloud LLM API Support (`actions/router.py`)
- **OpenAI, Groq, and Custom API providers** are now first-class citizens alongside local Ollama.
- The `LLMRouter` auto-selects the routing path based on the user's saved `llm_provider` and `api_key` settings.
- Cloud route implements an **OpenAI-compatible REST client** (no SDK dependency) with a hard 8-second timeout and graceful Ollama fallback if the cloud call fails.
- Supported cloud models out of the box: `gpt-4o-mini` (OpenAI), `llama-3.3-70b-versatile` (Groq), and any custom OpenAI-compatible endpoint.

#### 🎙️ Enhanced Voice Detection & Speaker Verification (`speech/voice_auth.py`)
- Upgraded ECAPA-TDNN voice biometrics model with improved Kaldi 80-channel filterbank.
- Tightened energy-based `trim_speech` pre-processing to strip silence before embedding extraction.
- Verification threshold tuning: owner scores `0.85–0.95`; rejection fires at `< 0.45`.
- Dynamic disk-profile reload — profile changes in the dashboard take effect immediately without restart.

#### 📱 WhatsApp Contact Manager (`ui/dashboard/index.html`, `ui/dashboard_bridge.py`)
- New **Contact Manager** panel in the Dashboard for the WhatsApp plugin.
- Add named contacts with display name, phone number, and spoken aliases.
- Fuzzy matching (`_resolve_contact`) now maps natural speech (e.g., *"send message to mom"*) to the correct WhatsApp chat name with high accuracy.

#### 🔌 LLM & API Settings in Dashboard
- New **AI Provider selector** in Settings: Local Ollama / OpenAI / Groq / Custom.
- API Key, Base URL, and cloud model fields — with a live **Test Connection** button.
- API key is stored locally in `user_profile.json` (never transmitted unless you use cloud providers).

### 🐛 Bug Fixes
- Fixed `LLMRouter.reload()` not respecting disabled plugins when building the tool name map.
- Fixed `profile_manager.py` race condition on concurrent settings saves from the dashboard.
- Voice enrollment via the Dashboard now shares the exact same audio path as live verification.

### 🧪 Tests Added
- `tests/test_cloud_llm_router.py` — unit tests for OpenAI & Groq cloud routing paths.
- `tests/test_voice_auth_unit.py` — unit tests for ECAPA-TDNN embedding extraction and cosine similarity verification.

### 📦 Build & Distribution
- **`build.bat`** upgraded to a full two-step release pipeline: PyInstaller EXE then Inno Setup installer.
- Inno Setup step is auto-skipped gracefully if ISCC.exe is not installed.
- **`build_exe.py`** now carries `APP_VERSION = "1.2.0"` and auto-includes `version_info.txt` for Windows EXE metadata if present.
- `installer.iss` updated to output `PRIVACY68-Setup-v1.2.0.exe`.

---

## [v1.1.0] — 2026-10-05

### ✨ New Features
- Silero VAD neural voice activity detection replaces RMS energy thresholding.
- Speaker Recognition & Voice Biometrics (Owner-Only Voice Lock) with ECAPA-TDNN.
- Two-step conversational wake word pipeline: *"Alexa"* triggers 7-second active listening window.
- WhatsApp launch mechanism with UWP -> Standalone EXE -> Protocol URI -> Web fallback chain.
- Mobile Web Remote: WebSocket server for controlling PRIVACY68 from a phone browser.
- NVIDIA CUDA runtime on-demand downloader (no bundled DLLs required in slim build).
- Control Center Dashboard (WebView2) with plugin management, voice lock, and diagnostics.

### 📦 Build
- PyInstaller `.spec` and `build_exe.py` with optional `--bundle-cuda` flag.
- Inno Setup `installer.iss` for a one-click Windows installer.

---

## [v1.0.0] — 2026-09-20

- Initial public release.
- Faster-Whisper ASR, wake word detection, System Tray, and Floating HUD overlay.
- Plugin system with Chrome, WhatsApp, VS Code, and PowerPoint plugins.
- Fast Lane deterministic Windows automation (< 5 ms, zero LLM overhead).
- Ollama integration for AI intent routing (qwen2.5:0.5b).

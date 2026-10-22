# 📋 PRIVACY68 Changelog

All notable changes to PRIVACY68 are documented here.
Versioning follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.

---

## [Unreleased]

### 🧭 Application discovery: the assistant knows what is installed

Before, only a hard-coded list of application names could be opened by voice,
and everything else needed a plugin. Now the assistant finds out for itself
what is on the computer.

- **New `core/apps.py`** — an index of the installed applications:
  - Linux: the freedesktop `.desktop` entries (system, user, Flatpak, Snap)
    plus every executable on `PATH`
  - Windows: the `App Paths` registry keys and the Start Menu shortcuts
  - macOS: the `.app` bundles of the Applications folders
- **`app.py`** indexes the machine at startup and hands the names to the
  command catalogue, so *"open <anything that is installed>"* works by voice.
- **`actions/catalog.py`** merges those names into the existing application
  command — one intent keeps one owner, so the taxonomy never forks.
- **`core/apps.py` → `command_for()`** resolves an application to a real
  command line, which is what the browser plugins now use to start Chrome
  and Brave on any operating system.
- **The Control Center** gained an **Applications** tab: the list of what was
  found, a search box and a rescan button.

### 🧹 The plugin system is for automation only

A plugin is no longer needed to open an application — that is what the index
above is for. A plugin is for *driving* an application: its tabs, slides,
dialogs and settings.

- The **WhatsApp plugin is deleted** (source, website copy and tests). Opening
  WhatsApp still works: the assistant finds the installed app by name.
- The WhatsApp contacts UI, its bridge methods and its training phrases are
  gone as well.

### 🐧 Linux support

- **`requirements.txt`** is now the common dependency set; the Windows-only
  packages moved to `requirements-windows.txt` and **`requirements-linux.txt`**
  documents the system packages the desktop environment needs.
- **`build_exe.py`** builds on any operating system and now ships the `core`
  package with the application; `build.sh` builds and packages the Linux
  release, and `install.sh` installs it with a launcher and a menu entry.
- The Chrome and Brave plugins start their browser from its real path instead
  of the Windows-only `start` shell command, and the VS Code plugin searches
  files with `find` on Linux.

### 🐛 Fixes: The Control Center no longer stalls on launch

The Control Center (the WebView2 dashboard opened from the system tray) was
slow to appear on many machines, and on some it never appeared at all. Four
separate causes were behind it, and all four are fixed.

#### 1. Missing Microsoft Edge WebView2 Runtime
- **New `utils/webview2.py`** — detects the Evergreen WebView2 runtime through
  the EdgeUpdate registry (with a filesystem fallback for machines where group
  policy hides the registry entries) and reports the installed version.
- The Control Center now checks the runtime **before** opening a window. When
  it is missing, the user gets an immediate dialog with a download link
  instead of a 30-60 second stall followed by a blank page — pywebview
  silently falls back to the deprecated MSHTML engine, which cannot render
  the Tailwind bundle.
- The same runtime is now reported in the Diagnostics tab, and
  **`installer.iss`** detects it and installs the official Evergreen
  bootstrapper after setup when it is missing.

#### 2. The Control Center booted the whole application
- The dashboard process paid for the assistant's entire startup: CUDA DLL
  registration, an `nvidia-smi` probe, `import config`, the plugin catalogue
  and the ONNX/Whisper stack. It now starts in **~0.2 s** instead of ~2.8 s.
- **`app.py`** dispatches `--dashboard`/`--settings` before any of that work,
  and the CUDA registration only runs for the assistant.
- **`config.py`** no longer shells out to `nvidia-smi` at import time. The
  CUDA-dependent Whisper settings resolve lazily on first access, so
  `import config` is instant again.
- **`ui/dashboard_bridge.py`** imports the plugin catalogue, the profile store
  and the voice authenticator lazily, through a small proxy, so the heavy
  stack is only loaded when a tab actually needs it.

#### 3. The microphone was opened on dashboard startup
- The dashboard used to construct a full `SpeechStreamer` at launch, which
  loads a **second copy of the Whisper model** and grabs the input device
  that the assistant already holds. On machines whose audio driver runs in
  exclusive mode, that second stream blocked the window indefinitely.
- **`speech/streamer.py`** gained a `capture_only` mode that builds the same
  input stream without loading Whisper.
- The microphone is now opened **only while the Voice Enrollment tab is
  open**, and released when the user leaves it.

#### 4. A failed launch looked like a slow one
- The dashboard now writes a readiness file when its window is actually on
  screen, and **`ui/plugin_window.py`** watches it. A launch that dies
  immediately is reported with its exit code and a pointer to the log file,
  rather than leaving the user waiting in silence.

### 🏗️ Architecture: The Command Registry

The command pipeline was rebuilt around a declarative command catalogue
instead of a chain of `if`/`else` branches. Every command is now one
`CommandSpec` that carries its own matchers, its own argument extraction
and its own handler.

#### 🧩 New modules
- **`actions/registry.py`** — the registry itself: `CommandSpec`, `Matcher`,
  `CommandContext` and the lookup indexes (exact phrase → O(1), patterns →
  priority ordered, intent → command).
- **`actions/catalog.py`** — the catalogue: every built-in command, its
  vocabulary (sites, apps, folders), its command tables and its handlers.
- **`actions/dispatch.py`** — the shared resolve/execute path used by both
  lanes, so Lane 1 and Lane 2 behave identically.

#### 🔁 Rewritten modules
- **`actions/executor.py`** — now a readable pipeline: interceptors →
  macros → compound planner → Lane 1 → Lane 2 → Lane 3.
- **`actions/fast_lane.py`** — no longer decides what a command is; it asks
  the registry and runs what it finds.
- **`actions/api_lane.py`** — the direct-API part is catalogue-driven; the
  cloud LLM part keeps its own plumbing, with the double tool-pruning
  removed and the rate-limit backoff preserved.
- **`actions/intent_classifier.py`** — the taxonomy is now derived from the
  registry, and layer 1 (the catalogue) resolves commands exactly. The
  trained model is the fallback for unseen phrasings.
- **`actions/param_extractor.py`** — rule-driven slot extraction. The token
  tagger could not tell *"create a folder called Cats and Dogs"* (one name)
  from *"delete tmp and build folders"* (one delete); the rules can, and
  they never guess.

#### 🐛 Fixed
- **"unmute" muted instead of unmuting** — it was mapped onto the same
  action as "mute".
- **"unmute", "restore window" and the brightness commands did nothing** —
  they were classified but had no handler.
- **"what is my ip" was answered by the Windows system-info bridge** in
  Lane 1 instead of the public IP API in Lane 2.
- **Absolute paths were dropped** — *"create MCA folder in C:\Users\..."*
  lost its folder and landed on the Desktop.
- **The rename command lost its target folder** — the new name was renamed
  in the wrong directory.
- **"open task manager" and "check battery" were claimed by two commands**
  at once; the shortcut now wins, as before.
- **Dev tools, diagnostics and clipboard shortcuts could not be used inside
  a compound command** — they now live in Lane 1, so
  *"copy this and paste it"* runs both clauses.

#### ➕ Added
- `tests/test_command_registry.py` — pins the registry guarantees down,
  including a test that registers a brand new command and runs it end to
  end without touching another file.

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

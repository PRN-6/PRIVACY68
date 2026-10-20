# PRIVACY68 — Complete Architecture & Handover Context

> **How to use this file:** If your AI chat session ends or runs out of tokens, copy and paste the text from the [AI Chat Continuation Prompt](#ai-chat-continuation-prompt) section at the bottom of this document into your new chat. It will instantly restore 100% of the project context.

---

## 1. Project Overview & Philosophy

**PRIVACY68** is an ultra-fast, privacy-first desktop voice assistant for Windows.

### The Core Privacy Boundary
- **Audio & Speech-To-Text Never Leaves the PC**: The microphone stream, Silero VAD, openWakeWord, and Whisper speech-to-text (`faster-whisper`) always run **100% locally on the user's machine**. Raw audio is never sent over the internet.
- **Text Intent Execution**: Once the user's speech is converted to short text locally (e.g. *"open chrome"*, *"mute audio"*), it is processed via the **Three-Lane Architecture**.

---

## 2. The Three-Lane Architecture

```
                      User Voice / Remote Command
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  0. Security Intercept & Macro Workflows & Diagnostics │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  LANE 1: FAST LANE (Highest Priority)                  │
      │  • Deterministic OS Tools (<5ms, Win32/UIA/Files)       │
      │  • Plugin Fast Intents (Chrome tabs, GitHub, etc.)     │
      │  • Pure regex extraction (WhatsApp contact/messages)   │
      │  • 100% Offline • Zero AI/RAM/GPU overhead             │
      │  • Runs on ALL computers (even 10-year-old laptops)    │
      └───────────────────────────┬────────────────────────────┘
                                  │ (if unmatched)
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  LANE 2: API LANE (High Priority)                      │
      │  • Direct App & Web APIs (Weather, IP, Search URLs)    │
      │  • Cloud LLM Semantic Router (Groq, Gemini, Claude,    │
      │    OpenAI, OpenRouter, Custom Astra)                   │
      │  • Ultra-low latency (~100-150ms via Groq)             │
      │  • 0% local GPU/RAM requirement                        │
      │  • Supports 100% FREE API Keys (No Credit Card)        │
      └───────────────────────────┬────────────────────────────┘
                                  │ (if unmatched)
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  LANE 3: LOCAL LLM LANE (Optional / User's Choice)     │
      │  • Local Air-Gapped Model (Ollama / Qwen / Llama)      │
      │  • Opt-in: Only runs if user wants/enables it          │
      │  • Non-blocking probe: Skips in <1ms if Ollama offline │
      │  • NEVER freezes, lags, or crashes on low-end PCs      │
      └────────────────────────────────────────────────────────┘
```

### Lane 1: Fast Lane (`actions/fast_lane.py`)
- Instant Win32 / UIA / filesystem actions (`volume_up`, `volume_mute`, `lock_screen`, `screenshot`, `type_text`, `open_application`).
- Direct Plugin Fast Intents (`chrome.new_tab`, `chrome.incognito`, `system.maximize_window`, `github.notifications`).
- Zero network, zero LLM, `<2ms` latency.

### Lane 2: API Lane (`actions/api_lane.py`)
- **Direct Web & Utility APIs**: Public weather API (via wttr.in, no key required), public IP info (`api.ipify.org`), search URLs.
- **Cloud LLM Semantic Tool Calling**: Sends natural language to high-speed cloud APIs (Groq, Gemini, Claude, OpenAI).
- Leaves 100% of user PC hardware free; handles infinite speech variations without fragile regex.

### Lane 3: Local LLM Lane (`actions/router.py`)
- Optional air-gapped local model via Ollama (`qwen2.5:0.5b`).
- Uses `is_ollama_alive(timeout_sec=0.3)` non-blocking socket check.
- If Ollama is not installed or running, skips in `<1ms` without freezing.

---

## 3. How to Use Free APIs (For Users With $0 Budget)

Anyone can run PRIVACY68 with cloud AI speed **for 100% free without a credit card**:

### Option A: Groq (Recommended — Fastest & 100% Free)
1. Go to [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign in with Google or GitHub (No credit card needed).
3. Click **Create API Key**, copy your key (starts with `gsk_...`).
4. Set in `%APPDATA%\PRIVACY68\user_profile.json` (or via Dashboard UI):
   ```json
   {
     "llm_provider": "groq",
     "api_key": "gsk_your_key_here",
     "cloud_model": "llama-3.3-70b-versatile"
   }
   ```
   *Limit: 14,400 requests/day, 30 requests/minute. Blazing fast (100–150ms).*

### Option B: Google Gemini (100% Free)
1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **Create API key** (No credit card needed).
3. Set in `user_profile.json`:
   ```json
   {
     "llm_provider": "gemini",
     "api_key": "AIzaSy...",
     "cloud_model": "gemini-2.0-flash"
   }
   ```
   *Limit: 1,500 requests/day for free.*

### Option C: OpenRouter Free Models (100% Free)
1. Go to [https://openrouter.ai/keys](https://openrouter.ai/keys)
2. Create an account and key.
3. Set in `user_profile.json`:
   ```json
   {
     "llm_provider": "openrouter",
     "api_key": "sk-or-v1-...",
     "cloud_model": "meta-llama/llama-3.3-70b-instruct:free"
   }
   ```

---

## 4. Paid / Subscription APIs (Optional)

For users with existing AI subscriptions:

### Anthropic Claude
- Provider: `"claude"` or `"anthropic"`
- API Key: `sk-ant-api03-...`
- Model: `claude-3-5-haiku-20241022` (or `claude-3-5-sonnet-20241022`)
- Native Anthropic Messages API tool-calling implemented in `actions/api_lane.py`.

### OpenAI / Astra
- Provider: `"openai"` (or `"custom"`)
- API Key: `sk-...`
- Model: `gpt-4o-mini` (or custom endpoint)

---

## 5. Key Files in the Repository

| File Path | Description |
| :--- | :--- |
| `app.py` | Main entry point for voice loop, tray, dashboard, and remote server. |
| `config.py` | Audio streamer, VAD, and Whisper configuration. |
| `actions/executor.py` | Master 3-lane dispatcher (`execute_system_command_detailed`). |
| `actions/command_planner.py` | Compound Command Planner — splits multi-command utterances into ordered clauses. |
| `actions/fast_lane.py` | Lane 1: Deterministic OS actions & plugin fast intents. |
| `actions/api_lane.py` | Lane 2: Direct Web APIs + Cloud LLM Semantic Router (Groq/Gemini/Claude/OpenAI). |
| `actions/router.py` | Lane 3: Local LLM Lane with non-blocking `is_ollama_alive` socket probe. |
| `actions/skill_manager.py` | Action coordinator for dynamic plugins. |
| `plugins/profile_manager.py` | Manages user settings persisted in `%APPDATA%/PRIVACY68/user_profile.json`. |
| `plugins/manager.py` | Loads and indexes built-in and custom plugins. |
| `extra_plugins/whatsapp_plugin.py` | WhatsApp desktop automation (regex-first, zero-Ollama latency). |
| `tests/test_three_lane_architecture.py` | Unit tests for the 3-lane system. |
| `tests/test_command_planner.py` | Unit tests for the Compound Command Planner. |
| `tests/test_security_guard_wiring.py` | Verifies the 3-tier security model is actually wired into execution. |
| `sync_website_plugins.py` | Regenerates `website/downloads/plugins/*.py` from canonical plugin sources. |

---

## 6. Recent Verification Status

- All **77 unit tests** pass with 0 failures:
  ```powershell
  python -m unittest discover tests
  # Ran 77 tests in 13.13s -> OK (0 failures)
  ```
  `python -m pytest tests/` runs the same 77 tests. Both runners are kept in sync:
  every test file uses `unittest.TestCase`, so neither runner silently skips a file.
- **CI**: `.github/workflows/ci.yml` runs the test suite, the website-plugin sync
  check, and a byte-compile pass on every push to `main`. The release workflow
  runs the same checks before building.
- **Website plugin sync**: `python sync_website_plugins.py` copies the canonical
  plugin sources into `website/downloads/plugins/` so the copies served to end
  users can never drift from `extra_plugins/` and `plugins/`. Run with
  `--check` in CI to fail the build if they diverge.
- **OpenClaw Architecture Cleanup**:
  - `actions/fast_lane.py`: Cut from 893 lines down to 470 lines (removed 420+ lines of brittle regex bloat). Now acts as a lean, deterministic Fast Dispatcher (<2ms).
  - `actions/api_lane.py`: Smart tool selector prunes definitions to top 40 relevant tools (~3,500 tokens), preventing Groq's 7,000 ITPM limit and 128-tool schema ceiling. Runs in ~150-200ms.
  - `actions/executor.py`: Streamlined to 251 lines with module-level immutable lookups and unified callbacks.
  - `speech/streamer.py`: Conversational prefixes ("Accept, ", "Please, ") automatically stripped by `autocorrect_speech_command`.
  - `computer_use/security_guard.py`: 3-Tier Security Confirmation Intercept 100% active.

---

## 7. AI Chat Continuation Prompt

If you run out of tokens in this chat session, copy and paste everything inside the block below into your new chat with the next AI:

```markdown
I am continuing development on PRIVACY68, a privacy-first Windows desktop voice assistant.
Please read `PROJECT_HANDOVER.md` in the repository root for full context before proceeding.

Key Context Summary:
1. Architecture: Three-Lane Command Architecture:
   - Lane 1: Fast Lane (actions/fast_lane.py) — Highest priority, deterministic OS tools & plugin fast intents (<2ms, 0% AI, runs on any PC).
   - Lane 2: API Lane (actions/api_lane.py) — High priority, direct app/web APIs and Cloud LLM Semantic Router (Groq, Gemini, Claude, OpenAI). Zero local RAM/GPU footprint, supports 100% free API keys (Groq/Gemini).
   - Lane 3: Local LLM Lane (actions/router.py) — Optional/opt-in local Ollama model with is_ollama_alive() probe (<1ms non-blocking check).
   - Compound Command Planner (actions/command_planner.py) — Splits multi-command utterances ("mute the volume and open chrome") into ordered clauses and runs each through the 3-lane path. Deterministic, no LLM, conservative: returns None (single command) whenever it is not certain.
2. Audio stream and Whisper STT run 100% locally on the device (privacy guaranteed).
3. All 77 unit tests currently pass (python -m unittest discover tests).
4. Goal: Keep the codebase clean, lean, and optimized. Avoid massive fragile regex or hardcoded word lists when APIs can handle natural language tool-calling effortlessly.

Please acknowledge that you have reviewed the handover and let me know you are ready to continue.
```

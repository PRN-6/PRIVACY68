# PRIVACY68 // SETUP, INSTALLATION & CONFIGURATION GUIDE

```
 ███████╗███████╗████████╗██╗   ██╗██████╗ 
 ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██╗
 ███████╗█████╗     ██║   ██║   ██║██████╔╝
 ╚════██║██╔══╝     ██║   ██║   ██║██╔═══╝ 
 ███████║███████╗   ██║   ╚██████╔╝██║     
 ╚══════╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝     
```

---

## 1. System Requirements

- **Operating System**: Microsoft Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **Python Version**: Python 3.11 or Python 3.12 (64-bit).
- **RAM**: Minimum 4 GB (Recommended: 8 GB+).
- **Disk Space**: ~350 MB (Zero local CUDA bloat).
- **GPU**: **None required**. PRIVACY68 runs on Cloud AI APIs (Gemini 3.1 Flash-Lite, Groq, Claude, OpenAI) with zero local GPU VRAM requirements.

---

## 2. Quick-Start Installation (5 Minutes)

### Step 1: Clone the Repository
```powershell
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68
```

### Step 2: Create a Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Core Dependencies
```powershell
pip install -r requirements.txt
```

> [!NOTE]
> PRIVACY68 uses CPU-optimized int8 Faster-Whisper and Cloud AI APIs. You do **not** need to install heavy CUDA runtimes, Visual Studio C++ build tools, or PyTorch wheels.

---

## 3. Environment Variables & API Key Configuration

Create a `.env` file in the project root (or configure via the Control Center Dashboard):

```ini
# -------------------------------------------------------------
# 1. Primary AI Brain Provider Configuration
# -------------------------------------------------------------
# Default model: gemini/gemini-3.1-flash-lite
DEFAULT_MODEL=gemini/gemini-3.1-flash-lite

# Google Gemini API Key (Get free key from https://aistudio.google.com/)
GEMINI_API_KEY=AIzaSy...

# Groq LPU API Key (Optional high-speed failover: https://console.groq.com/)
GROQ_API_KEY=gsk_...

# Anthropic Claude API Key (Optional complex reasoning)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API Key (Optional fallback)
OPENAI_API_KEY=sk-proj-...

# -------------------------------------------------------------
# 2. Telegram Remote Gateway Configuration
# -------------------------------------------------------------
# Create a bot via @BotFather on Telegram (https://t.me/BotFather)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Your personal Telegram Chat ID (Leave blank to use dynamic 6-digit PIN pairing)
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_ENABLE_VOICE=true

# -------------------------------------------------------------
# 3. Speech & Audio Architecture
# -------------------------------------------------------------
# "auto": Google Web Speech first, local Faster-Whisper fallback
SPEECH_ENGINE=auto
WHISPER_MODEL_SIZE=tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

---

## 4. Running PRIVACY68

### Start the Application
```powershell
python app.py
```
This initializes:
- The **Control Center Dashboard** (Edge Chromium window).
- The **System Tray Icon** in your Windows taskbar.
- The **Quick Command Bar** listener (`Ctrl+Alt+Space`).
- The **Telegram Remote Gateway** worker thread.

### Command-Line Arguments
```powershell
# Run directly in background tray mode (minimized)
python app.py --tray

# Run a single isolated agent script directly
python app.py --run-agent-script <script_path> <log_path>
```

---

## 5. Standalone Executable Packaging (PyInstaller)

To compile PRIVACY68 into a standalone Windows `.exe`:

```powershell
pyinstaller privacy68.spec --clean --noconfirm
```

The compiled standalone executable will be generated at:
`dist\PRIVACY68\PRIVACY68.exe`

---

*Authored by PRN-6 // PRIVACY68 Installation Guide*


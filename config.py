"""
    Configuration settings for Privacy68 Assistant
"""

import ctypes
import os
import sys
from dotenv import load_dotenv


def get_env_file_path() -> str:
    """
    Returns the persistent .env file path across standard Python and PyInstaller frozen modes.
    Priority:
    1. If frozen (compiled executable):
       a. Beside the executable (e.g. <exe_folder>/.env) if writable or existing.
       b. Fallback to %APPDATA%/PRIVACY68/.env (guaranteed writable across all Windows environments).
    2. If running from source (development):
       Project root directory (alongside config.py).
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        exe_env = os.path.join(exe_dir, ".env")
        if os.path.isfile(exe_env):
            return exe_env
        try:
            test_file = os.path.join(exe_dir, ".perm_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return exe_env
        except (OSError, PermissionError):
            pass
        appdata_dir = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
        os.makedirs(appdata_dir, exist_ok=True)
        return os.path.join(appdata_dir, ".env")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


# Load environment variables across frozen executable and source modes:
# 1. First check AppData .env if it exists
_appdata_env = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68", ".env")
if os.path.isfile(_appdata_env):
    load_dotenv(_appdata_env, override=True)

# 2. Then check primary env path (e.g. alongside .exe or in project root)
_primary_env = get_env_file_path()
if os.path.isfile(_primary_env):
    load_dotenv(_primary_env, override=True)
else:
    load_dotenv()

try:
    from utils.cuda_manager import register_cuda_dlls, get_cuda_status
    register_cuda_dlls()
    _status = get_cuda_status()
    _HAS_CUDA = _status["is_ready"]
except Exception:
    def _cuda_available() -> bool:
        try:
            ctypes.WinDLL("nvcuda.dll")
            return True
        except OSError:
            return False
    _HAS_CUDA = _cuda_available()


# Application Version
APP_VERSION = "1.6.4"

# Audio Stream Settings (16kHz standard for voice)
SAMPLE_RATE = 16000
BLOCK_SIZE = 1280
CHANNELS = 1
DTYPE = "float32"

# Silence & Recording thresholds
SILENCE_DURATION_CHUNKS = 8      # 8 chunks * 80ms = ~0.64s pause after speech for rapid cut-off
SILENCE_THRESHOLD = 0.008        # RMS noise floor

# Speech Engine Configuration
# "auto": First priority is Google Web Speech (100% free, zero setup). Automatically falls back to local Faster-Whisper if offline or no internet.
# "google": Google Web Speech cloud API (falls back to local Faster-Whisper if disconnected).
# "whisper": Strictly offline on-device transcription (Faster-Whisper / CTranslate2). Zero cloud data leakage.
SPEECH_ENGINE = os.environ.get("SPEECH_ENGINE", "auto")
SPEECH_LANGUAGE = os.environ.get("SPEECH_LANGUAGE", "auto")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# Audio feedback sounds (True = beep on activation, False = silent)
ENABLE_BEEP = False

# Ollama API Configuration (Local daemon or remote Cloud/Website Ollama server)
# Examples: "http://localhost:11434", "https://ollama.your-domain.com", "http://your-vps-ip:11434"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# Google Gemini API Configuration (Ultra-fast reasoning with free tier)
# Get free API key in seconds at https://aistudio.google.com/app/apikey (No credit card needed)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

# Groq Cloud LLM Configuration (Free fast reasoning LPU for AI Brain)
# Get free API key in 10 seconds at https://console.groq.com/keys (No credit card needed)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Anthropic Claude API Configuration (OpenClaw style out-of-the-box frontier intelligence)
# Set ANTHROPIC_API_KEY in environment or configure via dashboard UI
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Custom / OpenAI-Compatible API Base (LM Studio, LocalAI, vLLM, DeepSeek, Mistral, etc.)
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "")
CUSTOM_API_KEY = os.environ.get("CUSTOM_API_KEY", "")
CUSTOM_API_BASE = os.environ.get("CUSTOM_API_BASE", "")

# OpenRouter API Configuration (100+ Free Models: Gemini, Llama 3.3, Mistral)
# Free API key in seconds at https://openrouter.ai/keys (No credit card needed)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Agent Brain (LLM) Configuration - Pure API Mode with Auto-Failover (No local LLM required)
# Priority: Custom env -> Gemini (if key set) -> Groq (if key set) -> OpenRouter (if key set) -> Claude -> OpenAI -> Gemini 3.5 Flash (Free default)
if os.environ.get("AGENT_BRAIN_MODEL"):
    _default_model = os.environ.get("AGENT_BRAIN_MODEL")
elif GEMINI_API_KEY:
    _default_model = "gemini/gemini-3.5-flash"
elif GROQ_API_KEY:
    _default_model = "groq/openai/gpt-oss-120b"
elif OPENROUTER_API_KEY:
    _default_model = "openrouter/google/gemini-2.0-flash-exp:free"
elif ANTHROPIC_API_KEY:
    _default_model = "claude-3-5-sonnet-20241022"
elif OPENAI_API_KEY:
    _default_model = "openai/gpt-4o-mini"
elif OLLAMA_BASE_URL and OLLAMA_BASE_URL != "http://localhost:11434":
    _default_model = "ollama/llama3.2:latest"
else:
    _default_model = "gemini/gemini-3.5-flash"

AGENT_BRAIN_MODEL = _default_model
AGENT_BRAIN_MAX_RETRIES = 2  # Open-Interpreter style self-healing code retry loop

# Mobile Web Remote Server configuration
ENABLE_REMOTE_SERVER = True
REMOTE_SERVER_HOST = "0.0.0.0"
REMOTE_SERVER_PORT = 8765

# Telegram Remote Gateway configuration
ENABLE_TELEGRAM_BOT = True
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")


def update_dotenv_var(key: str, value: str, env_path: str = None) -> None:
    """Persists a key-value pair to the .env file and updates runtime config & environment."""
    os.environ[key] = value
    globals()[key] = value

    if env_path is None:
        env_path = get_env_file_path()

    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    key_found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f'{key}="{value}"\n')
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f'{key}="{value}"\n')

    try:
        os.makedirs(os.path.dirname(os.path.abspath(env_path)), exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        # Fallback to user APPDATA if writing next to executable fails (e.g. read-only folder)
        appdata_dir = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
        fallback_env = os.path.join(appdata_dir, ".env")
        if env_path != fallback_env:
            try:
                os.makedirs(appdata_dir, exist_ok=True)
                with open(fallback_env, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                return
            except Exception:
                pass
        import logging
        logging.getLogger("PRIVACY68.Config").warning(f"Could not persist {key} to {env_path}: {e}")


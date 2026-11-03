"""
    Configuration settings for Privacy68 Assistant
"""

import ctypes
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
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


# Audio Stream Settings (16kHz, 1280 samples = 80ms frames required by openWakeWord)
SAMPLE_RATE = 16000
BLOCK_SIZE = 1280
CHANNELS = 1
DTYPE = "float32"

# Silence / Voice Activity Detection (VAD)
VAD_THRESHOLD = 0.50             # Silero neural VAD speech probability threshold (0.0 to 1.0)
VAD_IDLE_THRESHOLD = 0.30        # Lower threshold for idle wake-word scan gating (skip Whisper on silence)
SILENCE_DURATION_CHUNKS = 8      # 8 chunks * 80ms = ~0.64s pause after speech for rapid cut-off
SILENCE_THRESHOLD = 0.008        # Fallback RMS noise floor

# Speech Engine Selection: "auto", "whispercpp", or "faster_whisper"
# "whispercpp" runs whisper.cpp in pure C++ on CPU (AVX2), ~180ms latency, zero GPU/CUDA dependencies.
# "faster_whisper" uses CTranslate2 (CUDA if available, or CPU int8).
SPEECH_ENGINE = "auto"
WHISPERCPP_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "whispercpp", "ggml-base.en.bin")

# Faster Whisper model configuration (for CUDA fallback)
WHISPER_MODEL_SIZE   = "medium.en"
WHISPER_DEVICE       = "cuda"     if _HAS_CUDA else "cpu"      # auto-detected
WHISPER_COMPUTE_TYPE = "float16"  if _HAS_CUDA else "int8"     # float16=GPU, int8=CPU
WHISPER_BEAM_SIZE    = 8          # wider beam = higher accuracy

# Hotwords: Whisper boosts log-probability for these tokens during decoding.
WHISPER_HOTWORDS = (
    "Jarvis, Jarvice, Alexa, Nova, Friday, Leo, Serena, Privacy68, open, close, launch, search, go to, "
    "Chrome, Brave, WhatsApp, YouTube, Google, Notepad, "
    "volume, mute, screenshot, lock, tab, new tab, enter, "
    "send message, message, chat, call"
)

# Initial prompt: Whisper conditions its decoder on this text before your audio.
INITIAL_PROMPT = (
    "Voice commands for a desktop assistant named Alexa. Commands always start with a wake word "
    "like Jarvis, Alexa, Nova, Friday, or Privacy68, followed by an action. Examples: 'Jarvis open Chrome', "
    "'Alexa search YouTube for music', 'Jarvis open WhatsApp', "
    "'Privacy 68 send message to mom', 'Jarvis take a screenshot', 'Jarvis lock the screen'."
)

# Wake word configuration
WAKE_WORD_MODEL = "alexa"
WAKE_WORD_THRESHOLD = 0.50

# Audio feedback sounds (True = beep on wake, False = silent)
ENABLE_BEEP = False

# Groq Cloud Whisper & LLM Configuration (Free 99% accuracy cloud LPU)
# Get free API key in 10 seconds at https://console.groq.com/keys (No credit card needed)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# Anthropic Claude API Configuration (OpenClaw style out-of-the-box frontier intelligence)
# Set ANTHROPIC_API_KEY in environment or configure via dashboard UI
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Agent Brain (LLM) Configuration
# Auto-selects Claude 3.5 Sonnet if ANTHROPIC_API_KEY is present, else falls back to local Ollama
_default_model = "claude-3-5-sonnet-20241022" if ANTHROPIC_API_KEY else "ollama/llama3.2:latest"
AGENT_BRAIN_MODEL = os.environ.get("AGENT_BRAIN_MODEL", _default_model)
AGENT_BRAIN_MAX_RETRIES = 2  # Open-Interpreter style self-healing code retry loop

# Mobile Web Remote Server configuration
ENABLE_REMOTE_SERVER = True
REMOTE_SERVER_HOST = "0.0.0.0"
REMOTE_SERVER_PORT = 8765

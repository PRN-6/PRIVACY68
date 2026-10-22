"""
    Configuration settings for Privacy68 Assistant
"""

import ctypes
from typing import Optional

try:
    from utils.cuda_manager import register_cuda_dlls
    register_cuda_dlls()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# CUDA capability detection is deferred to first use.
#
# `get_cuda_status()` shells out to nvidia-smi, which can take several seconds
# on cold or busy machines. Importing `config` therefore used to add that cost
# to *every* cold start — including the Control Center, which never touches
# Whisper at all. The Whisper settings below are now resolved lazily through
# the module-level __getattr__ hook at the bottom of this file.
# ─────────────────────────────────────────────────────────────────────────────
_CUDA_AVAILABLE: Optional[bool] = None


def cuda_is_available() -> bool:
    """Detects (once) whether CUDA acceleration can be used."""
    global _CUDA_AVAILABLE
    if _CUDA_AVAILABLE is None:
        try:
            from utils.cuda_manager import get_cuda_status
            _CUDA_AVAILABLE = bool(get_cuda_status()["is_ready"])
        except Exception:
            _CUDA_AVAILABLE = False
            try:
                ctypes.WinDLL("nvcuda.dll")
                _CUDA_AVAILABLE = True
            except (OSError, AttributeError):
                # AttributeError: ctypes.WinDLL only exists on Windows.
                _CUDA_AVAILABLE = False
    return _CUDA_AVAILABLE


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

# Whisper model configuration
# medium.en: ~30% better word accuracy over small.en for short commands.
# On CUDA this runs at ~120-160ms per transcription — imperceptible to the user.
WHISPER_MODEL_SIZE   = "medium.en"
# WHISPER_DEVICE / WHISPER_COMPUTE_TYPE are resolved lazily by the module
# __getattr__ hook at the bottom of this file.
WHISPER_BEAM_SIZE    = 8          # wider beam = higher accuracy (was 5)

# Hotwords: Whisper boosts log-probability for these tokens during decoding.
# List every app name, action word, and proper noun the assistant might hear.
WHISPER_HOTWORDS = (
    "Jarvis, Jarvice, Alexa, Nova, Friday, Leo, Serena, Privacy68, open, close, launch, search, go to, "
    "Chrome, Brave, WhatsApp, YouTube, Google, Notepad, "
    "volume, mute, screenshot, lock, tab, new tab, enter, "
    "send message, message, chat, call"
)

# Initial prompt: Whisper conditions its decoder on this text before your audio.
# A precise, command-style prompt dramatically reduces misrecognition of app names.
INITIAL_PROMPT = (
    "Voice commands for a desktop assistant named Privacy68. Commands always start with a wake word "
    "like Jarvis, Alexa, Nova, Friday, or Privacy68, followed by an action. Examples: 'Jarvis open Chrome', "
    "'Alexa search YouTube for music', 'Jarvis open WhatsApp', "
    "'Privacy 68 send message to mom', 'Jarvis take a screenshot', 'Jarvis lock the screen'."
)

# Wake word configuration
WAKE_WORD_MODEL = "privacy68"
WAKE_WORD_THRESHOLD = 0.50

# Audio feedback sounds (True = beep on wake, False = silent)
ENABLE_BEEP = False

# Mobile Web Remote Server configuration
ENABLE_REMOTE_SERVER = True
REMOTE_SERVER_HOST = "0.0.0.0"
REMOTE_SERVER_PORT = 8765


def __getattr__(name: str):
    """
    Resolves the CUDA-dependent Whisper settings on first access (PEP 562).

    Kept as module attributes for backwards compatibility: `config.WHISPER_DEVICE`
    and `from config import WHISPER_DEVICE` both keep working, but the CUDA
    probe only runs when a caller actually needs the answer.
    """
    if name == "WHISPER_DEVICE":
        return "cuda" if cuda_is_available() else "cpu"
    if name == "WHISPER_COMPUTE_TYPE":
        return "float16" if cuda_is_available() else "int8"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

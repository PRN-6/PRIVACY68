"""
    Configuration settings for Privacy68 Assistant
"""

import ctypes
import subprocess

try:
    from utils.cuda_manager import register_cuda_dlls, get_cuda_status
    register_cuda_dlls()
    _status = get_cuda_status()
    _HAS_CUDA = _status["is_ready"]
except Exception:
    def _cuda_available() -> bool:
        try:
            import ctypes
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

# Whisper model configuration
# medium.en: ~30% better word accuracy over small.en for short commands.
# On CUDA this runs at ~120-160ms per transcription — imperceptible to the user.
WHISPER_MODEL_SIZE   = "medium.en"
WHISPER_DEVICE       = "cuda"     if _HAS_CUDA else "cpu"      # auto-detected
WHISPER_COMPUTE_TYPE = "float16"  if _HAS_CUDA else "int8"     # float16=GPU, int8=CPU
WHISPER_BEAM_SIZE    = 8          # wider beam = higher accuracy (was 5)

# Hotwords: Whisper boosts log-probability for these tokens during decoding.
# List every app name, action word, and proper noun the assistant might hear.
WHISPER_HOTWORDS = (
    "Alexa, Nova, Privacy68, open, close, launch, search, go to, "
    "Chrome, Brave, WhatsApp, YouTube, Google, Notepad, "
    "volume, mute, screenshot, lock, tab, new tab, enter, "
    "send message, message, chat, call"
)

# Initial prompt: Whisper conditions its decoder on this text before your audio.
# A precise, command-style prompt dramatically reduces misrecognition of app names.
INITIAL_PROMPT = (
    "Voice commands for a desktop assistant. Commands always start with a wake word "
    "like Alexa or Nova, followed by an action. Examples: 'Alexa open Chrome', "
    "'Alexa search YouTube for music', 'Alexa open WhatsApp', "
    "'Alexa send message to mom', 'Alexa take a screenshot', 'Alexa lock the screen'."
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



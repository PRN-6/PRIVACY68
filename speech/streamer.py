"""
PRIVACY68 Speech & Audio Processing Module
Handles acoustic normalization, in-memory audio decoding (Telegram voice notes),
Google Web Speech recognition, and local Faster-Whisper transcription.
Local PC microphone hardware capture is permanently disabled in favor of Telegram Remote Gateway.
"""

from typing import Callable, Optional
import os
import io
import logging
import queue
import re
import threading
import numpy as np

import config

# Patch PyAV av.open to gracefully handle versions where metadata_errors was removed
try:
    import av
    if hasattr(av, "open"):
        _orig_av_open = av.open
        def _safe_av_open(*args, **kwargs):
            kwargs.pop("metadata_errors", None)
            return _orig_av_open(*args, **kwargs)
        av.open = _safe_av_open
except Exception:
    pass

logger = logging.getLogger("PRIVACY68.SpeechStreamer")


def autocorrect_speech_command(text: str) -> str:
    """Cleans filler words, duplicate stutters, quotes, polite prefixes, and common typos from transcribed speech."""
    if not text:
        return ""

    # Aggressively strip wrapping single/double quotes or backticks added by Whisper models
    cleaned = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", text.strip())

    # 1. Strip filler vocal tics (e.g., hmmm, ummm, uhhh, ahhh)
    cleaned = re.sub(r'\b(h+m+|u+m+|u+h+|a+h+|e+r+|b+m+|m+h+m+|m+m+)\b', ' ', cleaned, flags=re.IGNORECASE)

    # 2. Strip conversational prefixes (loops to strip chained greetings like "hey jarvis please open")
    prefix_pattern = re.compile(
        r'^(?:can\s+you(?:\s+please)?|could\s+you(?:\s+please)?|would\s+you(?:\s+please)?|'
        r'i\s+want\s+(?:you\s+)?to|please|kindly|hey|alexa|privacy68|jarvis|siri|ok\s+google|computer|just)[,\s]+',
        flags=re.IGNORECASE
    )
    while True:
        sub_cleaned = prefix_pattern.sub('', cleaned)
        if sub_cleaned == cleaned:
            break
        cleaned = sub_cleaned

    # 3. Strip consecutive repeated stutter words ('open open Chrome' -> 'open Chrome')
    cleaned = re.sub(r'\b([a-zA-Z]+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)

    # 4. Clean trailing prepositions/conjunctions
    cleaned = re.sub(r'\s+(in|at|on|for|with|and|to|the|a|of)\s*$', '', cleaned, flags=re.IGNORECASE)

    # 5. Normalize common spoken phonetic variations & app typos
    substitutions = [
        (r'\byoutub\b|\byou\s*tube\b', 'youtube'),
        (r"\bwhat(?:['’]s|s)?\s*(?:app|up|zap)\b", 'whatsapp'),
        (r'\bgoogl\b', 'google'),
        (r'\bbrower\b', 'browser'),
        (r'\bnotpad\b|\bnote\s*pad\b', 'notepad'),
        (r'\bchrom\b', 'chrome'),
        (r'\btele\s*gram\b|\btele\s*gran\b', 'telegram'),
        (r'\bvs\s*code\b|\bvisual\s*studio\s*code\b', 'vscode'),
        (r'\bgit\s*hub\b', 'github'),
        (r'\bcalc\b|\bcalci\b|\bcalculate\b(?!\s+\d)', 'calculator'),
        (r'\bcommand\s*prompt\b', 'cmd'),
        (r'\bfile\s*manager\b', 'file explorer'),
    ]
    for pattern, repl in substitutions:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'\s+', ' ', cleaned)
    return re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", cleaned).strip(".!?, \t\n")


_local_whisper_model = None
_whisper_lock = threading.Lock()


def reset_whisper_model() -> None:
    """Clears the cached local Whisper model so it reloads with updated settings."""
    global _local_whisper_model
    with _whisper_lock:
        _local_whisper_model = None


def get_whisper_model():
    """Lazily initializes and caches the local offline Faster-Whisper model."""
    global _local_whisper_model
    if _local_whisper_model is None:
        with _whisper_lock:
            if _local_whisper_model is None:
                try:
                    from faster_whisper import WhisperModel
                    model_size = getattr(config, "WHISPER_MODEL_SIZE", "tiny")
                    device = getattr(config, "WHISPER_DEVICE", "cpu")
                    compute_type = getattr(config, "WHISPER_COMPUTE_TYPE", "int8")
                    logger.info(f"Loading local offline Faster-Whisper model ({model_size}, {device}, {compute_type})...")
                    _local_whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
                except Exception as e:
                    logger.warning(f"Could not initialize local Faster-Whisper: {e}")
    return _local_whisper_model


def decode_audio_bytes_to_pcm(audio_bytes: bytes, target_sr: int = config.SAMPLE_RATE) -> np.ndarray:
    """Decodes arbitrary audio bytes (OGG/Opus, MP3, WAV, AAC, M4A, etc.) to a mono float32 NumPy array at target_sr.
    Supports PyAV (with safe av.open), ffmpeg subprocess, and standard wave parsing.
    """
    if not audio_bytes:
        return np.array([], dtype=np.float32)

    # 1. Primary: PyAV in-memory container decode
    try:
        import av
        if hasattr(av, "open"):
            _orig = av.open
            def _safe_open(*args, **kwargs):
                kwargs.pop("metadata_errors", None)
                return _orig(*args, **kwargs)
            av.open = _safe_open

        from faster_whisper.audio import decode_audio
        audio = decode_audio(io.BytesIO(audio_bytes), sampling_rate=target_sr)
        if audio is not None and len(audio) > 0:
            return audio.astype(np.float32)
    except Exception as e:
        logger.debug(f"PyAV in-memory decode note: {e}")

    # 2. Secondary: ffmpeg subprocess streaming
    try:
        import shutil
        import subprocess
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-nostdin",
                "-threads", "0",
                "-i", "pipe:0",
                "-f", "s16le",
                "-ac", "1",
                "-ar", str(target_sr),
                "pipe:1"
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_out, _ = proc.communicate(input=audio_bytes, timeout=15)
            if proc.returncode == 0 and len(raw_out) > 0:
                int16_arr = np.frombuffer(raw_out, dtype=np.int16)
                return int16_arr.astype(np.float32) / 32768.0
    except Exception as e:
        logger.debug(f"ffmpeg subprocess decode note: {e}")

    # 3. Tertiary: Python wave module for standard WAV
    try:
        import wave
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()
            nc = wf.getnchannels()
            fr = wf.getframerate()
            if sw == 2:
                int16_arr = np.frombuffer(frames, dtype=np.int16)
                if nc > 1:
                    int16_arr = int16_arr[::nc]
                audio = int16_arr.astype(np.float32) / 32768.0
                if fr != target_sr:
                    from scipy.signal import resample
                    target_len = int(len(audio) * float(target_sr) / fr)
                    audio = resample(audio, target_len).astype(np.float32)
                return audio
    except Exception:
        pass

    return np.array([], dtype=np.float32)


def transcribe_whisper(audio_data: np.ndarray) -> str:
    """Transcribes audio using 100% local, offline Faster-Whisper (zero network/cloud)."""
    try:
        model = get_whisper_model()
        if model is not None and len(audio_data) > 0:
            audio_float = audio_data.flatten().astype(np.float32)
            segments, _ = model.transcribe(audio_float, language="en", beam_size=1)
            text = " ".join([seg.text for seg in segments]).strip()
            if not text:
                segments, _ = model.transcribe(audio_float, beam_size=2)
                text = " ".join([seg.text for seg in segments]).strip()
            if text:
                logger.info(f"[LOCAL WHISPER OFFLINE] Transcribed: '{text}'")
                return text
    except Exception as e:
        logger.warning(f"Local Whisper transcription note: {e}")
    return ""


def transcribe_google(audio_data: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> str:
    """Transcribes audio using Google Web Speech Recognition with dual-accent recovery."""
    if len(audio_data) == 0:
        return ""

    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = False
        recognizer.energy_threshold = 120

        clipped_audio = np.clip(audio_data, -1.0, 1.0)
        int16_arr = (clipped_audio * 32767).astype(np.int16)
        audio = sr.AudioData(int16_arr.tobytes(), sample_rate, 2)

        primary_lang = getattr(config, "SPEECH_LANGUAGE", "auto")
        if not primary_lang or primary_lang == "auto":
            try:
                import locale
                sys_loc = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "").lower()
                primary_lang = "en-IN" if "in" in sys_loc else "en-US"
            except Exception:
                primary_lang = "en-IN"

        fallback_lang = "en-US" if primary_lang != "en-US" else "en-IN"

        # Pass 1: Primary dialect recognition
        try:
            text = recognizer.recognize_google(audio, language=primary_lang)
            if text:
                logger.info(f"[GOOGLE SPEECH FREE ({primary_lang})] Transcribed: '{text}'")
                return text.strip()
        except sr.UnknownValueError:
            # Pass 2: Accent fallback
            try:
                text = recognizer.recognize_google(audio, language=fallback_lang)
                if text:
                    logger.info(f"[GOOGLE SPEECH FREE ({fallback_lang} fallback)] Transcribed: '{text}'")
                    return text.strip()
            except sr.UnknownValueError:
                pass
        except sr.RequestError as e:
            logger.warning(f"Google Speech network error: {e}")
            return ""

        # Pass 3: Extract from alternative hypotheses if strict threshold rejected
        try:
            raw_result = recognizer.recognize_google(audio, language=primary_lang, show_all=True)
            if isinstance(raw_result, dict) and raw_result.get("alternative"):
                candidates = raw_result["alternative"]
                if candidates and "transcript" in candidates[0]:
                    cand_text = candidates[0]["transcript"].strip()
                    if cand_text:
                        logger.info(f"[GOOGLE SPEECH HYPOTHESIS] Transcribed: '{cand_text}'")
                        return cand_text
        except Exception:
            pass

    except Exception as e:
        err_name = type(e).__name__
        if "UnknownValueError" not in err_name:
            logger.debug(f"Google Speech note: {e}")
    return ""


def transcribe_audio_pipeline(audio_data: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> str:
    """Unified transcription method: Google Web Speech as first priority, falling back to local Faster-Whisper when offline."""
    if len(audio_data) == 0:
        return ""

    engine = getattr(config, "SPEECH_ENGINE", "auto").lower()

    if engine in ("whisper", "faster-whisper", "offline", "local"):
        text = transcribe_whisper(audio_data)
        if not text:
            text = transcribe_google(audio_data, sample_rate)
        return text

    # Default / Auto mode: Google Web Speech first, local Faster-Whisper fallback
    text = transcribe_google(audio_data, sample_rate)
    if not text:
        logger.info("Google Web Speech unavailable or no internet. Falling back to local offline Faster-Whisper...")
        text = transcribe_whisper(audio_data)
    return text


def transcribe_audio_data(
    audio_data: np.ndarray,
    sample_rate: int = config.SAMPLE_RATE,
    streamer: Optional['SpeechStreamer'] = None
) -> str:
    """Acoustically normalizes and transcribes a 16kHz float32 audio array using:
    1. DC bias centering (waveform centering).
    2. Dynamic peak normalization to 0.95 (maximum dynamic range without distortion).
    3. 60ms silence boundary padding (prevents truncation of initial/final phonemes).
    4. Google Web Speech (priority) with dual-accent recovery (en-IN <-> en-US).
    5. Local Faster-Whisper fallback when offline or Google Speech is unreachable.
    6. Lexical autocorrection for hotwords and typo normalization.
    """
    if audio_data is None or len(audio_data) < sample_rate * 0.15:  # less than 150ms
        return ""

    # 1. Remove DC bias (centers waveform around 0)
    audio_data = audio_data - np.mean(audio_data)

    # 2. Dynamic peak normalization to 0.95 for maximum dynamic range
    peak = float(np.max(np.abs(audio_data)))
    norm_audio = (audio_data / peak) * 0.95 if peak > 0.001 else audio_data

    # 3. Add 60ms silence padding to prevent neural acoustic truncation
    pad_len = int(sample_rate * 0.06)
    if pad_len > 0:
        norm_audio = np.pad(norm_audio, (pad_len, pad_len), mode="constant")

    text = ""
    if streamer is not None:
        text = streamer._transcribe(norm_audio, is_idle=False)
    else:
        text = transcribe_audio_pipeline(norm_audio, sample_rate=sample_rate)

    if text:
        text = autocorrect_speech_command(text)
    return text


class PushToTalkRecorder:
    """Manages audio buffer transcription.
    Hardware microphone capture is disabled on PC; voice teleoperation is routed via Telegram.
    """

    def __init__(self, sample_rate: int = config.SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.frames = []
        self._stream = None

    def start(self):
        """Prepares the in-memory buffer."""
        self.frames = []
        self.is_recording = True

    def stop_and_transcribe(self, streamer: Optional['SpeechStreamer'] = None) -> str:
        """Stops recording and returns transcribed text from accumulated frames."""
        self.is_recording = False
        if not self.frames:
            return ""

        audio_data = np.concatenate(self.frames).flatten()
        return transcribe_audio_data(audio_data, sample_rate=self.sample_rate, streamer=streamer)


# Alias for explicit Click-to-Speak usage
ClickToSpeakRecorder = PushToTalkRecorder


class SpeechStreamer:
    """Lightweight speech coordinator for unified transcription.
    Microphone hardware on the PC is permanently disabled; teleoperation runs via Telegram Remote Gateway.
    """

    def __init__(
        self,
        wake_word: Optional[str] = None,
        sample_rate: int = config.SAMPLE_RATE,
        auto_init_hardware: bool = False
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_threshold = getattr(config, "SILENCE_THRESHOLD", 0.008)
        self.silence_duration_chunks = config.SILENCE_DURATION_CHUNKS
        self.is_active = False
        self.is_muted = False
        self.audio_queue: queue.Queue = queue.Queue()
        self.stream = None
        self.recorder = PushToTalkRecorder(sample_rate=self.sample_rate)
        self.wake_word = "click-to-speak"
        self._running = False
        self.on_text_callback = None
        self.on_wake_word_callback = None
        self.on_audio_energy_callback = None
        self.on_sleep_callback = None

    def is_wake_word_detected(self, text: str) -> bool:
        """Wake words are permanently disabled for privacy."""
        return False

    def strip_wake_word(self, text: str) -> str:
        """Removes filler or leading conversational particles if present."""
        return re.sub(r'^(hey|ok|okay|hi|hello)\s+', '', text.strip(), flags=re.IGNORECASE).strip()

    def set_wake_word(self, wake_word: str) -> None:
        self.wake_word = wake_word.strip()

    def set_muted(self, muted: bool) -> None:
        self.is_muted = muted

    def toggle_mute(self) -> bool:
        self.is_muted = not self.is_muted
        return self.is_muted

    def _transcribe_whisper(self, audio_data: np.ndarray) -> str:
        return transcribe_whisper(audio_data)

    def _transcribe_google(self, audio_data: np.ndarray) -> str:
        return transcribe_google(audio_data, self.sample_rate)

    def _transcribe(self, audio_data: np.ndarray, is_idle: bool = False) -> str:
        """Unified transcription method: Google Web Speech as first priority, falling back to local Faster-Whisper when offline/no internet."""
        if len(audio_data) == 0:
            return ""

        engine = getattr(config, "SPEECH_ENGINE", "auto").lower()

        if engine in ("whisper", "faster-whisper", "offline", "local"):
            text = self._transcribe_whisper(audio_data)
            if not text:
                text = self._transcribe_google(audio_data)
            return text

        text = self._transcribe_google(audio_data)
        if not text:
            text = self._transcribe_whisper(audio_data)
        return text

    def start_recording(self) -> None:
        pass

    def stop_and_transcribe(self) -> str:
        return ""

    def start(
        self,
        on_text_callback: Callable[[str], bool],
        on_wake_word_callback: Optional[Callable[[], None]] = None,
        on_audio_energy_callback: Optional[Callable[[float], None]] = None,
        on_sleep_callback: Optional[Callable[[], None]] = None
    ) -> None:
        self.on_text_callback = on_text_callback
        self.on_wake_word_callback = on_wake_word_callback
        self.on_audio_energy_callback = on_audio_energy_callback
        self.on_sleep_callback = on_sleep_callback
        self._running = True

    def stop(self) -> None:
        self._running = False


# Module singleton
speech_streamer: Optional[SpeechStreamer] = None


def set_speech_streamer(instance: SpeechStreamer) -> None:
    global speech_streamer
    speech_streamer = instance


def get_speech_streamer() -> Optional[SpeechStreamer]:
    return speech_streamer

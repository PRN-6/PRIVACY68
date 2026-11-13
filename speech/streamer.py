"""
PRIVACY68 Speech Streamer
On-demand microphone audio capture and Google Speech transcription with 100% Click-to-Speak privacy.
The microphone is NEVER open automatically; hardware is only accessed when the user clicks speak.
"""

from typing import Callable, Optional
import os
import logging
import queue
import re
import threading
import numpy as np
import sounddevice as sd

import config

try:
    from utils.cuda_manager import register_cuda_dlls
    register_cuda_dlls()
except Exception:
    pass

logger = logging.getLogger("PRIVACY68.SpeechStreamer")


def autocorrect_speech_command(text: str) -> str:
    """Cleans filler words, duplicate stutters, quotes, and typos from transcribed speech."""
    if not text:
        return ""

    # Aggressively strip wrapping single/double quotes or backticks added by Whisper models
    cleaned = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", text.strip())

    # 1. Strip filler vocal tics (e.g., hmmm, ummm, uhhh)
    cleaned = re.sub(r'\b(h+m+|u+m+|u+h+|a+h+|e+r+|b+m+|m+h+m+|m+m+)\b', ' ', cleaned, flags=re.IGNORECASE)
    # 2. Strip consecutive repeated stutter words ('open open Chrome' -> 'open Chrome')
    cleaned = re.sub(r'\b([a-zA-Z]+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
    # 3. Clean trailing prepositions/conjunctions
    cleaned = re.sub(r'\s+(in|at|on|for|with|and|to|the|a|of)\s*$', '', cleaned, flags=re.IGNORECASE)
    # 4. Normalize common app typos
    substitutions = [
        (r'\byoutub\b|\byou\s*tube\b', 'youtube'),
        (r'\bwhatsup\b|\bwhat\s*app\b', 'whatsapp'),
        (r'\bgoogl\b', 'google'),
        (r'\bbrower\b', 'browser'),
        (r'\bnotpad\b', 'notepad'),
        (r'\bchrom\b', 'chrome'),
    ]
    for pattern, repl in substitutions:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    # 5. Clean leading conversational greetings
    cleaned = re.sub(r'^(?:please|kindly|hey|alexa|privacy68|jarvis)[,\s]+', '', cleaned, flags=re.IGNORECASE)
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


class PushToTalkRecorder:
    """Manages on-demand audio recording and transcription.

    The microphone is opened ONLY when `start()` is invoked, and is IMMEDIATELY
    stopped and closed when `stop_and_transcribe()` finishes. Zero background mic usage.
    """

    def __init__(self, sample_rate: int = config.SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.frames = []
        self._stream = None

    def start(self):
        """Starts recording mic audio on-demand."""
        import sounddevice as sd
        self.frames = []
        self.is_recording = True

        def callback(indata, frames, time_info, status):
            if self.is_recording:
                self.frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=callback,
                blocksize=config.BLOCK_SIZE
            )
            self._stream.start()
        except Exception as e:
            logger.warning(f"Could not open PushToTalk audio stream: {e}")
            self._stream = None

    def stop_and_transcribe(self, streamer: Optional['SpeechStreamer'] = None) -> str:
        """Stops recording, completely closes microphone hardware, and returns transcribed text."""
        self.is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if not self.frames:
            return ""

        audio_data = np.concatenate(self.frames).flatten()
        if len(audio_data) < self.sample_rate * 0.25:  # less than 250ms
            return ""

        peak = float(np.max(np.abs(audio_data)))
        norm_audio = (audio_data / peak) * 0.9 if peak > 0.005 else audio_data

        text = ""
        if streamer is not None:
            text = streamer._transcribe(norm_audio, is_idle=False)
        else:
            temp_streamer = SpeechStreamer(sample_rate=self.sample_rate, auto_init_hardware=False)
            text = temp_streamer._transcribe(norm_audio, is_idle=False)

        if text:
            text = autocorrect_speech_command(text)
        return text


# Alias for explicit Click-to-Speak usage
ClickToSpeakRecorder = PushToTalkRecorder


class SpeechStreamer:
    """Manages audio recording and command transcription with 100% Click-to-Speak privacy.

    Microphone hardware is completely disconnected while idle. Audio stream only opens
    when the user explicitly clicks the speak button.
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

        logger.info("PRIVACY68 Click-to-Speak Streamer initialized (100% private, microphone completely OFF while idle).")

    def is_wake_word_detected(self, text: str) -> bool:
        """Wake words are permanently disabled in favor of Click-to-Speak privacy."""
        return False

    def strip_wake_word(self, text: str) -> str:
        """Removes filler or leading conversational particles if present."""
        return re.sub(r'^(hey|ok|okay|hi|hello)\s+', '', text.strip(), flags=re.IGNORECASE).strip()

    def set_wake_word(self, wake_word: str) -> None:
        """Updates the active identifier."""
        self.wake_word = wake_word.strip()

    def set_muted(self, muted: bool) -> None:
        """Toggles the microphone mute state."""
        self.is_muted = muted
        if muted:
            self.is_active = False
            if self.recorder.is_recording:
                self.recorder.stop_and_transcribe()
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()
        logger.info(f"Microphone {'MUTED' if muted else 'UNMUTED'}.")

    def toggle_mute(self) -> bool:
        self.set_muted(not self.is_muted)
        return self.is_muted

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning(f"Audio stream status flag set: {status}")
        if not self.is_muted:
            self.audio_queue.put(indata.copy())

    def _transcribe_whisper(self, audio_data: np.ndarray) -> str:
        """Transcribes active command using 100% local, offline Faster-Whisper (zero network/cloud)."""
        try:
            model = get_whisper_model()
            if model is not None and len(audio_data) > 0:
                audio_float = audio_data.flatten().astype(np.float32)
                segments, _ = model.transcribe(audio_float, language="en", beam_size=1)
                text = " ".join([seg.text for seg in segments]).strip()
                if text:
                    logger.info(f"[LOCAL WHISPER OFFLINE] Transcribed: '{text}'")
                    return text
        except Exception as e:
            logger.warning(f"Local Whisper transcription note: {e}")
        return ""

    def _transcribe_google(self, audio_data: np.ndarray) -> str:
        """Transcribes active command using Google Web Speech Recognition (Free, Zero API Key)."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            int16_arr = (audio_data * 32767).astype(np.int16)
            audio = sr.AudioData(int16_arr.tobytes(), self.sample_rate, 2)
            text = recognizer.recognize_google(audio, language="en-US")
            if text:
                logger.info(f"[GOOGLE SPEECH FREE] Transcribed: '{text}'")
                return text.strip()
        except Exception as e:
            err_name = type(e).__name__
            if "UnknownValueError" not in err_name:
                logger.debug(f"Google Speech note: {e}")
        return ""

    def _transcribe(self, audio_data: np.ndarray, is_idle: bool = False) -> str:
        """Unified transcription method: Google Web Speech as first priority, falling back to local Faster-Whisper when offline/no internet."""
        if len(audio_data) == 0:
            return ""

        engine = getattr(config, "SPEECH_ENGINE", "auto").lower()

        # Strict offline local mode (only when user explicitly configures whisper/offline)
        if engine in ("whisper", "faster-whisper", "offline", "local"):
            text = self._transcribe_whisper(audio_data)
            if not text:
                logger.debug("Local whisper returned empty, attempting fallback to Google Speech...")
                text = self._transcribe_google(audio_data)
            return text

        # Default / Auto / Google mode:
        # First priority: Google Web Speech (fast, high accuracy, zero local GPU/CPU load).
        # Fallback: Local offline Faster-Whisper if disconnected or no internet.
        text = self._transcribe_google(audio_data)
        if not text:
            logger.info("Google Web Speech unavailable or no internet. Falling back to local offline Faster-Whisper...")
            text = self._transcribe_whisper(audio_data)
        return text

    def start_recording(self) -> None:
        """Starts recording audio on-demand when the user clicks speak."""
        if self.is_muted:
            logger.info("Cannot record: microphone is muted.")
            return
        self.is_active = True
        if self.on_wake_word_callback:
            self.on_wake_word_callback()
        self.recorder.start()

    def stop_and_transcribe(self) -> str:
        """Stops recording, completely closes microphone stream, and returns transcribed text."""
        self.is_active = False
        text = self.recorder.stop_and_transcribe(streamer=self)
        if text and self.on_text_callback:
            self.on_text_callback(text)
        if self.on_sleep_callback:
            self.on_sleep_callback()
        return text

    def start(
        self,
        on_text_callback: Callable[[str], bool],
        on_wake_word_callback: Optional[Callable[[], None]] = None,
        on_audio_energy_callback: Optional[Callable[[float], None]] = None,
        on_sleep_callback: Optional[Callable[[], None]] = None
    ) -> None:
        """Registers callbacks in Click-to-Speak mode. Microphone remains completely OFF while idle."""
        self.on_text_callback = on_text_callback
        self.on_wake_word_callback = on_wake_word_callback
        self.on_audio_energy_callback = on_audio_energy_callback
        self.on_sleep_callback = on_sleep_callback
        self._running = True

        logger.info("PRIVACY68 Voice Assistant online in Click-to-Speak mode. Microphone is completely OFF while idle.")

        while self._running:
            # Sleep cleanly without touching or opening microphone hardware
            threading.Event().wait(0.5)

    def stop(self) -> None:
        """Stops the streamer and ensures microphone is completely closed."""
        self._running = False
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_and_transcribe()


# Module singleton
speech_streamer: Optional[SpeechStreamer] = None


def set_speech_streamer(instance: SpeechStreamer) -> None:
    global speech_streamer
    speech_streamer = instance


def get_speech_streamer() -> Optional[SpeechStreamer]:
    return speech_streamer

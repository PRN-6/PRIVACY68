"""
PRIVACY68 Speech Streamer
Real-time microphone audio capture, Silero VAD gating, and Whisper transcription.
"""

from typing import Callable, Optional
import logging
import queue
import re
import difflib
import threading
import numpy as np
import sounddevice as sd

import config

try:
    from utils.cuda_manager import register_cuda_dlls
    register_cuda_dlls()
except Exception:
    pass

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

from speech.vad import SileroVAD

logger = logging.getLogger("PRIVACY68.SpeechStreamer")


def autocorrect_speech_command(text: str) -> str:
    """Cleans filler words, duplicate stutters, and typos from transcribed speech."""
    if not text:
        return ""

    cleaned = text
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
    return re.sub(r'\s+', ' ', cleaned).strip(".!?, \t\n")


class SpeechStreamer:
    """Manages continuous microphone recording, wake-word gating, and command transcription."""

    @staticmethod
    def _build_wake_pattern(wake_input: str) -> re.Pattern:
        """Builds a flexible regex matching the wake phrase and common aliases."""
        words = [w.strip() for w in (wake_input or "alexa").replace("/", ",").split(",") if w.strip()]
        if not words:
            words = ["alexa"]

        aliases = set()
        for w in words:
            clean = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', w).lower().strip()
            if not clean:
                continue
            aliases.add(clean)
            if "alexa" in clean:
                aliases.update({"alexa", "alexia", "alex"})
            if "privacy" in clean or "68" in clean:
                aliases.update({"privacy68", "privacy 68", "privacy sixty eight", "privacy"})
            if "jarvis" in clean:
                aliases.update({"jarvis", "jarvice"})

        escaped = [re.escape(a).replace(r'\ ', r'\s+') for a in sorted(aliases, key=len, reverse=True)]
        pattern_str = r'(?:\b(?:hey|hi|hello|ok|okay)\s+)?\b(' + '|'.join(escaped) + r')\b'
        return re.compile(pattern_str, re.IGNORECASE)

    def is_wake_word_detected(self, text: str) -> bool:
        """Evaluates whether the transcribed text contains the active wake word."""
        if not text:
            return False
        if self.wake_pattern.search(text):
            return True

        # Fuzzy fallback for minor ASR variations
        cleaned_words = [w.strip(".!?, \t\n").lower() for w in text.split()]
        targets = [w.strip().lower() for w in self.wake_word.replace("/", ",").split(",") if w.strip()]
        for target in targets:
            for cw in cleaned_words:
                if len(cw) >= 3 and len(target) >= 4:
                    if difflib.SequenceMatcher(None, target, cw).ratio() >= 0.75:
                        return True
        return False

    def strip_wake_word(self, text: str) -> str:
        """Removes the wake phrase from the command utterance."""
        res = self.wake_pattern.sub('', text)
        res = re.sub(r'^(hey|ok|okay|hi|hello)\s+', '', res, flags=re.IGNORECASE)
        return res.strip(".!?, \t\n")

    def __init__(self, wake_word: Optional[str] = None) -> None:
        self.sample_rate = config.SAMPLE_RATE
        self.silence_threshold = getattr(config, "SILENCE_THRESHOLD", 0.008)
        self.silence_duration_chunks = config.SILENCE_DURATION_CHUNKS
        self.vad = SileroVAD(threshold=getattr(config, "VAD_THRESHOLD", 0.50))
        self.is_active = False
        self.is_muted = False
        self.audio_queue: queue.Queue = queue.Queue()

        # Load wake word preference
        if wake_word:
            self.wake_word = wake_word
        else:
            try:
                from plugins.profile_manager import profile_manager
                self.wake_word = profile_manager.get("wake_word", getattr(config, "WAKE_WORD_MODEL", "alexa"))
            except Exception:
                self.wake_word = getattr(config, "WAKE_WORD_MODEL", "alexa")

        self.wake_pattern = self._build_wake_pattern(self.wake_word)
        logger.info(f"Wake word initialized: '{self.wake_word}'")

        # Initialize Whisper
        self.model = None
        if WhisperModel is not None:
            try:
                self.model = WhisperModel(
                    config.WHISPER_MODEL_SIZE,
                    device=config.WHISPER_DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE,
                    num_workers=1,
                    cpu_threads=2,
                )
                logger.info(f"Whisper loaded on {config.WHISPER_DEVICE} ({config.WHISPER_COMPUTE_TYPE}).")
            except Exception as e:
                logger.warning(f"Whisper CUDA init failed ({e}), falling back to CPU int8...")
                try:
                    self.model = WhisperModel(
                        config.WHISPER_MODEL_SIZE,
                        device="cpu",
                        compute_type="int8",
                        num_workers=1,
                        cpu_threads=4,
                    )
                    logger.info("Whisper loaded in CPU int8 fallback mode.")
                except Exception as ce:
                    logger.error(f"Whisper CPU load failed: {ce}")

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=config.CHANNELS,
            dtype=config.DTYPE,
            blocksize=config.BLOCK_SIZE,
            callback=self._audio_callback,
        )

    def set_muted(self, muted: bool) -> None:
        """Toggles the microphone mute state."""
        self.is_muted = muted
        if muted:
            self.is_active = False
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()
        logger.info(f"Microphone {'MUTED' if muted else 'UNMUTED'}.")

    def toggle_mute(self) -> bool:
        self.set_muted(not self.is_muted)
        return self.is_muted

    def set_wake_word(self, wake_word: str) -> None:
        """Updates the active wake word at runtime."""
        self.wake_word = wake_word.strip()
        self.wake_pattern = self._build_wake_pattern(self.wake_word)
        logger.info(f"Updated wake word to: '{self.wake_word}'")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning(f"Audio stream status flag set: {status}")
        if not self.is_muted:
            self.audio_queue.put(indata.copy())

    def start(
        self,
        on_text_callback: Callable[[str], bool],
        on_wake_word_callback: Optional[Callable[[], None]] = None,
        on_audio_energy_callback: Optional[Callable[[float], None]] = None,
        on_sleep_callback: Optional[Callable[[], None]] = None
    ) -> None:
        """Main listening loop."""
        audio_buffer = []
        idle_buffer = []
        silence_counter = 0
        has_spoken = False
        speech_chunks = 0

        idle_window_chunks = int(self.sample_rate * 1.6 / config.BLOCK_SIZE)
        idle_overlap_chunks = idle_window_chunks // 2

        logger.info(f"PRIVACY68 Voice Assistant online. Say '{self.wake_word}' to activate.")

        try:
            with self.stream:
                while self.stream.active:
                    if self.is_muted:
                        idle_buffer.clear()
                        audio_buffer.clear()
                        if on_audio_energy_callback:
                            on_audio_energy_callback(0.0)
                        threading.Event().wait(0.05)
                        continue

                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    # ── State 1: Idle Scanning for Wake Word ──
                    if not self.is_active:
                        idle_buffer.append(chunk)
                        if len(idle_buffer) >= idle_window_chunks:
                            idle_audio = np.concatenate(idle_buffer).flatten()
                            idle_buffer = idle_buffer[idle_overlap_chunks:]

                            # Energy check: skip silence / faint background hum
                            rms = float(np.sqrt(np.mean(idle_audio**2)))
                            peak = float(np.max(np.abs(idle_audio)))
                            if rms < 0.005 or peak < 0.015 or self.model is None:
                                continue

                            norm_idle = (idle_audio / peak) * 0.9 if peak > 0.01 else idle_audio
                            segments, info = self.model.transcribe(
                                norm_idle,
                                beam_size=2,
                                temperature=0.0,
                                without_timestamps=True,
                                language='en',
                                vad_filter=True,
                                initial_prompt=config.INITIAL_PROMPT,
                            )

                            if info and getattr(info, "no_speech_prob", 0.0) > 0.55:
                                continue

                            idle_text = " ".join([s.text.strip() for s in segments]).strip()

                            # Filter common Whisper silence artifacts
                            if idle_text.lower().strip(".!?, ") in {
                                "thank you", "thanks", "thanks for watching", "silence", "you",
                                "bye", "okay", "ok", "yeah", "yes", "mhm"
                            }:
                                continue

                            first_words = " ".join(idle_text.split()[:6])
                            if self.is_wake_word_detected(first_words):
                                logger.info(f"Wake word '{self.wake_word}' detected in: '{idle_text}'")
                                if on_wake_word_callback:
                                    on_wake_word_callback()

                                self.is_active = True
                                self.vad.reset()
                                has_spoken = False
                                speech_chunks = 0
                                silence_counter = 0
                                audio_buffer = list(idle_buffer)
                                idle_buffer.clear()
                        continue

                    # ── State 2: Active Command Recording ──
                    audio_buffer.append(chunk)
                    volume = float(np.sqrt(np.mean(chunk**2)))
                    if on_audio_energy_callback:
                        on_audio_energy_callback(volume)

                    is_voice = self.vad.is_speech(chunk)
                    if is_voice:
                        speech_chunks += 1
                        silence_counter = 0
                        if speech_chunks >= 2:
                            has_spoken = True
                    else:
                        if has_spoken:
                            silence_counter += 1

                    # Cancel if user stopped speaking before saying any command (6s timeout)
                    max_wait_chunks = int(self.sample_rate * 6.0 / config.BLOCK_SIZE)
                    if not has_spoken and len(audio_buffer) >= max_wait_chunks:
                        logger.info("Listening timed out without speech. Returning to sleep.")
                        audio_buffer.clear()
                        self.vad.reset()
                        self.is_active = False
                        if on_sleep_callback:
                            on_sleep_callback()
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        continue

                    # Process command on speech completion (~1.8s pause) or max limit (14s)
                    max_chunks = int(self.sample_rate * 14.0 / config.BLOCK_SIZE)
                    silence_cutoff = max(self.silence_duration_chunks, 22)
                    if (has_spoken and silence_counter >= silence_cutoff) or (has_spoken and len(audio_buffer) >= max_chunks):
                        logger.info("Speech finished. Processing command...")
                        full_audio = np.concatenate(audio_buffer).flatten()

                        rms = float(np.sqrt(np.mean(full_audio**2)))
                        peak = float(np.max(np.abs(full_audio)))
                        if rms < 0.004 or peak < 0.01:
                            logger.info("Audio energy too low. Discarding.")
                            audio_buffer.clear()
                            self.vad.reset()
                            self.is_active = False
                            if on_sleep_callback:
                                on_sleep_callback()
                            continue

                        norm_audio = (full_audio / peak) * 0.9 if peak > 0.005 else full_audio
                        if self.model is None:
                            text = ""
                        else:
                            segments, info = self.model.transcribe(
                                norm_audio,
                                beam_size=config.WHISPER_BEAM_SIZE,
                                temperature=0.0,
                                condition_on_previous_text=False,
                                without_timestamps=True,
                                language='en',
                                vad_filter=True,
                                initial_prompt=config.INITIAL_PROMPT,
                                hotwords=config.WHISPER_HOTWORDS,
                            )
                            if info and getattr(info, "no_speech_prob", 0.0) > 0.45:
                                text = ""
                            else:
                                text = " ".join([segment.text.strip() for segment in segments]).strip()

                        if text:
                            text = self.strip_wake_word(text)
                            text = autocorrect_speech_command(text)

                        # Filter standalone wake word / empty utterances
                        if text.lower().strip(".!?, ") in {"alexa", "privacy68", "jarvis", "yes", "okay"} or len(text.strip()) <= 2:
                            logger.info("Wake word received without command. Remaining in active listening...")
                            audio_buffer.clear()
                            self.vad.reset()
                            speech_chunks = 0
                            silence_counter = 0
                            has_spoken = False
                            continue

                        if text:
                            logger.info(f"Executing: '{text}'")
                            on_text_callback(text)

                        if on_sleep_callback:
                            on_sleep_callback()

                        audio_buffer.clear()
                        self.vad.reset()
                        speech_chunks = 0
                        silence_counter = 0
                        has_spoken = False
                        self.is_active = False
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        logger.info(f"Command cycle complete. Say '{self.wake_word}' to activate.")

        except Exception as e:
            logger.error(f"Error in streaming pipeline: {e}")
            raise


# Module singleton
speech_streamer: Optional[SpeechStreamer] = None


def set_speech_streamer(instance: SpeechStreamer) -> None:
    global speech_streamer
    speech_streamer = instance


def get_speech_streamer() -> Optional[SpeechStreamer]:
    return speech_streamer

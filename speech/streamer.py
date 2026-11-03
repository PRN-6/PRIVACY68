"""
PRIVACY68 Speech Streamer
Real-time microphone audio capture, Silero VAD gating, and Whisper transcription.
"""

from typing import Callable, Optional
import os
import io
import wave
import requests
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

from speech.vad import SileroVAD

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


class SpeechStreamer:
    """Manages continuous microphone recording, wake-word gating, and command transcription."""

    @staticmethod
    def _build_wake_pattern(wake_input: str) -> re.Pattern:
        """Builds a flexible regex matching the wake phrase and common phonetic aliases."""
        words = [w.strip() for w in (wake_input or "alexa").replace("/", ",").split(",") if w.strip()]
        if not words:
            words = ["alexa"]

        aliases = set()
        for w in words:
            clean = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', w).lower().strip()
            if not clean:
                continue
            aliases.add(clean)
            if "google" in clean:
                aliases.update({
                    "hey google", "ok google", "okay google"
                })
            if "alexa" in clean or "alex" in clean:
                aliases.update({
                    "alexa", "alexia", "alex", "alixa", "elexa", "alecsa"
                })
            if "privacy" in clean or "68" in clean:
                aliases.update({
                    "privacy68", "privacy 68", "privacy sixty eight",
                    "privacy sixty-eight", "privacy"
                })
            if "jarvis" in clean:
                aliases.update({
                    "jarvis", "jarvice", "jervis"
                })
            if "nova" in clean:
                aliases.update({"nova", "noba"})
            if "friday" in clean:
                aliases.update({"friday", "frieda"})

        escaped = [re.escape(a).replace(r'\ ', r'\s+') for a in sorted(aliases, key=len, reverse=True)]
        pattern_str = r'(?:\b(?:hey|hi|hello|ok|okay|ah|oh)\s+)?\b(' + '|'.join(escaped) + r')\b'
        return re.compile(pattern_str, re.IGNORECASE)

    def is_wake_word_detected(self, text: str) -> bool:
        """Evaluates whether the transcribed text contains the active wake word with strict matching."""
        if not text:
            return False
        if self.wake_pattern.search(text):
            return True

        target_wake = self.wake_word.lower()
        lowered = text.lower()

        # Strict checks for compound wake phrases (Hey Google, etc.)
        if "google" in target_wake:
            if any(p in lowered for p in ("hey google", "ok google", "okay google")):
                return True

        if "privacy" in target_wake:
            if "privacy 68" in lowered or "privacy68" in lowered:
                return True

        # Strict fuzzy whole-word match (ratio >= 0.88) to prevent phantom activations
        cleaned_words = [w.strip(".!?, \t\n'\"`") for w in lowered.split()]
        targets = [w.strip().lower() for w in self.wake_word.replace("/", ",").split(",") if w.strip()]
        for target in targets:
            for cw in cleaned_words:
                if len(cw) >= 4 and len(target) >= 4:
                    if difflib.SequenceMatcher(None, target, cw).ratio() >= 0.88:
                        return True
        return False

    def strip_wake_word(self, text: str) -> str:
        """Removes the wake phrase from the command utterance."""
        res = self.wake_pattern.sub('', text)
        res = re.sub(r'^(hey|ok|okay|hi|hello|ah|oh)\s+', '', res, flags=re.IGNORECASE)
        res = re.sub(r"^['\"`‘“\s]+|['\"`’”\s]+$", "", res.strip())
        return res.strip(".!?, \t\n")

    def _transcribe_groq(self, audio_data: np.ndarray) -> str:
        """Transcribes audio using Groq Cloud Whisper Large-v3-Turbo (~99% accuracy, ~150ms)."""
        api_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return ""

        try:
            int16_arr = (audio_data * 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(int16_arr.tobytes())
            buf.seek(0)

            files = {"file": ("command.wav", buf.getvalue(), "audio/wav")}
            data = {
                "model": getattr(config, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
                "language": "en",
                "temperature": "0.0",
                "prompt": config.INITIAL_PROMPT,
            }
            headers = {"Authorization": f"Bearer {api_key.strip()}"}

            resp = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=4.5
            )
            if resp.status_code == 200:
                result_text = resp.json().get("text", "").strip()
                logger.info(f"[GROQ WHISPER TURBO] Transcribed: '{result_text}'")
                return result_text
            else:
                logger.warning(f"Groq API returned {resp.status_code}: {resp.text}")
                return ""
        except Exception as e:
            logger.warning(f"Groq Whisper cloud call failed ({e}), falling back to local engine...")
            return ""

    def _transcribe_google(self, audio_data: np.ndarray) -> str:
        """Transcribes active command using Google Web Speech Recognition (100% Free, Zero API Key)."""
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
        """Unified transcription method using Google Cloud Speech (Free, zero keys) or Groq Cloud Whisper."""
        if len(audio_data) == 0:
            return ""

        engine = getattr(config, "SPEECH_ENGINE", "auto").lower()

        # 1. If explicit "google" engine selected
        if "google" in engine:
            g_res = self._transcribe_google(audio_data)
            if g_res:
                return g_res

        # 2. Prefer Groq Cloud Whisper Large Turbo if API key is present
        api_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        if api_key:
            groq_res = self._transcribe_groq(audio_data)
            if groq_res:
                return groq_res

        # 3. Default / Fallback: Google Web Speech API (100% Free, zero setup)
        g_res = self._transcribe_google(audio_data)
        if g_res:
            return g_res

        return ""

    def __init__(
        self,
        wake_word: Optional[str] = None,
        sample_rate: int = config.SAMPLE_RATE,
        auto_init_hardware: bool = True
    ) -> None:
        self.sample_rate = sample_rate
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

        self.stream = None
        if auto_init_hardware:
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=config.CHANNELS,
                    dtype=config.DTYPE,
                    blocksize=config.BLOCK_SIZE,
                    callback=self._audio_callback,
                )
            except Exception as e:
                logger.warning(f"Audio input device not available or could not open stream: {e}")
                self.stream = None

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

        idle_window_chunks = int(self.sample_rate * 2.2 / config.BLOCK_SIZE)
        idle_step_chunks = max(1, int(self.sample_rate * 0.6 / config.BLOCK_SIZE))

        logger.info(f"PRIVACY68 Voice Assistant online. Say '{self.wake_word}' to activate.")

        if self.stream is None:
            logger.warning("Audio input stream is not available; cannot start listening loop.")
            return

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
                            idle_buffer = idle_buffer[idle_step_chunks:]

                            # VAD + Energy check: require audible speech and reject ambient room noise / breathing
                            rms = float(np.sqrt(np.mean(idle_audio**2)))
                            peak = float(np.max(np.abs(idle_audio)))
                            if rms < 0.008:
                                continue

                            # Verify sustained human voice (at least 3 voice frames in recent buffer ~240ms)
                            speech_frames = sum(1 for c in idle_buffer[-8:] if self.vad.is_speech(c))
                            if speech_frames < 3:
                                continue

                            norm_idle = (idle_audio / peak) * 0.9 if peak > 0.01 else idle_audio
                            idle_text = self._transcribe(norm_idle, is_idle=True)

                            # Filter common Whisper silence artifacts
                            if idle_text.lower().strip(".!?, ") in {
                                "thank you", "thanks", "thanks for watching", "silence", "you",
                                "bye", "bye bye", "okay", "ok", "yeah", "yes", "mhm", "subtitles",
                                "watching", "cough"
                            }:
                                continue

                            if self.is_wake_word_detected(idle_text):
                                logger.info(f"Wake word '{self.wake_word}' detected in: '{idle_text}'")
                                if on_wake_word_callback:
                                    on_wake_word_callback()

                                self.is_active = True
                                self.vad.reset()

                                # Check if a command was spoken in the same utterance (e.g. "Alexa open Chrome")
                                command_candidate = self.strip_wake_word(idle_text)
                                command_candidate = autocorrect_speech_command(command_candidate)

                                has_prior_command = len(command_candidate.split()) >= 1 and command_candidate.lower() not in {
                                    "alexa", "jarvis", "privacy68", "hey", "hi", "hello", "yes", "ok", "okay"
                                }

                                if has_prior_command:
                                    logger.info(f"One-shot command candidate detected: '{command_candidate}'")
                                    has_spoken = True
                                    speech_chunks = 3
                                else:
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
                        text = self._transcribe(norm_audio, is_idle=False)

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


class PushToTalkRecorder:
    """Manages hold-to-talk audio recording and transcription with zero wake-word false alarms."""

    def __init__(self, sample_rate: int = config.SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.frames = []
        self._stream = None

    def start(self):
        """Starts recording mic audio."""
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

    def stop_and_transcribe(self, streamer: Optional[SpeechStreamer] = None) -> str:
        """Stops recording and returns the transcribed text."""
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

        if streamer is not None:
            text = streamer._transcribe(norm_audio, is_idle=False)
        else:
            # First try Google Web Speech (Free, zero keys)
            text = ""
            try:
                import speech_recognition as sr
                rec = sr.Recognizer()
                int16_arr = (norm_audio * 32767).astype(np.int16)
                aud = sr.AudioData(int16_arr.tobytes(), self.sample_rate, 2)
                text = rec.recognize_google(aud, language="en-US").strip()
            except Exception as ge:
                logger.debug(f"Google speech recognition error: {ge}")

            # If Google speech didn't return text and Groq API key is present, try Groq Cloud
            if not text:
                groq_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
                if groq_key:
                    try:
                        int16_arr = (norm_audio * 32767).astype(np.int16)
                        buf = io.BytesIO()
                        with wave.open(buf, 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(self.sample_rate)
                            wf.writeframes(int16_arr.tobytes())
                        buf.seek(0)
                        files = {"file": ("command.wav", buf.getvalue(), "audio/wav")}
                        data = {
                            "model": getattr(config, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
                            "language": "en",
                            "temperature": "0.0",
                            "prompt": config.INITIAL_PROMPT,
                        }
                        headers = {"Authorization": f"Bearer {groq_key.strip()}"}
                        resp = requests.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers=headers,
                            files=files,
                            data=data,
                            timeout=5.0
                        )
                        if resp.status_code == 200:
                            text = resp.json().get("text", "").strip()
                    except Exception as qe:
                        logger.debug(f"Groq speech transcription error: {qe}")

        if text:
            text = autocorrect_speech_command(text)
        return text


# Alias for explicit Click-to-Speak usage
ClickToSpeakRecorder = PushToTalkRecorder

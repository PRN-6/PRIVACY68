try:
    from utils.cuda_manager import register_cuda_dlls
    register_cuda_dlls()
except Exception as e:
    import logging as _logging
    _logging.getLogger("PRIVACY68.SpeechStreamer").debug(
        f"CUDA DLL registration skipped: {e}"
    )

# openWakeWord replaced by Whisper-based wake detection
from typing import Callable
import logging
import re
import threading
import config

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

def get_whisper_model_class():
    global WhisperModel
    if WhisperModel is None:
        try:
            from utils.cuda_manager import register_cuda_dlls
            register_cuda_dlls()
            from faster_whisper import WhisperModel as WM
            WhisperModel = WM
        except Exception:
            WhisperModel = None
    return WhisperModel
from speech.vad import SileroVAD
import queue
import sounddevice as sd
import numpy as np
try:
    from plugins.profile_manager import profile_manager
except Exception:
    profile_manager = None
logging.basicConfig(level=logging.INFO , format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PRIVACY68.SpeechStreamer")

def autocorrect_speech_command(text: str) -> str:
    """
    Cleans disfluencies, filler sounds (hmmm, ummm, bmmm, uhhh), hesitations,
    stutters, and trailing noise from transcribed speech to auto-correct
    the user's command into a clean, proper statement.
    """
    if not text:
        return ""

    cleaned = text

    # 1. Remove filler sounds, vocal tics, and hesitations (e.g. hmmm, ummm, bmmm, uhhh, ahhh, errr)
    filler_pattern = r'\b(h+m+|u+m+|u+h+|a+h+|e+r+|b+m+|m+h+m+|m+m+)\b'
    cleaned = re.sub(filler_pattern, ' ', cleaned, flags=re.IGNORECASE)

    # 2. Remove stuttered consecutive duplicate words (e.g. 'open open' -> 'open', 'the the' -> 'the')
    cleaned = re.sub(r'\b([a-zA-Z]+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)

    # 3. Clean trailing filler prepositions or orphaned conjunctions (e.g. 'search for youtube in' -> 'search for youtube')
    cleaned = re.sub(r'\s+(in|at|on|for|with|and|to|the|a|of)\s*$', '', cleaned, flags=re.IGNORECASE)

    # 4. Normalize common speech recognition misspellings
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

    # 5. Strip conversational/filler prefixes at start of command (e.g. 'accept, go to...' -> 'go to...')
    cleaned = re.sub(r'^(?:accept|please|kindly|hey|alexa|privacy68|jarvis|jarvice|nova|friday|leo|serena)[,\s]+', '', cleaned, flags=re.IGNORECASE)

    # 6. Collapse multiple spaces and clean punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(".!?, \t\n")
    return cleaned


class SpeechStreamer:
    @staticmethod
    def _build_wake_pattern(wake_input: str) -> re.Pattern:
        """
        Builds a robust regex pattern from one or more custom wake words.
        Supports:
        - Any arbitrary unique word or phrase (e.g. 'Zephyr', 'Bumblebee', 'Kratos', 'Aegis', 'Nova')
        - Phonetic variations of digits (e.g. 'privacy68' -> 'privacy 68', 'privacy sixty eight', 'privacy sixty-eight', 'privacy six eight', 'privacy 6 8')
        - Optional natural conversational greetings (e.g. 'hey privacy 68', 'ok privacy', 'hi nova')
        """
        if not wake_input:
            wake_input = "alexa"
        
        words = [w.strip() for w in wake_input.replace("/", ",").split(",") if w.strip()]
        if not words:
            words = ["alexa"]

        aliases = set()
        for w in words:
            # Separate letters and numbers: e.g. 'privacy68' -> 'privacy 68'
            spaced = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', w)
            spaced = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', spaced)
            for base in [w, spaced]:
                clean = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', base).lower().strip()
                clean = re.sub(r'\s+', ' ', clean)
                if not clean:
                    continue
                aliases.add(clean)
                if '68' in clean:
                    aliases.add(clean.replace('68', 'sixty eight').strip())
                    aliases.add(clean.replace('68', 'sixty-eight').strip())
                    aliases.add(clean.replace('68', 'six eight').strip())
                    aliases.add(clean.replace('68', '6 8').strip())
                    aliases.add(re.sub(r'\s*68\b', '', clean).strip())  # e.g. 'privacy'
                if 'privacy' in clean:
                    aliases.add('privacy')
                    aliases.add('privacy 68')
                    aliases.add('privacy68')
                    aliases.add('privacy sixty eight')
                    aliases.add('privacy sixty-eight')
                    aliases.add('privacy six eight')
                if any(k in clean for k in ('jarvis', 'jarvice', 'jarves', 'jarviz')):
                    aliases.update({'jarvis', 'jarvice', 'jarves', 'jarviz', 'jar vus', 'javis'})
                if 'alexa' in clean:
                    aliases.update({'alexa', 'alexia', 'alixa', 'alex'})
                if 'nova' in clean:
                    aliases.update({'nova', 'novah'})
                if 'friday' in clean:
                    aliases.update({'friday', 'fryday'})

        # Convert aliases to regex parts, handling spaces and hyphens flexibly
        escaped = [
            re.escape(a).replace(r'\ ', r'\s+').replace(r'\-', r'[\s\-]+')
            for a in sorted(aliases, key=len, reverse=True)
            if a
        ]
        if not escaped:
            escaped = [r'privacy68', r'privacy\s+68']

        pattern_str = r'(?:\b(?:hey|hi|hello|ok|okay)\s+)?\b(' + '|'.join(escaped) + r')\b'
        return re.compile(pattern_str, re.IGNORECASE)

    def is_wake_word_detected(self, text: str) -> bool:
        """
        Generic, dynamic detector for ANY wake word or phrase.
        Uses regex matching (including phonetic number expansions and conversational greetings)
        plus dynamic fuzzy matching for custom names so minor transcription variations match reliably.
        """
        if not text:
            return False

        # 1. Direct Regex / Substring check (covers exact, phonetic numbers, and greetings)
        if self.wake_pattern.search(text):
            return True

        # 2. Dynamic Fuzzy Matching for custom names (threshold 0.75 allows jarvis/jarvice & accents)
        import difflib
        cleaned_words = [w.strip(".!?, \t\n").lower() for w in text.split()]
        target_wake_words = [w.strip().lower() for w in self.wake_word.replace("/", ",").split(",") if w.strip()]

        for target in target_wake_words:
            # Single word fuzzy match (e.g. 'jarvice' vs 'jarvis' [0.77], 'novva' vs 'nova')
            for cw in cleaned_words:
                if len(cw) >= 3 and len(target) >= 4:
                    similarity = difflib.SequenceMatcher(None, target, cw).ratio()
                    if similarity >= 0.75:
                        logger.info(f"Fuzzy wake word match: '{cw}' matches '{target}' (Similarity: {similarity:.2f})")
                        return True
            
            # Multi-word 2-gram fuzzy match (e.g. 'hey nova', 'privacy sixty')
            if " " in target and len(cleaned_words) >= 2:
                for i in range(len(cleaned_words) - 1):
                    two_gram = f"{cleaned_words[i]} {cleaned_words[i+1]}"
                    similarity = difflib.SequenceMatcher(None, target, two_gram).ratio()
                    if similarity >= 0.75:
                        logger.info(f"Fuzzy 2-gram wake word match: '{two_gram}' matches '{target}' (Similarity: {similarity:.2f})")
                        return True

        return False

    def strip_wake_word(self, text: str) -> str:
        """Removes the wake word and any conversational greeting prefixes from commands."""
        res = self.wake_pattern.sub('', text)
        # Also clean leading conversational greetings
        res = re.sub(r'^(hey|ok|okay|hi|hello)\s+', '', res, flags=re.IGNORECASE)
        return res.strip(".!?, \t\n")

    def __init__(self, wake_word: str = None) -> None:
        self.sample_rate = config.SAMPLE_RATE
        self.silence_threshold = getattr(config, "SILENCE_THRESHOLD", 0.008)
        self.silence_duration_chunks = config.SILENCE_DURATION_CHUNKS
        self.vad = SileroVAD(threshold=getattr(config, "VAD_THRESHOLD", 0.50))
        self.is_active = False

        # Load user-configured custom wake word (e.g. Nova, Leo, Serena)
        if wake_word:
            self.wake_word = wake_word
        else:
            try:
                from plugins.profile_manager import profile_manager
                self.wake_word = profile_manager.get("wake_word", getattr(config, "WAKE_WORD_MODEL", "privacy68"))
            except Exception:
                self.wake_word = getattr(config, "WAKE_WORD_MODEL", "privacy68")

        self.wake_pattern = self._build_wake_pattern(self.wake_word)
        logger.info(f"Custom Wake Word initialized: '{self.wake_word}' (Patterns: {self.wake_pattern.pattern})")

        self.model = None
        WM = get_whisper_model_class()
        if WM is not None:
            try:
                self.model = WM(
                    config.WHISPER_MODEL_SIZE,
                    device=config.WHISPER_DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE,
                    num_workers=1,      # limit worker threads → less RAM overhead
                    cpu_threads=2,      # cap CPU threads → pushes compute to GPU
                )
                # Warm up GPU inference so first command is instant
                _warmup = np.zeros(config.SAMPLE_RATE, dtype=np.float32)
                list(self.model.transcribe(_warmup, beam_size=1, without_timestamps=True)[0])
                logger.info(f"Whisper model warmed up on {config.WHISPER_DEVICE}.")
            except Exception as e:
                if config.WHISPER_DEVICE == "cuda":
                    logger.warning(f"Failed to load Whisper model on CUDA ({e}). Falling back to multi-core CPU (int8)...")
                    try:
                        self.model = WM(
                            config.WHISPER_MODEL_SIZE,
                            device="cpu",
                            compute_type="int8",
                            num_workers=1,
                            cpu_threads=4,
                        )
                        logger.info("Whisper model successfully loaded on CPU (int8 fallback mode).")
                    except Exception as cpu_e:
                        logger.warning(f"Whisper model CPU load failed ({cpu_e}).")
                else:
                    logger.warning(f"Failed to load whisper model: {e}")
        else:
            logger.warning("faster_whisper is unavailable (DLL policy or missing dependencies). Voice microphone input disabled; HUD/Remote/Agent services remain active.")

        
        self.is_muted = False
        self.audio_queue: queue.Queue = queue.Queue()

        # Enrollment capture state – filled by _audio_callback when active
        self._enrollment_chunks: list = []
        self._enrollment_target_chunks: int = 0
        self._enrollment_event: threading.Event = threading.Event()
        self._enrollment_lock: threading.Lock = threading.Lock()

        self.stream = sd.InputStream(
            samplerate = self.sample_rate,
            channels = config.CHANNELS,
            dtype = config.DTYPE,
            blocksize = config.BLOCK_SIZE,
            callback = self._audio_callback,
        )

    def set_biometrics_enabled(self, enabled: bool) -> None:
        pass

    def set_biometric_threshold(self, threshold: float) -> None:
        pass

    def reload_voiceprint(self) -> bool:
        return False

    def set_muted(self, muted: bool) -> None:
        """Sets the microphone mute state."""
        self.is_muted = muted
        if muted:
            self.is_active = False
            # Clear any pending audio
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
        logger.info(f"SpeechStreamer microphone {'MUTED' if muted else 'UNMUTED'}.")

    def toggle_mute(self) -> bool:
        """Toggles the microphone mute state. Returns new muted state."""
        self.set_muted(not self.is_muted)
        return self.is_muted

    def set_wake_word(self, wake_word: str) -> None:
        """Dynamically updates the active wake word(s)."""
        self.wake_word = wake_word.strip()
        self.wake_pattern = self._build_wake_pattern(self.wake_word)
        logger.info(f"Updated active wake word to: '{self.wake_word}' (Pattern: {self.wake_pattern.pattern})")

    def _audio_callback(self, indata: np.ndarray, frames: int, time: dict, status: sd.CallbackFlags) -> None:
        # callback executed for each audio buffer
        if status:
            logger.warning(f"Audio stream status flag set: {status}")
        chunk = indata.copy()
        # Feed enrollment capture buffer (taps same device/gain as live stream)
        with self._enrollment_lock:
            if len(self._enrollment_chunks) < self._enrollment_target_chunks:
                self._enrollment_chunks.append(chunk)
                if len(self._enrollment_chunks) >= self._enrollment_target_chunks:
                    self._enrollment_event.set()
        # If muted, do not queue audio to whisper
        if not self.is_muted:
            self.audio_queue.put(chunk)
    
    def capture_enrollment_audio(self, duration: float = 3.0) -> np.ndarray:
        """
        Captures `duration` seconds of audio from the SAME stream/device/gain used for
        live speaker verification.  This ensures enrollment and verification embeddings
        are computed from acoustically identical input, fixing low-score mismatches when
        sd.rec() picked a different device or applied different gain.
        """
        num_chunks = int(self.sample_rate * duration / config.BLOCK_SIZE) + 1
        with self._enrollment_lock:
            self._enrollment_chunks.clear()
            self._enrollment_target_chunks = num_chunks
            self._enrollment_event.clear()
        if not self._enrollment_event.wait(timeout=duration + 5.0):
            logger.warning("Enrollment capture timed out; using partial audio.")
        with self._enrollment_lock:
            captured = list(self._enrollment_chunks)
            self._enrollment_target_chunks = 0
        if not captured:
            return np.zeros(int(self.sample_rate * duration), dtype=np.float32)
        audio = np.concatenate(captured).flatten()
        return audio[:int(self.sample_rate * duration)]

    def start(
        self,
        on_text_callback: Callable[[str], bool],
        on_wake_word_callback: Callable[[], None] = None,
        on_audio_energy_callback: Callable[[float], None] = None,
        on_sleep_callback: Callable[[], None] = None
    ) -> None:
        audio_buffer = []
        idle_buffer = []          # Short rolling buffer used for wake word detection
        silence_counter = 0
        has_spoken = False
        speech_chunks = 0

        # Scan window of 1.6 seconds to reliably capture multi-word wake phrases ("Privacy 68", "Hey Nova", etc.)
        IDLE_WINDOW_CHUNKS = int(self.sample_rate * 1.6 / config.BLOCK_SIZE)
        # 50% overlap: keep last half of the buffer so wake word at window boundaries is never missed
        IDLE_OVERLAP_CHUNKS = IDLE_WINDOW_CHUNKS // 2

        logger.info(f"PRIVACY68 Voice Assistant is online. Say '{self.wake_word}' to activate.")
        try:
            with self.stream:
                while self.stream.active:
                    if self.is_muted:
                        idle_buffer.clear()
                        audio_buffer.clear()
                        if on_audio_energy_callback:
                            on_audio_energy_callback(0.0)
                        import time as _t
                        _t.sleep(0.05)
                        continue

                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    # 1. Idle state: Listen for custom wake word via Whisper
                    if not self.is_active:
                        # Accumulate audio into idle_buffer
                        idle_buffer.append(chunk)

                        if len(idle_buffer) >= IDLE_WINDOW_CHUNKS:

                            # Transcribe the short idle buffer using Whisper
                            idle_audio = np.concatenate(idle_buffer).flatten()

                            # Overlapping window — keep last half for next scan
                            idle_buffer = idle_buffer[IDLE_OVERLAP_CHUNKS:]

                            # ── Energy gate: skip absolute silence and quiet background hum ──
                            # Adjusted to 0.005 RMS / 0.015 Peak so soft voices and distant/low-gain laptop mics are not dropped.
                            idle_rms  = float(np.sqrt(np.mean(idle_audio**2)))
                            idle_peak = float(np.max(np.abs(idle_audio)))
                            if idle_rms < 0.005 or idle_peak < 0.015:
                                continue

                            if self.model is None:
                                continue

                            # Normalize idle audio peak so Whisper receives clean, high-gain signal regardless of microphone hardware
                            if idle_peak > 0.01:
                                norm_idle_audio = (idle_audio / idle_peak) * 0.9
                            else:
                                norm_idle_audio = idle_audio

                            segments, info = self.model.transcribe(
                                norm_idle_audio,
                                beam_size=2,
                                temperature=0.0,
                                without_timestamps=True,
                                language='en',
                                vad_filter=True,
                                initial_prompt=config.INITIAL_PROMPT,
                            )

                            # ── Discard if model is uncertain about speech ──
                            # 0.55 threshold permits softer or accented speech while still filtering pure noise
                            if info and getattr(info, "no_speech_prob", 0.0) > 0.55:
                                continue

                            idle_text = " ".join([s.text.strip() for s in segments]).strip()

                            # ── Hallucination artifact filter ──
                            # Whisper consistently outputs these strings on near-silence
                            # or non-command background audio. Drop them unconditionally.
                            IDLE_ARTIFACTS = {
                                # Silence artifacts
                                "silence.", "silence", "silence. silence.",
                                # Thank-you / farewell artifacts
                                "thank you.", "thank you", "thank you very much.",
                                "thanks for watching.", "thanks for watching",
                                "thank you for listening.", "thank you for listening",
                                "thank you for watching.", "thank you for watching",
                                "thank you so much.", "thanks.", "thanks",
                                # Filler artifacts
                                "mhm.", "mhm", "mm-hmm.", "uh-huh.",
                                "yeah.", "yeah", "yes.", "yes",
                                "okay.", "okay", "ok.", "ok",
                                "right.", "right", "alright.", "alright", "all right.",
                                "sure.", "sure", "yep.", "yep", "nope.", "nope",
                                "bye.", "bye", "bye-bye.", "goodbye.",
                                "congratulations.", "congratulations",
                                "you", "people.", "people", "never",
                                "i don't know.", "i don't know", "i don't know.",
                                "maybe not.", "you know", "never mind.",
                                "very much", "sort of engineering.",
                                "little on that", "to think.", "anything.",
                                "done with an indicator.", "they learned with",
                                "you know they love you.", "i'm gonna teach you.",
                                "all right, we found.", "bye, everybody.",
                            }
                            if idle_text.lower().strip(".!?, ") in {a.strip(".!?, ") for a in IDLE_ARTIFACTS}:
                                continue

                            if idle_text:
                                logger.info(f"Idle scan heard: '{idle_text}'")

                            # Dynamically sync wake word from profile_manager
                            try:
                                if profile_manager:
                                    p_wake = profile_manager.get("wake_word")
                                    if p_wake and p_wake.strip().lower() != self.wake_word.lower():
                                        self.set_wake_word(p_wake)
                            except Exception as e:
                                logger.debug(f"Wake word sync from profile failed: {e}")

                            # Check if user said the custom wake word (ANY unique name or phrase)
                            # Checking within first 6 words allows natural leading greetings ("uh hey privacy 68")
                            first_words = " ".join(idle_text.split()[:6])
                            if self.is_wake_word_detected(first_words):
                                logger.info(f"Wake word '{self.wake_word}' matched in: '{idle_text}'")

                                if on_wake_word_callback:
                                    on_wake_word_callback()

                                # Play activation beep (if enabled in config)
                                if getattr(config, "ENABLE_BEEP", False):
                                    try:
                                        import winsound
                                        threading.Thread(target=lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK), daemon=True).start()
                                    except Exception as e:
                                        logger.debug(f"Activation beep failed: {e}")

                                # Activate listening mode and carry over recent audio chunks
                                # so continuous command words spoken right after wake word in one breath are preserved
                                logger.info("Activated listening mode. Listening for command...")
                                self.is_active = True
                                self.vad.reset()
                                has_spoken = False
                                speech_chunks = 0
                                silence_counter = 0
                                audio_buffer = list(idle_buffer)
                                idle_buffer.clear()
                                continue
                        continue

                    # 2. Active state: Record voice command
                    audio_buffer.append(chunk)
                    volume = float(np.sqrt(np.mean(chunk**2)))

                    if on_audio_energy_callback:
                        on_audio_energy_callback(volume)

                    # Silero Neural VAD: check for actual human speech
                    is_voice = self.vad.is_speech(chunk)

                    if is_voice:
                        speech_chunks += 1
                        if speech_chunks >= 3:  # Require at least ~240ms of speech before marking as active speaking
                            has_spoken = True
                            silence_counter = 0
                    else:
                        if has_spoken:
                            silence_counter += 1

                    # Check timeout if user never spoke after wake word (give full 7.0 seconds to start speaking)
                    total_chunks = len(audio_buffer)
                    timeout_chunks = int(self.sample_rate * 7.0 / config.BLOCK_SIZE)
                    if not has_spoken and total_chunks >= timeout_chunks:
                        logger.info("No command spoken after wake word. Returning to sleep.")
                        audio_buffer.clear()
                        self.vad.reset()
                        self.is_active = False
                        if on_sleep_callback:
                            on_sleep_callback()
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        continue

                    # Process command when speech finishes (allow ~1.8s silence pause) or max duration reached (14s)
                    max_chunks = int(self.sample_rate * 14.0 / config.BLOCK_SIZE)
                    silence_cutoff = max(self.silence_duration_chunks, 22)  # ~1.76 seconds of pause to allow thinking/long commands
                    if (has_spoken and silence_counter >= silence_cutoff) or (has_spoken and total_chunks >= max_chunks):
                        logger.info("Speech finished. Processing complete command...")
                        full_audio = np.concatenate(audio_buffer).flatten()

                        # ── Anti-hallucination gate 1: RMS Energy & Peak Check ──
                        rms = float(np.sqrt(np.mean(full_audio**2)))
                        max_peak = float(np.max(np.abs(full_audio)))
                        
                        if rms < 0.004 or max_peak < 0.01:
                            logger.info(f"Audio energy too low (RMS: {rms:.4f}, Peak: {max_peak:.4f}). Discarding.")
                            audio_buffer.clear()
                            self.vad.reset()
                            self.is_active = False
                            if on_sleep_callback:
                                on_sleep_callback()
                            with self.audio_queue.mutex:
                                self.audio_queue.queue.clear()
                            continue


                        # Normalize audio volume so Whisper receives clean, high-gain signal
                        if max_peak > 0.005:
                            full_audio = (full_audio / max_peak) * 0.9

                        if self.model is None:
                            logger.warning("Whisper model is not available for transcription.")
                            text = ""
                        else:
                            segments, info = self.model.transcribe(
                                full_audio,
                                beam_size=config.WHISPER_BEAM_SIZE,
                                temperature=0.0,
                                condition_on_previous_text=False,
                                without_timestamps=True,
                                language='en',
                                vad_filter=True,
                                initial_prompt=config.INITIAL_PROMPT,
                                hotwords=config.WHISPER_HOTWORDS,
                            )

                        # ── Anti-hallucination gate 2: no_speech_prob check ──
                        # medium.en is more calibrated — 0.45 discards more noise without
                        # losing real quiet speech (was 0.65, too lenient).
                        if info and getattr(info, "no_speech_prob", 0.0) > 0.45:
                            logger.info(f"Whisper flagged segment as non-speech (no_speech_prob={info.no_speech_prob:.2f}). Discarding.")
                            text = ""
                        else:
                            text = " ".join([segment.text.strip() for segment in segments]).strip()

                        # ── Anti-hallucination gate 3: Common silence artifacts filter ──
                        HALLUCINATION_PATTERNS = {
                            "thank you.", "thank you very much.", "thank you", "thanks for watching.",
                            "subtitles by", "you", "bye.", "bye", "okay.", "okay"
                        }
                        if text.lower().strip() in HALLUCINATION_PATTERNS and rms < 0.015:
                            logger.info(f"Filtered out hallucination artifact '{text}' on low-energy audio.")
                            text = ""

                        # ── Strip Wake Word Prefix if repeated in command audio ──
                        if text:
                            text = self.strip_wake_word(text)

                        # ── Auto-Correct & Clean Disfluencies (hmmm, bmmm, ummm, stutters) ──
                        if text:
                            raw_transcription = text
                            text = autocorrect_speech_command(raw_transcription)
                            if text != raw_transcription:
                                logger.info(f"Speech Auto-Corrected: '{raw_transcription}' -> '{text}'")

                        # ── Filter Out Standalone Wake Words / Empty Utterances ──
                        KNOWN_NON_COMMANDS = {
                            "alexa", "nova", "privacy68", "privacy 68", "privacy sixty eight", "privacy sixty-eight",
                            "privacy six eight", "privacy", "jarvis", "jarvice", "jarves", "friday", "leo", "serena",
                            "hey alexa", "hey nova", "hey privacy", "hey privacy68", "hey privacy 68",
                            "hey jarvis", "hey jarvice", "ok jarvis",
                            "ok privacy", "ok privacy 68", "yes", "yeah", "okay", "hi", "hello"
                        }
                        if text.lower().strip(".!?, ") in KNOWN_NON_COMMANDS or len(text.strip()) <= 2:
                            logger.info(f"Wake word detected ('{text}'). Actively listening for your command...")
                            text = ""

                        # If user spoke only the wake word, stay in active listening mode for their command!
                        if not text:
                            audio_buffer.clear()
                            self.vad.reset()
                            speech_chunks = 0
                            silence_counter = 0
                            has_spoken = False
                            continue

                        if text:
                            logger.info(f"Executing Transcribed Command: '{text}'")
                            on_text_callback(text)
                        else:
                            logger.info("Command was non-actionable.")
                        
                        # Return to sleep mode after command attempt
                        if on_sleep_callback:
                            on_sleep_callback()

                        # Reset state
                        audio_buffer.clear()
                        self.vad.reset()
                        speech_chunks = 0
                        silence_counter = 0
                        has_spoken = False
                        self.is_active = False

                        # Clear audio queue to avoid stale audio
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        logger.info(f"Command cycle completed. PRIVACY68 is in sleep mode (Say '{self.wake_word}' to speak).")

        except Exception as e:
            logger.error(f"Error in streaming pipeline: {e}")
            raise


# ---------------------------------------------------------------------------
# Module-level singleton – set by app.py after constructing the streamer.
# The dashboard bridge imports this to capture enrollment audio from the same
# InputStream that handles live speaker verification, ensuring identical gain.
# ---------------------------------------------------------------------------
speech_streamer: "SpeechStreamer | None" = None


def set_speech_streamer(instance: "SpeechStreamer") -> None:
    """Called by app.py after constructing the SpeechStreamer to register the singleton."""
    global speech_streamer
    speech_streamer = instance
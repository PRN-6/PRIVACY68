import os
import time
import json
import logging
import numpy as np
import onnxruntime as ort

# Fix for ONNX pybind API version mismatch on Windows
try:
    from onnxruntime.capi import onnxruntime_inference_collection
    if hasattr(onnxruntime_inference_collection.InferenceSession, "_validate_graph_capture_run_api"):
        onnxruntime_inference_collection.InferenceSession._validate_graph_capture_run_api = lambda self, run_options: None
except Exception:
    pass

from typing import Tuple, Optional, List, Dict
from huggingface_hub import hf_hub_download
import scipy.signal as signal

logger = logging.getLogger("PRIVACY68.VoiceAuth")

APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
MODELS_DIR = os.path.join(APPDATA_DIR, "models")
PROFILE_PATH = os.path.join(APPDATA_DIR, "voice_profile.npy")
PROFILE_META_PATH = os.path.join(APPDATA_DIR, "voice_profile_meta.json")

# Legacy migration path
LEGACY_APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "SANA")
LEGACY_PROFILE_PATH = os.path.join(LEGACY_APPDATA_DIR, "voice_profile.npy")
LEGACY_META_PATH = os.path.join(LEGACY_APPDATA_DIR, "voice_profile_meta.json")

os.makedirs(MODELS_DIR, exist_ok=True)


def preprocess_farfield_audio(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Conditions far-field microphone audio for biometric verification:
    1. Removes DC offset and sub-bass room rumble (HVAC, laptop fan, table vibrations) using an 80Hz Butterworth HPF.
    2. Dynamically scales RMS energy to standard listening levels so distance attenuation does not penalize cosine similarity.
    """
    waveform = audio.flatten().astype(np.float32)
    if len(waveform) < 160:  # < 10ms
        return waveform

    # 1. DC offset removal
    waveform = waveform - np.mean(waveform)

    # 2. 80Hz High-pass Butterworth filter (removes low-frequency mechanical & room rumble)
    try:
        sos = signal.butter(4, 80.0, 'hp', fs=sample_rate, output='sos')
        filtered = signal.sosfilt(sos, waveform).astype(np.float32)
    except Exception:
        filtered = waveform

    # 3. RMS Loudness Normalization to target -20 dBFS (~0.10 RMS)
    rms = float(np.sqrt(np.mean(filtered**2)))
    if rms > 1e-4:
        target_rms = 0.10
        gain = min(target_rms / rms, 25.0)  # max 25x digital gain boost
        filtered = filtered * gain

    # 4. Soft peak limiter to avoid hard clipping distortion
    max_peak = float(np.max(np.abs(filtered)))
    if max_peak > 0.95:
        filtered = (filtered / max_peak) * 0.95

    return filtered.astype(np.float32)


def normalize_audio(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    """
    Normalizes audio waveform to a consistent target peak amplitude.
    Ensures identical dynamic range across enrollment samples, testing modal,
    and live microphone streaming.
    """
    waveform = audio.flatten().astype(np.float32)
    max_peak = np.max(np.abs(waveform))
    if max_peak > 0.002:
        return (waveform / max_peak) * target_peak
    return waveform


def trim_speech(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Dynamically trims silence based on adaptive background noise floor estimation.
    Ensures 100% of voiced speech is captured across all microphones without clipping soft vowels or consonants.
    """
    waveform = audio.flatten().astype(np.float32)
    if len(waveform) < sample_rate * 0.2:  # Less than 200ms, keep as is
        return waveform
    
    frame_len = int(sample_rate * 0.02)  # 20ms frame (320 samples @ 16kHz)
    num_frames = len(waveform) // frame_len
    if num_frames == 0:
        return waveform

    reshaped = waveform[:num_frames * frame_len].reshape(num_frames, frame_len)
    energies = np.sqrt(np.mean(reshaped ** 2, axis=1))
    
    noise_floor = float(np.percentile(energies, 15))
    peak_energy = float(np.percentile(energies, 95))
    if peak_energy < 0.003:
        return waveform
        
    cutoff = noise_floor + 0.12 * (peak_energy - noise_floor)
    active = np.where(energies >= cutoff)[0]
    if len(active) == 0:
        return waveform
        
    pad_frames = 3  # 60ms padding
    start_frame = max(0, active[0] - pad_frames)
    end_frame = min(num_frames, active[-1] + 1 + pad_frames)
    
    return waveform[start_frame * frame_len : end_frame * frame_len]


class VoiceAuthenticator:
    """
    State-of-the-art Speaker Verification biometrics using ECAPA-TDNN (ONNX).
    Extracts 192-dimensional speaker embeddings and computes multi-sample ensemble
    cosine similarity against enrolled master voice profile (Google Voice Match style).
    """
    def __init__(self, sample_rate: int = 16000, n_mels: int = 80, frame_length: float = 25.0, frame_shift: float = 10.0):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.win_len = int(sample_rate * frame_length / 1000)  # 400 samples
        self.hop_len = int(sample_rate * frame_shift / 1000)   # 160 samples
        self.n_fft = 512
        
        self.session: Optional[ort.InferenceSession] = None
        self.is_ready = False
        
        # Enrolled master embeddings (centroid 192-d and individual sample vectors)
        self.master_embedding: Optional[np.ndarray] = None
        self.enrolled_samples: Optional[np.ndarray] = None
        self.temp_enrollment_samples: List[np.ndarray] = []
        
        # Precompute Kaldi Povey window and Mel filterbank matrix once for sub-2ms speed
        self._precompute_kaldi_filters()
        
        # Initialize model session
        self._init_model()
        
        # Load existing profile if available
        self.load_profile()

    def _precompute_kaldi_filters(self):
        """Precomputes exact Kaldi-compliant Povey window and Mel filterbank matrix."""
        # Povey Window: Hamming^0.85 = (0.5 - 0.5 * cos(2*pi*i / (N-1)))^0.85
        i = np.arange(self.win_len)
        self.window = ((0.5 - 0.5 * np.cos(2.0 * np.pi * i / (self.win_len - 1))) ** 0.85).astype(np.float32)
        
        # Exact Kaldi Mel Filterbank (Formula: 1127.0 * ln(1 + f / 700))
        low_freq = 20.0
        high_freq = self.sample_rate / 2.0  # 8000.0 Hz (Nyquist)
        num_fft_bins = self.n_fft // 2      # 256
        fft_bin_width = self.sample_rate / self.n_fft  # 31.25 Hz

        mel_low = 1127.0 * np.log(1.0 + low_freq / 700.0)
        mel_high = 1127.0 * np.log(1.0 + high_freq / 700.0)
        mel_delta = (mel_high - mel_low) / (self.n_mels + 1)

        b = np.arange(self.n_mels)[:, None]  # (80, 1)
        left_mel = mel_low + b * mel_delta
        center_mel = mel_low + (b + 1.0) * mel_delta
        right_mel = mel_low + (b + 2.0) * mel_delta

        fft_freqs = fft_bin_width * np.arange(num_fft_bins)[None, :]  # (1, 256)
        mel = 1127.0 * np.log(1.0 + fft_freqs / 700.0)

        up_slope = (mel - left_mel) / (center_mel - left_mel)
        down_slope = (right_mel - mel) / (right_mel - center_mel)
        bins = np.maximum(0.0, np.minimum(up_slope, down_slope))  # (80, 256)

        # Kaldi pads Nyquist bin (k = 256) with zero, giving (num_mel_bins, 257)
        padded_bins = np.pad(bins, ((0, 0), (0, 1)), mode="constant", constant_values=0)
        self.mel_filterbank = padded_bins.T.astype(np.float32)  # Shape: (257, 80)

    def _init_model(self):
        """Loads SOTA CAM++ (Context-Aware Masking) Speaker Recognition ONNX model (512-d)."""
        try:
            model_path = os.path.join(MODELS_DIR, "voxceleb_CAM++_LM.onnx")
            if not os.path.exists(model_path):
                logger.info("Downloading SOTA CAM++ Speaker Recognition ONNX model (~29MB)...")
                downloaded_path = hf_hub_download(
                    repo_id="Wespeaker/wespeaker-voxceleb-campplus-LM",
                    filename="voxceleb_CAM++_LM.onnx",
                    local_dir=MODELS_DIR
                )
                if os.path.exists(downloaded_path) and downloaded_path != model_path:
                    try:
                        import shutil
                        shutil.copy2(downloaded_path, model_path)
                    except Exception:
                        model_path = downloaded_path

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            self.session = ort.InferenceSession(model_path, sess_options=opts, providers=['CPUExecutionProvider'])
            self.is_ready = True
            logger.info("CAM++ Speaker Authenticator initialized successfully (512-d).")
        except Exception as e:
            logger.error(f"Failed to initialize Voice Authenticator model: {e}")
            self.is_ready = False

    def compute_fbank(self, audio: np.ndarray) -> np.ndarray:
        """
        Extracts 80-channel Kaldi Log-Mel Filterbanks strictly matching torchaudio.compliance.kaldi.fbank
        and WeSpeaker's training pipeline.
        Processes audio array and returns (num_frames, 80) feature matrix.
        """
        waveform = audio.flatten().astype(np.float32)
        
        # Scale float [-1.0, 1.0] to standard 16-bit PCM integer range [-32768, 32767] expected by Kaldi
        if np.max(np.abs(waveform)) <= 1.5:
            waveform = waveform * 32768.0

        if len(waveform) < self.win_len:
            waveform = np.pad(waveform, (0, self.win_len - len(waveform)))

        # 1. Framing (snip_edges=True)
        num_frames = 1 + (len(waveform) - self.win_len) // self.hop_len
        frames = np.lib.stride_tricks.as_strided(
            waveform,
            shape=(num_frames, self.win_len),
            strides=(waveform.strides[0] * self.hop_len, waveform.strides[0])
        ).copy()

        # 2. Kaldi remove DC offset per frame
        frames -= np.mean(frames, axis=1, keepdims=True)

        # 3. Kaldi per-frame pre-emphasis (0.97) with replicate left-padding
        padded = np.pad(frames, ((0, 0), (1, 0)), mode="edge")
        frames = frames - 0.97 * padded[:, :-1]

        # 4. Kaldi Povey window
        frames *= self.window

        # 5. FFT power spectrum (padded to next power of 2: n_fft = 512)
        frames = np.pad(frames, ((0, 0), (0, self.n_fft - self.win_len)), mode="constant", constant_values=0)
        fft_complex = np.fft.rfft(frames, n=self.n_fft)
        power_spectrum = np.abs(fft_complex) ** 2.0

        # 6. Mel Filterbank dot product
        mel_energy = np.dot(power_spectrum, self.mel_filterbank)
        mel_energy = np.maximum(mel_energy, np.finfo(np.float32).eps)
        log_mel = np.log(mel_energy)

        # 7. Cepstral Mean Normalization (CMN) matching WeSpeaker
        log_mel -= np.mean(log_mel, axis=0, keepdims=True)
        return log_mel.astype(np.float32)

    def extract_embedding(self, audio: np.ndarray, apply_preprocess: bool = True) -> Optional[np.ndarray]:
        """
        Extracts a 512-dimensional unit-normalized speaker embedding vector from 16kHz audio using CAM++.
        Applies far-field filtering, RMS normalization, and silence trimming to isolate pure vocal tract resonance.
        """
        if not self.is_ready or self.session is None:
            return None

        try:
            if apply_preprocess:
                prep = preprocess_farfield_audio(audio, sample_rate=self.sample_rate)
                clean_audio = trim_speech(prep, sample_rate=self.sample_rate)
            else:
                clean_audio = audio

            if len(clean_audio) < int(self.sample_rate * 0.1):  # Less than 100ms
                return None

            feats = self.compute_fbank(clean_audio)
            feats_batch = np.expand_dims(feats, axis=0)  # Shape: (1, T, 80)
            
            output = self.session.run(None, {'feats': feats_batch})
            emb = output[0][0].astype(np.float32)
            
            # L2 Unit Normalization
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            return emb
        except Exception as e:
            logger.error(f"Error extracting voice embedding: {e}")
            return None

    def extract_multi_window_embeddings(self, audio: np.ndarray, window_sec: float = 1.2, hop_sec: float = 0.5) -> List[np.ndarray]:
        """
        Extracts temporal sliding-window embeddings across the voiced segments of an utterance.
        Prevents a single momentary room reflection or muffled syllable from corrupting the entire score.
        """
        prep = preprocess_farfield_audio(audio, sample_rate=self.sample_rate)
        voiced = trim_speech(prep, sample_rate=self.sample_rate)
        
        window_samples = int(self.sample_rate * window_sec)
        hop_samples = int(self.sample_rate * hop_sec)
        
        embeddings: List[np.ndarray] = []
        
        # If utterance is shorter than sliding window, extract directly
        if len(voiced) <= window_samples:
            emb = self.extract_embedding(voiced, apply_preprocess=False)
            return [emb] if emb is not None else []
            
        # Sliding temporal windows
        for start in range(0, len(voiced) - window_samples + 1, hop_samples):
            chunk = voiced[start : start + window_samples]
            chunk_rms = float(np.sqrt(np.mean(chunk**2)))
            if chunk_rms >= 0.003:
                emb = self.extract_embedding(chunk, apply_preprocess=False)
                if emb is not None:
                    embeddings.append(emb)
                    
        # Also include global whole-utterance embedding
        global_emb = self.extract_embedding(voiced, apply_preprocess=False)
        if global_emb is not None:
            embeddings.append(global_emb)
            
        return embeddings

    def enroll_sample(self, audio: np.ndarray) -> Dict:
        """
        Records an enrollment audio sample into temporary buffer.
        Returns the current sample count and sample status.
        """
        emb = self.extract_embedding(audio, apply_preprocess=True)
        if emb is None:
            return {"success": False, "message": "Failed to extract voice embedding from sample.", "count": len(self.temp_enrollment_samples)}

        self.temp_enrollment_samples.append(emb)
        logger.info(f"Voice enrollment sample {len(self.temp_enrollment_samples)} recorded successfully.")
        return {
            "success": True,
            "message": f"Sample {len(self.temp_enrollment_samples)} recorded successfully.",
            "count": len(self.temp_enrollment_samples),
            "max": 3
        }

    def save_profile(self, owner_name: str = "Owner") -> bool:
        """
        Saves all recorded enrollment sample embeddings as an ensemble matrix (N, 512)
        and computes the master centroid vector for Google Voice Match style ensemble verification.
        """
        if not self.temp_enrollment_samples:
            logger.warning("Cannot save voice profile: No enrollment samples recorded.")
            return False

        try:
            stacked = np.array(self.temp_enrollment_samples, dtype=np.float32)
            centroid = np.mean(stacked, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm

            self.master_embedding = centroid.astype(np.float32)
            self.enrolled_samples = stacked

            # Save full multi-sample ensemble matrix
            np.save(PROFILE_PATH, self.enrolled_samples)

            meta = {
                "owner_name": owner_name,
                "samples_count": len(self.temp_enrollment_samples),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": "CAM++-512d",
                "dim": 512,
                "ensemble": True
            }
            with open(PROFILE_META_PATH, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            self.temp_enrollment_samples.clear()
            logger.info(f"Master voice profile saved for '{owner_name}' with {len(stacked)} ensemble samples at {PROFILE_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to save voice profile: {e}")
            return False

    def load_profile(self) -> bool:
        """Loads master voice embeddings (both ensemble matrix and centroid) from disk if available."""
        target_path = PROFILE_PATH
        if not os.path.exists(target_path) and os.path.exists(LEGACY_PROFILE_PATH):
            target_path = LEGACY_PROFILE_PATH

        if os.path.exists(target_path):
            try:
                data = np.load(target_path).astype(np.float32)
                if data.ndim == 1:
                    # Legacy 1D centroid vector
                    norm = np.linalg.norm(data)
                    self.master_embedding = (data / norm) if norm > 0 else data
                    self.enrolled_samples = self.master_embedding.reshape(1, -1)
                elif data.ndim == 2:
                    # Multi-sample ensemble matrix (N, 512)
                    self.enrolled_samples = data
                    centroid = np.mean(data, axis=0)
                    norm = np.linalg.norm(centroid)
                    self.master_embedding = (centroid / norm).astype(np.float32) if norm > 0 else centroid
                
                logger.info(f"Loaded master voice profile from disk ({len(self.enrolled_samples)} sample vectors).")
                return True
            except Exception as e:
                logger.warning(f"Could not load voice profile: {e}")
        self.master_embedding = None
        self.enrolled_samples = None
        return False

    def clear_profile(self) -> bool:
        """Deletes master voice profile and resets enrollment state."""
        self.master_embedding = None
        self.enrolled_samples = None
        self.temp_enrollment_samples.clear()
        try:
            for p in [PROFILE_PATH, PROFILE_META_PATH, LEGACY_PROFILE_PATH, LEGACY_META_PATH]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            logger.info("Voice profile cleared.")
            return True
        except Exception as e:
            logger.error(f"Error clearing voice profile: {e}")
            return False

    def verify_speaker(self, audio: np.ndarray, threshold: float = 0.50) -> Tuple[bool, float]:
        """
        Compares live far-field audio against master voice profile using Multi-Window Ensemble Biometrics.
        Evaluates sliding temporal speech segments against the centroid and sample cluster.
        Returns: (is_authorized: bool, score: float)
        """
        if self.master_embedding is None:
            self.load_profile()

        if self.master_embedding is None:
            logger.warning("Voice Lock active, but no master profile is enrolled! Access blocked.")
            return False, 0.0

        window_embs = self.extract_multi_window_embeddings(audio)
        if not window_embs:
            return False, 0.0

        scores = []
        centroid_scores = []
        for emb in window_embs:
            c_score = float(np.dot(self.master_embedding, emb))
            centroid_scores.append(c_score)
            
            if self.enrolled_samples is not None and len(self.enrolled_samples) > 0:
                sample_sims = np.dot(self.enrolled_samples, emb)
                max_s = float(np.max(sample_sims))
                mean_s = float(np.mean(sample_sims))
                # Balance closest exemplar with centroid
                w_score = max(c_score, max_s, 0.60 * max_s + 0.40 * c_score)
            else:
                w_score = c_score
            scores.append(w_score)

        scores.sort(reverse=True)
        max_chunk_score = scores[0]
        top_k = max(1, len(scores) // 2)
        top_k_mean = float(np.mean(scores[:top_k]))
        centroid_avg = float(np.mean(centroid_scores))

        # Robust aggregation: Top-K mean prevents single bad/reverberant chunk from hurting score
        effective_score = max(
            top_k_mean,
            max_chunk_score * 0.92,
            0.65 * top_k_mean + 0.35 * max_chunk_score
        )

        is_authorized = bool(effective_score >= threshold)
        logger.info(
            f"Voice Lock Verification: Score = {effective_score:.3f} "
            f"(Top Chunk: {max_chunk_score:.3f}, Top-K Mean: {top_k_mean:.3f}, Centroid: {centroid_avg:.3f}, Windows: {len(window_embs)}) "
            f"| Threshold = {threshold:.2f} | Authorized = {is_authorized}"
        )
        return is_authorized, round(effective_score, 4)

    def get_status(self) -> Dict:
        """Returns the current state of voice biometrics."""
        is_enrolled = self.master_embedding is not None and os.path.exists(PROFILE_PATH)
        meta = {}
        if is_enrolled and os.path.exists(PROFILE_META_PATH):
            try:
                with open(PROFILE_META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        return {
            "model_ready": self.is_ready,
            "is_enrolled": is_enrolled,
            "temp_samples_count": len(self.temp_enrollment_samples),
            "owner_name": meta.get("owner_name", "User"),
            "created_at": meta.get("created_at", None),
        }


# Global singleton instance
voice_authenticator = VoiceAuthenticator()

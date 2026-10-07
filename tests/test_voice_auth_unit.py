import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from speech.voice_auth import voice_authenticator, preprocess_farfield_audio, trim_speech

def test_voice_auth():
    print("=== Testing Voice Authenticator Unit Pipeline ===")
    print(f"Model Ready: {voice_authenticator.is_ready}")
    print(f"Master embedding loaded: {voice_authenticator.master_embedding is not None}")
    
    sr = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # 1. Test Far-field Preprocessor
    low_rumble = 0.05 * np.sin(2 * np.pi * 30 * t)  # 30Hz hum
    voice_tone = 0.10 * np.sin(2 * np.pi * 300 * t) # 300Hz tone
    test_audio = (low_rumble + voice_tone).astype(np.float32)
    
    filtered = preprocess_farfield_audio(test_audio, sample_rate=sr)
    print(f"  [Preprocessor] Input RMS: {np.sqrt(np.mean(test_audio**2)):.4f} -> Output RMS: {np.sqrt(np.mean(filtered**2)):.4f}")
    assert len(filtered) == len(test_audio)
    
    # 2. Test Multi-Window Embedding Extraction
    embs = voice_authenticator.extract_multi_window_embeddings(test_audio)
    print(f"  [Multi-Window] Extracted {len(embs)} embeddings (shape: {embs[0].shape if embs else 'None'})")
    assert len(embs) > 0, "Failed to extract embeddings"
    assert embs[0].shape == (512,), f"Expected 512-d CAM++ embedding, got {embs[0].shape}"
    
    # 3. Test Rejection of Random Noise
    rand_noise = (np.random.randn(sr * 2) * 0.02).astype(np.float32)
    auth, score = voice_authenticator.verify_speaker(rand_noise, threshold=0.50)
    print(f"  [Security] Noise Verification -> Authorized: {auth}, Score: {score:.3f}")
    assert not auth, "Noise must be rejected by Voice Lock!"
    
    print(">>> All Voice Authenticator Unit Tests Passed Successfully! <<<")

if __name__ == "__main__":
    test_voice_auth()

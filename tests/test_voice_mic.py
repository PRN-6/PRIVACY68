"""
Interactive Voice Lock Tester
Run this script to speak into your microphone and test if PRIVACY68 verifies your voice!
Usage: .venv\\Scripts\\python.exe test_voice_mic.py
"""
import os
import sys
import time
sys.path.insert(0, os.path.abspath("."))

import numpy as np
import sounddevice as sd
from plugins.profile_manager import profile_manager
from speech.voice_auth import voice_authenticator

def test_mic():
    print("=" * 60)
    print("      PRIVACY68 VOICE LOCK BIOMETRICS TESTER")
    print("=" * 60)
    
    if not voice_authenticator.master_embedding is not None:
        print("[ERROR] No master voice profile found on disk.")
        print("Please open the Dashboard and complete the 3-sample voice enrollment first.")
        return

    threshold = float(profile_manager.get("voice_lock_threshold", 0.65))
    user_name = profile_manager.get("user_name", "Owner")
    print(f"Enrolled Owner: '{user_name}'")
    print(f"Current Voice Lock Threshold: {threshold:.2f} (or higher to pass)")
    print()
    print("Get ready to speak a test phrase (e.g., 'Alexa, open PowerPoint')...")
    for i in range(3, 0, -1):
        print(f"Starting in {i}...", end="\r", flush=True)
        time.sleep(1)

    duration = 3.0
    sr = 16000
    print("\n🎤 RECORDING NOW... (Speak naturally for 3 seconds)")
    recording = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    print("✅ Recording complete! Analyzing voice biometrics...")

    audio = recording.flatten()
    rms = float(np.sqrt(np.mean(audio**2)))
    if rms < 0.005:
        print(f"[WARN] Audio too quiet (RMS: {rms:.4f}). Speak louder or move closer to mic.")
        return

    is_match, score = voice_authenticator.verify_speaker(audio, threshold=threshold)
    pct = int(score * 100)

    print("-" * 60)
    print(f"Similarity Score: {score:.3f} ({pct}%)")
    print(f"Required Threshold: {threshold:.2f} ({int(threshold * 100)}%)")
    if is_match:
        print(f" Result: ✅ [AUTHORIZED] Welcome back, {user_name}! Voice verified.")
    else:
        print(f" Result: 🚨 [ACCESS DENIED] Voice did not match the enrolled owner profile.")
    print("-" * 60)

if __name__ == "__main__":
    test_mic()

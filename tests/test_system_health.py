import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
import numpy as np
from plugins.profile_manager import profile_manager
from speech.voice_auth import voice_authenticator
from actions.router import LLMRouter


class TestSystemHealth(unittest.TestCase):

    def test_system(self):
        print("=== PRIVACY68 System Health Check ===")
        print(f"Wake word: '{profile_manager.get('wake_word')}'")
        print(f"Voice Lock enabled: {profile_manager.get('voice_lock_enabled')}")
        print(f"Voice Lock threshold: {profile_manager.get('voice_lock_threshold')}")
        print(f"Master voice profile loaded: {voice_authenticator.master_embedding is not None}")

        # 1. LLM Router test
        router = LLMRouter()
        test_phrases = [
            "launch chrome",
            "open whatsapp",
            "open vscode"
        ]
        for phrase in test_phrases:
            tool = router.route(phrase)
            print(f"  [Router] '{phrase}' -> {tool}")
            self.assertIsNotNone(tool, f"Failed to route '{phrase}'")

        # 2. Voice Authenticator Rejection test
        test_noise = (np.random.randn(32000) * 0.05).astype(np.float32)
        auth, score = voice_authenticator.verify_speaker(
            test_noise,
            threshold=float(profile_manager.get('voice_lock_threshold', 0.65))
        )
        print(f"  [Voice Lock] Random noise test -> Authorized: {auth} (Score: {score:.3f})")
        self.assertFalse(auth, "Voice Lock failed to block random noise!")

        # 3. Foreign voice rejection test
        sr = 16000
        t = np.linspace(0, 2.0, 2 * sr)
        fake_voice = (0.2 * np.sin(2 * np.pi * 350 * t)).astype(np.float32)
        auth_fake, score_fake = voice_authenticator.verify_speaker(
            fake_voice,
            threshold=float(profile_manager.get('voice_lock_threshold', 0.65))
        )
        print(f"  [Voice Lock] Foreign voice test -> Authorized: {auth_fake} (Score: {score_fake:.3f})")
        self.assertFalse(auth_fake, "Voice Lock failed to block foreign voice!")

        print("\n>>> ALL SYSTEM CHECKS PASSED PERFECTLY! <<<")


if __name__ == "__main__":
    unittest.main()

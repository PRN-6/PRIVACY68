import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
import numpy as np
from plugins.profile_manager import profile_manager
from speech.voice_auth import voice_authenticator
from actions.router import LLMRouter, is_ollama_alive


class TestSystemHealth(unittest.TestCase):

    def test_system(self):
        print("=== PRIVACY68 System Health Check ===")
        print(f"Wake word: '{profile_manager.get('wake_word')}'")
        print(f"Voice Lock enabled: {profile_manager.get('voice_lock_enabled')}")
        print(f"Voice Lock threshold: {profile_manager.get('voice_lock_threshold')}")
        print(f"Master voice profile loaded: {voice_authenticator.master_embedding is not None}")

        # 1. LLM Router test.
        # Routing through the LLM lane needs a live model: a local Ollama on
        # port 11434, or a configured cloud provider. On a clean CI runner
        # neither exists, so the router correctly returns None. The tool
        # catalogue is still verified — that part is machine-independent.
        router = LLMRouter()
        test_phrases = [
            "launch chrome",
            "open whatsapp",
            "open vscode"
        ]

        provider = profile_manager.get("llm_provider", "ollama").lower()
        has_cloud = provider in ("openai", "groq", "custom") and bool(profile_manager.get("api_key"))
        llm_available = has_cloud or is_ollama_alive()

        for phrase in test_phrases:
            tool = router.route(phrase)
            print(f"  [Router] '{phrase}' -> {tool}")
            if llm_available:
                self.assertIsNotNone(tool, f"Failed to route '{phrase}'")
            else:
                self.assertIsNone(
                    tool,
                    f"'{phrase}' should not resolve without a live LLM backend.",
                )

        # The tool catalogue is what makes routing possible at all — it must
        # always be indexed, with or without a model running.
        self.assertGreater(len(router._tools), 0, "LLM Router indexed no tools")
        print(f"  [Router] Tools indexed: {len(router._tools)}")

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

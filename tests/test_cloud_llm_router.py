import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
from plugins.profile_manager import profile_manager
from actions.router import LLMRouter

class TestDualModeRouter(unittest.TestCase):
    def test_default_profile_mode(self):
        provider = profile_manager.get("llm_provider", "ollama")
        self.assertIn(provider, ["ollama", "openai", "groq", "custom"])
        print(f"  [Profile] Active LLM provider is '{provider}'")

    def test_router_initialization(self):
        router = LLMRouter()
        self.assertIsNotNone(router)
        print(f"  [Router] Tools indexed: {len(router._tools)}")

    def test_empty_route(self):
        router = LLMRouter()
        res = router.route("")
        self.assertIsNone(res)
        print("  [Router] Empty text returns None cleanly")

if __name__ == "__main__":
    unittest.main()

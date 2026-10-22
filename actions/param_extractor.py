"""
PRIVACY68 — Slot Extractor.

Given an utterance and the intent it was classified as, this module
returns the arguments of the command: the folder name, the file to
rename, the search query, the city, the text to type.

Extraction is deterministic and driven by the command catalogue:

    1. the matcher that recognised the command may already have captured
       the arguments as named groups ("open the (?P<page>...) page")
    2. whatever is still missing is filled in by the command's own slot
       extractor (a small, readable set of rules per command family)

A trained token tagger used to sit here, but it could not tell the
difference between "create a folder called Cats and Dogs" (one name) and
"delete tmp and build folders" (one delete), and it silently dropped
arguments it had never seen in training. Rules that are visible in the
catalogue are easier to read, easier to test, and never guess.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Dict

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from actions.registry import registry  # noqa: E402

import actions.catalog  # noqa: E402,F401  (populates the registry)

logger = logging.getLogger("PRIVACY68.ParamExtractor")

# Kept for compatibility with older builds that shipped a token tagger.
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "param_model.pkl")


class ParamExtractor:
    """Extracts the arguments of a command from an utterance."""

    def extract_slots(self, text: str, intent: str) -> Dict[str, str]:
        """
        Returns the slot values for `text` under `intent`.

        Recognised slot names: name, source, path, query, site, browser,
        content, city, page, action, backend, operation, metric.
        """
        if not text or not text.strip():
            return {}

        spec = registry.spec_for_intent(intent)
        if spec is None:
            return {}

        slots: Dict[str, str] = {}

        # 1. Arguments the recognising matcher already captured.
        match = registry.match_spec(text, spec.id)
        if match:
            slots.update(match.slots)

        # 2. Whatever is still missing comes from the command's own rules.
        if spec.slot_extractor:
            try:
                extracted = spec.slot_extractor(text) or {}
            except Exception as exc:
                logger.debug("Slot extraction for '%s' failed: %s", spec.id, exc)
                extracted = {}
            for key, value in extracted.items():
                if value and not slots.get(key):
                    slots[key] = value

        return slots

    def extract(self, text: str, intent: str) -> Dict[str, str]:
        """Alias for extract_slots()."""
        return self.extract_slots(text, intent)


# Global singleton
param_extractor = ParamExtractor()


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")

    test_cases = [
        ("create a folder named Privacy on Desktop", "create_folder"),
        ("create MCA folder in downloads", "create_folder"),
        ("create file sample.txt in downloads", "create_file"),
        ("create file todo.txt with content buy groceries", "create_file"),
        ("rename file old_doc.txt to final_doc.txt in downloads", "rename_item"),
        ("delete file test.txt in downloads", "delete_item"),
        ("search machine learning algorithms on google", "web_search"),
        ("open chrome and search for youtube", "compound_browser"),
        ("play believer on youtube", "compound_browser"),
        ("open bluetooth settings", "open_settings"),
        ("what is the weather in Tokyo", "api_weather"),
    ]
    print(f"{'INTENT':18s} | EXTRACTED PARAMETERS")
    print("-" * 72)
    for sentence, intent in test_cases:
        print(f"{intent:18s} | {param_extractor.extract_slots(sentence, intent)}")

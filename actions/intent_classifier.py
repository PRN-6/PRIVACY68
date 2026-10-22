"""
PRIVACY68 — Intent Classifier.

The classifier answers one question: *what does this utterance mean?*
It has three layers, each more forgiving than the last:

    1. THE REGISTRY — a registered command is recognised exactly, with
       full confidence. This is the layer that does the real work: the
       command catalogue already knows how to recognise "mute the volume"
       or "create a folder named Privacy on Desktop".
    2. THE MODEL — a character n-gram classifier trained on the command
       catalogue, used for phrasings the catalogue does not spell out.
    3. A HEURISTIC — a last resort when no model is available.

The taxonomy (which intents exist, and which lane owns each of them) is
derived from the registry, so the classifier and the dispatcher can never
disagree about what a command is called.
"""

from __future__ import annotations

import logging
import os
import pickle
import sys
from typing import Dict, List, Optional, Tuple

# Ensure the project root is importable when the module is loaded directly.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from actions.registry import (  # noqa: E402
    LANE_API,
    LANE_FAST,
    LANE_LLM,
    normalize,
    registry,
)

# Importing the catalogue populates the registry with every built-in
# command — the classifier's taxonomy and training data come from there.
import actions.catalog  # noqa: E402,F401

logger = logging.getLogger("PRIVACY68.IntentClassifier")

# Model storage paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "intent_model.pkl")

# ─── Lane Definitions ────────────────────────────────────────────────────────
LANES = (LANE_FAST, LANE_API, LANE_LLM)

# ─── Intent Taxonomy (derived from the command catalogue) ───────────────────
INTENT_TO_LANE: Dict[str, str] = registry.intent_lane()

FAST_INTENTS = frozenset(i for i, lane in INTENT_TO_LANE.items() if lane == LANE_FAST)
API_INTENTS = frozenset(i for i, lane in INTENT_TO_LANE.items() if lane == LANE_API)
LLM_INTENTS = frozenset(i for i, lane in INTENT_TO_LANE.items() if lane == LANE_LLM)

ALL_INTENTS = sorted(INTENT_TO_LANE)

#: Exact phrase -> (lane, intent). Derived from the command catalogue, so it
#: can never drift away from the commands that actually exist.
CANONICAL_EXACT_MAP: Dict[str, Tuple[str, str]] = {}
for _lane in LANES:
    for _phrase, _entries in registry._phrases.get(_lane, {}).items():
        for _spec, _matcher in _entries:
            CANONICAL_EXACT_MAP.setdefault(_phrase, (_spec.lane, _spec.intent))

# ─── Training Corpus ─────────────────────────────────────────────────────────
# The catalogue is the primary source of training data. These extra
# examples cover the phrasings the compound planner has to reason about
# and the open-ended requests that belong to the LLM lane.
EXTRA_TRAINING_DATA: List[Tuple[str, str]] = [
    # Open-ended reasoning
    ("write a python script", "llm_reasoning"),
    ("write a python script to parse a csv file", "llm_reasoning"),
    ("tell me a joke", "llm_reasoning"),
    ("what does this error mean", "llm_reasoning"),
    ("summarize this text", "llm_reasoning"),
    ("translate this to spanish", "llm_reasoning"),

    # Plugin tool calls
    ("send it to mom", "plugin_tool_call"),
    ("send hi to mom", "plugin_tool_call"),
    ("message mom saying hi", "plugin_tool_call"),
    ("tell mom hi", "plugin_tool_call"),
    ("text john saying hi", "plugin_tool_call"),
    ("open a chat with mom", "plugin_tool_call"),

    # Ambiguous verbs the planner must not treat as commands
    ("new and final.txt", "unknown"),
    ("and final.txt", "unknown"),

    # Bare system commands
    ("mute", "system_action"),
    ("unmute", "system_action"),
    ("lock", "system_action"),
    ("close it", "system_action"),
    ("press enter", "system_action"),

    # Ambiguous openers
    ("open it", "open_application"),
    ("play lofi", "compound_browser"),
    ("delete file old.txt", "delete_item"),
    ("delete tmp", "delete_item"),
    ("create file notes.txt", "create_file"),
    ("type hello", "type_text"),
]


def training_corpus() -> List[Tuple[str, str]]:
    """The full training set: catalogue examples plus the extras above."""
    corpus: List[Tuple[str, str]] = []
    seen = set()
    for text, intent in list(registry.training_corpus()) + EXTRA_TRAINING_DATA:
        key = (normalize(text), intent)
        if not text.strip() or key in seen:
            continue
        seen.add(key)
        corpus.append((text.strip(), intent))
    return corpus


# Backwards-compatible alias.
TRAINING_DATA = training_corpus()


class IntentClassifier:
    """
    Recognises the intent of an utterance.

    Layer 1 (the registry) resolves everything the catalogue knows, which
    is why the model is only consulted for phrasings the catalogue does
    not spell out.
    """

    def __init__(self):
        self._vectorizer = None
        self._model = None
        self._is_loaded = False
        self._load_model()

    # ── Model ───────────────────────────────────────────────────────────────
    def _load_model(self) -> bool:
        """Loads the trained model if it is present."""
        if not os.path.exists(MODEL_PATH):
            logger.debug("Intent model not found at %s — using the registry only.", MODEL_PATH)
            return False
        try:
            with open(MODEL_PATH, "rb") as handle:
                data = pickle.load(handle)
            self._vectorizer = data["vectorizer"]
            self._model = data["model"]
            self._is_loaded = True
            logger.debug("Intent model loaded (accuracy %.1f%%).",
                         float(data.get("train_accuracy", 0.0)) * 100)
            return True
        except Exception as exc:
            logger.warning("Failed to load the intent model: %s", exc)
            self._is_loaded = False
            return False

    @classmethod
    def train_and_save(cls) -> float:
        """
        Trains the fallback classifier on the command catalogue.

        The catalogue is the source of truth, so retraining after adding a
        command is a single command. Saves to actions/models/intent_model.pkl.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        import numpy as np

        corpus = training_corpus()
        texts = [text.lower().strip() for text, _ in corpus]
        labels = [intent for _, intent in corpus]

        # Character n-grams forgive the typos a speech recogniser makes.
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
            sublinear_tf=True,
        )
        features = vectorizer.fit_transform(texts)

        model = LogisticRegression(
            C=15.0,
            max_iter=3000,
            solver="lbfgs",
            random_state=42,
        )
        model.fit(features, labels)

        train_accuracy = float(np.mean(model.predict(features) == labels))
        cv_accuracy = float(np.mean(cross_val_score(model, features, labels, cv=3,
                                                     scoring="accuracy")))

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as handle:
            pickle.dump({
                "vectorizer": vectorizer,
                "model": model,
                "classes": list(model.classes_),
                "train_accuracy": train_accuracy,
                "cv_accuracy": cv_accuracy,
            }, handle)

        logger.info(
            "Trained the intent classifier: train=%.1f%% cv=%.1f%% examples=%d",
            train_accuracy * 100, cv_accuracy * 100, len(texts),
        )
        return train_accuracy

    # ── Classification ──────────────────────────────────────────────────────
    def classify(self, text: str) -> Tuple[str, str, float]:
        """
        Returns (lane, intent, confidence) for an utterance.
        """
        if not text or not text.strip():
            return LANE_LLM, "unknown", 0.0

        # ── Layer 1: the command catalogue (deterministic, exact) ────────────
        match = registry.match(text)
        if match:
            confidence = 1.0 if match.matched_by == "phrase" else 0.9
            return match.spec.lane, match.spec.intent, confidence

        clean = text.strip().lower()

        # ── Layer 2: the trained model ──────────────────────────────────────
        if self._is_loaded and self._model is not None and self._vectorizer is not None:
            import numpy as np

            features = self._vectorizer.transform([clean])
            probabilities = self._model.predict_proba(features)[0]
            index = int(np.argmax(probabilities))
            intent = str(self._model.classes_[index])
            confidence = float(probabilities[index])

            from actions.dispatch import MIN_CONFIDENCE

            if confidence < MIN_CONFIDENCE:
                # The model is guessing. Say so instead of acting on it.
                return LANE_LLM, "unknown", confidence

            return INTENT_TO_LANE.get(intent, LANE_LLM), intent, confidence

        # ── Layer 3: heuristic ───────────────────────────────────────────────
        return self._heuristic_fallback(clean)

    def _heuristic_fallback(self, text: str) -> Tuple[str, str, float]:
        """Used only when no model is installed."""
        if any(word in text for word in ("mute", "volume", "lock", "screenshot",
                                         "window", "enter", "tab")):
            return LANE_FAST, "system_action", 0.95
        if "setting" in text or any(word in text for word in ("go to", "switch to")):
            return LANE_FAST, "open_settings", 0.90
        if text.startswith(("open ", "launch ")) and len(text.split()) <= 3:
            return LANE_FAST, "open_application", 0.85
        return LANE_LLM, "llm_reasoning", 0.70

    # ── Convenience ─────────────────────────────────────────────────────────
    def predict(self, text: str) -> Tuple[str, float]:
        """Returns (intent, confidence)."""
        _, intent, confidence = self.classify(text)
        return intent, confidence

    def predict_lane(self, text: str) -> Tuple[str, float]:
        """Returns (lane, confidence)."""
        lane, _, confidence = self.classify(text)
        return lane, confidence

    def should_fast_execute(self, text: str, confidence_threshold: float = 0.70) -> Optional[str]:
        """Returns the intent if the command should execute via Lane 1."""
        lane, intent, confidence = self.classify(text)
        if lane == LANE_FAST and confidence >= confidence_threshold:
            return intent
        return None


# Global singleton
intent_classifier = IntentClassifier()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--train" in sys.argv:
        print("Training the PRIVACY68 intent classifier...")
        accuracy = IntentClassifier.train_and_save()
        print(f"\n[OK] Model saved to {MODEL_PATH}")
        print(f"  Training Accuracy: {accuracy:.1%}")
        print(f"  Total Intents: {len(ALL_INTENTS)}")
        print(f"  Training Examples: {len(TRAINING_DATA)}")
    else:
        classifier = IntentClassifier()
        test_phrases = [
            "mute volume",
            "Go to system",
            "open settings",
            "open chrome",
            "open youtube",
            "open downloads",
            "what is the weather in Tokyo",
            "what is my ip",
            "search machine learning algorithms on google",
            "open chrome and search for youtube",
            "Create a folder named Privacy on Desktop",
            "rename file old_doc.txt to final_doc.txt in downloads",
            "explain quantum computing to me",
            "send a message to mom saying hello",
        ]
        print(f"{'LANE':12s} | {'CONF':5s} | {'INTENT':22s} | COMMAND")
        print("-" * 76)
        for phrase in test_phrases:
            lane, intent, confidence = classifier.classify(phrase)
            print(f"{lane:12s} | {confidence:4.0%} | {intent:22s} | '{phrase}'")

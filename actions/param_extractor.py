"""
PRIVACY68 ML Parameter & Slot Extractor (Named Entity Recognition).

Replaces fragile multi-capture-group regex with a trained ML Sequence Tagger (DictVectorizer + LogReg).
- Extracts parameters (names, filepaths, search queries, websites, browsers) with zero regex
- Model size: <1MB pickle
- Inference latency: <2ms on CPU, zero GPU requirement
- Training: Offline, one-time, from token-annotated examples
"""

import logging
import os
import pickle
import sys
from typing import Any, Dict, List, Tuple

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger("PRIVACY68.ParamExtractor")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "param_model.pkl")

# ─── Training Corpus for ML Slot Filling ──────────────────────────────────────
# Format: (tokens_list, intent, labels_list)
# BIO Tag definitions:
#   B-NAME / I-NAME: Item name (folder name, file name)
#   B-SRC / I-SRC: Source item name (for rename/move)
#   B-PATH / I-PATH: Destination folder/directory path
#   B-QUERY / I-QUERY: Search query / media query
#   B-SITE / I-SITE: Website / platform target (google, youtube, wikipedia)
#   B-BROWSER: Target browser (chrome, brave, edge, firefox)
#   B-CONTENT / I-CONTENT: Text content for typing or file body
#   O: Outside (syntax word)

SLOT_TRAINING_DATA: List[Tuple[List[str], str, List[str]]] = [
    # ── create_folder ──
    (["create", "a", "folder", "named", "Privacy", "on", "Desktop"], "create_folder", ["O", "O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "a", "folder", "called", "test_project", "in", "downloads"], "create_folder", ["O", "O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "folder", "test", "in", "downloads"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "folder", "notes", "on", "desktop"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["Create", "MCA", "folder", "in", "downloads"], "create_folder", ["O", "B-NAME", "O", "O", "B-PATH"]),
    (["make", "a", "folder", "named", "photos", "in", "pictures"], "create_folder", ["O", "O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["new", "folder", "assets", "in", "documents"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "directory", "backup", "in", "documents"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "folder", "music_collection", "in", "music"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["make", "folder", "temp_files", "in", "downloads"], "create_folder", ["O", "O", "B-NAME", "O", "B-PATH"]),

    # ── create_file ──
    (["create", "file", "sample.txt", "in", "downloads"], "create_file", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "a", "file", "called", "notes.txt", "on", "desktop"], "create_file", ["O", "O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "a", "file", "named", "todo.txt", "in", "documents"], "create_file", ["O", "O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["make", "file", "report.docx", "in", "documents"], "create_file", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["new", "document", "draft.md", "on", "desktop"], "create_file", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "file", "data.csv", "in", "downloads"], "create_file", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["create", "file", "index.html", "in", "desktop"], "create_file", ["O", "O", "B-NAME", "O", "B-PATH"]),

    # ── rename_item ──
    (["rename", "file", "old_doc.txt", "to", "final_doc.txt", "in", "downloads"], "rename_item", ["O", "O", "B-SRC", "O", "B-NAME", "O", "B-PATH"]),
    (["rename", "file", "sample.txt", "to", "renamed_sample.txt"], "rename_item", ["O", "O", "B-SRC", "O", "B-NAME"]),
    (["rename", "old_doc.txt", "to", "final_doc.txt"], "rename_item", ["O", "B-SRC", "O", "B-NAME"]),
    (["rename", "folder", "temp", "to", "archive", "in", "desktop"], "rename_item", ["O", "O", "B-SRC", "O", "B-NAME", "O", "B-PATH"]),
    (["rename", "item", "draft.txt", "to", "published.txt"], "rename_item", ["O", "O", "B-SRC", "O", "B-NAME"]),
    (["change", "name", "of", "old.txt", "to", "new.txt"], "rename_item", ["O", "O", "O", "B-SRC", "O", "B-NAME"]),

    # ── delete_item ──
    (["delete", "file", "test.txt", "in", "downloads"], "delete_item", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["delete", "the", "file", "old.log", "from", "desktop"], "delete_item", ["O", "O", "O", "B-NAME", "O", "B-PATH"]),
    (["delete", "folder", "temp", "in", "downloads"], "delete_item", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["remove", "file", "notes.txt", "from", "documents"], "delete_item", ["O", "O", "B-NAME", "O", "B-PATH"]),
    (["delete", "file", "unneeded.txt"], "delete_item", ["O", "O", "B-NAME"]),

    # ── web_search ──
    (["search", "machine", "learning", "algorithms", "on", "google"], "web_search", ["O", "B-QUERY", "I-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["search", "python", "tutorials", "on", "google"], "web_search", ["O", "B-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["search", "quantum", "computing", "on", "wikipedia"], "web_search", ["O", "B-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["search", "for", "weather", "forecast", "on", "bing"], "web_search", ["O", "O", "B-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["search", "recipes", "for", "dinner", "on", "google"], "web_search", ["O", "B-QUERY", "I-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["google", "best", "laptops", "2026"], "web_search", ["O", "B-QUERY", "I-QUERY", "I-QUERY"]),
    (["look", "up", "privacy68", "architecture"], "web_search", ["O", "O", "B-QUERY", "I-QUERY"]),
    (["search", "latest", "world", "news"], "web_search", ["O", "B-QUERY", "I-QUERY", "I-QUERY"]),

    # ── compound_browser ──
    (["open", "chrome", "and", "search", "for", "youtube"], "compound_browser", ["O", "B-BROWSER", "O", "O", "O", "B-QUERY"]),
    (["open", "chrome", "and", "go", "to", "reddit.com"], "compound_browser", ["O", "B-BROWSER", "O", "O", "O", "B-QUERY"]),
    (["open", "youtube", "and", "search", "for", "lofi", "beats"], "compound_browser", ["O", "B-SITE", "O", "O", "O", "B-QUERY", "I-QUERY"]),
    (["play", "believer", "on", "youtube"], "compound_browser", ["O", "B-QUERY", "O", "B-SITE"]),
    (["play", "shape", "of", "you", "on", "youtube"], "compound_browser", ["O", "B-QUERY", "I-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["in", "chrome", "search", "for", "python", "tutorials"], "compound_browser", ["O", "B-BROWSER", "O", "O", "B-QUERY", "I-QUERY"]),
    (["open", "brave", "and", "search", "for", "python", "tutorials", "on", "youtube"], "compound_browser", ["O", "B-BROWSER", "O", "O", "O", "B-QUERY", "I-QUERY", "O", "B-SITE"]),
    (["open", "firefox", "and", "visit", "github.com"], "compound_browser", ["O", "B-BROWSER", "O", "O", "B-QUERY"]),

    # ── open_folder ──
    (["open", "downloads", "folder"], "open_folder", ["O", "B-PATH", "O"]),
    (["open", "my", "desktop"], "open_folder", ["O", "O", "B-PATH"]),
    (["open", "documents"], "open_folder", ["O", "B-PATH"]),
    (["open", "pictures", "folder"], "open_folder", ["O", "B-PATH", "O"]),

    # ── open_application ──
    (["open", "chrome"], "open_application", ["O", "B-NAME"]),
    (["launch", "notepad"], "open_application", ["O", "B-NAME"]),
    (["start", "vs", "code"], "open_application", ["O", "B-NAME", "I-NAME"]),
    (["open", "calculator"], "open_application", ["O", "B-NAME"]),
    (["launch", "task", "manager"], "open_application", ["O", "B-NAME", "I-NAME"]),

    # ── type_text ──
    (["type", "hello", "world"], "type_text", ["O", "B-CONTENT", "I-CONTENT"]),
    (["write", "out", "my", "notes"], "type_text", ["O", "O", "B-CONTENT", "I-CONTENT"]),
]


def extract_token_features(tokens: List[str], index: int, intent: str) -> Dict[str, Any]:
    """Extracts contextual feature dictionary for a single token."""
    word = tokens[index]
    features = {
        "intent": intent,
        "word.lower": word.lower(),
        "word.has_dot": "." in word,
        "word.has_slash": "/" in word or "\\" in word or ":" in word,
        "word.isupper": word.isupper(),
        "word.istitle": word.istitle(),
        "position": index / max(1, len(tokens) - 1),
    }

    if index > 0:
        prev_w = tokens[index - 1]
        features["prev_word"] = prev_w.lower()
        features["prev_has_to"] = prev_w.lower() == "to"
        features["prev_has_in"] = prev_w.lower() in ("in", "on", "at", "inside")
    else:
        features["BOS"] = True

    if index < len(tokens) - 1:
        next_w = tokens[index + 1]
        features["next_word"] = next_w.lower()
        features["next_has_to"] = next_w.lower() == "to"
    else:
        features["EOS"] = True

    return features


class ParamExtractor:
    """
    ML Slot & Parameter Extractor using Sequence Labeling.
    Extracts structured entities from voice commands with zero regex capture groups.
    """

    def __init__(self):
        self._vectorizer = None
        self._model = None
        self._is_loaded = False
        self._load_model()

    def _load_model(self) -> bool:
        if not os.path.exists(MODEL_PATH):
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            self._vectorizer = data["vectorizer"]
            self._model = data["model"]
            self._is_loaded = True
            logger.debug("ParamExtractor model loaded successfully.")
            return True
        except Exception as e:
            logger.warning(f"Failed to load ParamExtractor model: {e}")
            self._is_loaded = False
            return False

    @classmethod
    def train_and_save(cls) -> float:
        """Trains DictVectorizer + LogisticRegression token classifier."""
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        X_feats = []
        y_labels = []

        for tokens, intent, labels in SLOT_TRAINING_DATA:
            for i in range(len(tokens)):
                X_feats.append(extract_token_features(tokens, i, intent))
                y_labels.append(labels[i])

        vectorizer = DictVectorizer(sparse=True)
        X = vectorizer.fit_transform(X_feats)

        model = LogisticRegression(
            C=15.0,
            max_iter=3000,
            solver="lbfgs",
            random_state=42,
        )
        model.fit(X, y_labels)

        train_acc = float(np.mean(model.predict(X) == y_labels))

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({
                "vectorizer": vectorizer,
                "model": model,
                "classes": list(model.classes_),
                "train_accuracy": train_acc,
            }, f)

        logger.info(f"ParamExtractor model saved (Train Accuracy: {train_acc:.1%})")
        return train_acc

    def extract_slots(self, text: str, intent: str) -> Dict[str, str]:
        """
        Extracts structured slot values from user text given the intent.
        Returns dictionary of extracted parameters:
          - name: Target item name
          - source: Source item name (for rename)
          - path: Directory path / destination
          - query: Search string or media query
          - site: Target site / engine
          - browser: Target browser
          - content: Text payload
        """
        if not text or not text.strip():
            return {}

        tokens = text.strip().split()
        if not tokens:
            return {}

        if not self._is_loaded or self._model is None:
            # Fallback heuristic
            return self._heuristic_extract(text, intent)

        features = [extract_token_features(tokens, i, intent) for i in range(len(tokens))]
        X = self._vectorizer.transform(features)
        tags = self._model.predict(X)

        slots: Dict[str, List[str]] = {
            "name": [],
            "source": [],
            "path": [],
            "query": [],
            "site": [],
            "browser": [],
            "content": [],
        }

        tag_map = {
            "NAME": "name",
            "SRC": "source",
            "PATH": "path",
            "QUERY": "query",
            "SITE": "site",
            "BROWSER": "browser",
            "CONTENT": "content",
        }

        for token, tag in zip(tokens, tags):
            clean_tag = tag.replace("B-", "").replace("I-", "")
            if clean_tag in tag_map:
                slots[tag_map[clean_tag]].append(token)

        result = {k: " ".join(v).strip() for k, v in slots.items() if v}

        # Fallback if critical slots were missed
        if intent in ("create_folder", "create_file") and not result.get("name"):
            return self._heuristic_extract(text, intent)

        return result

    def _heuristic_extract(self, text: str, intent: str) -> Dict[str, str]:
        """Lightweight heuristic fallback."""
        low = text.lower().strip()
        res: Dict[str, str] = {}

        if intent in ("create_folder", "create_file"):
            # Target path
            for p in ("desktop", "downloads", "documents", "pictures", "music", "videos"):
                if p in low:
                    res["path"] = p
                    break
            # Name
            words = text.split()
            if "named" in low or "called" in low:
                for marker in ("named", "called"):
                    if marker in low:
                        parts = text.split(marker, 1)[1].strip().split()
                        if parts:
                            res["name"] = parts[0].strip(" '\".,")
            elif len(words) >= 2:
                for w in words:
                    if w.lower() not in ("create", "make", "new", "add", "a", "folder", "file", "in", "on", "at"):
                        res["name"] = w.strip(" '\".,")
                        break

        elif intent == "rename_item":
            if " to " in low:
                parts = text.split(" to ", 1)
                src_words = parts[0].strip().split()
                dst_words = parts[1].strip().split()
                if src_words:
                    res["source"] = src_words[-1].strip(" '\".,")
                if dst_words:
                    res["name"] = dst_words[0].strip(" '\".,")

        elif intent in ("web_search", "compound_browser"):
            for site in ("google", "youtube", "wikipedia", "reddit", "github", "bing"):
                if site in low:
                    res["site"] = site
                    break
            for b in ("chrome", "brave", "edge", "firefox"):
                if b in low:
                    res["browser"] = b
                    break
            if "search for " in low:
                res["query"] = text.split("search for ", 1)[1].strip()
            elif "search " in low:
                res["query"] = text.split("search ", 1)[1].strip()

        return res


# Global singleton
param_extractor = ParamExtractor()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--train" in sys.argv:
        print("Training ML Parameter / Slot Extractor...")
        acc = ParamExtractor.train_and_save()
        print(f"\n[OK] ParamExtractor saved to {MODEL_PATH}")
        print(f"  Token Classification Accuracy: {acc:.1%}")
    else:
        pe = ParamExtractor()
        test_cases = [
            ("create a folder named Privacy on Desktop", "create_folder"),
            ("create MCA folder in downloads", "create_folder"),
            ("create file sample.txt in downloads", "create_file"),
            ("rename file old_doc.txt to final_doc.txt in downloads", "rename_item"),
            ("delete file test.txt in downloads", "delete_item"),
            ("search machine learning algorithms on google", "web_search"),
            ("open chrome and search for youtube", "compound_browser"),
            ("play believer on youtube", "compound_browser"),
        ]
        print(f"{'INTENT':18s} | EXTRACTED PARAMETERS")
        print("-" * 70)
        for sentence, intent in test_cases:
            extracted = pe.extract_slots(sentence, intent)
            print(f"{intent:18s} | {extracted}")

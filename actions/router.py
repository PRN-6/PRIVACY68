import re
import logging
import numpy as np
from actions.skill_manager import manager
from plugins.manager import plugin_manager

logger = logging.getLogger("PRIVACY68.SemanticRouter")

class SimpleTfidfVectorizer:
    """
    Lightweight, pure-NumPy TF-IDF Vectorizer with unigram/bigram tokenization.
    Avoids heavy C-extension DLLs (scipy/sklearn) to guarantee compatibility across
    all Windows systems and App Control / WDAC policies.
    """
    # Filler/stop words are dropped before tokenization so Whisper-injected
    # noise ("enable and gestures") does not dilute or shift intent matches.
    STOP_WORDS = frozenset({
        "and", "the", "a", "an", "to", "for", "of", "on", "in", "with",
        "please", "can", "could", "you", "me", "my", "that", "this", "sir",
    })

    def __init__(self, ngram_range=(1, 2)):
        self.ngram_range = ngram_range
        self.vocabulary = {}
        self.idf_ = None

    def _tokenize(self, text: str):
        words = [w for w in re.findall(r'\b\w+\b', text.lower()) if w not in self.STOP_WORDS]
        tokens = []
        n_min, n_max = self.ngram_range
        for n in range(n_min, n_max + 1):
            for i in range(len(words) - n + 1):
                tokens.append(' '.join(words[i:i+n]))
        return tokens

    def fit_transform(self, documents: list) -> np.ndarray:
        doc_tokens = [self._tokenize(doc) for doc in documents]
        vocab = {}
        for tokens in doc_tokens:
            for t in tokens:
                if t not in vocab:
                    vocab[t] = len(vocab)
        self.vocabulary = vocab
        n_docs = len(documents)
        n_vocab = len(vocab)
        if n_vocab == 0:
            return np.zeros((n_docs, 0), dtype=np.float32)

        df = np.zeros(n_vocab, dtype=np.float32)
        for tokens in doc_tokens:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                df[vocab[t]] += 1

        # Smooth Inverse Document Frequency
        self.idf_ = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0

        matrix = np.zeros((n_docs, n_vocab), dtype=np.float32)
        for i, tokens in enumerate(doc_tokens):
            for t in tokens:
                matrix[i, vocab[t]] += 1
            matrix[i] *= self.idf_
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm
        return matrix

    def transform(self, documents: list) -> np.ndarray:
        n_docs = len(documents)
        n_vocab = len(self.vocabulary)
        if n_vocab == 0:
            return np.zeros((n_docs, 0), dtype=np.float32)

        matrix = np.zeros((n_docs, n_vocab), dtype=np.float32)
        for i, doc in enumerate(documents):
            tokens = self._tokenize(doc)
            for t in tokens:
                if t in self.vocabulary:
                    matrix[i, self.vocabulary[t]] += 1
            matrix[i] *= self.idf_
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm
        return matrix


class SemanticRouter:
    def __init__(self):
        self.reload()
        # Register for dynamic hot-reload when plugins are toggled in UI!
        plugin_manager.register_reload_listener(self.reload)

    def reload(self):
        """Re-indexes fast training phrases dynamically on the fly."""
        self.intents = manager.get_all_intents()
        
        self.tool_names = []
        self.training_sentences = []
        
        for tool, phrases in self.intents.items():
            for phrase in phrases:
                self.tool_names.append(tool)
                self.training_sentences.append(phrase)
                
        self.vectorizer = SimpleTfidfVectorizer(ngram_range=(1, 2))
        if self.training_sentences:
            self.knowledge_base_vectors = self.vectorizer.fit_transform(self.training_sentences)
            logger.info(f"Semantic Router indexed {len(self.tool_names)} training phrases across active skills & plugins.")
        else:
            self.knowledge_base_vectors = None
            logger.warning("No skills active! Semantic Router is empty.")

    def route(self, user_text: str, threshold: float = 0.78) -> str:
        if self.knowledge_base_vectors is None or not user_text:
            return None
            
        cleaned_text = user_text.lower().strip(".!?, \t\n")

        # Instant dictation / typing match for any phrase starting with "type ..." or "write ..."
        if re.match(r'^(?:sana,?\s*|sena,?\s*|orion,?\s*|nova,?\s*)?(?:please\s*)?(?:can\s+you\s*)?(?:type\s+that|type\s+out|type|write\s+that|write\s+out|write)\s+', cleaned_text):
            logger.info("Fast Lane Router matched 'system.type_text' (Direct Dictation Prefix)")
            return "system.type_text"

        user_vector = self.vectorizer.transform([cleaned_text])
        # Cosine similarity between normalized vectors is dot product
        similarities = (user_vector @ self.knowledge_base_vectors.T)[0]
        
        best_match_index = int(np.argmax(similarities))
        best_score = float(similarities[best_match_index])
        
        if best_score >= threshold:
            best_tool = self.tool_names[best_match_index]
            logger.info(f"Fast Lane Router matched '{best_tool}' (Confidence: {best_score:.2f})")
            return best_tool
        else:
            logger.info(f"Fast Lane Router rejected best match '{self.tool_names[best_match_index]}' (Confidence: {best_score:.2f} < {threshold})")
            
        return None

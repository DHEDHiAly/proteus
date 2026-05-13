import json
import os
import numpy as np
from typing import Dict, Optional


class ESM2EmbeddingCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self._cache: Dict[str, np.ndarray] = {}
        self._load_cache()

    def _load_cache(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            return
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".npy"):
                key = fname.replace(".npy", "")
                path = os.path.join(self.cache_dir, fname)
                try:
                    self._cache[key] = np.load(path)
                except Exception:
                    pass

    def get_embedding(self, sequence: str) -> Optional[np.ndarray]:
        if sequence in self._cache:
            return self._cache[sequence]
        embedding = self._compute_embedding(sequence)
        if embedding is not None:
            self._cache[sequence] = embedding
            self._save_embedding(sequence, embedding)
        return embedding

    def _compute_embedding(self, sequence: str) -> np.ndarray:
        seq_len = len(sequence)
        embedding = np.random.randn(seq_len, 1280).astype(np.float32) * 0.02
        aa_embed = {
            "A": 0, "C": 1, "D": 2, "E": 3, "F": 4, "G": 5, "H": 6,
            "I": 7, "K": 8, "L": 9, "M": 10, "N": 11, "P": 12, "Q": 13,
            "R": 14, "S": 15, "T": 16, "V": 17, "W": 18, "Y": 19,
        }
        for i, aa in enumerate(sequence):
            if aa in aa_embed:
                embedding[i, aa_embed[aa] * 64:(aa_embed[aa] + 1) * 64] = 1.0
        return embedding

    def _save_embedding(self, sequence: str, embedding: np.ndarray):
        path = os.path.join(self.cache_dir, f"{hash(sequence)}.npy")
        np.save(path, embedding)

    def get_mutation_logits(self, sequence: str, position: int) -> np.ndarray:
        embedding = self.get_embedding(sequence)
        if embedding is None:
            return np.zeros(20)
        pos_embed = embedding[position] if position < embedding.shape[0] else embedding[-1]
        rng = np.random.RandomState(int(np.sum(pos_embed[:100]) * 1000) % (2**31))
        logits = rng.randn(20) * 0.3
        return logits

    def clear(self):
        self._cache.clear()

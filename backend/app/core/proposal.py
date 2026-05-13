import numpy as np
from typing import Optional, Tuple
from app.core.energy import AMINO_ACIDS, AA_INDEX, HYDROPHOBICITY_SCALE, BLOSUM62


class ProposalDistribution:
    def __init__(self, esm_embedding_cache: Optional[dict] = None):
        self.esm_cache = esm_embedding_cache or {}
        self.amino_acids = AMINO_ACIDS
        self.aa_index = {aa: i for i, aa in enumerate(self.amino_acids)}
        self.esm_logits_cache: dict = {}

    def point_substitution(self, sequence: str) -> Tuple[str, int, str, str]:
        seq_list = list(sequence)
        pos = np.random.randint(0, len(seq_list))
        from_aa = seq_list[pos]
        to_aa = np.random.choice([aa for aa in self.amino_acids if aa != from_aa])
        seq_list[pos] = to_aa
        return "".join(seq_list), pos, from_aa, to_aa

    def esm_guided_substitution(self, sequence: str, target_name: str = "") -> Tuple[str, int, str, str]:
        seq_list = list(sequence)
        pos = np.random.randint(0, len(seq_list))
        from_aa = seq_list[pos]

        if target_name in self.esm_logits_cache and pos in self.esm_logits_cache[target_name]:
            logits = self.esm_logits_cache[target_name][pos]
        elif from_aa in self.esm_cache:
            embedding = self.esm_cache[from_aa]
            logits = self._compute_logits_from_embedding(embedding, pos)
        else:
            logits = self._compute_logits_from_blosum(from_aa)

        probs = np.exp(logits) / np.sum(np.exp(logits))
        if from_aa in self.aa_index:
            probs[self.aa_index[from_aa]] = 0.0
        probs /= probs.sum()

        to_idx = np.random.choice(len(self.amino_acids), p=probs)
        to_aa = self.amino_acids[to_idx]

        seq_list[pos] = to_aa
        return "".join(seq_list), pos, from_aa, to_aa

    def block_replacement(self, sequence: str, block_size: int = 3) -> Tuple[str, int, str, str]:
        seq_list = list(sequence)
        max_start = max(0, len(seq_list) - block_size)
        if max_start <= 0:
            return self.point_substitution(sequence)

        start = np.random.randint(0, max_start + 1)
        end = min(start + block_size, len(seq_list))

        old_block = "".join(seq_list[start:end])
        new_block = ""
        for i in range(start, end):
            from_aa = seq_list[i]
            to_aa = np.random.choice([aa for aa in self.amino_acids if aa != from_aa])
            seq_list[i] = to_aa
            new_block += to_aa

        return "".join(seq_list), start, old_block, new_block

    def llm_jump(self, sequence: str) -> Tuple[str, int, str, str]:
        seq_list = list(sequence)
        num_mutations = np.random.randint(2, min(5, len(seq_list)))
        positions = np.random.choice(len(seq_list), size=num_mutations, replace=False)

        old_chars = ""
        new_chars = ""
        for pos in sorted(positions):
            from_aa = seq_list[pos]
            old_chars += from_aa
            to_aa = np.random.choice([aa for aa in self.amino_acids if aa != from_aa])
            new_chars += to_aa
            seq_list[pos] = to_aa

        return "".join(seq_list), positions.tolist(), old_chars, new_chars

    def propose(self, sequence: str, target_name: str = "",
                op_probs: Optional[dict] = None) -> Tuple[str, int, str, str, str]:
        if op_probs is None:
            op_probs = {
                "point_substitution": 0.70,
                "esm_guided_substitution": 0.20,
                "block_replacement": 0.08,
                "llm_jump": 0.02,
            }

        ops = list(op_probs.keys())
        probs = [op_probs[op] for op in ops]
        operation = np.random.choice(ops, p=probs)

        if operation == "point_substitution":
            new_seq, pos, from_aa, to_aa = self.point_substitution(sequence)
        elif operation == "esm_guided_substitution":
            new_seq, pos, from_aa, to_aa = self.esm_guided_substitution(sequence, target_name)
        elif operation == "block_replacement":
            new_seq, pos, from_aa, to_aa = self.block_replacement(sequence)
        elif operation == "llm_jump":
            new_seq, pos, from_aa, to_aa = self.llm_jump(sequence)
        else:
            new_seq, pos, from_aa, to_aa = self.point_substitution(sequence)

        return new_seq, pos, from_aa, to_aa, operation

    def _compute_logits_from_embedding(self, embedding: np.ndarray, pos: int) -> np.ndarray:
        if embedding.ndim == 1:
            rng = np.random.RandomState(int(np.sum(embedding[:10]) * 1000 + pos))
            logits = rng.randn(20) * 0.5
            return logits
        return np.random.randn(20) * 0.5

    def _compute_logits_from_blosum(self, from_aa: str) -> np.ndarray:
        if from_aa not in self.aa_index:
            return np.zeros(20)
        i = self.aa_index[from_aa]
        row = BLOSUM62[i, :]
        return row

    def get_proposal_log_prob(self, from_seq: str, to_seq: str,
                              from_pos: int, to_aa: str, operation: str) -> float:
        if operation == "point_substitution":
            return np.log(1.0 / (len(self.amino_acids) - 1))
        return np.log(1.0 / (len(self.amino_acids) - 1))

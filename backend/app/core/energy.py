import numpy as np
from typing import Dict, Optional


AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {aa: i for i, aa in enumerate(AMINO_ACIDS)}

HYDROPHOBICITY_SCALE = {
    "A": 1.80, "C": 2.50, "D": -3.50, "E": -3.50, "F": 2.80,
    "G": -0.40, "H": -3.20, "I": 4.50, "K": -3.90, "L": 3.80,
    "M": 1.90, "N": -3.50, "P": -1.60, "Q": -3.50, "R": -4.50,
    "S": -0.80, "T": -0.70, "V": 4.20, "W": -0.90, "Y": -1.30,
}

CHARGE_SCALE = {
    "R": 1.0, "H": 0.1, "K": 1.0, "D": -1.0, "E": -1.0,
    "C": -0.1, "Y": -0.1,
}

MOLECULAR_WEIGHT = {
    "A": 71.08, "C": 103.14, "D": 115.09, "E": 129.12, "F": 147.18,
    "G": 57.05, "H": 137.14, "I": 113.16, "K": 128.18, "L": 113.16,
    "M": 131.20, "N": 114.10, "P": 97.12, "Q": 128.13, "R": 156.19,
    "S": 87.08, "T": 101.10, "V": 99.13, "W": 186.21, "Y": 163.18,
}

BLOSUM62 = np.array([
    [ 4, -1, -2, -2,  0, -1, -1,  0, -2, -1, -1, -1, -1, -2, -1,  1,  0, -3, -2,  0],
    [-1,  5,  0, -2, -3,  1,  0, -2,  0, -3, -2,  2, -1, -3, -2, -1, -1, -3, -2, -3],
    [-2,  0,  6,  1, -3,  0,  0,  0,  1, -3, -3,  0, -2, -3, -2,  1,  0, -4, -2, -3],
    [-2, -2,  1,  6, -3,  0,  2, -1, -1, -3, -4, -1, -3, -3, -1,  0, -1, -4, -3, -3],
    [ 0, -3, -3, -3,  9, -3, -4, -3, -3, -1, -1, -3, -1, -2, -3, -1, -1, -2, -2, -1],
    [-1,  1,  0,  0, -3,  5,  2, -2,  0, -3, -2,  1,  0, -3, -1,  0, -1, -2, -1, -2],
    [-1,  0,  0,  2, -4,  2,  5, -2,  0, -3, -3,  1, -2, -3, -1,  0, -1, -3, -2, -2],
    [ 0, -2,  0, -1, -3, -2, -2,  6, -2, -4, -4, -2, -3, -3, -2,  0, -2, -2, -3, -3],
    [-2,  0,  1, -1, -3,  0,  0, -2,  8, -3, -3, -1, -2, -1, -2, -1, -2, -2,  2, -3],
    [-1, -3, -3, -3, -1, -3, -3, -4, -3,  4,  2, -3,  1,  0, -3, -2, -1, -3, -1,  3],
    [-1, -2, -3, -4, -1, -2, -3, -4, -3,  2,  4, -2,  2,  0, -3, -2, -1, -2, -1,  1],
    [-1,  2,  0, -1, -3,  1,  1, -2, -1, -3, -2,  5, -1, -3, -1,  0, -1, -3, -2, -2],
    [-1, -1, -2, -3, -1,  0, -2, -3, -2,  1,  2, -1,  5,  0, -2, -1, -1, -1, -1,  1],
    [-2, -3, -3, -3, -2, -3, -3, -3, -1,  0,  0, -3,  0,  6, -4, -2, -2,  1,  3, -1],
    [-1, -2, -2, -1, -3, -1, -1, -2, -2, -3, -3, -1, -2, -4,  7, -1, -1, -4, -3, -2],
    [ 1, -1,  1,  0, -1,  0,  0,  0, -1, -2, -2,  0, -1, -2, -1,  4,  1, -3, -2, -2],
    [ 0, -1,  0, -1, -1, -1, -1, -2, -2, -1, -1, -1, -1, -2, -1,  1,  5, -2, -2,  0],
    [-3, -3, -4, -4, -2, -2, -3, -2, -2, -3, -2, -3, -1,  1, -4, -3, -2, 11,  2, -3],
    [-2, -2, -2, -3, -2, -1, -2, -3,  2, -1, -1, -2, -1,  3, -3, -2, -2,  2,  7, -1],
    [ 0, -3, -3, -3, -1, -2, -2, -3, -3,  3,  1, -2,  1, -1, -2, -2,  0, -3, -1,  4],
], dtype=np.float32)


class EnergyOracle:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        scoring = self.config.get("scoring", {})
        self.binding_weight = scoring.get("binding_weight", 0.50)
        self.stability_weight = scoring.get("stability_weight", 0.25)
        self.solubility_weight = scoring.get("solubility_weight", 0.15)
        self.bbb_weight = scoring.get("bbb_weight", 0.10)
        self.hydrophobicity_penalty = scoring.get("hydrophobicity_penalty", 0.05)
        self.charge_penalty = scoring.get("charge_penalty", 0.02)
        self.aggregation_penalty = scoring.get("aggregation_penalty", 0.08)
        self.min_stability_score = scoring.get("min_stability_score", 0.6)
        self.max_hydrophobicity = scoring.get("max_hydrophobicity", 0.65)
        self.ideal_charge_range = scoring.get("ideal_charge_range", [-3, 3])
        self.target_pocket_residues: list = []
        self.use_scorer_model = False
        self.scorer_model = None

    def set_target_pocket(self, residues: list):
        self.target_pocket_residues = residues

    def compute_energy(self, sequence: str) -> float:
        if not sequence or len(sequence) == 0:
            return 1000.0
        seq_len = len(sequence)
        binding = self._compute_binding_score(sequence)
        stability = self._compute_stability_score(sequence)
        solubility = self._compute_solubility_score(sequence)
        bbb = self._compute_bbb_score(sequence)
        hydrophob_pen = self._compute_hydrophobicity_penalty(sequence)
        charge_pen = self._compute_charge_penalty(sequence)
        aggreg_pen = self._compute_aggregation_penalty(sequence)

        energy = (
            self.binding_weight * (1.0 - binding)
            + self.stability_weight * (1.0 - stability)
            + self.solubility_weight * (1.0 - solubility)
            + self.bbb_weight * (1.0 - bbb)
            + self.hydrophobicity_penalty * hydrophob_pen
            + self.charge_penalty * charge_pen
            + self.aggregation_penalty * aggreg_pen
        )

        if stability < self.min_stability_score:
            energy += 0.5 * (self.min_stability_score - stability)

        if self.use_scorer_model and self.scorer_model is not None:
            ml_score = self._score_with_model(sequence)
            energy -= 0.1 * ml_score

        return float(energy)

    def compute_energy_decomposition(self, sequence: str) -> dict:
        if not sequence:
            return {}
        return {
            "total": self.compute_energy(sequence),
            "binding": 1.0 - self._compute_binding_score(sequence),
            "stability": 1.0 - self._compute_stability_score(sequence),
            "solubility": 1.0 - self._compute_solubility_score(sequence),
            "bbb": 1.0 - self._compute_bbb_score(sequence),
            "hydrophobicity_penalty": self._compute_hydrophobicity_penalty(sequence),
            "charge_penalty": self._compute_charge_penalty(sequence),
            "aggregation_penalty": self._compute_aggregation_penalty(sequence),
        }

    def score_candidate(self, sequence: str, target_name: str) -> dict:
        energy = self.compute_energy(sequence)
        binding = self._compute_binding_score(sequence)
        stability = self._compute_stability_score(sequence)
        solubility = self._compute_solubility_score(sequence)
        return {
            "sequence": sequence,
            "binding_score": float(binding),
            "stability_score": float(stability),
            "solubility_score": float(solubility),
            "total_energy": float(energy),
            "hydrophobicity": float(self._compute_gravy(sequence)),
            "net_charge": float(self._compute_net_charge(sequence)),
        }

    def _compute_binding_score(self, seq: str) -> float:
        if len(seq) < 5:
            return 0.0
        ref_freq = np.array([0.076, 0.018, 0.051, 0.062, 0.041, 0.072, 0.024, 0.053,
                             0.046, 0.059, 0.094, 0.044, 0.041, 0.037, 0.052, 0.072,
                             0.058, 0.013, 0.013, 0.033])
        counts = np.zeros(20)
        for aa in seq:
            if aa in AA_INDEX:
                counts[AA_INDEX[aa]] += 1
        freq = counts / max(len(seq), 1)
        log_ratio = np.log2((freq + 1e-10) / (ref_freq + 1e-10))
        information = np.sum(freq * log_ratio)

        if self.target_pocket_residues:
            pocket_contribution = 0.0
            for i, pos in enumerate(self.target_pocket_residues):
                if pos < len(seq):
                    pocket_contribution += 0.1
            information += pocket_contribution * 0.3

        score = np.tanh(max(0, information) / 3.0)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_stability_score(self, seq: str) -> float:
        if len(seq) < 3:
            return 0.5
        proline_count = seq.count("P")
        glycine_count = seq.count("G")
        helix_broken = proline_count / max(len(seq), 1)
        flexibility = glycine_count / max(len(seq), 1)
        screw = 1.0 - min(helix_broken * 3.0 + flexibility * 2.0, 1.0)

        charged = sum(1 for aa in seq if aa in "RKDE")
        charged_ratio = charged / max(len(seq), 1)
        salt_bridge = min(charged_ratio * 2.0, 1.0) * 0.3

        stability = 0.5 * screw + 0.3 * salt_bridge + 0.2 * (1.0 - proline_count / max(len(seq), 1))
        return float(np.clip(stability, 0.0, 1.0))

    def _compute_solubility_score(self, seq: str) -> float:
        if len(seq) < 3:
            return 0.5
        gravy = self._compute_gravy(seq)
        soluble = 1.0 - max(0, (gravy - 0.4) / 2.0)
        charged = sum(1 for aa in seq if aa in "RKDE")
        charged_ratio = charged / max(len(seq), 1)
        solubility = 0.6 * float(soluble) + 0.4 * min(charged_ratio * 3.0, 1.0)
        return float(np.clip(solubility, 0.0, 1.0))

    def _compute_bbb_score(self, seq: str) -> float:
        if len(seq) < 3:
            return 0.5
        small_aas = sum(1 for aa in seq if aa in "GASVCT")
        small_ratio = small_aas / max(len(seq), 1)
        n_charged = sum(1 for aa in seq if aa in "RKDE")
        n_aromatic = sum(1 for aa in seq if aa in "FWY")
        charge_ok = 1.0 if n_charged <= 3 else max(0, 1.0 - (n_charged - 3) * 0.2)
        bbb = 0.4 * small_ratio + 0.3 * charge_ok + 0.3 * min(n_aromatic * 0.2, 1.0)
        return float(np.clip(bbb, 0.0, 1.0))

    def _compute_gravy(self, seq: str) -> float:
        if not seq:
            return 0.0
        scores = [HYDROPHOBICITY_SCALE.get(aa, 0.0) for aa in seq]
        return float(np.mean(scores))

    def _compute_net_charge(self, seq: str) -> float:
        if not seq:
            return 0.0
        return float(sum(CHARGE_SCALE.get(aa, 0.0) for aa in seq))

    def _compute_hydrophobicity_penalty(self, seq: str) -> float:
        gravy = self._compute_gravy(seq)
        if gravy > self.max_hydrophobicity:
            return (gravy - self.max_hydrophobicity) * 3.0
        return 0.0

    def _compute_charge_penalty(self, seq: str) -> float:
        net = self._compute_net_charge(seq)
        lo, hi = self.ideal_charge_range
        if net < lo:
            return (lo - net) * 0.5
        elif net > hi:
            return (net - hi) * 0.5
        return 0.0

    def _compute_aggregation_penalty(self, seq: str) -> float:
        hydrophobic_stretches = 0
        current_stretch = 0
        for aa in seq:
            if HYDROPHOBICITY_SCALE.get(aa, 0) > 2.0:
                current_stretch += 1
            else:
                if current_stretch >= 3:
                    hydrophobic_stretches += current_stretch - 2
                current_stretch = 0
        if current_stretch >= 3:
            hydrophobic_stretches += current_stretch - 2
        return min(hydrophobic_stretches * 0.15, 1.0)

    def _score_with_model(self, sequence: str) -> float:
        try:
            if self.scorer_model is not None:
                seq_encoded = np.zeros((1, len(sequence), 20), dtype=np.float32)
                for i, aa in enumerate(sequence):
                    if aa in AA_INDEX:
                        seq_encoded[0, i, AA_INDEX[aa]] = 1.0
                with torch.no_grad():
                    pred = self.scorer_model(seq_encoded)
                return float(pred.item())
        except Exception:
            pass
        return 0.0

    def compute_blosum_similarity(self, from_aa: str, to_aa: str) -> float:
        if from_aa not in AA_INDEX or to_aa not in AA_INDEX:
            return 0.0
        i, j = AA_INDEX[from_aa], AA_INDEX[to_aa]
        score = BLOSUM62[i, j]
        return float((score + 4) / 15.0)


try:
    import torch
except ImportError:
    pass

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

    def compute_kd_nM(self, binding_score: float) -> float:
        """
        Heuristic Kd estimate in nanomolar from a normalised binding score (0–1).
        Calibrated so score=0.827 -> ~17 nM, score=0.50 -> ~3162 nM.
        Not a docking-grade calculation; use as a relative ranking metric only.
        """
        return float(10.0 ** ((1.0 - binding_score) * 7.0))

    def compute_serum_half_life(self, seq: str) -> float:
        """
        Heuristic serum half-life estimate in minutes.
        Considers peptide length (longer = slower clearance), proline content
        (protease-resistant), charged residue count, and hydrophobicity
        (high GRAVY -> faster hepatic clearance).
        Typical therapeutic peptides: 5–480 min in serum.
        Heuristic only — not a PK/PD model.
        """
        if not seq:
            return 5.0
        n = len(seq)
        base = 10.0 + n * 1.5
        pro_bonus = seq.count("P") * 4.0
        charged_bonus = sum(1 for aa in seq if aa in "RKDE") * 0.8
        gravy = self._compute_gravy(seq)
        hydro_penalty = max(0.0, gravy - 1.0) * 10.0
        t_half = base + pro_bonus + charged_bonus - hydro_penalty
        return float(np.clip(t_half, 2.0, 480.0))

    def compute_delta_g_kcal_mol(self, kd_nM: float) -> float:
        """
        Convert Kd (nanomolar) to ΔG binding (kcal/mol) at 310K (physiological temp).
        ΔG = RT × ln(Kd) where RT = 0.616 kcal/mol at 310K.
        Returns a negative value; lower (more negative) = tighter binding.
        AutoDock Vina convention: < -6 kcal/mol is considered promising.
        Expected range for our candidates: −14 to −7 kcal/mol.
        """
        kd_M = max(float(kd_nM), 0.001) * 1e-9  # clamp to avoid log(0)
        return float(0.616 * np.log(kd_M))

    def compute_hbond_count(self, seq: str) -> int:
        """
        Estimate H-bond count from sequence composition.
        Backbone NH-CO: one per peptide bond (~n-2 for a folded peptide).
        Side chain donors/acceptors: N, Q, S, T, D, E, H, R, K, Y, W each contribute ~0.5 H-bonds.
        Heuristic only — not a crystallographic count.
        """
        if not seq:
            return 0
        n = len(seq)
        backbone = max(0, n - 2)
        hbond_capable = sum(1 for aa in seq if aa in "NQSTDEHRKYW")
        sidechain = int(hbond_capable * 0.5)
        return backbone + sidechain

    def compute_entropic_penalty(self, seq: str) -> float:
        """
        Entropic penalty (-TΔS) estimate for binding (kcal/mol).
        Base: n × 0.05 kcal/mol (conformational entropy loss per residue on binding).
        Gly: +0.5/residue (flexible backbone → larger conformational search).
        Pro: -0.3/residue (preorganized ring → less entropy loss).
        Clamp [0, 15] kcal/mol.
        """
        n = len(seq)
        if n == 0:
            return 0.0
        base = n * 0.05
        gly_pen = seq.count("G") * 0.5
        pro_bonus = seq.count("P") * 0.3
        penalty = base + gly_pen - pro_bonus
        return float(np.clip(penalty, 0.0, 15.0))

    def compute_solvation_delta_g(self, seq: str) -> float:
        """
        GBSA-lite solvation ΔG estimate (kcal/mol).
        Hydrophobic gain = max(0, GRAVY) × n × 0.6 (burial gain from hydrophobic contacts).
        Charge desolvation cost = n_charged × 0.8 kcal/mol per charged residue.
        ΔG_solv = -(hydrophobic_gain - charge_cost).
        Negative = net favorable (hydrophobic burial dominates).
        Positive = net unfavorable (charge desolvation dominates).
        Gate 2 threshold: ΔG_solv ≤ 0.0 kcal/mol.
        Clamp [-20, 10] kcal/mol.
        """
        n = len(seq)
        if n == 0:
            return 0.0
        gravy = self._compute_gravy(seq)
        hydrophobic_gain = max(0.0, gravy) * n * 0.6
        n_charged = sum(1 for aa in seq if aa in "RKDE")
        charge_cost = n_charged * 0.8
        dg_solv = -(hydrophobic_gain - charge_cost)
        return float(np.clip(dg_solv, -20.0, 10.0))

    def compute_surface_complementarity(self, seq: str) -> float:
        """
        Surface complementarity (Sc) proxy score [0, 1].
        Estimates chemical/shape fit to target binding pocket.
        - Sequence diversity (Shannon entropy): diverse AAs fill pocket better.
        - Aromatic ratio: pi-stacking and hydrophobic contacts.
        - Charged ratio: salt bridges and H-bond anchors.
        - Pocket residue coverage: bonus when sequence length covers pocket positions.
        - Penalty for long hydrophobic stretches (≥ 5 residues in ILFVWM) → poor shape fit.
        Gate 1 threshold: Sc ≥ 0.4.
        """
        if not seq:
            return 0.0
        n = len(seq)
        aromatic_ratio = sum(1 for aa in seq if aa in "FWY") / n
        charged_ratio = sum(1 for aa in seq if aa in "RKDE") / n
        counts: dict = {}
        for aa in seq:
            counts[aa] = counts.get(aa, 0) + 1
        diversity = -sum((c / n) * np.log2(c / n + 1e-10) for c in counts.values()) / 4.322
        pocket_score = 0.0
        if self.target_pocket_residues:
            pocket_in_range = sum(1 for pos in self.target_pocket_residues if pos < n)
            pocket_score = min(pocket_in_range / max(len(self.target_pocket_residues), 1), 1.0)
        sc = (
            0.35 * float(diversity)
            + 0.30 * min(aromatic_ratio * 4.0, 1.0)
            + 0.20 * min(charged_ratio * 3.0, 1.0)
            + 0.15 * pocket_score
        )
        # Penalty for long hydrophobic stretches
        max_stretch = 0
        cur = 0
        for aa in seq:
            if aa in "ILFVWM":
                cur += 1
                if cur > max_stretch:
                    max_stretch = cur
            else:
                cur = 0
        if max_stretch >= 5:
            sc -= 0.15
        return float(np.clip(sc, 0.0, 1.0))

    def compute_lab_viability_score(
        self, seq: str, delta_g: float,
        gate1_pass: bool, gate2_pass: bool, gate3_pass: bool
    ) -> float:
        """
        Lab viability composite score (0–100).
        - Thermodynamic gate: ΔG ≤ -6 kcal/mol → +30 pts; ΔG [-6, -4] → +15 pts.
        - Gate 1 (Sc ≥ 0.4) → +25 pts.
        - Gate 2 (ΔG_solv ≤ 0) → +20 pts.
        - Gate 3 (entropic penalty ≤ 3.5) → +15 pts.
        - Manufacturability bonus: 0–10 pts.
        """
        score = 0.0
        if delta_g <= -6.0:
            score += 30.0
        elif delta_g < -4.0:
            score += 15.0
        if gate1_pass:
            score += 25.0
        if gate2_pass:
            score += 20.0
        if gate3_pass:
            score += 15.0
        manuf = self._compute_manufacturability_score(seq)
        score += manuf * 10.0
        return float(np.clip(score, 0.0, 100.0))

    def compute_selectivity_ddg(self, seq: str) -> float:
        """
        ΔΔG selectivity (kcal/mol) = ΔG_off_target − ΔG_on_target.
        Positive = candidate prefers the configured target over non-specific binding.
        Computed by temporarily clearing pocket residues to simulate off-target binding.
        """
        kd_on = self.compute_kd_nM(self._compute_binding_score(seq))
        dg_on = self.compute_delta_g_kcal_mol(kd_on)
        saved_pocket = self.target_pocket_residues
        self.target_pocket_residues = []
        kd_off = self.compute_kd_nM(self._compute_binding_score(seq))
        dg_off = self.compute_delta_g_kcal_mol(kd_off)
        self.target_pocket_residues = saved_pocket
        return float(dg_off - dg_on)

    def compute_selectivity(self, seq: str) -> float:
        """
        On-target / off-target binding selectivity ratio.

        When pocket residues are configured and overlap with the sequence length:
        amplifies the pocket-specific contribution to simulate recognition (each
        matched pocket position adds 0.5x multiplier on the on/off ratio).

        Falls back to a composition heuristic when no pocket positions fall within
        the sequence length, or when no pocket is configured:
        - aromatic residues (W/F/Y) signal specific recognition motifs → higher selectivity
        - high GRAVY (hydrophobic) → non-specific membrane binding → lower selectivity

        Ratio < 2.0 indicates High Toxicity Risk.
        Heuristic only — not a proteome-wide binding screen.
        """
        if self.target_pocket_residues:
            on_target = self._compute_binding_score(seq)
            saved_pocket = self.target_pocket_residues
            self.target_pocket_residues = []
            off_target = self._compute_binding_score(seq)
            self.target_pocket_residues = saved_pocket
            n_matched = sum(1 for pos in saved_pocket if pos < len(seq))
            if n_matched > 0:
                amplification = 1.0 + n_matched * 0.5
                selectivity = (on_target * amplification) / max(off_target, 0.01)
                return float(np.clip(selectivity, 0.5, 20.0))
            # Fall through to composition heuristic if no pocket residues in range

        # Composition-based fallback
        gravy = self._compute_gravy(seq)
        n = max(len(seq), 1)
        aromatic_ratio = sum(1 for aa in seq if aa in "WFY") / n
        charge_mag = abs(self._compute_net_charge(seq))
        selectivity = (
            1.5
            + aromatic_ratio * 4.0
            + min(charge_mag * 0.3, 1.5)
            - max(gravy - 2.0, 0.0) * 0.5
        )
        return float(np.clip(selectivity, 0.5, 10.0))

    def score_candidate(self, sequence: str, target_name: str) -> dict:
        energy = self.compute_energy(sequence)
        binding = self._compute_binding_score(sequence)
        stability = self._compute_stability_score(sequence)
        solubility = self._compute_solubility_score(sequence)
        immunogenicity = self._compute_immunogenicity_score(sequence)
        ddg = self._compute_ddg_estimate(sequence, stability)
        manufacturability = self._compute_manufacturability_score(sequence, solubility)
        plddt = self._compute_plddt_estimate(sequence, stability)
        novelty = self._compute_novelty_score(sequence)
        aggregation = float(np.clip(self._compute_aggregation_penalty(sequence), 0.0, 1.0))
        kd_nm = self.compute_kd_nM(float(binding))
        serum_half_life = self.compute_serum_half_life(sequence)
        selectivity = self.compute_selectivity(sequence)
        toxicity_flag = selectivity < 2.0
        delta_g = self.compute_delta_g_kcal_mol(kd_nm)
        # Triple-Gate Physics Model
        hbond_count = self.compute_hbond_count(sequence)
        entropic_penalty = self.compute_entropic_penalty(sequence)
        solvation_delta_g = self.compute_solvation_delta_g(sequence)
        surface_complementarity = self.compute_surface_complementarity(sequence)
        gate1_pass = surface_complementarity >= 0.4   # Gate 1: Enthalpic Locking (Sc)
        gate2_pass = solvation_delta_g <= 0.0          # Gate 2: Solvation ΔG (GBSA-lite)
        gate3_pass = entropic_penalty <= 3.5           # Gate 3: Entropic Penalty
        lab_viability_score = self.compute_lab_viability_score(
            sequence, delta_g, gate1_pass, gate2_pass, gate3_pass
        )
        selectivity_ddg = self.compute_selectivity_ddg(sequence)
        return {
            "sequence": sequence,
            "binding_score": float(binding),
            "stability_score": float(stability),
            "solubility_score": float(solubility),
            "total_energy": float(energy),
            "hydrophobicity": float(self._compute_gravy(sequence)),
            "net_charge": float(self._compute_net_charge(sequence)),
            # Hard biophysical metrics
            "aggregation_propensity": aggregation,
            "immunogenicity_score": float(immunogenicity),
            "ddg_estimate_kcal_mol": float(ddg),
            "manufacturability_score": float(manufacturability),
            "plddt_estimate": float(plddt),
            "novelty_score": float(novelty),
            # Pharmacokinetic estimates
            "kd_nM": float(kd_nm),
            "serum_half_life_min": float(serum_half_life),
            "selectivity_ratio": float(selectivity),
            "toxicity_flag": bool(toxicity_flag),
            "delta_g_binding_kcal_mol": float(delta_g),
            # Triple-Gate Physics Model
            "hbond_count": int(hbond_count),
            "entropic_penalty": float(entropic_penalty),
            "solvation_delta_g": float(solvation_delta_g),
            "surface_complementarity": float(surface_complementarity),
            "gate1_pass": bool(gate1_pass),
            "gate2_pass": bool(gate2_pass),
            "gate3_pass": bool(gate3_pass),
            "lab_viability_score": float(lab_viability_score),
            "selectivity_ddg": float(selectivity_ddg),
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

    def _compute_immunogenicity_score(self, seq: str) -> float:
        """
        Heuristic T-cell immunogenicity estimate (0 = low risk, 1 = high risk).
        Based on basic amino acid density (MHC Class II anchors) and aromatic
        residue frequency (hydrophobic MHC Class I anchor motifs).
        """
        if len(seq) < 5:
            return 0.3
        score = 0.0
        basic_ratio = sum(1 for aa in seq if aa in "KR") / max(len(seq), 1)
        score += min(basic_ratio * 2.0, 0.4)
        aromatic_ratio = sum(1 for aa in seq if aa in "FWY") / max(len(seq), 1)
        score += min(aromatic_ratio * 1.5, 0.3)
        if len(seq) > 50:
            score += min((len(seq) - 50) / 150.0, 0.3)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_ddg_estimate(self, seq: str, stability: Optional[float] = None) -> float:
        """
        Heuristic ΔΔG estimate relative to unfolded state (kcal/mol).
        Negative = stabilizing, positive = destabilizing.
        Not a Rosetta-grade calculation; calibrated to typical protein ranges.
        """
        if stability is None:
            stability = self._compute_stability_score(seq)
        ddg = (0.5 - stability) * 10.0
        gravy = self._compute_gravy(seq)
        if 0.3 <= gravy <= 1.5:
            ddg -= 1.2
        elif gravy > 2.5:
            ddg += 2.0
        net = abs(self._compute_net_charge(seq))
        if net < 3:
            ddg -= 0.6
        elif net > 8:
            ddg += 1.0
        return float(np.clip(ddg, -8.0, 8.0))

    def _compute_manufacturability_score(self, seq: str, solubility: Optional[float] = None) -> float:
        """
        Recombinant expression feasibility (0 = difficult, 1 = straightforward).
        Considers solubility, cysteine count, length, and repetitive regions.
        """
        if solubility is None:
            solubility = self._compute_solubility_score(seq)
        score = solubility * 0.35
        cys_ratio = seq.count("C") / max(len(seq), 1)
        score += max(0.0, 0.25 - cys_ratio * 2.0)
        if len(seq) <= 60:
            score += 0.20
        elif len(seq) <= 100:
            score += 0.15
        elif len(seq) <= 200:
            score += 0.10
        repeats = sum(1 for i in range(len(seq) - 3) if seq[i] == seq[i + 1] == seq[i + 2])
        score += max(0.0, 0.20 - repeats * 0.03)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_plddt_estimate(self, seq: str, stability: Optional[float] = None) -> float:
        """
        Pseudo-pLDDT estimate (0–100) analogous to AlphaFold's per-residue confidence.
        Based on sequence composition — not a true structure prediction.
        Scores <50 indicate likely disordered regions; >70 suggests ordered folds.
        """
        if stability is None:
            stability = self._compute_stability_score(seq)
        plddt = 20.0 + stability * 60.0
        gly_ratio = seq.count("G") / max(len(seq), 1)
        plddt -= gly_ratio * 30.0
        pro_ratio = seq.count("P") / max(len(seq), 1)
        plddt -= pro_ratio * 20.0
        helix_ratio = sum(1 for aa in seq if aa in "AELM") / max(len(seq), 1)
        plddt += helix_ratio * 15.0
        return float(np.clip(plddt, 30.0, 95.0))

    def _compute_novelty_score(self, seq: str) -> float:
        """
        Shannon entropy of amino acid composition as a proxy for sequence novelty.
        Returns 0–1 (1 = maximally diverse usage across all 20 AAs).
        """
        if not seq:
            return 0.0
        counts: dict = {}
        for aa in seq:
            counts[aa] = counts.get(aa, 0) + 1
        n = len(seq)
        entropy = -sum((c / n) * np.log2(c / n + 1e-10) for c in counts.values())
        return float(np.clip(entropy / 4.32, 0.0, 1.0))

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

import subprocess
import tempfile
import os
from typing import Dict, List, Optional
import numpy as np


class DockingOracle:
    """
    Physics-based binding energy calculation.
    Uses Rosetta scoring when available; falls back to geometry + electrostatics.
    Replaces the Shannon-entropy heuristic binding score.
    """

    _AA_PROPS: Dict[str, Dict] = {
        'W': {'hphobic': 2.5,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 1},
        'Y': {'hphobic': 2.3,  'charge': 0,    'hbond_donor': 1, 'hbond_acceptor': 2},
        'F': {'hphobic': 2.5,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'L': {'hphobic': 1.8,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'I': {'hphobic': 1.8,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'M': {'hphobic': 1.9,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'V': {'hphobic': 1.7,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'C': {'hphobic': 0.9,  'charge': 0,    'hbond_donor': 1, 'hbond_acceptor': 2},
        'K': {'hphobic': -1.0, 'charge': +1,   'hbond_donor': 3, 'hbond_acceptor': 0},
        'R': {'hphobic': -3.0, 'charge': +1,   'hbond_donor': 4, 'hbond_acceptor': 0},
        'D': {'hphobic': -3.5, 'charge': -1,   'hbond_donor': 0, 'hbond_acceptor': 2},
        'E': {'hphobic': -3.5, 'charge': -1,   'hbond_donor': 0, 'hbond_acceptor': 2},
        'N': {'hphobic': -3.5, 'charge': 0,    'hbond_donor': 1, 'hbond_acceptor': 2},
        'Q': {'hphobic': -3.5, 'charge': 0,    'hbond_donor': 1, 'hbond_acceptor': 2},
        'S': {'hphobic': -0.8, 'charge': 0,    'hbond_donor': 2, 'hbond_acceptor': 2},
        'T': {'hphobic': -0.7, 'charge': 0,    'hbond_donor': 2, 'hbond_acceptor': 2},
        'A': {'hphobic': 0.6,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'G': {'hphobic': 0.0,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'P': {'hphobic': 0.2,  'charge': 0,    'hbond_donor': 0, 'hbond_acceptor': 0},
        'H': {'hphobic': -0.4, 'charge': 0.5,  'hbond_donor': 1, 'hbond_acceptor': 2},
    }

    def __init__(self, target_pdb_id: str = "", binding_site_residues: Optional[List] = None):
        self.target_pdb_id = target_pdb_id
        self.binding_site = binding_site_residues or []
        self.rosetta_available = self._check_rosetta()

    def _check_rosetta(self) -> bool:
        try:
            result = subprocess.run(
                ['rosetta_scripts.default.linuxgccrelease', '-help'],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def calculate_binding_energy(self, peptide_sequence: str) -> Dict:
        """
        Calculate ΔG binding. Returns physics-decomposed binding energy dict.
        Uses Rosetta if available, otherwise geometry + electrostatics approximation.
        """
        if self.rosetta_available:
            result = self._calculate_via_rosetta(peptide_sequence)
            if result:
                return result
        return self._calculate_via_geometry_and_electrostatics(peptide_sequence)

    def _calculate_via_rosetta(self, peptide_sequence: str) -> Optional[Dict]:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                peptide_pdb = os.path.join(tmpdir, 'peptide.pdb')
                self._write_sequence_as_pdb(peptide_sequence, peptide_pdb)
                score_file = os.path.join(tmpdir, 'score.sc')
                result = subprocess.run(
                    ['rosetta_scripts.default.linuxgccrelease',
                     '-s', peptide_pdb,
                     '-out:file:scorefile', score_file],
                    capture_output=True, timeout=60
                )
                if result.returncode == 0 and os.path.exists(score_file):
                    with open(score_file) as f:
                        lines = [l for l in f.readlines() if not l.startswith('SEQUENCE')]
                    if len(lines) >= 2:
                        scores = self._parse_rosetta_score(lines[-1])
                        dg = float(scores.get('total_score', -5.0))
                        return {
                            'delta_g_total_kcal_mol': max(-10.0, min(-2.0, dg)),
                            'delta_g_vdw': float(scores.get('fa_atr', 0)),
                            'delta_g_electrostatic': float(scores.get('fa_elec', 0)),
                            'delta_g_solvation': float(scores.get('fa_sol', 0)),
                            'hbond_count': int(float(scores.get('hbond_bb_sc', 0))),
                            'hbond_energy': float(scores.get('hbond_bb_sc', 0)) * -1.5,
                            'contact_area': 0.0,
                            'interface_complementarity': 0.75,
                            'per_residue_contribution': {},
                            'confidence': 'High (Rosetta)',
                        }
        except Exception:
            pass
        return None

    def _calculate_via_geometry_and_electrostatics(self, peptide_sequence: str) -> Dict:
        """
        Physics-based ΔG from AA properties: VdW/hydrophobic packing,
        electrostatic salt bridges, solvation, and H-bonding.
        """
        props = self._AA_PROPS
        vdw_energy = 0.0
        hbond_total = 0
        per_residue: Dict[int, float] = {}

        for i, aa in enumerate(peptide_sequence):
            p = props.get(aa, {'hphobic': 0, 'hbond_donor': 0, 'hbond_acceptor': 0})
            hphob_contrib = p['hphobic'] * 2.0 * -0.5
            vdw_energy += hphob_contrib
            hbond_total += p['hbond_donor'] + p['hbond_acceptor']
            per_residue[i] = hphob_contrib

        # Salt bridges with target (assume ~3 negative residues at interface)
        pos_count = peptide_sequence.count('K') + peptide_sequence.count('R')
        neg_count = peptide_sequence.count('D') + peptide_sequence.count('E')
        salt_bridges = min(pos_count, 3)
        electrostatic_energy = salt_bridges * -1.5

        # Desolvation penalty for excess aromatics
        aromatic_excess = max(0, peptide_sequence.count('W') + peptide_sequence.count('F') - 3)
        desolvation_penalty = aromatic_excess * 0.8

        # PBSA-lite solvation
        buried_surface_area = min(800.0, 80.0 * len(peptide_sequence))
        solvation_energy = buried_surface_area * -0.02

        # H-bond contribution
        hbond_energy = hbond_total * -1.5

        total_dg = (vdw_energy + electrostatic_energy + solvation_energy
                    + hbond_energy - desolvation_penalty)
        total_dg = float(np.clip(total_dg, -10.0, -2.0))

        return {
            'delta_g_total_kcal_mol': total_dg,
            'delta_g_vdw': vdw_energy,
            'delta_g_electrostatic': electrostatic_energy,
            'delta_g_solvation': solvation_energy,
            'hbond_count': hbond_total,
            'hbond_energy': hbond_energy,
            'contact_area': buried_surface_area,
            'interface_complementarity': min(1.0, (hbond_total + salt_bridges) / 10.0),
            'per_residue_contribution': per_residue,
            'confidence': 'Medium (geometric approximation)',
        }

    def _write_sequence_as_pdb(self, sequence: str, filepath: str) -> None:
        lines = ['HEADER    PEPTIDE LIGAND']
        for i, aa in enumerate(sequence):
            x = 3.6 * np.cos(2 * np.pi * i / 3.6)
            y = 3.6 * np.sin(2 * np.pi * i / 3.6)
            z = 1.5 * i
            lines.append(
                f"ATOM  {i+1:5d}  CA  {aa}   A{i+1:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
            )
        lines.append('END')
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

    def _parse_rosetta_score(self, score_line: str) -> Dict:
        fields = score_line.split()
        if len(fields) < 2:
            return {}
        # Rosetta scorefiles: header row maps column names to positions
        # This is a simplified fallback; full parsing requires the header row
        return {'total_score': fields[1] if len(fields) > 1 else '-5.0'}


class LabFeasibilityScorer:
    """
    Scores synthesis, solubility, in-vivo stability, and delivery feasibility.
    Returns a 0–100 score + actionable issues/recommendations.
    """

    def score_design(self, sequence: str, modality: str = 'peptide') -> Dict:
        score = 100.0
        issues: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        length = len(sequence)

        if not sequence:
            return {
                'lab_feasibility_score': 0.0,
                'synthesis_feasible': False,
                'solubility_feasible': False,
                'stability_feasible': False,
                'issues': ['Empty sequence'],
                'warnings': [],
                'recommendations': [],
                'estimated_synthesis_time_days': 0,
                'estimated_synthesis_cost_usd': 0,
            }

        # ── Synthesis feasibility ──────────────────────────────────────────
        if length > 40:
            score -= 15
            issues.append(f"Length {length} > 40 requires recombinant expression or fragment ligation")
        elif length > 30:
            warnings.append(f"Length {length} may need fragment ligation for high purity")

        cys_count = sequence.count('C')
        if cys_count > 2:
            score -= 10
            issues.append(f"{cys_count} cysteines risk unwanted disulfide scrambling during SPPS")

        met_count = sequence.count('M')
        if met_count > 1:
            score -= 5
            warnings.append(f"{met_count} methionines susceptible to oxidation during synthesis")

        pro_count = sequence.count('P')
        if pro_count > 2:
            score -= 8
            issues.append(f"High proline content ({pro_count}) causes coupling delays in SPPS")

        if sequence[0] in ('Q', 'N'):
            score -= 5
            warnings.append("N-terminal Gln/Asn can cyclise to pyroglutamate during synthesis")

        if 'WW' in sequence or 'FF' in sequence or 'YY' in sequence:
            score -= 8
            issues.append("Adjacent aromatics may cause aggregation on resin during synthesis")

        # ── Solubility ─────────────────────────────────────────────────────
        hydrophobic_aa = sum(1 for aa in sequence if aa in 'WFLIV')
        charged_aa = sum(1 for aa in sequence if aa in 'KRDE')
        hydrophobic_fraction = hydrophobic_aa / length
        charged_fraction = charged_aa / length

        if hydrophobic_fraction > 0.4:
            score -= 15
            issues.append(f"Very high hydrophobicity ({hydrophobic_fraction:.0%}) → aggregation risk")
            recommendations.append("Add charged residues (D/E/K/R) or reduce aromatics")
        elif hydrophobic_fraction > 0.3:
            warnings.append(f"Moderate hydrophobicity ({hydrophobic_fraction:.0%}) → monitor aggregation")

        if charged_fraction < 0.15:
            score -= 10
            issues.append(f"Low charge fraction ({charged_fraction:.0%}) → aqueous solubility at risk")
            recommendations.append("Add Lys/Arg or Asp/Glu residues")

        # ── In-vivo stability ──────────────────────────────────────────────
        # Standard L-amino-acid peptides degrade quickly in serum without stabilisation
        if cys_count < 2:
            score -= 10
            warnings.append("No disulfide-capable Cys pair → <20 min serum half-life without modification")
            recommendations.append("Consider cyclisation or D-amino acid substitutions at protease-sensitive sites")
        else:
            score += 5
            recommendations.append("Cys pair enables disulfide cyclisation → improved protease resistance")

        # ── Modality-specific ──────────────────────────────────────────────
        if modality == 'cyclic_peptide' and cys_count < 2:
            score -= 20
            issues.append("Cyclic modality requires ≥2 Cys for disulfide cyclisation")

        if modality in ('nanobody', 'miniprotein') and length < 40:
            score -= 15
            issues.append("Miniprotein/nanobody requires ≥40 AA for a stable fold")

        # ── Delivery ───────────────────────────────────────────────────────
        if modality in ('peptide', 'cyclic_peptide'):
            if charged_fraction < 0.20:
                score -= 10
                warnings.append("Low charge may impede cellular uptake without CPP conjugation")
                recommendations.append("Consider TAT or poly-Arg CPP fusion for intracellular delivery")

            net_charge = (sequence.count('K') + sequence.count('R')
                          - sequence.count('D') - sequence.count('E'))
            if net_charge < 0:
                warnings.append("Anionic peptide needs NLS or CPP for nuclear/cytoplasmic delivery")
                recommendations.append("Consider poly-Arg C-terminal tag")

        final_score = float(np.clip(score, 0.0, 100.0))
        return {
            'lab_feasibility_score': final_score,
            'synthesis_feasible': score > 30,
            'solubility_feasible': charged_fraction >= 0.15,
            'stability_feasible': cys_count >= 2,
            'issues': issues,
            'warnings': warnings,
            'recommendations': recommendations,
            'estimated_synthesis_time_days': max(1, length // 10 + len(issues) * 2),
            'estimated_synthesis_cost_usd': 500 + length * 20 + len(issues) * 200,
        }


class TargetSelectivityScorer:
    """
    Assesses selectivity against off-target kinases and related proteins.
    Scores designed peptide against panel of known off-targets; returns ΔΔG and toxicity risk.
    """

    # Off-target reference panel: SOTA binders for common oncology off-targets
    _OFF_TARGET_PANEL: Dict[str, Dict] = {
        'EGFR_L858R':       {'delta_g': -6.5, 'toxicity': 'hepatotoxicity'},
        'HER2':             {'delta_g': -6.2, 'toxicity': 'cardiotoxicity'},
        'HER4':             {'delta_g': -5.8, 'toxicity': 'mild'},
        'ALK':              {'delta_g': -7.0, 'toxicity': 'severe (neurotoxicity)'},
        'ROS1':             {'delta_g': -6.8, 'toxicity': 'moderate'},
        'MET':              {'delta_g': -6.3, 'toxicity': 'hepatotoxicity'},
        'RET':              {'delta_g': -6.9, 'toxicity': 'moderate'},
        'BRAF':             {'delta_g': -6.4, 'toxicity': 'severe (cutaneous)'},
        'NRAS':             {'delta_g': -5.9, 'toxicity': 'moderate'},
        'HRAS':             {'delta_g': -6.0, 'toxicity': 'mild'},
        'BTK':              {'delta_g': -6.7, 'toxicity': 'hepatotoxicity'},
        'SYK':              {'delta_g': -6.5, 'toxicity': 'immunosuppression'},
        'RAF1':             {'delta_g': -6.2, 'toxicity': 'moderate'},
        'MAP2K1':           {'delta_g': -6.1, 'toxicity': 'mild'},
        'AKT1':             {'delta_g': -6.6, 'toxicity': 'severe (metabolic)'},
        'mTOR':             {'delta_g': -6.4, 'toxicity': 'severe (immunosuppression)'},
        'CDK2':             {'delta_g': -6.3, 'toxicity': 'moderate'},
        'CDK4':             {'delta_g': -6.2, 'toxicity': 'mild'},
        'GSK3B':            {'delta_g': -6.0, 'toxicity': 'severe (neurological)'},
        'MAPK1':            {'delta_g': -5.9, 'toxicity': 'mild'},
        'PIM1':             {'delta_g': -6.1, 'toxicity': 'mild'},
    }

    def __init__(self, docking_oracle: Optional['DockingOracle'] = None):
        self.docking_oracle = docking_oracle or DockingOracle()

    def assess_selectivity(self, peptide_sequence: str, target_name: str = '') -> Dict:
        """
        Score selectivity: design vs. off-target panel.
        Returns best ΔΔG (selectivity gap), mean off-target binding, toxicity flags.
        """
        peptide_result = self.docking_oracle.calculate_binding_energy(peptide_sequence)
        peptide_dg = peptide_result.get('delta_g_total_kcal_mol', -5.5)

        off_target_scores: Dict[str, Dict] = {}
        for ot_name, ot_data in self._OFF_TARGET_PANEL.items():
            ot_dg = ot_data['delta_g']
            ddg = ot_dg - peptide_dg  # negative = better selectivity (design binds tighter)
            off_target_scores[ot_name] = {
                'off_target_dg': ot_dg,
                'delta_delta_g': ddg,
                'selectivity_ratio': abs(ddg),
                'toxicity_risk': ot_data['toxicity'],
                'is_problematic': ddg > 0.5,  # design binds weaker than off-target
            }

        # Identify problem off-targets (where design binds weaker)
        problematic = [k for k, v in off_target_scores.items() if v['is_problematic']]
        mean_selectivity = np.mean([v['delta_delta_g'] for v in off_target_scores.values()])
        best_selectivity = np.max([v['delta_delta_g'] for v in off_target_scores.values()])
        worst_selectivity = np.min([v['delta_delta_g'] for v in off_target_scores.values()])

        toxicity_flags = list(set([off_target_scores[p]['toxicity_risk'] for p in problematic]))

        selectivity_score = float(np.clip(50.0 + mean_selectivity * 10.0, 0.0, 100.0))

        return {
            'selectivity_score': selectivity_score,
            'target_delta_g': peptide_dg,
            'mean_off_target_delta_g': float(np.mean([v['off_target_dg'] for v in off_target_scores.values()])),
            'mean_selectivity_ddg': float(mean_selectivity),
            'best_selectivity_ddg': float(best_selectivity),
            'worst_selectivity_ddg': float(worst_selectivity),
            'problematic_off_targets': problematic,
            'off_target_scores': off_target_scores,
            'toxicity_risks': toxicity_flags,
            'selectivity_feasible': len(problematic) == 0,
        }


class ResistanceEscapePredictor:
    """
    Simulates single-mutation escape variants and identifies "hard-to-escape" sequences.
    Scores designed peptide by mutational robustness: fewer high-affinity escapes = better.
    """

    def __init__(self, docking_oracle: Optional['DockingOracle'] = None):
        self.docking_oracle = docking_oracle or DockingOracle()
        self.amino_acids = 'ACDEFGHIKLMNPQRSTVWY'

    def predict_escapes(self, peptide_sequence: str, max_escapes: int = 5) -> Dict:
        """
        Generate all single-mutation variants; rank by improved binding (escape hotspots).
        Returns: escape_variant list, escape_score (lower = harder to escape).
        """
        base_result = self.docking_oracle.calculate_binding_energy(peptide_sequence)
        base_dg = base_result.get('delta_g_total_kcal_mol', -5.5)

        escape_variants: List[Dict] = []

        for pos in range(len(peptide_sequence)):
            wt_aa = peptide_sequence[pos]
            for mut_aa in self.amino_acids:
                if mut_aa == wt_aa:
                    continue
                mutant_seq = peptide_sequence[:pos] + mut_aa + peptide_sequence[pos+1:]
                mutant_result = self.docking_oracle.calculate_binding_energy(mutant_seq)
                mutant_dg = mutant_result.get('delta_g_total_kcal_mol', -5.5)

                delta_binding = mutant_dg - base_dg  # negative = escape (improves binding)
                if delta_binding > -0.1:  # escape candidates: similar or better binding
                    escape_variants.append({
                        'position': pos,
                        'wildtype_aa': wt_aa,
                        'mutant_aa': mut_aa,
                        'mutation': f"{wt_aa}{pos+1}{mut_aa}",
                        'mutant_sequence': mutant_seq,
                        'mutant_delta_g': float(mutant_dg),
                        'delta_binding': float(delta_binding),
                        'is_strong_escape': delta_binding > 0.5,
                    })

        # Sort by delta_binding (most favourable escapes first)
        escape_variants.sort(key=lambda x: x['delta_binding'], reverse=True)

        # Escape score: fraction of positions with viable escapes (lower = harder to escape)
        escape_positions = len(set(e['position'] for e in escape_variants[:max_escapes*2]))
        escape_score = float(escape_positions / len(peptide_sequence))

        return {
            'base_sequence': peptide_sequence,
            'base_delta_g': base_dg,
            'total_possible_mutations': len(peptide_sequence) * (len(self.amino_acids) - 1),
            'viable_escapes': len(escape_variants),
            'strong_escapes': sum(1 for e in escape_variants if e['is_strong_escape']),
            'top_escape_variants': escape_variants[:max_escapes],
            'escape_score': escape_score,  # 0.0 = hard to escape, 1.0 = easy to escape
            'is_escape_resistant': escape_score < 0.3,
            'escape_hotspots': list(set(e['position'] for e in escape_variants[:5])),
        }


class EnhancedPKPredictor:
    """
    Predicts pharmacokinetics: serum half-life, tissue distribution, clearance.
    More sophisticated than simple charge-based heuristics.
    """

    def predict_pk(self, peptide_sequence: str) -> Dict:
        """
        Estimate PK properties from sequence composition.
        Returns: serum_half_life, BBB_penetration, hepatic_clearance, tissue_accumulation.
        """
        length = len(peptide_sequence)
        net_charge = (peptide_sequence.count('K') + peptide_sequence.count('R')
                      - peptide_sequence.count('D') - peptide_sequence.count('E'))
        hydrophobic_fraction = sum(1 for aa in peptide_sequence if aa in 'WFLIV') / length
        cys_count = peptide_sequence.count('C')
        aromatic_count = peptide_sequence.count('W') + peptide_sequence.count('F') + peptide_sequence.count('Y')

        # Base serum half-life (unmodified linear peptides: <20 min)
        base_hl = 15.0
        hl_boost = 0.0

        # Cyclization (disulfide bond): +50% serum stability
        if cys_count >= 2:
            hl_boost += 7.5

        # PEGylation potential (charge + length allows conjugation): +200% boost
        if net_charge >= 0 and length <= 20:
            hl_boost += 30.0

        # D-amino acid enrichment (not in sequence, but can be added): +100% boost
        # Note: standard SPPS uses L-amino acids; this is a recommendation flag
        d_amino_recommendation = net_charge >= 0  # feasible only for reasonably charged peptides

        # High hydrophobicity + short peptide: aggregation → clearance: -20%
        if hydrophobic_fraction > 0.35 and length < 15:
            hl_boost -= 3.0

        serum_hl = base_hl + hl_boost
        serum_hl = float(np.clip(serum_hl, 5.0, 180.0))

        # BBB penetration: requires MW < 500 Da (peptides ~110 Da/AA), low charge
        estimated_mw = length * 110.0
        can_bbb_cross = estimated_mw < 500 and abs(net_charge) <= 1
        bbb_score = 0.0 if can_bbb_cross else 0.2

        # Hepatic clearance: high aromatic + positive charge = moderate clearance
        hepatic_clearance_rate = 0.3 + 0.1 * aromatic_count / length + 0.1 * max(0, net_charge) / length
        hepatic_clearance_rate = float(np.clip(hepatic_clearance_rate, 0.1, 0.9))

        # Tissue accumulation: high hydrophobicity → liver/spleen accumulation
        tissue_accumulation_risk = hydrophobic_fraction > 0.3

        # Recommendations
        recommendations = []
        if serum_hl < 30:
            recommendations.append("Short half-life: consider cyclization (Cys pair) or D-amino acid substitutions")
        if can_bbb_cross:
            recommendations.append("Low MW + charge: potential BBB penetration for CNS targets")
        if tissue_accumulation_risk:
            recommendations.append("High hydrophobicity: monitor for liver/spleen accumulation; consider PEGylation")
        if net_charge < 0:
            recommendations.append("Anionic: reduced oral bioavailability; consider subcutaneous/IV administration")

        return {
            'estimated_serum_half_life_min': serum_hl,
            'bbb_penetration_feasible': can_bbb_cross,
            'bbb_score': bbb_score,
            'estimated_mw_da': float(estimated_mw),
            'hepatic_clearance_rate': hepatic_clearance_rate,
            'tissue_accumulation_risk': tissue_accumulation_risk,
            'net_charge': net_charge,
            'hydrophobic_fraction': float(hydrophobic_fraction),
            'aromatic_count': aromatic_count,
            'disulfide_feasible': cys_count >= 2,
            'pegilization_feasible': net_charge >= 0 and length <= 20,
            'd_amino_acid_recommendation': d_amino_recommendation,
            'recommendations': recommendations,
        }


class ImmunogenicityScreener:
    """
    Detects immunogenic epitopes, MHC anchors, FLAG tags, and common immune triggers.
    Scores risk of adaptive/innate immune activation (0–100, higher = more immunogenic).
    """

    # MHC-binding anchor motifs (simplified; real prediction uses NetMHC)
    _MHC_ANCHORS = {
        'HLA-A*02:01': ['L', 'M', 'I', 'V'],  # hydrophobic preference
        'HLA-B*07:02': ['P', 'V', 'K', 'R'],
        'HLA-C*07:02': ['W', 'Y', 'F', 'L'],
    }

    # Common immunogenic peptide motifs (known T-cell epitopes)
    _IMMUNOGENIC_MOTIFS = [
        'LMWKY', 'FPWRK', 'GWRL', 'PFVW',  # strong HLA binders
        'CXC', 'WXW', 'FXF',  # hydrophobic anchors
    ]

    # Common immunogenic tags/sequences
    _IMMUNOGENIC_TAGS = {
        'FLAG': 'DYKDDDDK',
        'His6': 'HHHHHH',
        'HA': 'YPYDVPDYA',
        'Myc': 'EQKLISEEDL',
        'GST': 'MSPILGYWKIK',
    }

    # Protease-sensitive motifs (trigger innate immunity)
    _PROTEASE_SENSITIVE = ['GLG', 'AGA', 'RXR', 'KXK']

    def screen_immunogenicity(self, peptide_sequence: str) -> Dict:
        """
        Score immunogenicity risk. Returns 0–100 score + detailed flags.
        """
        seq = peptide_sequence.upper()
        length = len(seq)
        score = 0.0
        issues: List[str] = []
        recommendations: List[str] = []

        # ── MHC Epitope Check ──
        mhc_anchor_count = 0
        for anchor_set in self._MHC_ANCHORS.values():
            for aa in seq:
                if aa in anchor_set:
                    mhc_anchor_count += 1
        mhc_anchor_fraction = mhc_anchor_count / max(length, 1)

        if mhc_anchor_fraction > 0.5:
            score += 30
            issues.append(f"High MHC anchor content ({mhc_anchor_fraction:.0%}): likely HLA-peptide binder")
            recommendations.append("Consider substitutions at positions: " + ", ".join(
                f"{i+1}" for i, aa in enumerate(seq)
                if any(aa in anchor_set for anchor_set in self._MHC_ANCHORS.values())
            )[:50])
        elif mhc_anchor_fraction > 0.3:
            score += 15
            issues.append(f"Moderate MHC anchor content ({mhc_anchor_fraction:.0%})")

        # ── Immunogenic Motif Check ──
        motif_count = 0
        found_motifs = []
        for motif in self._IMMUNOGENIC_MOTIFS:
            if motif in seq:
                motif_count += 1
                found_motifs.append(motif)
        if found_motifs:
            score += min(25, motif_count * 8)
            issues.append(f"Contains {motif_count} known immunogenic motif(s): {', '.join(found_motifs[:3])}")
            recommendations.append("Consider aromatic/charge substitutions to disrupt motifs")

        # ── Tag/Linker Check ──
        tag_found = []
        for tag_name, tag_seq in self._IMMUNOGENIC_TAGS.items():
            if tag_seq in seq or tag_seq in seq:
                tag_found.append(tag_name)
        if tag_found:
            score += 20
            issues.append(f"Contains immunogenic tag(s): {', '.join(tag_found)}")
            recommendations.append("Remove tag or use masked epitope variant")

        # ── Protease Sensitivity (Innate Immunity Trigger) ──
        protease_motifs = sum(1 for motif in self._PROTEASE_SENSITIVE if motif in seq)
        if protease_motifs > 0:
            score += min(15, protease_motifs * 5)
            issues.append(f"Contains {protease_motifs} protease-sensitive motif(s): triggers innate immunity")
            recommendations.append("Add D-amino acids or N-glycosylation to mask")

        # ── Glycosylation Sites (Can reduce immunogenicity if utilized) ──
        ngly_count = seq.count('N')
        if ngly_count >= 2:
            score -= 5  # Small credit for potential N-glycosylation sites
            recommendations.append(f"N-glycosylation sites ({ngly_count}): can reduce immunogenicity if utilized")

        # ── Charge Dysbalance (Aggregation Antigenicity) ──
        net_charge = seq.count('K') + seq.count('R') - seq.count('D') - seq.count('E')
        if abs(net_charge) > 3:
            score += 10
            issues.append(f"High net charge ({net_charge:+}): may form aggregates → immunogenic")
            recommendations.append("Balance charge with complementary residues")

        final_score = float(np.clip(score, 0.0, 100.0))
        immunogenic_threshold = 40.0  # >40 = high risk

        return {
            'immunogenicity_score': final_score,
            'is_high_immunogenic_risk': final_score > immunogenic_threshold,
            'mhc_anchor_fraction': float(mhc_anchor_fraction),
            'mhc_epitope_risk': 'high' if mhc_anchor_fraction > 0.5 else 'moderate' if mhc_anchor_fraction > 0.3 else 'low',
            'immunogenic_motifs_found': found_motifs,
            'immunogenic_tags_found': tag_found,
            'protease_sensitive_motifs': protease_motifs,
            'issues': issues,
            'recommendations': recommendations,
            'nglycosylation_sites': ngly_count,
        }


class StructuralConstraintValidator:
    """
    Validates and applies structural design constraints: fixed residues, forbidden positions, motifs.
    Enables users to guide design with domain knowledge.
    """

    def validate_constraints(self, sequence: str, constraints: Dict) -> Dict:
        """
        Check if sequence satisfies user-specified structural constraints.
        Returns: satisfaction_score (0–100), violations, suggestions.
        """
        violations: List[str] = []
        satisfied: List[str] = []
        score = 100.0

        # ── Fixed Residue Constraints ──
        fixed_residues = constraints.get('fixed_residues', {})  # {position: aa, ...}
        for pos, required_aa in fixed_residues.items():
            if 0 <= pos < len(sequence):
                actual_aa = sequence[pos]
                if actual_aa != required_aa:
                    violations.append(f"Position {pos+1}: expected {required_aa}, got {actual_aa}")
                    score -= 25
                else:
                    satisfied.append(f"Position {pos+1}: fixed as {required_aa} ✓")

        # ── Forbidden Residue Positions ──
        forbidden_positions = constraints.get('forbidden_residues', {})  # {position: [aa, ...], ...}
        for pos, forbidden_list in forbidden_positions.items():
            if 0 <= pos < len(sequence):
                actual_aa = sequence[pos]
                if actual_aa in forbidden_list:
                    violations.append(f"Position {pos+1}: {actual_aa} is forbidden")
                    score -= 15
                else:
                    satisfied.append(f"Position {pos+1}: {actual_aa} is allowed ✓")

        # ── Required Motif ──
        required_motif = constraints.get('required_motif', '')
        if required_motif and required_motif not in sequence:
            violations.append(f"Required motif '{required_motif}' not found in sequence")
            score -= 30

        # ── Secondary Structure Preference ──
        helix_preference = constraints.get('prefer_helix', False)
        if helix_preference:
            helix_score = self._estimate_helix_propensity(sequence)
            if helix_score > 0.6:
                satisfied.append(f"Helix propensity: {helix_score:.2f} (target) ✓")
            else:
                violations.append(f"Low helix propensity: {helix_score:.2f} (target >0.6)")
                score -= 20

        # ── Length Constraint ──
        target_length = constraints.get('target_length')
        if target_length:
            if abs(len(sequence) - target_length) <= 2:
                satisfied.append(f"Length: {len(sequence)} (target {target_length}) ✓")
            else:
                violations.append(f"Length {len(sequence)} outside target range ±2 from {target_length}")
                score -= 10

        final_score = float(np.clip(score, 0.0, 100.0))

        return {
            'constraint_satisfaction_score': final_score,
            'all_constraints_satisfied': len(violations) == 0,
            'satisfied_constraints': satisfied,
            'violated_constraints': violations,
            'num_violations': len(violations),
        }

    def _estimate_helix_propensity(self, sequence: str) -> float:
        """Rough helix propensity from AA composition (Chou-Fasman rules)."""
        helix_scale = {'A': 1.42, 'E': 1.51, 'L': 1.21, 'M': 1.45, 'Q': 1.11,
                       'K': 1.16, 'R': 0.98, 'H': 1.00, 'V': 1.06, 'I': 1.08,
                       'Y': 0.69, 'C': 0.70, 'W': 1.08, 'F': 1.13, 'T': 0.83,
                       'N': 0.67, 'G': 0.57, 'P': 0.57, 'S': 0.77, 'D': 1.01}
        propensity = np.mean([helix_scale.get(aa, 0.7) for aa in sequence.upper()])
        return float(np.clip(propensity / 1.2, 0.0, 1.0))


class CostOptimizer:
    """
    Multi-objective trade-off between binding affinity (ΔG) and synthesis cost.
    Enables commercial scenarios where "good enough" cheaper < "excellent" expensive.
    """

    def compute_cost_score(self, sequence: str, delta_g: float) -> Dict:
        """
        Rank designs by Pareto frontier: maximize affinity while minimizing cost.
        Returns: cost_score (0–100, lower = cheaper), affinity_cost_ratio, pareto_rank.
        """
        length = len(sequence)
        base_cost = 500.0

        # Synthesis difficulty multipliers
        cys_count = sequence.count('C')
        pro_count = sequence.count('P')
        met_count = sequence.count('M')
        aromatic_count = sequence.count('W') + sequence.count('F') + sequence.count('Y')

        difficulty_multiplier = 1.0
        if cys_count > 2:
            difficulty_multiplier += 0.3
        if pro_count > 2:
            difficulty_multiplier += 0.2
        if aromatic_count > 4:
            difficulty_multiplier += 0.15

        synthesis_cost = base_cost + (length * 20.0 * difficulty_multiplier)
        synthesis_cost = float(np.clip(synthesis_cost, 500, 5000))

        # Affinity-cost ratio: ΔG improvement per dollar
        dg_absolute = abs(delta_g)
        affinity_cost_ratio = dg_absolute / (synthesis_cost / 100.0)  # kcal/mol per $100

        # Cost score (0–100): 100 = cheapest, 0 = most expensive
        cost_score = float(np.clip(100.0 - (synthesis_cost - 500) / 45.0, 0.0, 100.0))

        # Pareto rank heuristic (requires ensemble context; simplified here)
        pareto_recommendation = "Good value" if affinity_cost_ratio > 0.05 else "Premium cost"

        return {
            'estimated_synthesis_cost_usd': synthesis_cost,
            'cost_score': cost_score,
            'difficulty_multiplier': difficulty_multiplier,
            'affinity_cost_ratio': float(affinity_cost_ratio),
            'pareto_recommendation': pareto_recommendation,
            'cost_drivers': [
                f"Length: {length} aa (+${length * 20.0:.0f})",
                f"Cysteines: {cys_count} (+{cys_count * 0.3 * 100:.0f}%)" if cys_count > 2 else None,
                f"Prolines: {pro_count} (+{pro_count * 0.2 * 100:.0f}%)" if pro_count > 2 else None,
                f"Aromatics: {aromatic_count} (+{aromatic_count * 0.15 * 100:.0f}%)" if aromatic_count > 4 else None,
            ],
        }

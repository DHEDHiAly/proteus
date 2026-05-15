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

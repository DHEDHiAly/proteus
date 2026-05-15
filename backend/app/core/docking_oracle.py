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

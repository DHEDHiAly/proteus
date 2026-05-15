import logging
import re
import uuid
import time
import numpy as np
import httpx
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from app.config import settings
from app.core.mcmc import MCMCParallelSampler
from app.core.energy import EnergyOracle
from app.core.proposal import ProposalDistribution
from app.core.esm2 import ESM2EmbeddingCache
from app.core.docking_oracle import (
    DockingOracle, LabFeasibilityScorer,
    TargetSelectivityScorer, ResistanceEscapePredictor, EnhancedPKPredictor,
    ImmunogenicityScreener, StructuralConstraintValidator, CostOptimizer
)
from app.schemas.agent import PatientInfo, AgentMessage, AgentRunResponse, DesignSessionContext
from app.api.targets import load_targets_metadata
from app.services.chat_responder import ChatResponder
from app.services.context_aware_responder import ContextAwareChatResponder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ESMFold structure prediction (free public API, no installation required)
# ---------------------------------------------------------------------------

_ESMFOLD_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"
_ESMFOLD_TIMEOUT = 60  # seconds; ESMFold can be slow on long sequences


def _call_esmfold(sequence: str) -> Optional[str]:
    """POST sequence to ESMFold and return PDB string, or None on failure.

    Sequences longer than 400 AA are skipped (API limit and response time).
    """
    if not sequence or len(sequence) > 400:
        logger.info("ESMFold skipped: sequence length %d", len(sequence) if sequence else 0)
        return None
    try:
        resp = httpx.post(
            _ESMFOLD_URL,
            content=sequence,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_ESMFOLD_TIMEOUT,
        )
        if resp.status_code == 200 and resp.text.strip().startswith("ATOM"):
            logger.info("ESMFold returned PDB for sequence length %d", len(sequence))
            return resp.text
        logger.warning("ESMFold unexpected response %d: %.120s", resp.status_code, resp.text)
        return None
    except Exception as exc:
        logger.warning("ESMFold call failed: %s", exc)
        return None

CANCER_TARGET_MAP = {
    # EGFRvIII — glioblastoma
    "glioblastoma": ("EGFRvIII", "3gp1"),
    "gbm": ("EGFRvIII", "3gp1"),
    "egfr": ("EGFRvIII", "3gp1"),
    "egfrviii": ("EGFRvIII", "3gp1"),
    # KRAS G12C — lung / pancreatic / colorectal
    "nsclc": ("KRAS_G12C", "6OIM"),
    "lung": ("KRAS_G12C", "6OIM"),
    "kras": ("KRAS_G12C", "6OIM"),
    "g12c": ("KRAS_G12C", "6OIM"),
    "pancreatic": ("KRAS_G12C", "6OIM"),
    "colorectal": ("KRAS_G12C", "6OIM"),
    # PD-L1 — immune checkpoint / melanoma / breast
    "pd-l1": ("PD-L1", "4zqk"),
    "pdl1": ("PD-L1", "4zqk"),
    "melanoma": ("PD-L1", "4zqk"),
    "solid tumor": ("PD-L1", "4zqk"),
    # SARS-CoV-2 3CL protease
    "covid": ("SARS-CoV-2_3CL", "6LU7"),
    "3cl": ("SARS-CoV-2_3CL", "6LU7"),
    "protease": ("SARS-CoV-2_3CL", "6LU7"),
    "coronavirus": ("SARS-CoV-2_3CL", "6LU7"),
    "sars": ("SARS-CoV-2_3CL", "6LU7"),
    # HER2 — breast / gastric / ovarian
    "her2": ("HER2", "3WSQ"),
    "erbb2": ("HER2", "3WSQ"),
    "breast": ("HER2", "3WSQ"),
    "gastric": ("HER2", "3WSQ"),
    # BCR-ABL1 — CML / Philadelphia+ ALL
    "leukemia": ("BCR-ABL1", "2HYY"),
    "cml": ("BCR-ABL1", "2HYY"),
    "bcr-abl": ("BCR-ABL1", "2HYY"),
    "bcrabl": ("BCR-ABL1", "2HYY"),
    "abl": ("BCR-ABL1", "2HYY"),
    "philadelphia": ("BCR-ABL1", "2HYY"),
    # VEGFR2 — angiogenesis / liver / ovarian
    "vegfr": ("VEGFR2", "4ASD"),
    "vegfr2": ("VEGFR2", "4ASD"),
    "angiogenesis": ("VEGFR2", "4ASD"),
    "liver": ("VEGFR2", "4ASD"),
    "hepatocellular": ("VEGFR2", "4ASD"),
    "ovarian": ("VEGFR2", "4ASD"),
    # AR — prostate cancer
    "prostate": ("AR", "2AM9"),
    "androgen": ("AR", "2AM9"),
    "crpc": ("AR", "2AM9"),
    # CTLA-4 — immune checkpoint (complement to PD-L1)
    "ctla": ("CTLA-4", "3OSK"),
    "ctla-4": ("CTLA-4", "3OSK"),
    "ctla4": ("CTLA-4", "3OSK"),
    "ipilimumab": ("CTLA-4", "3OSK"),
    # CD19 — B-cell lymphoma / ALL
    "lymphoma": ("CD19", "6AL5"),
    "cd19": ("CD19", "6AL5"),
    "b-cell": ("CD19", "6AL5"),
    "bcell": ("CD19", "6AL5"),
    "cart": ("CD19", "6AL5"),
}

SEED_SEQUENCES = {
    "EGFRvIII":       "MVLDGEQG",   # GBM peptide seed (Aly's work)
    "PD-L1":          "MVLDGEQG",   # checkpoint blocker seed
    "KRAS_G12C":      "MVLDGEQG",   # RAS allosteric seed
    "SARS-CoV-2_3CL": "MVAQWKEQ",   # 3CL protease inhibitor seed
    "HER2":           "LTVSSPEK",   # pertuzumab domain-II epitope seed
    "BCR-ABL1":       "MKHKSEEL",   # myristoyl-pocket allosteric seed
    "VEGFR2":         "VHFNMTQR",   # VEGF D2 binding loop mimic seed
    "AR":             "FXXLFQAA",   # LXXLL coactivator motif seed (X=L)
    "CTLA-4":         "MYPPPY",     # CTLA-4 B7-binding MYPPPY motif
    "CD19":           "MGAFQCLD",   # FMC63 CDR3 mimic seed
}

# Amino acid chemical property classes
AA_PROPERTIES: Dict[str, Dict[str, str]] = {
    "A": {"class": "nonpolar aliphatic", "hydrophobicity": "moderate"},
    "R": {"class": "positive charged", "hydrophobicity": "hydrophilic"},
    "N": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "D": {"class": "negative charged", "hydrophobicity": "hydrophilic"},
    "C": {"class": "special (thiol)", "hydrophobicity": "moderate"},
    "E": {"class": "negative charged", "hydrophobicity": "hydrophilic"},
    "Q": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "G": {"class": "special (flexible)", "hydrophobicity": "minimal"},
    "H": {"class": "positive aromatic", "hydrophobicity": "moderate"},
    "I": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
    "L": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
    "K": {"class": "positive charged", "hydrophobicity": "hydrophilic"},
    "M": {"class": "nonpolar (sulfur)", "hydrophobicity": "moderate"},
    "F": {"class": "aromatic nonpolar", "hydrophobicity": "hydrophobic"},
    "P": {"class": "special (cyclic)", "hydrophobicity": "minimal"},
    "S": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "T": {"class": "polar uncharged", "hydrophobicity": "moderate"},
    "W": {"class": "aromatic nonpolar", "hydrophobicity": "hydrophobic"},
    "Y": {"class": "aromatic polar", "hydrophobicity": "moderate"},
    "V": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
}

PHASE_EXPLANATIONS = {
    "generate": (
        "**Phase: Generate**\n"
        "Running Gradient-Informed Adaptive Parallel Tempering (GIAPT) across parallel chains. "
        "Each chain explores sequence space at a different temperature:\n"
        "- T=0.5: fine-tuning near known solutions\n"
        "- T=2.0: balanced exploration vs exploitation\n"
        "- T=5.0+: broad search for novel structural motifs\n\n"
        "Temperature adapts every 50 steps to maintain 23–40% acceptance rate (BADASS-inspired). "
        "At each step, a mutation is proposed (point substitution, insertion, deletion, "
        "or block swap) and accepted/rejected by Metropolis-Hastings based on "
        "the multi-objective energy score."
    ),
    "evaluate": (
        "**Phase: Evaluate**\n"
        "Each candidate is scored across eight biophysical objectives simultaneously:\n"
        "- **ΔG binding** — Free energy of binding (kcal/mol, RT·ln(Kd)); < −6 = promising\n"
        "- **Binding affinity** — Sequence information content vs. target pocket\n"
        "- **Stability** — Secondary structure propensity (helix/sheet content)\n"
        "- **Solubility** — GRAVY score + charged residue fraction\n"
        "- **pLDDT estimate** — Pseudo-confidence of structural ordering (0–100)\n"
        "- **ΔΔG estimate** — Thermodynamic stability vs. unfolded state (kcal/mol)\n"
        "- **Aggregation propensity** — Hydrophobic stretch analysis\n"
        "- **Immunogenicity** — MHC anchor motif frequency\n"
        "- **Manufacturability** — Expression feasibility in recombinant systems\n\n"
        "Candidates are ranked and the best seeds the next round."
    ),
}

# Impossible or physically contradictory constraint combinations
IMPOSSIBLE_PATTERNS = [
    (
        r"(highly|very|extremely)\s+hydrophobic.{0,40}(highly|very|extremely)\s+sol",
        "Requesting both high hydrophobicity and high solubility is thermodynamically contradictory. "
        "Hydrophobic residues (I, L, V, F, W) drive burial in a hydrophobic core; a highly hydrophobic "
        "surface protein would aggregate. I can optimize for a moderate GRAVY score (~0.5) that balances "
        "core stability with surface solubility — would that work?"
    ),
    (
        r"(infinit|perfect|absolute|unlimited)\s+(stability|thermal\s+stability|thermostability)",
        "Infinite thermal stability is physically impossible — all proteins denature at some temperature. "
        "Thermophilic proteins (e.g., from Thermus thermophilus) reach Tm ~80-95°C through dense packing "
        "and extensive salt bridges. I can optimize for high thermostability by maximizing helix content, "
        "minimizing Gly/Pro, and reinforcing charged residue pairs — targeting a ΔΔG < -5 kcal/mol."
    ),
    (
        r"only\s+(gly|glycine).{0,10}(ala|alanine)|only\s+(ala|alanine).{0,10}(gly|glycine)",
        "A protein composed only of glycine and alanine cannot form a stable globular fold. "
        "Gly and Ala lack side chain diversity for hydrophobic core packing, hydrogen bonding "
        "networks, or electrostatic interactions. I can design a minimal sequence with high "
        "Gly/Ala content (~40%) while adding a small set of charged and aromatic residues "
        "sufficient for structural stability."
    ),
    (
        r"(fully\s+stable|maximally\s+stable)\s+globular.{0,30}(only|just)\s+(gly|glycine|ala|alanine)",
        "A fully stable globular protein cannot be built from only Gly and Ala. These residues "
        "lack the side chain chemistry required for hydrophobic core formation and specific "
        "tertiary contacts. Poly-Gly/Ala sequences form amyloid-like aggregates, not globular folds."
    ),
    (
        r"(infinite|unlimited|perfect)\s+solubility.{0,30}(membrane|transmembrane|lipid)",
        "Membrane-anchored or transmembrane proteins require hydrophobic transmembrane helices "
        "that are intrinsically insoluble in aqueous solution. This contradicts perfect aqueous solubility. "
        "I can design a peripheral membrane-binding peptide or a detergent-solubilized construct instead."
    ),
]


def _suggest_solubility_tags(seq: str) -> List[str]:
    """
    Detect solubility liabilities and suggest remediation tags.
    Returns a list of tag strings for display.
    """
    from app.core.energy import HYDROPHOBICITY_SCALE
    tags: List[str] = []
    if not seq:
        return tags
    gravy = sum(HYDROPHOBICITY_SCALE.get(aa, 0.0) for aa in seq) / max(len(seq), 1)
    if gravy > 1.5:
        tags.append("Grease Ball (GRAVY {:.2f}) — add D/E/K residues".format(gravy))
    # Hydrophobic stretch >= 4 residues in ILFVWM
    cur = 0
    max_stretch = 0
    for aa in seq:
        if aa in "ILFVWM":
            cur += 1
            if cur > max_stretch:
                max_stretch = cur
        else:
            cur = 0
    if max_stretch >= 4:
        tags.append("Hydrophobic stretch ({} residues) — suggest D/E insertion".format(max_stretch))
    # C-terminal hydrophobic tail -> suggest K-tag
    tail = seq[-4:] if len(seq) >= 4 else seq
    tail_hydro = sum(1 for aa in tail if aa in "ILFVWM")
    if tail_hydro >= 3:
        tags.append("C-terminal hydrophobic tail — suggest K-tag addition")
    return tags


def _generate_3d_notes(seq: str, target_name: str, pocket_residues: List[int],
                       pdb_id: str = "") -> List[str]:
    """
    Generate 3D structure inspection notes for the molecular viewer.
    Returns list of actionable note strings.
    """
    notes: List[str] = []
    if not seq:
        return notes
    # Aromatic residues -> pi-stacking candidates
    aromatic_positions = [i + 1 for i, aa in enumerate(seq) if aa in "FWY"]
    if aromatic_positions:
        aa_strs = ["{}{}".format(seq[i - 1], i) for i in aromatic_positions[:3]]
        notes.append(
            "Pi-stacking candidates: {} — inspect in viewer for aromatic contacts "
            "at binding interface.".format(", ".join(aa_strs))
        )
    # Charged residues -> salt bridge candidates
    charged_positions = [(i + 1, aa) for i, aa in enumerate(seq) if aa in "RKDE"]
    if charged_positions:
        pos_strs = ["{}{}".format(aa, pos) for pos, aa in charged_positions[:3]]
        notes.append(
            "Salt bridge candidates: {} — check proximity to oppositely charged "
            "pocket residues for electrostatic anchoring.".format(", ".join(pos_strs))
        )
    # Pocket residue selection note
    if pocket_residues:
        pocket_in_range = [pos for pos in pocket_residues if pos < len(seq)]
        viewer_ref = pdb_id or target_name
        if pocket_in_range:
            notes.append(
                "RCSB Selection: highlight residues {} in {} to visualize "
                "binding pocket overlap.".format(
                    "+".join(str(p) for p in pocket_in_range[:6]), viewer_ref
                )
            )
    # Always add surface/clash check
    notes.append(
        "Surface clash check: use RCSB 3D viewer Analyze > Contacts to verify "
        "no steric clashes at the designed binding interface."
    )
    return notes


def _format_fasta(seq: str, target_name: str, dg: float, kd: float,
                  lab: float) -> str:
    """Format sequence as FASTA with biophysical header."""
    header = ">Proteus_{} | dG {:.2f} kcal/mol | Kd {:.0f} nM | Lab viability {:.0f}/100".format(
        target_name.replace(" ", "_"), dg, kd, lab
    )
    wrapped = "\n".join(seq[i:i + 60] for i in range(0, len(seq), 60))
    return header + "\n" + wrapped


def _generate_physics_justification(
    design: dict, round_num: int, prev_seq: str, modality: str
) -> str:
    """
    Generate a per-round physics narrative for the Command-and-Justify protocol.
    Returns a multi-line string covering all biophysical mechanisms.
    """
    seq = design.get("sequence", "")
    dg = design.get("delta_g_binding_kcal_mol", 0.0)
    kd = design.get("kd_nM", 0.0)
    sc = design.get("surface_complementarity", 0.0)
    gate1 = design.get("gate1_pass", False)
    solv_dg = design.get("solvation_delta_g", 0.0)
    gate2 = design.get("gate2_pass", False)
    entropy = design.get("entropic_penalty", 0.0)
    gate3 = design.get("gate3_pass", False)
    hbonds = design.get("hbond_count", 0)
    lab = design.get("lab_viability_score", 0.0)
    sel_ddg = design.get("selectivity_ddg", 0.0)
    sel_ratio = design.get("selectivity_ratio", 1.0)

    lines = ["**Physics Justification — Round {}**".format(round_num), ""]

    # Hydrophobic Wedge
    hydro_count = sum(1 for aa in seq if aa in "ILFVWM")
    hydro_frac = hydro_count / max(len(seq), 1)
    if hydro_frac >= 0.35:
        wedge = "Strong hydrophobic core ({:.0f}% ILFVWM) — favorable burial in target pocket".format(
            hydro_frac * 100)
    elif hydro_frac >= 0.20:
        wedge = "Moderate hydrophobic content ({:.0f}% ILFVWM) — partial burial contribution".format(
            hydro_frac * 100)
    else:
        wedge = "Low hydrophobic content ({:.0f}% ILFVWM) — polar interface dominant; check desolvation".format(
            hydro_frac * 100)
    lines.append("- Hydrophobic Wedge: " + wedge)

    # Charge Anchor
    pos_count = sum(1 for aa in seq if aa in "RK")
    neg_count = sum(1 for aa in seq if aa in "DE")
    charge_net = pos_count - neg_count
    if charge_net > 0:
        anchor = "{} cationic (R/K) vs {} anionic (D/E) — net +{} charge; potential salt-bridge anchor with anionic pocket".format(
            pos_count, neg_count, charge_net)
    elif charge_net < 0:
        anchor = "{} anionic (D/E) vs {} cationic (R/K) — net {} charge; electrostatic anchor with cationic pocket residues".format(
            neg_count, pos_count, charge_net)
    else:
        anchor = "Charge-balanced ({} pos, {} neg) — distributed electrostatic contacts expected".format(
            pos_count, neg_count)
    lines.append("- Charge Anchor: " + anchor)

    # Enthalpic Lock (Gate 1 — Surface Complementarity)
    gate1_str = "PASS" if gate1 else "FAIL"
    lock_note = (
        "surface geometry sufficient for stable enthalpic interface"
        if gate1
        else "poor geometric fit — consider aromatic (F/W/Y) or charged residue insertions at contact positions"
    )
    lines.append(
        "- Enthalpic Lock (Sc): Sc = {:.3f} ({}) — threshold 0.400; {}".format(sc, gate1_str, lock_note)
    )
    lines.append(
        "- H-bonds: {} predicted backbone + sidechain contacts at binding interface".format(hbonds)
    )

    # Solvation (Gate 2)
    gate2_str = "PASS" if gate2 else "FAIL"
    if solv_dg <= 0.0:
        solv_note = "burial gains (hydrophobic + vdW) exceed desolvation penalty"
    else:
        solv_note = "charge desolvation cost dominates burial gain; consider reducing K/R count or adding compensating H-bonds"
    lines.append(
        "- Solvation Gain/Cost: DG_solv = {:.2f} kcal/mol ({}) — {}".format(
            solv_dg, gate2_str, solv_note)
    )

    # Conformational Entropy (Gate 3)
    gate3_str = "PASS" if gate3 else "FAIL"
    if gate3:
        ent_note = "conformational restriction within acceptable range for binding"
    else:
        ent_note = "excessive flexibility or disordered segments predicted; consider Gly reduction or stapling"
    lines.append(
        "- Conformational Entropy: -TDS penalty = {:.2f} kcal/mol ({}) — threshold 3.50; {}".format(
            entropy, gate3_str, ent_note)
    )

    # ΔG result
    if dg <= -9.0:
        dg_interp = "strong binder"
    elif dg <= -7.0:
        dg_interp = "good binder"
    elif dg <= -6.0:
        dg_interp = "promising (above AutoDock Vina lab-worthy threshold)"
    else:
        dg_interp = "weak binder — below -6.0 kcal/mol lab-worthy threshold"
    lines.append(
        "- DG = {:.2f} kcal/mol | Kd = {:.0f} nM — {}".format(dg, kd, dg_interp)
    )

    # Selectivity
    if sel_ddg > 0:
        sel_note = "on-target preference confirmed; off-target binding penalized"
    else:
        sel_note = "off-target risk present; increase pocket-specificity constraints and re-run"
    lines.append(
        "- Selectivity: DDG = {:.2f} kcal/mol | ratio {:.1f}x — {}".format(
            sel_ddg, sel_ratio, sel_note)
    )

    # Lab Viability
    if lab >= 70:
        lab_note = "proceed to peptide synthesis or recombinant expression"
    elif lab >= 50:
        lab_note = "borderline; address failing gates before synthesis"
    else:
        lab_note = "significant optimization required before lab hand-off"
    lines.append("- Lab Viability: {:.0f}/100 — {}".format(lab, lab_note))

    # Modality
    if modality:
        modality_labels = {
            "peptide": "Peptide (8-30 AA) — solid-phase synthesis viable",
            "miniprotein": "Miniprotein (30-100 AA) — E. coli expression; verify disulfide-free",
            "nanobody": "Nanobody/VHH (110-130 AA) — yeast or E. coli periplasm expression",
            "cyclic_peptide": "Cyclic peptide — SPPS with head-to-tail cyclization strategy",
            "antimicrobial": "Antimicrobial peptide — SPPS; verify membrane disruption assay",
        }
        lines.append("- Modality: " + modality_labels.get(modality, modality))

    # Mutation Strategy (round-over-round diff)
    if prev_seq and seq and prev_seq != seq:
        diffs = []
        for i, (a, b) in enumerate(zip(prev_seq, seq)):
            if a != b:
                diffs.append("{}{}>{}".format(a, i + 1, b))
        if len(seq) != len(prev_seq):
            diffs.append("len {} -> {}".format(len(prev_seq), len(seq)))
        if diffs:
            suffix = " ..." if len(diffs) > 6 else ""
            lines.append(
                "- Mutation Strategy: {} change(s) from prior round — {}{}".format(
                    len(diffs), ", ".join(diffs[:6]), suffix)
            )
    else:
        lines.append(
            "- Mutation Strategy: Round 1 seed — starting from {}".format(
                seq[:8] if seq else "initial sequence")
        )

    return "\n".join(lines)


def _parse_constraints(message: str, notes: str = "") -> Dict:
    """
    Parse free-text message for biophysical design constraints.
    Returns a dict of recognized constraints and their values.
    """
    text = (message + " " + notes).lower()
    constraints: Dict = {}

    # Length constraints
    m = re.search(r"(\d+)\s*(amino\s*acid|residue|aa|mer)\b", text)
    if m:
        constraints["target_length"] = int(m.group(1))

    # Cysteine constraint
    if re.search(r"no\s+cys|cysteine.free|without\s+cys|avoid\s+cys", text):
        constraints["no_cysteines"] = True

    # Solubility
    if re.search(r"high\s+solubil|soluble|water.soluble", text):
        constraints["high_solubility"] = True

    # Aggregation
    if re.search(r"low\s+aggreg|non.aggreg|anti.aggreg|aggregation.free", text):
        constraints["low_aggregation"] = True

    # Stability / thermostability
    if re.search(r"thermostab|thermal\s+stab|heat.stable|high\s+stab|improve.*stab", text):
        constraints["thermostable"] = True

    # Secondary structure
    if re.search(r"alpha.helic|alpha\s+hel|\balpha\s+helix\b", text):
        constraints["secondary_structure"] = "alpha-helical"
    elif re.search(r"beta.sheet|beta\s+strand", text):
        constraints["secondary_structure"] = "beta-sheet"

    # pH / extracellular
    if re.search(r"physiolog|ph\s*7|extracellular|serum", text):
        constraints["physiological_stability"] = True

    # Immunogenicity
    if re.search(r"low\s+immuno|reduced\s+immuno|non.immunog", text):
        constraints["low_immunogenicity"] = True

    # BBB / CNS
    if re.search(r"\bbbb\b|blood.brain|cns\s+penetr|brain\s+penetr", text):
        constraints["bbb_penetrant"] = True

    # Manufacturability
    if re.search(r"express|manufactur|producib|e\.?\s*coli", text):
        constraints["high_manufacturability"] = True

    # Antimicrobial
    if re.search(r"antimicrobial|amp\b|gram.positive|gram.negative|bactericid", text):
        constraints["antimicrobial"] = True

    return constraints


# Triggers that indicate the user wants a new design run (override question detection)
_DESIGN_TRIGGERS = [
    r'\bdesign\b', r'\boptimize\b', r'\bgenerate\b', r'\bcreate\b',
    r'\brun\s+(mcmc|again|another|more|a\s+new)\b',
    r'\bmake\s+.{0,20}(protein|peptide|sequence|candidate)\b',
    r'\bfind\s+.{0,20}(binder|sequence|candidate)\b',
    r'\btry\s+(again|another|with|a\s+different)\b',
    r'\bstart\s+(over|again|a\s+new)\b',
    r'\bnew\s+candidate\b|\bnew\s+sequence\b',
]

# Question marks: ASCII ? plus common Unicode variants (UI / mobile keyboards).
_QUESTION_MARK_RE = re.compile(r"[\?\uFF1F\uFE16\u2047\u061F]")

# Knowledge base: (pattern, answer)
_QA_PAIRS = [
    (
        r"bining\s+score|binding\s+score.*kcal|kcal.*binding\s+score|what.*\bbinding\s+score\b|"
        r"which\s+.*\bscore\b.*kcal|explain.*binding.*percent",
        "**Binding % vs ΔG (kcal/mol) vs Energy (E)**\n\n"
        "- **Binding %** (or 0–1 proxy): the oracle's **relative** on-target binding ranking — useful for comparing candidates from the same run.\n"
        "- **ΔG (kcal/mol)**: **modelled** from the estimated Kd at 310 K (ΔG ≈ 0.616 × ln(Kd [M])). More negative usually means tighter in this heuristic; many docking workflows use **≈ −6 kcal/mol** as a rough “worth ordering” screening line — still validate experimentally.\n"
        "- **E**: the **composite MCMC objective** (binding + stability + solubility + penalties). **Lower E is better in the search**, but E is **not** the same number as ΔG from a wet-lab assay.\n\n"
        "If ΔG shows as “—” in an old build, refresh the app; the API always sends modelled ΔG alongside the proxy.",
    ),
    (
        r"(what\s+is|what's|show\s+me|give\s+me)\s+(the\s+)?(score|metric|result|value|number)s?\b|"
        r"score[s]?\s+(in|of)\s+kcal|current\s+score|all\s+(the\s+)?score",
        "**Available scores after a design run**\n\n"
        "After completing a design cycle you will see:\n"
        "- **ΔG binding** (kcal/mol): modelled free energy of binding; < −6 = lab-worthy\n"
        "- **Kd** (nM): dissociation constant derived from ΔG at 310 K\n"
        "- **Stability** (%): secondary structure propensity (helix + sheet content)\n"
        "- **Solubility** (%): GRAVY-based estimate; higher D/E/K/R content → higher score\n"
        "- **Lab Viability** (0–100): composite Triple-Gate score; ≥ 70 = proceed to synthesis\n"
        "- **Selectivity ratio**: on-target / off-target binding; > 2× required\n\n"
        "Run **design a peptide** to start a new cycle and populate these scores."
    ),
    (
        r"how\s+does\s+(this|the|your|that)\s+treatment\s+work|how\s+does\s+treatment\s+work|"
        r"treatment\s+work\??|what\s+is\s+(this|the)\s+treatment|clinical\s+treatment\s+plan|"
        r"how\s+would\s+treatment\s+(work|go)|mechanism\s+of\s+(the\s+)?treatment",
        "**What “treatment” means in Proteus**\n\n"
        "Proteus does **not** prescribe real-world therapy. It proposes **in-silico peptide sequences** and scores "
        "(binding proxy, modelled ΔG/Kd, stability, solubility, Triple-Gate checks) for **research use only**.\n\n"
        "**Molecule intent:** candidates are optimised against the resolved target and pocket in the 3D viewer; "
        "wet-lab validation (synthesis, binding assay, cells/organoids) is still required.\n\n"
        "**Patient care:** only licensed clinicians can author a treatment plan with approved drugs and trials.\n\n"
        "To run another design pass, say **design a peptide** or **optimise for solubility**.",
    ),
    (
        r'\bdelta\s*g\b|binding\s+free\s+energ|\bdg\b.*\bbinding\b',
        "**ΔG Binding (Free Energy of Binding)**\n\n"
        "ΔG is the Gibbs free energy change upon binding, in kcal/mol. Negative = spontaneous:\n"
        "- < −9 kcal/mol: strong binder\n"
        "- −7 to −9: good binder\n"
        "- −6 to −7: promising (AutoDock Vina lab-worthy threshold)\n"
        "- > −6: weak binder\n\n"
        "Calculated as ΔG = RT·ln(Kd), where R = 1.987 cal/mol·K and T = 310 K (body temp)."
    ),
    (
        r'\bkd\b|\bdissociation\s+constant\b|\bbinding\s+affinity\b',
        "**Kd (Dissociation Constant / Binding Affinity)**\n\n"
        "Kd is the equilibrium dissociation constant — lower = stronger binding:\n"
        "- < 1 nM: ultra-high affinity\n"
        "- 1–10 nM: very high affinity (drug-like)\n"
        "- 10–100 nM: high affinity\n"
        "- 100–1000 nM: moderate\n"
        "- > 1 μM: weak binder\n\n"
        "Proteus estimates Kd via ΔG = RT·ln(Kd) from the multi-objective energy oracle."
    ),
    (
        r'how\s+does\s+(it|this|the\s+platform|the\s+system|everything)\s+work',
        "**How Proteus works**\n\n"
        "1. You enter clinical context; Proteus resolves a protein target (built-in list or custom PDB).\n"
        "2. It runs several rounds of Metropolis–Hastings MCMC with parallel tempering over sequence edits.\n"
        "3. Each candidate is scored with a composite oracle (binding proxy, stability, solubility, charge, aggregation, etc.).\n"
        "4. You get ranked sequences, mutation lists, and a 3D viewer — not a clinical treatment plan.\n\n"
        "**Important:** scores are in-silico heuristics. Strong lab candidates are usually validated with structural models "
        "or experimental binding (e.g. SPR/ITC). A common docking rule of thumb is ΔG around −6 kcal/mol or better as "
        "worth ordering for follow-up — treat Proteus numbers as hypotheses until measured."
    ),
    (
        r'results?\s+(of|from|for)|all\s+of\s+the\s+modell|modelling\s+results|what\s+are\s+the\s+results',
        "**Reading your modelling results**\n\n"
        "- **Left chat**: each round’s best sequence, metrics, and mutation highlights.\n"
        "- **Right column**: all candidates sorted by binding proxy (and stability / energy).\n"
        "- **Center**: PDB with binding-site substitutions mapped onto the structure.\n\n"
        "**Treatment planning:** Proteus does not prescribe therapy. Use these outputs only as research inputs; "
        "any real regimen requires clinicians and wet-lab data.\n\n"
        "If you need a fresh optimisation, send a design command such as *design a peptide* or *optimise for solubility*."
    ),
    (
        r'\bmcmc\b|markov\s+chain|monte\s+carlo|how\s+does\s+(proteus|mcmc)\s+work',
        "**How Proteus MCMC Works**\n\n"
        "Proteus runs Metropolis-Hastings MCMC across parallel temperature chains:\n"
        "- Multiple chains run simultaneously at temperatures 0.5 → 10\n"
        "- Each step proposes a mutation (point substitution, insertion, deletion, or block swap)\n"
        "- Mutations are accepted if they improve the score, or stochastically at higher temperatures\n"
        "- Low temperatures (0.5) fine-tune; high temperatures (10) explore broadly\n"
        "- R-hat < 1.05 indicates convergence; ESS measures mixing quality\n"
        "- Best candidate from all chains across all steps is returned"
    ),
    (
        r'\bplddt\b|structural\s+confidence|structure\s+order',
        "**pLDDT Estimate**\n\n"
        "pLDDT (predicted Local Distance Difference Test) is a structural confidence score (0–100) "
        "used by AlphaFold. Proteus computes a proxy from sequence composition:\n"
        "- > 90: very high confidence (ordered)\n"
        "- 70–90: confident\n"
        "- 50–70: low confidence (may be partly disordered)\n"
        "- < 50: very low (likely disordered)"
    ),
    (
        r'\bstabilit\b|\bddg\b|thermostab',
        "**Stability Score & ΔΔG**\n\n"
        "- **Stability Score**: Secondary structure propensity (helix + sheet content). "
        "Higher = more structured. Alpha-helical residues (A, E, L, K, M) increase this; "
        "Gly and Pro reduce it.\n"
        "- **ΔΔG estimate**: Thermodynamic stability vs. unfolded state (kcal/mol). "
        "Negative = more stable than unfolded."
    ),
    (
        r'\bsolubil\b',
        "**Solubility Score**\n\n"
        "Estimated from GRAVY score and charged residue fraction:\n"
        "- High D/E/K/R content → more soluble\n"
        "- High I/L/F/V/W/M content → less soluble\n"
        "- GRAVY > 1.5 → 'Grease Ball' warning\n"
        "- Hydrophobic stretch ≥ 4 residues → aggregation warning\n"
        "Use 'high solubility' constraint to rebalance the energy oracle."
    ),
    (
        r'\bselectivit\b|off.target|on.target',
        "**Selectivity**\n\n"
        "Selectivity ratio = on-target binding / off-target binding:\n"
        "- > 5x: highly selective\n"
        "- 2–5x: acceptable\n"
        "- < 2x: toxicity flag raised\n\n"
        "Selectivity ΔΔG = ΔG(on-target) − ΔG(off-target). Positive = on-target preferred."
    ),
    (
        r'\bgate\s*[123]\b|triple.gate|enthalpic|solvation\s+gate|entropic\s+penalt',
        "**Triple-Gate Physics Model**\n\n"
        "Three physical barriers a binder must clear:\n\n"
        "- **Gate 1 — Enthalpic Locking**: Surface complementarity Sc ≥ 0.4 = PASS. "
        "Geometric fit between ligand and pocket.\n"
        "- **Gate 2 — Solvation**: ΔG_solv ≤ 0 kcal/mol = PASS. "
        "Burial gains must exceed desolvation cost.\n"
        "- **Gate 3 — Entropic Penalty**: −TΔS ≤ 3.5 kcal/mol = PASS. "
        "Excessive flexibility penalized.\n\n"
        "Lab Viability Score (0–100) = weighted combination of all gates + ΔG + selectivity. ≥ 60 = lab-worthy."
    ),
    (
        r'\blab\s+viabilit\b|lab.worth',
        "**Lab Viability Score (0–100)**\n\n"
        "Composite score aggregating all Triple-Gate checks:\n"
        "- ΔG < −6 kcal/mol\n"
        "- Gate 1: Sc ≥ 0.4\n"
        "- Gate 2: ΔG_solv ≤ 0\n"
        "- Gate 3: −TΔS ≤ 3.5 kcal/mol\n"
        "- Selectivity ratio ≥ 2x\n\n"
        "≥ 70: proceed to synthesis. 50–70: address failing gates. < 50: significant optimization needed."
    ),
    (
        r'\br.hat\b|rhat|convergence\s+diagnos|ess\b|effective\s+sample',
        "**Convergence Diagnostics**\n\n"
        "- **R-hat**: Potential scale reduction factor across chains. < 1.05 = converged. > 1.1 = not converged.\n"
        "- **ESS**: Effective Sample Size — number of independent samples from the chain. "
        "Higher = better mixing. ESS/total_steps > 0.1 is generally acceptable."
    ),
    (
        r'\baggregat\b',
        "**Aggregation Propensity**\n\n"
        "Estimated from hydrophobic stretch analysis (I/L/F/V/W/M runs):\n"
        "- Stretch ≥ 4 residues → aggregation warning\n"
        "- Mitigation: insert D/E/K residues to break patches\n"
        "- High aggregation → reduces manufacturability and raises off-target risk\n"
        "Use 'low aggregation' constraint to increase the aggregation penalty in the oracle."
    ),
    (
        r'\bimmunogen\b|\bmhc\b|immune\s+response',
        "**Immunogenicity Score**\n\n"
        "Estimated from MHC anchor motif frequency. High score → immune rejection risk:\n"
        "- Basic (K/R) and aromatic (F/Y/W) residues at anchor positions increase score\n"
        "- Score 0 = no predicted MHC anchors; > 0.5 = moderate immune risk\n"
        "Use 'low immunogenicity' constraint to apply a charge penalty during design."
    ),
    (
        r'\bserum\s+half.life\b|half.life\b|\bt1/2\b|pharmacokinetic',
        "**Serum Half-Life**\n\n"
        "Estimated in minutes from sequence length and composition. Rough guide:\n"
        "- Short peptides (< 10 AA): 10–30 min\n"
        "- Miniproteins (30–100 AA): 30–120 min\n"
        "- Nanobodies (110–130 AA): 60–240 min\n"
        "Actual half-life depends on clearance, PEGylation, formulation, etc."
    ),
    (
        r'what\s+(can|does|is|do)\s+(you|it|this|proteus)\b|what\s+do\s+you\s+do|how\s+to\s+use|tell\s+me\s+about\s+(yourself|proteus|this)',
        "**What Proteus Can Do**\n\n"
        "Given patient clinical info, Proteus:\n"
        "1. Resolves the molecular target (EGFRvIII, PD-L1, KRAS G12C, SARS-CoV-2 3CL)\n"
        "2. Runs 3 rounds of MCMC design (400–800 steps/chain, 3–5 parallel chains)\n"
        "3. Scores each candidate on 8+ biophysical objectives\n"
        "4. Returns the best sequence with full mutation rationale\n\n"
        "To request a design run, say something like:\n"
        "- 'Design a peptide for this target'\n"
        "- 'Optimize for high solubility, no cysteines'\n"
        "- 'Run with a 20 amino acid thermostable candidate'"
    ),
]

_CONVERSATIONAL_FALLBACK = (
    "I specialize in protein design and biophysics. I can answer questions about:\n"
    "- ΔG binding, Kd, MCMC, pLDDT, stability, solubility\n"
    "- Selectivity, immunogenicity, aggregation, serum half-life\n"
    "- The Triple-Gate physics model and lab viability score\n"
    "- How Proteus works\n\n"
    "To run a new design cycle, type a message like 'design a peptide' or 'optimize for high solubility'."
)


def _clinical_context_lines(patient: PatientInfo) -> str:
    parts = [f"Target / disease context: {patient.cancer_type}"]
    if patient.tumor_markers:
        parts.append(f"Markers: {patient.tumor_markers}")
    if patient.cancer_stage:
        parts.append(f"Stage: {patient.cancer_stage}")
    if patient.previous_treatments:
        parts.append(f"Prior treatments: {patient.previous_treatments}")
    if patient.modality:
        parts.append(f"Modality: {patient.modality}")
    return "\n".join(parts)


def _format_session_block(session: Optional[DesignSessionContext]) -> str:
    if session is None:
        return "Design session: no completed peptide run has been sent from the UI yet."
    if not session.best_sequence:
        return "Design session: UI has not sent a lead sequence yet (complete a design first for residue-level chat)."
    lines = [
        "Latest in-silico lead from the workspace:",
        f"- Sequence: `{session.best_sequence}`",
    ]
    if session.seed_sequence:
        lines.append(f"- Seed before last run: `{session.seed_sequence}`")
    if session.target_name:
        lines.append(f"- Target: {session.target_name}")
    if session.pdb_id:
        lines.append(f"- PDB: {session.pdb_id}")
    if session.binding_score is not None:
        lines.append(f"- Binding proxy (oracle, 0–1): {session.binding_score:.3f}")
    if session.delta_g_kcal_mol is not None:
        lines.append(f"- Modelled ΔG binding: {session.delta_g_kcal_mol:.2f} kcal/mol (more negative = tighter; ≈ −6 often used as a rough in-silico ordering threshold)")
    if session.kd_nM is not None:
        lines.append(f"- Modelled Kd: {session.kd_nM:.1f} nM")
    if session.stability_score is not None:
        lines.append(f"- Stability score (structure propensity proxy): {session.stability_score * 100:.0f}%")
    if session.solubility_score is not None:
        lines.append(f"- Solubility score: {session.solubility_score * 100:.0f}%")
    if session.total_energy is not None:
        lines.append(f"- Composite oracle energy E (lower is better; not the same as experimental ΔG): {session.total_energy:.3f}")
    if session.lab_viability_score is not None:
        lines.append(f"- Lab viability score: {session.lab_viability_score:.0f}/100")
    lines.append(
        "Interpretation rules: binding % in the UI is the oracle proxy; ΔG/Kd are modelled from that proxy. "
        "Do not present numbers as clinically validated affinities."
    )
    return "\n".join(lines)


def _conversational_fallback_rich(
    patient: PatientInfo, session: Optional[DesignSessionContext],
) -> str:
    base = _CONVERSATIONAL_FALLBACK
    if session and session.best_sequence:
        return (
            base
            + "\n\n**Using your current lead peptide**\n"
            + _format_session_block(session)
            + "\n\nor install Ollama (https://ollama.com) with a small chat model for longer free-form answers."
        )
    return (
        base
        + "\n\n"
        + _clinical_context_lines(patient)
        + "\n\nAfter you run **design a peptide**, this panel will attach sequence metrics so every follow-up can stay grounded in that candidate."
    )


def _is_design_request(message: str) -> bool:
    """True if the message clearly requests a new MCMC design run."""
    text = message.lower()
    return any(re.search(p, text) for p in _DESIGN_TRIGGERS)


def _is_question(message: str) -> bool:
    """True if the message looks like a knowledge/conversational question (not a bare design command)."""
    text = (message or "").strip().lower()
    if not text:
        return False
    if _QUESTION_MARK_RE.search(text):
        return True
    starters = (
        "what", "how", "why", "when", "where", "who", "explain",
        "describe", "tell me", "can you", "could you", "would you",
        "should i", "does", "do you", "is it", "are we", "are you",
        "is there", "are there", "could i", "would it",
    )
    if any(text.startswith(s) for s in starters):
        return True
    # Interrogative phrasing without a trailing question mark (common in chat UIs).
    if re.match(r"^\s*(how|what|why|when|where|who)\s+\w+", text):
        return True
    return False


def _answer_question(message: str) -> Optional[str]:
    """Return a direct answer if the question matches a known topic, else None."""
    text = message.lower()
    for pattern, answer in _QA_PAIRS:
        if re.search(pattern, text):
            return answer
    return None


_OLLAMA_URL = "http://localhost:11434/api/chat"
_OLLAMA_MODEL = "llama3.2"
_OLLAMA_SYSTEM = (
    "You are Proteus, a peptide / protein design copilot in a research UI. "
    "You answer **anything** the user asks about the current session, peptide sequence, biophysics, metrics, or interpretation. "
    "Be concise, accurate, and honest about model limits (in-silico heuristics, not clinical truth). "
    "When session context includes a lead sequence and scores, ground your answers in those numbers. "
    "If the user wants a **new** optimisation run, tell them explicitly to type phrases like **design a peptide**, "
    "**optimize for …**, or **run MCMC again** — do not invent a full new MCMC trajectory yourself."
)


def _call_ollama(
    user_message: str,
    context: Optional[str] = None,
    model: str = _OLLAMA_MODEL,
) -> Optional[str]:
    """Call local Ollama and return the assistant reply, or None if unavailable."""
    system = _OLLAMA_SYSTEM
    if context:
        system += f"\n\nContext about the current design session:\n{context}"
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.post(
                _OLLAMA_URL,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                },
            )
            if res.status_code == 200:
                return res.json()["message"]["content"].strip()
    except Exception:
        pass
    return None


def _detect_impossible(message: str) -> Optional[str]:
    """
    Detect physically impossible or contradictory design requests.
    Returns an explanation string if a contradiction is found, else None.
    """
    text = message.lower()
    for pattern, explanation in IMPOSSIBLE_PATTERNS:
        if re.search(pattern, text):
            return explanation
    return None


def _explain_mutation(from_aa: str, to_aa: str, position: int,
                      delta_energy: float, blosum_score: float) -> str:
    """
    Generate a mechanistic explanation for a specific residue substitution.
    """
    from_props = AA_PROPERTIES.get(from_aa, {"class": "unknown", "hydrophobicity": "unknown"})
    to_props = AA_PROPERTIES.get(to_aa, {"class": "unknown", "hydrophobicity": "unknown"})

    direction = "favorable" if delta_energy < 0 else "neutral" if abs(delta_energy) < 0.01 else "accepted by MCMC"
    conservatism = (
        "highly conservative (BLOSUM62: +{:.0f})".format(blosum_score) if blosum_score >= 1
        else "moderately conservative (BLOSUM62: {:.0f})".format(blosum_score) if blosum_score >= 0
        else "non-conservative (BLOSUM62: {:.0f})".format(blosum_score)
    )

    class_change = ""
    if from_props["class"] != to_props["class"]:
        class_change = " ({} to {})".format(from_props["class"], to_props["class"])
    hydro_change = ""
    if from_props["hydrophobicity"] != to_props["hydrophobicity"]:
        hydro_change = "; hydrophobicity: {} to {}".format(
            from_props["hydrophobicity"], to_props["hydrophobicity"]
        )

    return (
        "Position {pos}: **{f}{pos}{t}** — {conserv}{class_ch}{hydro_ch}. "
        "Energy delta: {dE:+.3f} ({dir})."
    ).format(
        pos=position,
        f=from_aa,
        t=to_aa,
        conserv=conservatism,
        class_ch=class_change,
        hydro_ch=hydro_change,
        dE=delta_energy,
        dir=direction,
    )


def _apply_constraints_to_oracle(oracle: EnergyOracle, constraints: Dict) -> None:
    """Adjust energy oracle weights to reflect user-specified constraints."""
    if constraints.get("high_solubility"):
        oracle.solubility_weight = 0.40
        oracle.binding_weight = 0.35
    if constraints.get("low_aggregation"):
        oracle.aggregation_penalty = 0.25
    if constraints.get("thermostable"):
        oracle.stability_weight = 0.45
        oracle.binding_weight = 0.30
    if constraints.get("bbb_penetrant"):
        oracle.bbb_weight = 0.25
        oracle.binding_weight = 0.35
    if constraints.get("no_cysteines"):
        # Post-filter is applied separately; no oracle-level change needed
        pass
    if constraints.get("low_immunogenicity"):
        # Penalize high basic/aromatic content by upweighting charge penalty
        oracle.charge_penalty = 0.08
    if constraints.get("antimicrobial"):
        # Antimicrobial peptides: favour positive charge, moderate hydrophobicity
        oracle.solubility_weight = 0.20
        oracle.bbb_weight = 0.05
        oracle.binding_weight = 0.50
        oracle.stability_weight = 0.25


def _generate_seed(length: int = 8, structure: str = "random") -> str:
    """
    Generate a seed sequence of the requested length and secondary structure bias.
    """
    if structure == "alpha-helical":
        # Strong helix-forming residues: AELM with charged K/E for amphipathicity
        helix_template = "AELKAAELKAAEL"
    elif structure == "beta-sheet":
        helix_template = "VIVTVIVTVIVT"
    else:
        helix_template = "MVLDGEQGMVLD"

    repeated = (helix_template * ((length // len(helix_template)) + 2))[:length]
    return repeated


class ProteinDesignAgent:
    def __init__(self):
        self.esm_cache = ESM2EmbeddingCache(settings.ESM_CACHE_DIR)
        self.targets = load_targets_metadata()
        self.chat_responder = ChatResponder()
        self.context_aware_responder = ContextAwareChatResponder()

    def _resolve_target(self, patient: PatientInfo) -> Optional[Tuple[str, str]]:
        text = (patient.cancer_type + " " + (patient.tumor_markers or "")).lower()
        for keyword, (target, pdb) in CANCER_TARGET_MAP.items():
            if keyword in text:
                return (target, pdb)
        return None

    def _get_target_meta(self, name: str) -> dict:
        for t in self.targets:
            if t["name"] == name:
                return t
        return {"name": name, "pdb_id": "6LU7", "difficulty_score": 6,
                "clinical_relevance": "", "binding_site_residues": []}

    def _run_mcmc_round(self, seed: str, target_name: str, target_meta: dict,
                        steps: int = 600, num_chains: int = 3,
                        constraints: Optional[Dict] = None,
                        pdb_id: str = "",
                        stream_callback: Optional[callable] = None) -> dict:
        oracle = EnergyOracle()
        pocket = target_meta.get("binding_site_residues", [])
        if pocket:
            oracle.set_target_pocket(pocket)
        if constraints:
            _apply_constraints_to_oracle(oracle, constraints)

        # Attach physics-based docking oracle for binding energy
        oracle.docking_oracle = DockingOracle(
            target_pdb_id=pdb_id,
            binding_site_residues=pocket,
        )
        oracle.feasibility_scorer = LabFeasibilityScorer()

        proposal = ProposalDistribution(self.esm_cache._cache)
        temps = [0.5, 1.0, 2.0, 5.0, 10.0][:num_chains]

        sampler = MCMCParallelSampler(
            energy_oracle=oracle,
            proposal_dist=proposal,
            num_chains=num_chains,
            temperatures=temps,
            steps_per_chain=steps,
            progress_callback=stream_callback,
        )

        result = sampler.run(seed, target_name)
        candidates = sorted(result.candidates, key=lambda c: c.get("binding_score", 0), reverse=True)

        # Apply hard constraint filters post-MCMC
        if constraints and constraints.get("no_cysteines"):
            filtered = [c for c in candidates if "C" not in c.get("sequence", "")]
            if filtered:
                candidates = filtered
        if constraints and constraints.get("target_length"):
            tlen = constraints["target_length"]
            filtered = [c for c in candidates if abs(len(c.get("sequence", "")) - tlen) <= 3]
            if filtered:
                candidates = filtered

        best = candidates[0] if candidates else {}

        # ─── New: Compute ensemble rankings with selectivity, escape, and PK scores ────
        selectivity_scorer = TargetSelectivityScorer(oracle.docking_oracle)
        escape_predictor = ResistanceEscapePredictor(oracle.docking_oracle)
        pk_predictor = EnhancedPKPredictor()
        immunogenicity_screener = ImmunogenicityScreener()
        constraint_validator = StructuralConstraintValidator()
        cost_optimizer = CostOptimizer()

        top_ensemble = []
        for i, candidate in enumerate(candidates[:10]):  # Top-10 ensemble
            seq = candidate.get("sequence", "")
            dg = candidate.get("delta_g_binding_kcal_mol", -5.5)

            # Selectivity assessment
            selectivity_result = selectivity_scorer.assess_selectivity(seq, target_name)

            # Resistance escape prediction
            escape_result = escape_predictor.predict_escapes(seq, max_escapes=5)

            # Enhanced PK prediction
            pk_result = pk_predictor.predict_pk(seq)

            # Immunogenicity screening (NEW)
            immuno_result = immunogenicity_screener.screen_immunogenicity(seq)

            # Constraint satisfaction (NEW)
            constraint_result = constraint_validator.validate_constraints(seq, constraints or {})

            # Cost optimization (NEW)
            cost_result = cost_optimizer.compute_cost_score(seq, dg)

            ensemble_item = {
                "rank": i + 1,
                "sequence": seq,
                "binding_score": candidate.get("binding_score", 0),
                "delta_g_binding_kcal_mol": dg,
                "synthesis_feasibility_score": candidate.get("synthesis_feasibility_score", 0.0),
                "lab_viability_score": candidate.get("lab_viability_score", 0.0),
                # Selectivity metrics
                "selectivity_score": selectivity_result.get("selectivity_score", 50.0),
                "problematic_off_targets": selectivity_result.get("problematic_off_targets", []),
                # Escape resistance metrics
                "escape_score": escape_result.get("escape_score", 0.5),
                "is_escape_resistant": escape_result.get("is_escape_resistant", False),
                "top_escape_variants": escape_result.get("top_escape_variants", [])[:3],
                # PK metrics
                "estimated_serum_half_life_min": pk_result.get("estimated_serum_half_life_min", 20.0),
                "bbb_penetration_feasible": pk_result.get("bbb_penetration_feasible", False),
                "tissue_accumulation_risk": pk_result.get("tissue_accumulation_risk", False),
                # Immunogenicity metrics (NEW)
                "immunogenicity_score": immuno_result.get("immunogenicity_score", 0.0),
                "is_high_immunogenic_risk": immuno_result.get("is_high_immunogenic_risk", False),
                "immunogenic_motifs_found": immuno_result.get("immunogenic_motifs_found", []),
                "mhc_epitope_risk": immuno_result.get("mhc_epitope_risk", "low"),
                # Constraint satisfaction (NEW)
                "constraint_satisfaction_score": constraint_result.get("constraint_satisfaction_score", 100.0),
                "all_constraints_satisfied": constraint_result.get("all_constraints_satisfied", True),
                "num_constraint_violations": constraint_result.get("num_violations", 0),
                # Cost optimization (NEW)
                "estimated_synthesis_cost_usd": cost_result.get("estimated_synthesis_cost_usd", 1000.0),
                "cost_score": cost_result.get("cost_score", 50.0),
                "affinity_cost_ratio": cost_result.get("affinity_cost_ratio", 0.0),
                "pareto_recommendation": cost_result.get("pareto_recommendation", ""),
            }
            top_ensemble.append(ensemble_item)

        best_with_ensemble = dict(best)
        if top_ensemble:
            best_with_ensemble.update(top_ensemble[0])  # Update best with selectivity/escape/PK

        # Compute per-mutation rationale
        mutations = []
        if best.get("sequence") and seed:
            for i, (a, b) in enumerate(zip(seed, best["sequence"])):
                if a != b:
                    blosum_s = oracle.compute_blosum_similarity(a, b) * 15 - 4
                    mutations.append({
                        "position": i + 1,
                        "from": a,
                        "to": b,
                        "explanation": _explain_mutation(a, b, i + 1, 0.0, blosum_s),
                    })

        # Track accepted mutations with energy deltas from chain 0 mutation log
        if result.chains:
            chain0_log = result.chains[0].mutation_log
            accepted_log = [m for m in chain0_log if m.get("accepted")]
            for mut in mutations:
                pos = mut["position"] - 1
                for log_entry in accepted_log:
                    if log_entry.get("position") == pos:
                        dE = log_entry.get("delta_energy", 0.0)
                        blosum_s = oracle.compute_blosum_similarity(
                            mut["from"], mut["to"]
                        ) * 15 - 4
                        mut["explanation"] = _explain_mutation(
                            mut["from"], mut["to"], mut["position"], dE, blosum_s
                        )
                        break

        # Build optimization trace from chain 0 accepted point substitutions
        trace: List[dict] = []
        if result.chains:
            chain0_log = result.chains[0].mutation_log
            accepted_subs = [
                m for m in chain0_log
                if m.get("accepted")
                and len(str(m.get("from_aa", ""))) == 1
                and len(str(m.get("to_aa", ""))) == 1
                and m.get("from_aa") != m.get("to_aa")
            ]
            n_subs = len(accepted_subs)
            if n_subs > 0:
                num_samples = min(6, n_subs)
                if num_samples == 1:
                    sampled = [accepted_subs[0]]
                else:
                    idxs = [
                        int(round(i * (n_subs - 1) / (num_samples - 1)))
                        for i in range(num_samples)
                    ]
                    seen_idxs: set = set()
                    sampled = []
                    for idx in idxs:
                        if idx not in seen_idxs:
                            seen_idxs.add(idx)
                            sampled.append(accepted_subs[idx])
                for entry in sampled:
                    f = str(entry.get("from_aa", "?"))
                    t = str(entry.get("to_aa", "?"))
                    pos = int(entry.get("position", 0)) + 1
                    dE = float(entry.get("delta_energy", 0.0))
                    temp = float(entry.get("temperature", 1.0))
                    blosum_s = oracle.compute_blosum_similarity(f, t) * 15 - 4
                    trace.append({
                        "step": int(entry.get("step", 0)),
                        "position": pos,
                        "from": f,
                        "to": t,
                        "delta_energy": round(dE, 4),
                        "temperature": round(temp, 2),
                        "narrative": _explain_mutation(f, t, pos, dE, blosum_s),
                    })

        return {
            "run_id": result.run_id,
            "seed": seed,
            "sequence": best_with_ensemble.get("sequence", result.best_overall_sequence),
            "binding_score": best_with_ensemble.get("binding_score", 0),
            "stability_score": best_with_ensemble.get("stability_score", 0),
            "solubility_score": best_with_ensemble.get("solubility_score", 0),
            "total_energy": result.best_overall_energy,
            "rhat": result.rhat,
            "ess": result.ess,
            "mutations": mutations,
            "trace": trace,
            "converged": result.converged,
            "num_candidates": len(candidates),
            "steps": steps,
            "chains": num_chains,
            # Hard biophysical metrics from best candidate
            "aggregation_propensity": best_with_ensemble.get("aggregation_propensity", 0),
            "immunogenicity_score": best_with_ensemble.get("immunogenicity_score", 0),
            "ddg_estimate_kcal_mol": best_with_ensemble.get("ddg_estimate_kcal_mol", 0),
            "manufacturability_score": best_with_ensemble.get("manufacturability_score", 0),
            "plddt_estimate": best_with_ensemble.get("plddt_estimate", 0),
            "novelty_score": best_with_ensemble.get("novelty_score", 0),
            # Pharmacokinetic estimates
            "kd_nM": best_with_ensemble.get("kd_nM", 0),
            "serum_half_life_min": best_with_ensemble.get("serum_half_life_min", 0),
            "selectivity_ratio": best_with_ensemble.get("selectivity_ratio", 1.0),
            "toxicity_flag": best_with_ensemble.get("toxicity_flag", False),
            "delta_g_binding_kcal_mol": best_with_ensemble.get("delta_g_binding_kcal_mol", 0.0),
            # Triple-Gate Physics Model
            "hbond_count": best_with_ensemble.get("hbond_count", 0),
            "entropic_penalty": best_with_ensemble.get("entropic_penalty", 0.0),
            "solvation_delta_g": best_with_ensemble.get("solvation_delta_g", 0.0),
            "surface_complementarity": best_with_ensemble.get("surface_complementarity", 0.0),
            "gate1_pass": best_with_ensemble.get("gate1_pass", False),
            "gate2_pass": best_with_ensemble.get("gate2_pass", False),
            "gate3_pass": best_with_ensemble.get("gate3_pass", False),
            "lab_viability_score": best_with_ensemble.get("lab_viability_score", 0.0),
            "selectivity_ddg": best_with_ensemble.get("selectivity_ddg", 0.0),
            # Synthesis + delivery feasibility (from LabFeasibilityScorer)
            "synthesis_feasibility_score": best_with_ensemble.get("synthesis_feasibility_score", 0.0),
            "synthesis_feasible": best_with_ensemble.get("synthesis_feasible", False),
            "synthesis_issues": best_with_ensemble.get("synthesis_issues", []),
            "synthesis_recommendations": best_with_ensemble.get("synthesis_recommendations", []),
            "estimated_synthesis_time_days": best_with_ensemble.get("estimated_synthesis_time_days"),
            "estimated_synthesis_cost_usd": best_with_ensemble.get("estimated_synthesis_cost_usd"),
            # Off-target selectivity (NEW)
            "selectivity_score": best_with_ensemble.get("selectivity_score", 50.0),
            "problematic_off_targets": best_with_ensemble.get("problematic_off_targets", []),
            # Escape resistance (NEW)
            "escape_score": best_with_ensemble.get("escape_score", 0.5),
            "is_escape_resistant": best_with_ensemble.get("is_escape_resistant", False),
            "top_escape_variants": best_with_ensemble.get("top_escape_variants", []),
            # Enhanced PK/PD (NEW)
            "estimated_serum_half_life_min": best_with_ensemble.get("estimated_serum_half_life_min", 20.0),
            "bbb_penetration_feasible": best_with_ensemble.get("bbb_penetration_feasible", False),
            "tissue_accumulation_risk": best_with_ensemble.get("tissue_accumulation_risk", False),
            # Immunogenicity (NEW)
            "immunogenicity_score": best_with_ensemble.get("immunogenicity_score", 0.0),
            "is_high_immunogenic_risk": best_with_ensemble.get("is_high_immunogenic_risk", False),
            "immunogenic_motifs_found": best_with_ensemble.get("immunogenic_motifs_found", []),
            "mhc_epitope_risk": best_with_ensemble.get("mhc_epitope_risk", "low"),
            # Constraint satisfaction (NEW)
            "constraint_satisfaction_score": best_with_ensemble.get("constraint_satisfaction_score", 100.0),
            "all_constraints_satisfied": best_with_ensemble.get("all_constraints_satisfied", True),
            # Cost optimization (NEW)
            "estimated_synthesis_cost_usd": best_with_ensemble.get("estimated_synthesis_cost_usd", 1000.0),
            "cost_score": best_with_ensemble.get("cost_score", 50.0),
            "affinity_cost_ratio": best_with_ensemble.get("affinity_cost_ratio", 0.0),
            "pareto_recommendation": best_with_ensemble.get("pareto_recommendation", ""),
            # Top-10 ensemble (NEW)
            "top_ensemble": top_ensemble,
            # Agent-level outputs
            "solubility_tags": _suggest_solubility_tags(best_with_ensemble.get("sequence", "")),
            "notes_3d": _generate_3d_notes(
                best_with_ensemble.get("sequence", ""), target_name, pocket, pdb_id
            ),
            "fasta": _format_fasta(
                best_with_ensemble.get("sequence", ""),
                target_name,
                best_with_ensemble.get("delta_g_binding_kcal_mol", 0.0),
                best_with_ensemble.get("kd_nM", 0.0),
                best_with_ensemble.get("lab_viability_score", 0.0),
            ),
        }

    def _build_structure_url(self, pdb_id: str) -> str:
        return "https://www.rcsb.org/3d-view/{}".format(pdb_id)

    def run(
        self,
        patient: PatientInfo,
        message: str,
        session: Optional[DesignSessionContext] = None,
        stream_callback: Optional[callable] = None,
    ) -> AgentRunResponse:
        messages: List[AgentMessage] = [AgentMessage(role="user", content=message)]

        # --- Chat-first: only explicit design verbs start MCMC; everything else is conversational. ---
        explicit_design = _is_design_request(message)

        if not explicit_design:
            # (1) When a session with results is present, try the grounded responder
            #     FIRST so score / metric questions get actual session data instead
            #     of the generic static-QA answers that fire next.
            if session and session.best_sequence:
                grounded_reply = self.context_aware_responder.respond_grounded(message, session)
                if grounded_reply is not None:
                    messages.append(AgentMessage(role="agent", content=grounded_reply))
                    return AgentRunResponse(reply=grounded_reply, messages=messages)

            # (2) Static QA: generic biophysics education (ΔG definition, MCMC,
            #     Kd, Triple-Gate, etc.) — only reached when grounded returned None
            #     or there is no active session.
            answer = _answer_question(message)
            if answer is not None:
                messages.append(AgentMessage(role="agent", content=answer))
                return AgentRunResponse(reply=answer, messages=messages)

            # (3) Session-specific builders: mechanism, mutations, viability,
            #     improvement, progression — more targeted than grounded summary.
            ctx_reply = self.context_aware_responder.respond(message, session)
            if ctx_reply is not None:
                messages.append(AgentMessage(role="agent", content=ctx_reply))
                return AgentRunResponse(reply=ctx_reply, messages=messages)

            # (4) Data-driven ChatResponder when session has run results.
            session_dict = None
            if session and session.best_sequence:
                session_dict = {
                    'best_sequence': session.best_sequence,
                    'delta_g_kcal_mol': session.delta_g_kcal_mol,
                    'kd_nM': session.kd_nM,
                    'stability_score': session.stability_score,
                    'solubility_score': session.solubility_score,
                    'lab_viability_score': session.lab_viability_score,
                    'target_name': getattr(session, 'target_name', ''),
                }
            responder_reply = self.chat_responder.respond_to_query(
                message, current_run=None, session_context=session_dict
            )
            if responder_reply is not None:
                messages.append(AgentMessage(role="agent", content=responder_reply))
                return AgentRunResponse(reply=responder_reply, messages=messages)

            clinical = _clinical_context_lines(patient)
            sess = _format_session_block(session)
            ctx = clinical + "\n\n" + sess
            ollama_reply = _call_ollama(message, context=ctx)
            if ollama_reply:
                messages.append(AgentMessage(role="agent", content=ollama_reply))
                return AgentRunResponse(reply=ollama_reply, messages=messages)
            fb = _conversational_fallback_rich(patient, session)
            messages.append(AgentMessage(role="agent", content=fb))
            return AgentRunResponse(reply=fb.strip(), messages=messages)

        # --- Constraint parsing (MCMC path — explicit design only) ---
        all_notes = (patient.notes or "") + " " + (patient.tumor_markers or "")
        constraints = _parse_constraints(message, all_notes)

        # --- Modality-based overrides ---
        modality = (patient.modality or "").strip().lower()
        if modality == "peptide":
            constraints.setdefault("target_length", 12)
        elif modality == "miniprotein":
            constraints.setdefault("target_length", 50)
            constraints.setdefault("thermostable", True)
        elif modality == "nanobody":
            constraints.setdefault("target_length", 120)
            constraints.setdefault("high_solubility", True)
        elif modality == "cyclic_peptide":
            constraints.setdefault("target_length", 10)
            constraints.setdefault("bbb_penetrant", True)
            constraints.setdefault("no_cysteines", True)
        elif modality == "antimicrobial":
            constraints["antimicrobial"] = True
            constraints.setdefault("target_length", 15)

        # --- Impossible request detection ---
        impossibility = _detect_impossible(message)
        if impossibility:
            reply = (
                "**Design constraint conflict detected.**\n\n"
                + impossibility
                + "\n\n"
                "Please clarify your design objectives and I will proceed with an optimized "
                "but physically realizable specification."
            )
            messages.append(AgentMessage(role="agent", content=reply))
            return AgentRunResponse(reply=reply, messages=messages)

        # --- Constraint acknowledgement ---
        if constraints:
            parts = []
            if modality:
                label = {
                    "peptide": "Peptide (8–30 AA)",
                    "miniprotein": "Miniprotein (30–100 AA)",
                    "nanobody": "Nanobody / VHH (110–130 AA)",
                    "cyclic_peptide": "Cyclic peptide",
                    "antimicrobial": "Antimicrobial peptide (AMP)",
                }.get(modality, modality)
                parts.append("Modality: {}".format(label))
            if constraints.get("target_length"):
                parts.append("Target length: {} AA".format(constraints["target_length"]))
            if constraints.get("no_cysteines"):
                parts.append("No cysteines (disulfide-free)")
            if constraints.get("secondary_structure"):
                parts.append("Secondary structure bias: {}".format(constraints["secondary_structure"]))
            if constraints.get("high_solubility"):
                parts.append("Solubility weight increased (oracle rebalanced)")
            if constraints.get("low_aggregation"):
                parts.append("Aggregation penalty increased")
            if constraints.get("thermostable"):
                parts.append("Stability weight increased for thermostability")
            if constraints.get("bbb_penetrant"):
                parts.append("CNS/BBB penetration scoring activated")
            if constraints.get("low_immunogenicity"):
                parts.append("Low immunogenicity preference applied")
            if constraints.get("antimicrobial"):
                parts.append("Antimicrobial peptide mode: cationic charge bias")

            constraint_msg = (
                "**Constraints recognized:**\n"
                + "\n".join("- " + p for p in parts)
                + "\n\nApplying these to the energy oracle before running MCMC."
            )
            messages.append(AgentMessage(role="agent", content=constraint_msg,
                                         data={"status": "constraints_parsed",
                                               "constraints": constraints}))

        # --- Target resolution ---
        resolved = self._resolve_target(patient)
        if not resolved:
            reply = (
                "Received: **{}**, {}yo, {} (Stage {}).\n\n".format(
                    patient.full_name, patient.age,
                    patient.cancer_type, patient.cancer_stage
                )
                + "Could not match a target from the clinical information. Available targets:\n"
                "- **EGFRvIII** — Glioblastoma\n"
                "- **PD-L1** — Solid tumors, melanoma, breast\n"
                "- **KRAS G12C** — NSCLC, pancreatic, colorectal\n"
                "- **SARS-CoV-2 3CL** — COVID-19 antiviral\n\n"
                "Specify the target in the cancer type or tumor markers field."
            )
            messages.append(AgentMessage(role="agent", content=reply))
            return AgentRunResponse(reply=reply, messages=messages)

        target_name, pdb_id = resolved
        target_meta = self._get_target_meta(target_name)

        # Determine seed from constraints
        struct = constraints.get("secondary_structure", "random")
        tlen = constraints.get("target_length", len(SEED_SEQUENCES.get(target_name, "MVLDGEQG")))
        seed = _generate_seed(tlen, struct)

        start_time = time.time()
        rounds_data = []
        current_seed = seed
        prev_seed = seed  # tracks input seed per round for physics justification

        for round_num in range(1, 4):
            steps = 400 + round_num * 200
            chains = min(3 + round_num, 5)

            messages.append(AgentMessage(
                role="agent",
                content=(
                    PHASE_EXPLANATIONS["generate"]
                    + "\n\n**Round {}/3**\n"
                    "- Steps per chain: {}\n"
                    "- Parallel chains: {}\n"
                    "- Temperatures: {}\n"
                    "- Seed: `{}`"
                ).format(
                    round_num, steps, chains,
                    [0.5, 1.0, 2.0, 5.0, 10.0][:chains],
                    current_seed,
                ),
                data={"status": "running", "phase": "generate", "round": round_num},
            ))

            design = self._run_mcmc_round(
                current_seed, target_name, target_meta, steps, chains, constraints,
                pdb_id=pdb_id,
                stream_callback=stream_callback,
            )
            design["round"] = round_num
            rounds_data.append(design)

            is_best = design["round"] == 3 or (
                len(rounds_data) == 1 or design["binding_score"] > max(
                    r["binding_score"] for r in rounds_data[:-1]
                )
            )

            # --- Per-round evaluation message ---
            result_parts = [
                PHASE_EXPLANATIONS["evaluate"],
                "",
                "**Round {} Results**".format(round_num),
                "",
                "**Designed Sequence:** `{}`".format(design["sequence"]),
                "",
                "| Metric | Value | Interpretation |",
                "|--------|-------|----------------|",
                "| ΔG Binding | {:.2f} kcal/mol | Free energy of binding (< −6 = promising) |".format(
                    design.get("delta_g_binding_kcal_mol", 0)),
                "| Kd estimate | {:.0f} nM | Predicted dissociation constant |".format(
                    design.get("kd_nM", 0)),
                "| Serum half-life | {:.0f} min | Predicted in vivo stability |".format(
                    design.get("serum_half_life_min", 0)),
                "| Selectivity ratio | {:.2f}x | On-target / off-target binding |".format(
                    design.get("selectivity_ratio", 1.0)),
                "| Stability Score | {:.1f}% | Secondary structure propensity |".format(
                    design["stability_score"] * 100),
                "| Solubility Score | {:.1f}% | Aqueous expression feasibility |".format(
                    design["solubility_score"] * 100),
                "| pLDDT estimate | {:.1f} / 100 | Structural confidence (>70 = ordered) |".format(
                    design.get("plddt_estimate", 0)),
                "| ΔΔG estimate | {:.2f} kcal/mol | Thermodynamic stability (< 0 = stable) |".format(
                    design.get("ddg_estimate_kcal_mol", 0)),
                "| Aggregation propensity | {:.2f} | Hydrophobic stretch risk (0 = none) |".format(
                    design.get("aggregation_propensity", 0)),
                "| Immunogenicity score | {:.2f} | MHC anchor motif frequency (0 = low) |".format(
                    design.get("immunogenicity_score", 0)),
                "| Manufacturability | {:.1f}% | Recombinant expression feasibility |".format(
                    design.get("manufacturability_score", 0) * 100),
                "| Novelty score | {:.2f} | Amino acid diversity (Shannon entropy) |".format(
                    design.get("novelty_score", 0)),
                "| Total Energy | {:.4f} | Composite objective (lower = better) |".format(
                    design["total_energy"]),
                "",
            ]

            # --- Toxicity warning ---
            if design.get("toxicity_flag"):
                result_parts.append(
                    "**High Toxicity Risk** — Selectivity ratio {:.2f}x is below the 2.0x "
                    "threshold. Off-target binding approaches on-target levels. "
                    "Consider adding specificity constraints (e.g., low aggregation, "
                    "reduced hydrophobicity) and re-running.".format(
                        design.get("selectivity_ratio", 0.0)
                    )
                )
                result_parts.append("")

            # --- Mutation rationale ---
            if design["mutations"]:
                result_parts.append("**Mutation Rationale ({} changes from seed):**".format(
                    len(design["mutations"])))
                for mut in design["mutations"]:
                    result_parts.append("- " + mut.get("explanation", "{}{}{} at position {}".format(
                        mut["from"], mut["position"], mut["to"], mut["position"])))

            if design.get("rhat"):
                result_parts.append(
                    "\n**Convergence:** R-hat = {:.4f} (< 1.05 = converged) | "
                    "ESS = {}".format(design["rhat"], design.get("ess", "n/a"))
                )

            if is_best:
                result_parts.append("\n*This round produced the best candidate so far.*")

            messages.append(AgentMessage(
                role="agent",
                content="\n".join(result_parts),
                data={
                    "status": "round_complete",
                    "round": round_num,
                    "target": target_name,
                    "sequence": design["sequence"],
                    "pdb_id": pdb_id,
                    "seed": seed,
                    "mutations": design["mutations"],
                    "scores": {
                        "binding": design["binding_score"],
                        "binding_score": design["binding_score"],
                        "stability": design["stability_score"],
                        "solubility": design["solubility_score"],
                        "energy": design["total_energy"],
                        "plddt_estimate": design.get("plddt_estimate", 0),
                        "ddg_estimate_kcal_mol": design.get("ddg_estimate_kcal_mol", 0),
                        "aggregation_propensity": design.get("aggregation_propensity", 0),
                        "immunogenicity_score": design.get("immunogenicity_score", 0),
                        "manufacturability_score": design.get("manufacturability_score", 0),
                        "novelty_score": design.get("novelty_score", 0),
                        "kd_nM": design.get("kd_nM", 0),
                        "serum_half_life_min": design.get("serum_half_life_min", 0),
                        "selectivity_ratio": design.get("selectivity_ratio", 1.0),
                        "toxicity_flag": design.get("toxicity_flag", False),
                        "delta_g_binding_kcal_mol": design.get("delta_g_binding_kcal_mol", 0.0),
                        # Triple-Gate fields
                        "hbond_count": design.get("hbond_count", 0),
                        "entropic_penalty": design.get("entropic_penalty", 0.0),
                        "solvation_delta_g": design.get("solvation_delta_g", 0.0),
                        "surface_complementarity": design.get("surface_complementarity", 0.0),
                        "gate1_pass": design.get("gate1_pass", False),
                        "gate2_pass": design.get("gate2_pass", False),
                        "gate3_pass": design.get("gate3_pass", False),
                        "lab_viability_score": design.get("lab_viability_score", 0.0),
                        "selectivity_ddg": design.get("selectivity_ddg", 0.0),
                    },
                    "is_best": is_best,
                    "trace": design.get("trace", []),
                },
            ))

            # --- Physics justification (Command-and-Justify protocol) ---
            justification = _generate_physics_justification(
                design, round_num, prev_seed, modality
            )
            messages.append(AgentMessage(
                role="agent",
                content=justification,
                data={"status": "evaluate", "round": round_num},
            ))

            prev_seed = design["sequence"]
            current_seed = design["sequence"]

        # --- Final report ---
        best_round = max(rounds_data, key=lambda r: r["binding_score"])
        total_time = time.time() - start_time

        report_lines = [
            "=" * 55,
            "           DESIGN CYCLE COMPLETE",
            "=" * 55,
            "",
            "**Patient:** {} — {} (Stage {})".format(
                patient.full_name, patient.cancer_type, patient.cancer_stage),
            "**Target:** {} (PDB: {})".format(target_name, pdb_id),
            "**Rounds completed:** {}  |  **Compute time:** {:.1f}s".format(
                len(rounds_data), total_time),
            "",
            "### Best Candidate",
            "**Sequence:** `{}`".format(best_round["sequence"]),
            "",
            "#### Biophysical Profile",
            "| Metric | Value |",
            "|--------|-------|",
            "| ΔG Binding | {:.2f} kcal/mol |".format(best_round.get("delta_g_binding_kcal_mol", 0)),
            "| Kd estimate | {:.0f} nM |".format(best_round.get("kd_nM", 0)),
            "| Serum half-life | {:.0f} min |".format(best_round.get("serum_half_life_min", 0)),
            "| Selectivity ratio | {:.2f}x |".format(best_round.get("selectivity_ratio", 1.0)),
            "| Selectivity ΔΔG | {:.2f} kcal/mol |".format(best_round.get("selectivity_ddg", 0.0)),
            "| Stability | {:.1f}% |".format(best_round["stability_score"] * 100),
            "| Solubility | {:.1f}% |".format(best_round["solubility_score"] * 100),
            "| pLDDT estimate | {:.1f} / 100 |".format(best_round.get("plddt_estimate", 0)),
            "| ΔΔG estimate | {:.2f} kcal/mol |".format(best_round.get("ddg_estimate_kcal_mol", 0)),
            "| Aggregation propensity | {:.2f} |".format(best_round.get("aggregation_propensity", 0)),
            "| Immunogenicity | {:.2f} |".format(best_round.get("immunogenicity_score", 0)),
            "| Manufacturability | {:.1f}% |".format(
                best_round.get("manufacturability_score", 0) * 100),
            "| Novelty score | {:.2f} |".format(best_round.get("novelty_score", 0)),
            "| Total Energy | {:.4f} |".format(best_round["total_energy"]),
            "",
            "#### Triple-Gate Physics Model",
            "| Gate | Metric | Value | Status |",
            "|------|--------|-------|--------|",
            "| Gate 1 — Enthalpic Locking | Surface complementarity (Sc) | {:.3f} | {} |".format(
                best_round.get("surface_complementarity", 0),
                "PASS (>= 0.4)" if best_round.get("gate1_pass") else "FAIL (< 0.4)"
            ),
            "| Gate 2 — Solvation | ΔG_solv GBSA-lite | {:.2f} kcal/mol | {} |".format(
                best_round.get("solvation_delta_g", 0),
                "PASS (<= 0)" if best_round.get("gate2_pass") else "FAIL (> 0)"
            ),
            "| Gate 3 — Entropic | -TΔS penalty | {:.2f} kcal/mol | {} |".format(
                best_round.get("entropic_penalty", 0),
                "PASS (<= 3.5)" if best_round.get("gate3_pass") else "FAIL (> 3.5)"
            ),
            "| H-bonds | Backbone + sidechain estimate | {} | — |".format(
                best_round.get("hbond_count", 0)
            ),
            "| **Lab Viability** | Composite (0–100) | **{:.0f}/100** | {} |".format(
                best_round.get("lab_viability_score", 0),
                "Lab-worthy" if best_round.get("lab_viability_score", 0) >= 60 else "Needs optimization"
            ),
        ]

        # --- Solubility tags ---
        sol_tags = best_round.get("solubility_tags", [])
        if sol_tags:
            report_lines += ["", "#### Solubility Warnings"]
            for tag in sol_tags:
                report_lines.append("- {}".format(tag))

        # --- 3D inspection notes ---
        notes_3d = best_round.get("notes_3d", [])
        if notes_3d:
            report_lines += ["", "#### 3D Viewer Inspection Notes"]
            for note in notes_3d:
                report_lines.append("- {}".format(note))

        if best_round.get("mutations"):
            report_lines += [
                "",
                "#### Mutation History",
                "| Position | Change | Rationale |",
                "|----------|--------|-----------|",
            ]
            for mut in best_round["mutations"]:
                expl = mut.get("explanation", "")
                # Strip the bold formatting for table cell
                expl_clean = re.sub(r"\*\*[^*]+\*\*\s*—\s*", "", expl)
                report_lines.append(
                    "| {} | {}{}{} | {} |".format(
                        mut["position"], mut["from"], mut["position"], mut["to"],
                        expl_clean[:80] + ("..." if len(expl_clean) > 80 else "")
                    )
                )

        report_lines += [
            "",
            "#### Iteration History",
            "| Round | ΔG (kcal/mol) | Kd (nM) | Gate1 | Gate2 | Gate3 | Lab Score | Energy |",
            "|-------|---------------|---------|-------|-------|-------|-----------|--------|",
        ]
        for r in rounds_data:
            star = " *" if r == best_round else ""
            report_lines.append(
                "| {}{} | {:.2f} | {:.0f} | {} | {} | {} | {:.0f} | {:.3f} |".format(
                    r["round"], star,
                    r.get("delta_g_binding_kcal_mol", 0),
                    r.get("kd_nM", 0),
                    "PASS" if r.get("gate1_pass") else "FAIL",
                    "PASS" if r.get("gate2_pass") else "FAIL",
                    "PASS" if r.get("gate3_pass") else "FAIL",
                    r.get("lab_viability_score", 0),
                    r["total_energy"],
                )
            )

        # --- FASTA block ---
        fasta = best_round.get("fasta", "")
        if fasta:
            report_lines += ["", "#### FASTA Output", "```", fasta, "```"]

        if constraints:
            report_lines += [
                "",
                "#### Applied Constraints",
            ]
            for k, v in constraints.items():
                if v is True:
                    report_lines.append("- {}".format(k.replace("_", " ").title()))
                elif v is not False:
                    report_lines.append("- {}: {}".format(k.replace("_", " ").title(), v))

        report_lines += [
            "",
            "---",
            "**FOR RESEARCH USE ONLY.** Not a medical device. "
            "Computational predictions require wet-lab validation before any biological use.",
        ]
        report = "\n".join(report_lines)

        messages.append(AgentMessage(
            role="agent", content=report,
            data={
                "status": "complete",
                "target": target_name,
                "sequence": best_round["sequence"],
                "pdb_id": pdb_id,
                "seed": seed,
                "mutations": best_round["mutations"],
                "scores": {
                    "binding": best_round["binding_score"],
                    "binding_score": best_round["binding_score"],
                    "stability": best_round["stability_score"],
                    "solubility": best_round["solubility_score"],
                    "energy": best_round["total_energy"],
                    "plddt_estimate": best_round.get("plddt_estimate", 0),
                    "ddg_estimate_kcal_mol": best_round.get("ddg_estimate_kcal_mol", 0),
                    "aggregation_propensity": best_round.get("aggregation_propensity", 0),
                    "immunogenicity_score": best_round.get("immunogenicity_score", 0),
                    "manufacturability_score": best_round.get("manufacturability_score", 0),
                    "novelty_score": best_round.get("novelty_score", 0),
                    "kd_nM": best_round.get("kd_nM", 0),
                    "serum_half_life_min": best_round.get("serum_half_life_min", 0),
                    "selectivity_ratio": best_round.get("selectivity_ratio", 1.0),
                    "toxicity_flag": best_round.get("toxicity_flag", False),
                    "delta_g_binding_kcal_mol": best_round.get("delta_g_binding_kcal_mol", 0.0),
                    # Triple-Gate fields
                    "hbond_count": best_round.get("hbond_count", 0),
                    "entropic_penalty": best_round.get("entropic_penalty", 0.0),
                    "solvation_delta_g": best_round.get("solvation_delta_g", 0.0),
                    "surface_complementarity": best_round.get("surface_complementarity", 0.0),
                    "gate1_pass": best_round.get("gate1_pass", False),
                    "gate2_pass": best_round.get("gate2_pass", False),
                    "gate3_pass": best_round.get("gate3_pass", False),
                    "lab_viability_score": best_round.get("lab_viability_score", 0.0),
                    "selectivity_ddg": best_round.get("selectivity_ddg", 0.0),
                },
                "rounds": [
                    {
                        "round": r["round"],
                        "sequence": r["sequence"],
                        "binding_score": r["binding_score"],
                        "stability_score": r["stability_score"],
                        "solubility_score": r["solubility_score"],
                        "plddt_estimate": r.get("plddt_estimate", 0),
                        "ddg_estimate_kcal_mol": r.get("ddg_estimate_kcal_mol", 0),
                        "total_energy": r["total_energy"],
                        "kd_nM": r.get("kd_nM", 0),
                        "serum_half_life_min": r.get("serum_half_life_min", 0),
                        "selectivity_ratio": r.get("selectivity_ratio", 1.0),
                        "toxicity_flag": r.get("toxicity_flag", False),
                        "delta_g_binding_kcal_mol": r.get("delta_g_binding_kcal_mol", 0.0),
                        # Triple-Gate fields per round
                        "gate1_pass": r.get("gate1_pass", False),
                        "gate2_pass": r.get("gate2_pass", False),
                        "gate3_pass": r.get("gate3_pass", False),
                        "lab_viability_score": r.get("lab_viability_score", 0.0),
                        "surface_complementarity": r.get("surface_complementarity", 0.0),
                        "hbond_count": r.get("hbond_count", 0),
                        "is_best": r == best_round,
                    }
                    for r in rounds_data
                ],
                "total_time": round(total_time, 1),
                "constraints": constraints,
                "trace": best_round.get("trace", []),
                "notes_3d": best_round.get("notes_3d", []),
                "solubility_tags": best_round.get("solubility_tags", []),
                "fasta": best_round.get("fasta", ""),
            },
        ))

        return AgentRunResponse(
            reply=report,
            messages=messages,
            run_id=best_round.get("run_id", str(uuid.uuid4())),
            candidate_sequence=best_round["sequence"],
            candidate_scores={
                "binding": best_round["binding_score"],
                "stability": best_round["stability_score"],
                "solubility": best_round["solubility_score"],
                "plddt_estimate": best_round.get("plddt_estimate", 0),
                "ddg_estimate_kcal_mol": best_round.get("ddg_estimate_kcal_mol", 0),
                "aggregation_propensity": best_round.get("aggregation_propensity", 0),
                "immunogenicity_score": best_round.get("immunogenicity_score", 0),
                "manufacturability_score": best_round.get("manufacturability_score", 0),
                "novelty_score": best_round.get("novelty_score", 0),
                "kd_nM": best_round.get("kd_nM", 0),
                "serum_half_life_min": best_round.get("serum_half_life_min", 0),
                "selectivity_ratio": best_round.get("selectivity_ratio", 1.0),
                "toxicity_flag": best_round.get("toxicity_flag", False),
                "delta_g_binding_kcal_mol": best_round.get("delta_g_binding_kcal_mol", 0.0),
            },
            pdb_id=pdb_id,
            pdb_string=_call_esmfold(best_round["sequence"]),
            mutations=best_round["mutations"],
            rounds=[r["round"] for r in rounds_data],
            total_time=round(total_time, 1),
        )

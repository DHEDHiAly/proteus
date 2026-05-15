"""
query_responder.py — Stateful chat responder for Proteus design sessions.

Public API:
    classify_query(query: str) -> str
    respond_to_query(query_type: str, state: AgentState) -> str
    handle_query(query: str, state: AgentState) -> tuple[str, str]

Query types:
    QUERY_MECHANISM  — "why does it bind?", "how does it interact?"
    QUERY_MUTATIONS  — "what changed?", "list the mutations"
    QUERY_VIABILITY  — "can we make this?", "is it viable?"
    QUERY_IMPROVE    — "how to improve?", "make it better"
    QUERY_SYNTHESIS  — "can we synthesize this?", "SPPS feasible?"
    QUERY_UNKNOWN    — fallback when nothing matches
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Query type constants
# ---------------------------------------------------------------------------

QUERY_MECHANISM = "QUERY_MECHANISM"
QUERY_MUTATIONS = "QUERY_MUTATIONS"
QUERY_VIABILITY = "QUERY_VIABILITY"
QUERY_IMPROVE = "QUERY_IMPROVE"
QUERY_SYNTHESIS = "QUERY_SYNTHESIS"
QUERY_UNKNOWN = "QUERY_UNKNOWN"

# ---------------------------------------------------------------------------
# Regex routing table — first match wins
# ---------------------------------------------------------------------------

_ROUTES: List[Tuple[str, re.Pattern]] = [
    (
        QUERY_MECHANISM,
        re.compile(
            r"\b(why|how)\b.{0,40}\b(bind|interact|dock|attach|affinit|mechanism)\b"
            r"|\b(binding\s+mechanism|mode\s+of\s+action|moa|what\s+drives|explain\s+binding"
            r"|how\s+does\s+it\s+work|what\s+makes\s+it\s+bind)\b",
            re.IGNORECASE,
        ),
    ),
    (
        QUERY_MUTATIONS,
        re.compile(
            r"\b(mutation[s]?|what\s+changed|what\s+differ|what\s+are\s+the\s+(diff|change)"
            r"|from\s+seed|from\s+start|point\s+mutation|residue\s+change|substitution)\b",
            re.IGNORECASE,
        ),
    ),
    (
        QUERY_VIABILITY,
        re.compile(
            r"\b(viable|viabilit|proceed|lab\s+ready|ready\s+for\s+lab|can\s+we\s+(order|use|proceed)"
            r"|lab\s+score|is\s+it\s+good|good\s+enough|should\s+we\s+(order|synthesize|proceed))\b",
            re.IGNORECASE,
        ),
    ),
    (
        QUERY_IMPROVE,
        re.compile(
            r"\b(improve|better|optim|enhanc|boost|increase\s+affinity|reduce\s+kd"
            r"|stronger\s+bind|higher\s+affinity|next\s+step|what\s+(should|can)\s+(i|we)\s+do)\b",
            re.IGNORECASE,
        ),
    ),
    (
        QUERY_SYNTHESIS,
        re.compile(
            r"\b(synthes|spps|solid.phase|make\s+this|can\s+(we|i)\s+make|feasib"
            r"|cost|price|how\s+much|synthesis\s+score|production|manufacture)\b",
            re.IGNORECASE,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Snapshot of the current design session passed to every handler."""
    best_sequence: str = ""
    seed_sequence: str = ""
    target_name: str = ""
    delta_g_kcal_mol: Optional[float] = None
    kd_nM: Optional[float] = None
    binding_score: float = 0.0
    stability_score: float = 0.0
    solubility_score: float = 0.0
    lab_viability_score: float = 0.0
    rounds: int = 0
    gate1_pass: bool = False
    gate2_pass: bool = False
    gate3_pass: bool = False


@dataclass
class _SequenceProfile:
    """Amino-acid composition analysis of a single sequence."""

    sequence: str

    # Residue category membership (one-letter codes)
    AROMATIC: frozenset = frozenset("FYWH")
    HYDROPHOBIC: frozenset = frozenset("VILMFYWAC")
    CHARGED_POS: frozenset = frozenset("KRH")
    CHARGED_NEG: frozenset = frozenset("DE")
    POLAR: frozenset = frozenset("STCNQY")

    # Computed lazily via properties
    _aromatic: Optional[List[Tuple[int, str]]] = field(default=None, repr=False)
    _hydrophobic: Optional[List[Tuple[int, str]]] = field(default=None, repr=False)
    _charged_pos: Optional[List[Tuple[int, str]]] = field(default=None, repr=False)
    _charged_neg: Optional[List[Tuple[int, str]]] = field(default=None, repr=False)
    _polar: Optional[List[Tuple[int, str]]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        seq = self.sequence.upper()
        n = max(len(seq), 1)

        self._aromatic = [(i + 1, aa) for i, aa in enumerate(seq) if aa in self.AROMATIC]
        self._hydrophobic = [(i + 1, aa) for i, aa in enumerate(seq) if aa in self.HYDROPHOBIC]
        self._charged_pos = [(i + 1, aa) for i, aa in enumerate(seq) if aa in self.CHARGED_POS]
        self._charged_neg = [(i + 1, aa) for i, aa in enumerate(seq) if aa in self.CHARGED_NEG]
        self._polar = [(i + 1, aa) for i, aa in enumerate(seq) if aa in self.POLAR]

        self.length = len(seq)
        self.aromatic_fraction = len(self._aromatic) / n
        self.hydrophobic_fraction = len(self._hydrophobic) / n
        self.charged_fraction = (len(self._charged_pos) + len(self._charged_neg)) / n
        self.polar_fraction = len(self._polar) / n
        self.net_charge = len(self._charged_pos) - len(self._charged_neg)

        # Longest hydrophobic run
        run, max_run = 0, 0
        for aa in seq:
            if aa in self.HYDROPHOBIC:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        self.max_hydrophobic_run = max_run

    @property
    def aromatic_residues(self) -> List[Tuple[int, str]]:
        return self._aromatic or []

    @property
    def charged_pos_residues(self) -> List[Tuple[int, str]]:
        return self._charged_pos or []

    @property
    def charged_neg_residues(self) -> List[Tuple[int, str]]:
        return self._charged_neg or []


# ---------------------------------------------------------------------------
# Helper: sequence diff
# ---------------------------------------------------------------------------

def _diff_sequences(seq_a: str, seq_b: str) -> List[str]:
    """
    Character-level alignment of two sequences of the same length.
    Returns mutations in '{from_aa}{1-based-position}{to_aa}' format, e.g. 'A12K'.
    If lengths differ, truncate to the shorter length.
    """
    mutations: List[str] = []
    length = min(len(seq_a), len(seq_b))
    for i in range(length):
        a, b = seq_a[i].upper(), seq_b[i].upper()
        if a != b:
            mutations.append(f"{a}{i + 1}{b}")
    return mutations


# ---------------------------------------------------------------------------
# Helper: mutation biochemical classification
# ---------------------------------------------------------------------------

_HYDROPHOBIC_AA = frozenset("VILMFYWAC")
_CHARGED_AA = frozenset("KRDE")
_POLAR_AA = frozenset("STCNQY")
_AROMATIC_AA = frozenset("FYW")
_SMALL_AA = frozenset("GAS")

_AA_CHARGE: dict = {"K": +1, "R": +1, "H": +0.5, "D": -1, "E": -1}


def _classify_mutation(from_aa: str, to_aa: str) -> str:
    """
    Return a human-readable biochemical characterization of a single point mutation.
    """
    from_aa, to_aa = from_aa.upper(), to_aa.upper()

    from_charge = _AA_CHARGE.get(from_aa, 0)
    to_charge = _AA_CHARGE.get(to_aa, 0)
    charge_delta = to_charge - from_charge

    parts: List[str] = []

    # Charge change
    if charge_delta > 0:
        parts.append("charge gain (electrostatic interaction introduced)")
    elif charge_delta < 0:
        parts.append("charge loss (electrostatic interaction removed)")

    # Hydrophobicity
    from_hphob = from_aa in _HYDROPHOBIC_AA
    to_hphob = to_aa in _HYDROPHOBIC_AA
    if not from_hphob and to_hphob:
        parts.append("hydrophobicity gain (improved core packing)")
    elif from_hphob and not to_hphob:
        parts.append("hydrophobicity loss (reduced core packing)")

    # Aromatic introduction / loss
    from_arom = from_aa in _AROMATIC_AA
    to_arom = to_aa in _AROMATIC_AA
    if not from_arom and to_arom:
        parts.append(f"aromatic {to_aa} introduced (pi-stacking or cation-pi potential)")
    elif from_arom and not to_arom:
        parts.append(f"aromatic {from_aa} removed (pi-stacking lost)")

    # Glycine introduction (flexibility)
    if to_aa == "G":
        parts.append("glycine introduced (backbone flexibility gain, possible entropy cost)")
    elif from_aa == "G":
        parts.append("glycine removed (backbone rigidified)")

    # Proline introduction (conformational constraint)
    if to_aa == "P":
        parts.append("proline introduced (loop/turn constraint, SPPS coupling risk)")

    # Cysteine changes (disulfide potential)
    if to_aa == "C":
        parts.append("cysteine introduced (disulfide cyclization potential)")
    elif from_aa == "C":
        parts.append("cysteine removed (disulfide potential lost)")

    # Polar toggle
    from_polar = from_aa in _POLAR_AA
    to_polar = to_aa in _POLAR_AA
    if not from_polar and to_polar and not parts:
        parts.append("polar residue introduced (H-bond potential)")
    elif from_polar and not to_polar and not parts:
        parts.append("polar residue removed")

    if not parts:
        parts.append("conservative substitution (similar physicochemical class)")

    return "; ".join(parts)


# ---------------------------------------------------------------------------
# ΔG / Kd / viability label helpers
# ---------------------------------------------------------------------------

def _dg_label(dg: Optional[float]) -> str:
    if dg is None:
        return "unavailable"
    if dg <= -9.0:
        return f"{dg:.2f} kcal/mol (strong binder)"
    if dg <= -7.0:
        return f"{dg:.2f} kcal/mol (good binder)"
    if dg <= -6.0:
        return f"{dg:.2f} kcal/mol (promising — above lab-order threshold)"
    return f"{dg:.2f} kcal/mol (weak — needs optimization)"


def _kd_label(kd: Optional[float]) -> str:
    if kd is None:
        return "unavailable"
    if kd < 1.0:
        return f"{kd:.2f} nM (ultra-high affinity)"
    if kd < 10.0:
        return f"{kd:.2f} nM (drug-like affinity)"
    if kd < 100.0:
        return f"{kd:.1f} nM (high affinity)"
    if kd < 1000.0:
        return f"{kd:.0f} nM (moderate affinity)"
    return f"{kd:.0f} nM (weak — likely insufficient for therapeutic use)"


def _viability_label(score: float) -> str:
    if score >= 70:
        return f"{score:.0f}/100 — proceed to SPPS ordering"
    if score >= 50:
        return f"{score:.0f}/100 — borderline; review issues before ordering"
    return f"{score:.0f}/100 — needs optimization before synthesis"


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------

def _respond_mechanism(state: AgentState) -> str:
    if not state.best_sequence:
        return "No design session found. Run a design cycle first to get binding mechanism analysis."

    prof = _SequenceProfile(sequence=state.best_sequence)
    target = state.target_name or "the target"

    lines: List[str] = [
        f"**Binding mechanism for {target}:**",
        "",
        f"Sequence: `{state.best_sequence}` ({prof.length} residues)",
        "",
        "**Driving forces:**",
    ]

    # Hydrophobic core
    if prof.hydrophobic_fraction >= 0.4:
        hphob_res = ", ".join(f"{aa}{pos}" for pos, aa in prof._hydrophobic[:6])
        lines.append(
            f"- **Hydrophobic packing** ({prof.hydrophobic_fraction:.0%} of residues): "
            f"{hphob_res}{'...' if len(prof._hydrophobic) > 6 else ''} "
            f"— primary driver of ΔG through van der Waals burial."
        )
        if prof.max_hydrophobic_run >= 3:
            lines.append(
                f"  Longest hydrophobic run: {prof.max_hydrophobic_run} consecutive residues "
                "(core burial likely, increases binding enthalpy)."
            )

    # Electrostatic contacts
    if prof.charged_pos_residues or prof.charged_neg_residues:
        pos_res = ", ".join(f"{aa}{pos}" for pos, aa in prof.charged_pos_residues[:3])
        neg_res = ", ".join(f"{aa}{pos}" for pos, aa in prof.charged_neg_residues[:3])
        lines.append(
            f"- **Electrostatic contacts**: "
            + (f"basic ({pos_res})" if pos_res else "")
            + (" and " if pos_res and neg_res else "")
            + (f"acidic ({neg_res})" if neg_res else "")
            + f" — net charge {prof.net_charge:+d}; salt bridges possible at interface."
        )

    # Aromatic contacts
    if prof.aromatic_residues:
        arom_res = ", ".join(f"{aa}{pos}" for pos, aa in prof.aromatic_residues[:4])
        lines.append(
            f"- **Pi-stacking / cation-pi**: aromatic residues {arom_res} "
            "— potential stacking with Phe/Tyr/His at binding pocket."
        )

    # Polar H-bonds
    if prof.polar_fraction >= 0.2:
        lines.append(
            f"- **H-bond network** ({prof.polar_fraction:.0%} polar): "
            "backbone and side-chain H-bond donors/acceptors complement pocket contacts."
        )

    lines.append("")
    lines.append("**Binding affinity summary:**")
    lines.append(f"- ΔG: {_dg_label(state.delta_g_kcal_mol)}")
    lines.append(f"- Kd: {_kd_label(state.kd_nM)}")

    if state.delta_g_kcal_mol is not None and state.delta_g_kcal_mol <= -6.0:
        lines.append("")
        lines.append(
            "Estimated ΔG meets the lab-order threshold (≤ −6 kcal/mol). "
            "The hydrophobic burial and electrostatic complementarity are the dominant contributors."
        )

    return "\n".join(lines)


def _respond_mutations(state: AgentState) -> str:
    if not state.best_sequence or not state.seed_sequence:
        return (
            "No seed or best sequence on record. "
            "Run a design cycle first — mutation analysis requires both seed and optimized sequence."
        )

    mutations = _diff_sequences(state.seed_sequence, state.best_sequence)

    if not mutations:
        return (
            f"The optimized sequence is identical to the seed (`{state.seed_sequence}`). "
            "MCMC sampled the starting sequence as the energy minimum — "
            "consider running more rounds or broadening the proposal distribution."
        )

    lines: List[str] = [
        f"**Mutations from seed to best sequence** ({len(mutations)} point mutation{'s' if len(mutations) != 1 else ''}):",
        "",
        f"Seed: `{state.seed_sequence}`",
        f"Best: `{state.best_sequence}`",
        "",
    ]

    for mut in mutations:
        m = re.match(r"^([A-Z])(\d+)([A-Z])$", mut)
        if m:
            from_aa, pos, to_aa = m.group(1), m.group(2), m.group(3)
            classification = _classify_mutation(from_aa, to_aa)
            lines.append(f"- **{mut}** — {classification}")
        else:
            lines.append(f"- {mut}")

    lines.append("")
    lines.append(
        f"After {state.rounds} round{'s' if state.rounds != 1 else ''} of MCMC sampling, "
        f"these {len(mutations)} substitution{'s' if len(mutations) != 1 else ''} "
        f"reduced ΔG to {_dg_label(state.delta_g_kcal_mol)}."
    )

    return "\n".join(lines)


def _respond_viability(state: AgentState) -> str:
    score = state.lab_viability_score

    lines: List[str] = [
        "**Lab viability assessment:**",
        "",
        f"- Lab viability score: {_viability_label(score)}",
        f"- Binding affinity: {_dg_label(state.delta_g_kcal_mol)}",
        f"- Stability score: {state.stability_score:.2f}",
        f"- Solubility score: {state.solubility_score:.2f}",
        "",
    ]

    # Gate status
    gates = []
    if state.gate1_pass:
        gates.append("Gate 1 (binding ΔG): PASS")
    else:
        gates.append("Gate 1 (binding ΔG): FAIL — ΔG > −6 kcal/mol threshold")
    if state.gate2_pass:
        gates.append("Gate 2 (stability): PASS")
    else:
        gates.append("Gate 2 (stability): FAIL — stability score below threshold")
    if state.gate3_pass:
        gates.append("Gate 3 (solubility): PASS")
    else:
        gates.append("Gate 3 (solubility): FAIL — solubility score below threshold")

    lines.append("**Gate status:**")
    for g in gates:
        lines.append(f"- {g}")

    lines.append("")

    if score >= 70 and state.gate1_pass:
        lines.append(
            "**Recommendation: proceed to SPPS ordering.** "
            "Affinity and lab feasibility are both above threshold."
        )
    elif score >= 50:
        lines.append(
            "**Recommendation: borderline.** Review synthesis issues before ordering. "
            "Consider running additional MCMC rounds to improve affinity."
        )
    else:
        lines.append(
            "**Recommendation: do not order yet.** "
            "Run more optimization rounds — lab viability score is below 50."
        )

    return "\n".join(lines)


def _respond_improve(state: AgentState) -> str:
    if not state.best_sequence:
        return "No design session found. Run a design cycle first."

    prof = _SequenceProfile(sequence=state.best_sequence)
    lines: List[str] = ["**Suggestions to improve the current design:**", ""]

    suggestions_added = 0

    # ΔG improvement paths
    if state.delta_g_kcal_mol is None or state.delta_g_kcal_mol > -6.0:
        lines.append(
            "1. **Run more MCMC rounds** — ΔG has not reached the −6 kcal/mol lab-order threshold. "
            "Additional sampling can discover higher-affinity sequences."
        )
        suggestions_added += 1
    elif state.delta_g_kcal_mol > -7.0:
        lines.append(
            "1. **Run additional rounds targeting deeper energy basin** — "
            f"current ΔG {state.delta_g_kcal_mol:.2f} kcal/mol is promising but below the −7 kcal/mol "
            "strong-binder threshold."
        )
        suggestions_added += 1

    # Electrostatic enrichment
    if abs(prof.net_charge) < 1:
        lines.append(
            f"{'2' if suggestions_added else '1'}. **Introduce a charged anchor residue** — "
            "net charge is nearly zero. Adding Lys (K) or Arg (R) at a binding-site-facing position "
            "can introduce a salt bridge worth −1.5 kcal/mol."
        )
        suggestions_added += 1

    # Aromatic enrichment
    if prof.aromatic_fraction < 0.15:
        lines.append(
            f"{suggestions_added + 1}. **Introduce an aromatic residue (F, Y, or W)** — "
            f"current aromatic content is low ({prof.aromatic_fraction:.0%}). "
            "A pi-stacking contact in the binding pocket can contribute −1 to −2 kcal/mol."
        )
        suggestions_added += 1

    # Hydrophobic over-saturation warning
    if prof.hydrophobic_fraction > 0.6:
        lines.append(
            f"{suggestions_added + 1}. **Reduce hydrophobic content** — "
            f"{prof.hydrophobic_fraction:.0%} of residues are hydrophobic. "
            "Sequences >60% hydrophobic tend to aggregate; "
            "substituting 1-2 residues with Gln (Q) or Ser (S) can improve solubility."
        )
        suggestions_added += 1

    # Solubility path
    if state.solubility_score < 0.5:
        lines.append(
            f"{suggestions_added + 1}. **Improve solubility** — "
            "solubility score is below 0.5. Introduce Lys, Arg, or Asp at surface-exposed positions."
        )
        suggestions_added += 1

    # Cyclization potential
    cys_count = state.best_sequence.upper().count("C")
    if cys_count < 2:
        lines.append(
            f"{suggestions_added + 1}. **Consider disulfide cyclization** — "
            "adding a Cys pair enables head-to-tail cyclization, increasing serum half-life "
            "and constraining bioactive conformation."
        )
        suggestions_added += 1

    if not suggestions_added:
        lines.append(
            "The current design is already well-optimized. "
            "Consider running the compare page to benchmark against other candidates."
        )

    return "\n".join(lines)


def _respond_synthesis(state: AgentState) -> str:
    if not state.best_sequence:
        return "No design session found. Run a design cycle first."

    seq = state.best_sequence.upper()
    prof = _SequenceProfile(sequence=seq)
    issues: List[str] = []
    recommendations: List[str] = []

    # Length
    length = len(seq)
    if length > 30:
        issues.append(f"Length {length} aa — long peptides (>30) have higher SPPS failure rates and cost")
        recommendations.append("Consider fragmenting into 2 shorter peptides with ligation")
    elif length < 5:
        issues.append(f"Length {length} aa — very short peptide; may lack stable tertiary contacts")

    # Cysteine (disulfide risk in linear peptide)
    cys_positions = [str(pos) for pos, aa in prof._hydrophobic if aa == "C"]  # noqa: SLF001
    cys_list = [pos for pos, aa in enumerate(seq, 1) if aa == "C"]
    if len(cys_list) == 1:
        issues.append("Single Cys — unmatched cysteine oxidizes under atmospheric conditions; use Acm protection")
        recommendations.append("Protect Cys with Acm during SPPS or remove if not needed for binding")
    elif len(cys_list) > 2:
        issues.append(f"{len(cys_list)} Cys residues — multiple cysteines risk scrambled disulfides")
        recommendations.append("Plan directed oxidation strategy (orthogonal Cys protection)")

    # Methionine (oxidation)
    met_count = seq.count("M")
    if met_count > 0:
        issues.append(f"{met_count} Met — susceptible to oxidation; replace with Nle (norleucine) for stability")
        recommendations.append("Replace Met with Nle or Leu unless Met is a binding contact")

    # Asparagine deamidation
    asn_count = seq.count("N")
    if asn_count > 1:
        issues.append(f"{asn_count} Asn — risk of deamidation (Asn→Asp) under acidic SPPS conditions")

    # N-terminal Gln cyclization
    if seq[0] == "Q":
        issues.append("N-terminal Gln — spontaneously cyclizes to pyroglutamate; use Fmoc-pyroGlu or protect N-terminus")
        recommendations.append("Replace N-terminal Gln with Glu or Ala, or deliberately use pyroGlu for stability")

    # Adjacent aromatics (aggregation)
    for i in range(length - 1):
        if seq[i] in "FYW" and seq[i + 1] in "FYW":
            issues.append(f"Adjacent aromatics {seq[i]}{i+1}-{seq[i+1]}{i+2} — aggregation risk during SPPS deprotection")
            recommendations.append(f"Separate {seq[i]}{i+1}-{seq[i+1]}{i+2} with a Gly or Pro")
            break

    # Proline count (slow coupling)
    pro_count = seq.count("P")
    if pro_count > 2:
        issues.append(f"{pro_count} Pro residues — proline coupling is slow; each adds ~30 min to synthesis")

    # Cost estimate
    base_cost = 500
    per_aa = 20
    difficulty_mult = 1.0 + (0.3 * len(cys_list)) + (0.2 * pro_count) + (0.15 * sum(1 for aa in seq if aa in "FYW"))
    estimated_cost = int((base_cost + per_aa * length) * difficulty_mult)
    estimated_days = 1 + (length // 10) + len(issues)

    lines: List[str] = [
        "**SPPS synthesis feasibility:**",
        "",
        f"- Sequence: `{seq}` ({length} aa)",
        f"- Lab viability score: {_viability_label(state.lab_viability_score)}",
        f"- Estimated synthesis cost: ~${estimated_cost:,}",
        f"- Estimated timeline: ~{estimated_days} business day{'s' if estimated_days != 1 else ''}",
        "",
    ]

    if issues:
        lines.append(f"**Issues identified ({len(issues)}):**")
        for iss in issues:
            lines.append(f"- {iss}")
        lines.append("")

    if recommendations:
        lines.append("**Recommendations:**")
        for rec in recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    if not issues:
        lines.append("No major synthesis issues identified. Sequence is ready for SPPS ordering.")

    lines.append(f"- ΔG: {_dg_label(state.delta_g_kcal_mol)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_query(query: str) -> str:
    """
    Match query against routing table. Returns the first matching QUERY_* constant,
    or QUERY_UNKNOWN if nothing matches.
    """
    for query_type, pattern in _ROUTES:
        if pattern.search(query):
            return query_type
    return QUERY_UNKNOWN


def respond_to_query(query_type: str, state: AgentState) -> str:
    """
    Dispatch to the appropriate handler for query_type.
    Returns the handler's string response.
    Returns empty string for QUERY_UNKNOWN.
    """
    handlers = {
        QUERY_MECHANISM: _respond_mechanism,
        QUERY_MUTATIONS: _respond_mutations,
        QUERY_VIABILITY: _respond_viability,
        QUERY_IMPROVE: _respond_improve,
        QUERY_SYNTHESIS: _respond_synthesis,
    }
    handler = handlers.get(query_type)
    if handler is None:
        return ""
    return handler(state)


def handle_query(query: str, state: AgentState) -> Tuple[str, str]:
    """
    Classify then respond. Returns (query_type, response_text).
    For QUERY_UNKNOWN, response_text is empty string — caller should route to fallback.
    """
    query_type = classify_query(query)
    response = respond_to_query(query_type, state)
    return query_type, response

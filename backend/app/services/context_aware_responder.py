"""
Context-aware chat responder: answers questions about the actual designed peptide
(sequence, mutations, mechanism, viability, round progression, improvement) using
the DesignSessionContext attached to each message.

Returns None if no session or no best_sequence, allowing fallthrough to static QA.
"""

import re
from typing import Optional, List

from app.schemas.agent import DesignSessionContext

# Amino acid property classes for mutation explanations
_AA_PROPERTIES = {
    "A": "nonpolar aliphatic",
    "R": "positive charged",
    "N": "polar uncharged",
    "D": "negative charged",
    "C": "special (thiol)",
    "E": "negative charged",
    "Q": "polar uncharged",
    "G": "special (flexible)",
    "H": "positive aromatic",
    "I": "nonpolar aliphatic (hydrophobic)",
    "L": "nonpolar aliphatic (hydrophobic)",
    "K": "positive charged",
    "M": "nonpolar (sulfur)",
    "F": "aromatic nonpolar",
    "P": "special (cyclic/rigid)",
    "S": "polar hydroxyl",
    "T": "polar hydroxyl",
    "W": "aromatic nonpolar (bulky)",
    "Y": "aromatic polar",
    "V": "nonpolar aliphatic (hydrophobic)",
}

# -- Pattern lists for each topic --

_MECHANISM_PATTERNS = [
    r"how\s+does\s+(this|the|it|the\s+designed|the\s+current)\s+(peptide|sequence|molecule|candidate|treatment|drug)\s+work",
    r"(mechanism|mode\s+of\s+action|moa)\s+of\s+(the\s+)?(peptide|sequence|design|candidate|treatment)",
    r"what\s+is\s+the\s+mechanism",
    r"how\s+does\s+it\s+bind",
    r"how\s+does\s+the\s+(sequence|peptide|candidate|design)\s+work",
    r"what\s+does\s+the\s+(peptide|sequence|design|candidate)\s+do",
    r"explain\s+(the\s+)?(mechanism|binding\s+mechanism|mode\s+of\s+action|how\s+it\s+works)",
]

_MUTATION_PATTERNS = [
    r"what\s+(are\s+)?(the\s+)?mutations",
    r"which\s+(residues?\s+)?(changed|were\s+mutated|are\s+different|differ)",
    r"(list|show|explain|describe)\s+(the\s+)?mutations",
    r"what\s+changed\s+(from\s+the\s+seed|from\s+the\s+original|between\s+rounds|in\s+the\s+design)",
    r"mutation\s+(list|summary|details|rationale|breakdown)",
    r"which\s+(positions?|aa|amino\s+acids?)\s+(changed|are\s+mutated|differ)",
    r"how\s+many\s+mutations",
]

_VIABILITY_PATTERNS = [
    r"is\s+it\s+(lab.?viable|lab.?worthy|ready\s+for\s+(lab|synthesis|the\s+lab)|synthesizable|synthesis.?ready)",
    r"can\s+it\s+be\s+(made|synthesized|expressed|produced)",
    r"(synthesis|synthesis)\s+(feasibility|ready|readiness|score)",
    r"what\s+is\s+the\s+lab\s+viability",
    r"viability\s+(score|assessment|of\s+the\s+(design|candidate|peptide))",
    r"is\s+(the\s+)?(design|candidate|peptide|sequence)\s+(viable|synthesizable|ready)",
]

_IMPROVEMENT_PATTERNS = [
    r"how\s+(can|to|do\s+I|would\s+you|should\s+I)\s+(improve|optimize|enhance|increase|boost)\s+(it|this|the\s+design|binding|stability|solubility|the\s+sequence|the\s+candidate)",
    r"(improve|optimize|enhance|boost)\s+(the\s+)?(binding|stability|solubility|design|candidate|sequence|affinity)",
    r"next\s+steps?\s+for\s+(optimization|improving|enhancing|design)",
    r"what\s+would\s+improve\s+(it|this|the\s+(design|candidate|sequence|binding))",
    r"how\s+to\s+(get\s+better|do\s+better|improve)\s+(the\s+)?results?",
    r"what\s+(would|could|can)\s+(I|we)\s+do\s+(to\s+)?(better|improve|optimize|enhance)\s+(it|the|this)",
    r"make\s+it\s+(better|stronger|tighter|more\s+potent|more\s+soluble|more\s+stable)",
    r"(suggest|recommend)\s+(changes?|modifications?|improvements?)\s+(to|for)\s+(the\s+)?(design|candidate|peptide|sequence)",
]

_PROGRESSION_PATTERNS = [
    r"how\s+did\s+it\s+(improve|evolve|progress|change|get\s+better)\s+(across|between|over)\s+rounds?",
    r"round\s+(by\s+round|progression|history|summary|comparison)",
    r"(show|explain|describe)\s+(the\s+)?(round|iteration)\s+(progression|history|summary|results)",
    r"what\s+happened\s+in\s+(each\s+round|round\s+[123]|the\s+rounds?)",
    r"(how|what)\s+(did|do)\s+the\s+(scores?|binding|energy|results?)\s+(improve|change|evolve|progress|look)\s+(across|over|between)\s+rounds?",
    r"progression\s+(of\s+)?(the\s+)?(design|binding|scores?|candidate)",
]


class ContextAwareChatResponder:
    """
    Answers session-specific questions by grounding answers in the actual
    DesignSessionContext (sequence, scores, mutations, round data).

    Returns None when:
    - No session is attached, or session has no best_sequence
    - The message does not match any handled pattern

    Designed to sit AFTER static QA (which handles generic biophysics) and BEFORE
    the generic ChatResponder, providing the most specific possible answers.
    """

    def respond(
        self,
        message: str,
        session: Optional[DesignSessionContext],
    ) -> Optional[str]:
        if not session or not session.best_sequence:
            return None

        text = message.lower().strip()

        for pattern in _MECHANISM_PATTERNS:
            if re.search(pattern, text):
                return self._explain_mechanism(session)

        for pattern in _MUTATION_PATTERNS:
            if re.search(pattern, text):
                return self._explain_mutations(session)

        for pattern in _VIABILITY_PATTERNS:
            if re.search(pattern, text):
                return self._assess_viability(session)

        for pattern in _IMPROVEMENT_PATTERNS:
            if re.search(pattern, text):
                return self._suggest_improvement(session)

        for pattern in _PROGRESSION_PATTERNS:
            if re.search(pattern, text):
                return self._show_progression(session)

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Answer builders
    # ──────────────────────────────────────────────────────────────────────────

    def _explain_mechanism(self, session: DesignSessionContext) -> str:
        seq = session.best_sequence or ""
        target = session.target_name or "the target"
        dg = session.delta_g_kcal_mol
        kd = session.kd_nM

        hydro_residues = [aa for aa in seq if aa in "ILFVWM"]
        hydro_frac = len(hydro_residues) / max(len(seq), 1)
        aromatic = [aa for aa in seq if aa in "FWY"]
        cationic = [aa for aa in seq if aa in "RK"]
        anionic = [aa for aa in seq if aa in "DE"]

        lines = [
            f"**Mechanism of action for `{seq}`**",
            "",
            f"This peptide is designed to bind **{target}** through the following physicochemical interactions:",
            "",
        ]

        if hydro_frac >= 0.3:
            lines.append(
                f"- **Hydrophobic burial** ({len(hydro_residues)} ILFVWM residues, {hydro_frac:.0%}): "
                "drives insertion into the hydrophobic pocket, providing the primary ΔG burial gain."
            )
        elif hydro_frac >= 0.15:
            lines.append(
                f"- **Moderate hydrophobic content** ({len(hydro_residues)} ILFVWM residues): "
                "partial contribution to burial; mixed polar/hydrophobic interface."
            )

        if aromatic:
            lines.append(
                f"- **Aromatic contacts** ({', '.join(aromatic[:5])}): "
                "π-stacking and cation-π interactions with pocket aromatic residues (Phe, Tyr, Trp, or His)."
            )

        if cationic:
            lines.append(
                f"- **Electrostatic anchoring** ({len(cationic)} basic R/K residues): "
                "salt bridges with acidic residues (D/E) in the target binding cleft."
            )

        if anionic:
            lines.append(
                f"- **Complementary electrostatics** ({len(anionic)} acidic D/E residues): "
                "contact with cationic patch on the target surface."
            )

        if not hydro_residues and not aromatic and not cationic and not anionic:
            lines.append(
                "- Sequence is largely composed of polar uncharged residues — "
                "binding is driven by H-bonding and shape complementarity."
            )

        lines.append("")

        if dg is not None:
            if dg <= -9.0:
                interp = "strong binder"
            elif dg <= -7.0:
                interp = "good binder"
            elif dg <= -6.0:
                interp = "promising (near the lab-ordering threshold)"
            else:
                interp = "weak binder (below the −6 kcal/mol lab threshold)"
            lines.append(f"**Estimated binding energy:** ΔG = {dg:.2f} kcal/mol — {interp}")

        if kd is not None:
            if kd < 10:
                kd_interp = "drug-like affinity"
            elif kd < 100:
                kd_interp = "high affinity"
            elif kd < 1000:
                kd_interp = "moderate affinity"
            else:
                kd_interp = "weak affinity"
            lines.append(f"**Estimated Kd:** {kd:.0f} nM ({kd_interp})")

        lines += [
            "",
            "*In-silico predictions. Actual binding mode and affinity require crystallography, "
            "cryo-EM, NMR, or SPR/ITC validation.*",
        ]

        return "\n".join(lines)

    def _explain_mutations(self, session: DesignSessionContext) -> str:
        seq = session.best_sequence or ""
        seed = session.seed_sequence or ""
        mutations_from_seed: List[str] = list(session.mutations_from_seed or [])

        # Compute on-the-fly if not provided
        if not mutations_from_seed and seed:
            for i, (a, b) in enumerate(zip(seed, seq)):
                if a != b:
                    mutations_from_seed.append(f"{a}{i + 1}{b}")
            if len(seq) != len(seed):
                mutations_from_seed.append(f"length {len(seed)}→{len(seq)}")

        if not seed and not mutations_from_seed:
            return (
                f"**Mutations for `{seq}`**\n\n"
                "No seed sequence is attached to this session — the mutation diff is not available. "
                "Run a full design cycle and mutations will appear with per-position BLOSUM62 scores "
                "and energy deltas in the round-by-round physics justification."
            )

        if not mutations_from_seed:
            return (
                f"**Mutations for `{seq}`**\n\n"
                f"Sequence is identical to the seed `{seed}` — no substitutions were made. "
                "This is uncommon; try re-running with different constraints or a different seed length."
            )

        sub_mutations = [m for m in mutations_from_seed if len(m) >= 3 and m[0].isalpha() and m[-1].isalpha()]
        other_changes = [m for m in mutations_from_seed if m not in sub_mutations]

        lines = [
            f"**Mutations: seed `{seed}` → design `{seq}`**",
            "",
            f"{len(sub_mutations)} residue substitution(s):",
            "",
        ]

        for mut in sub_mutations[:12]:
            from_aa = mut[0]
            to_aa = mut[-1]
            pos = mut[1:-1]
            from_class = _AA_PROPERTIES.get(from_aa, "unknown")
            to_class = _AA_PROPERTIES.get(to_aa, "unknown")
            lines.append(f"- **{mut}**: {from_aa} ({from_class}) → {to_aa} ({to_class})")

        if other_changes:
            for change in other_changes:
                lines.append(f"- {change}")

        # Add residue-level notes for key amino acids in the design
        notes = []
        if "W" in seq:
            notes.append(f"Trp (W) ×{seq.count('W')}: aromatic anchor for π-stacking in hydrophobic pocket")
        if seq.count("K") + seq.count("R") > 2:
            notes.append(
                f"Lys/Arg ×{seq.count('K') + seq.count('R')}: cationic charge for salt-bridge anchoring"
            )
        if seq.count("C") >= 2:
            notes.append("Cys pair: enables disulfide cyclisation → reduced conformational entropy, improved stability")
        if "P" in seq:
            notes.append(f"Pro (P) ×{seq.count('P')}: introduces rigid turns; reduces backbone flexibility")

        if notes:
            lines += ["", "**Key residue roles in the current design:**"]
            for n in notes:
                lines.append(f"- {n}")

        lines += [
            "",
            "*For energy deltas and BLOSUM62 conservatism scores, see the physics justification "
            "in the round-by-round chat history.*",
        ]

        return "\n".join(lines)

    def _assess_viability(self, session: DesignSessionContext) -> str:
        seq = session.best_sequence or ""
        lab = session.lab_viability_score
        dg = session.delta_g_kcal_mol
        stability = session.stability_score
        solubility = session.solubility_score

        if lab is None:
            return (
                f"**Lab viability for `{seq}`**\n\n"
                "Lab viability score not available in the current session. "
                "Run a full design cycle — the composite lab viability score (0–100) will appear "
                "in the final report with per-gate breakdown."
            )

        if lab >= 70:
            verdict = "Lab-worthy — candidate is ready for peptide synthesis or recombinant expression."
        elif lab >= 50:
            verdict = "Borderline — address failing Triple-Gate checks before ordering synthesis."
        else:
            verdict = "Below threshold — significant optimization required before lab hand-off."

        lines = [
            f"**Lab Viability Assessment: {lab:.0f}/100**",
            f"**Verdict:** {verdict}",
            "",
            "**Score contributors:**",
        ]

        if dg is not None:
            gate = "PASS" if dg <= -6.0 else "FAIL"
            lines.append(
                f"- ΔG binding: {dg:.2f} kcal/mol — "
                f"{'below −6.0 threshold (lab-worthy binding)' if dg <= -6.0 else 'above −6.0 threshold (needs stronger binding)'} [{gate}]"
            )

        if stability is not None:
            lines.append(
                f"- Stability: {stability * 100:.0f}% secondary structure propensity "
                f"({'adequate' if stability >= 0.4 else 'low — consider helix-promoting constraints'})"
            )

        if solubility is not None:
            lines.append(
                f"- Solubility: {solubility * 100:.0f}% GRAVY-based estimate "
                f"({'adequate' if solubility >= 0.4 else 'low — consider high solubility constraint'})"
            )

        lines += [
            "",
            "**Next steps if lab-worthy:**",
            "- Peptide synthesis: solid-phase (SPPS) for sequences ≤ 30 AA",
            "- Binding assay: surface plasmon resonance (SPR) or isothermal titration calorimetry (ITC)",
            "- Cellular assay: IC50 in target-expressing cell line",
            "- If below threshold: re-run with constraint adjustments (see improvement suggestions)",
        ]

        return "\n".join(lines)

    def _suggest_improvement(self, session: DesignSessionContext) -> str:
        seq = session.best_sequence or ""
        dg = session.delta_g_kcal_mol
        kd = session.kd_nM
        stability = session.stability_score
        solubility = session.solubility_score
        lab = session.lab_viability_score

        suggestions = []

        # Binding
        if dg is not None and dg > -6.0:
            suggestions.append(
                "**Binding affinity (ΔG = {:.2f} kcal/mol, below −6 lab threshold):**\n"
                "  - Add aromatic residues F/W/Y at N-terminal positions for π-stacking\n"
                "  - Introduce R/K to anchor against acidic pocket residues\n"
                "  - Constraint: `design with higher binding weight` or `optimize for binding`".format(dg)
            )
        elif dg is not None:
            suggestions.append(
                "**Binding affinity (ΔG = {:.2f} kcal/mol — good):**\n"
                "  - Near-optimal binding; focus on selectivity and stability\n"
                "  - Constraint: `optimize for selectivity` to widen on/off-target ratio".format(dg)
            )

        # Stability
        if stability is not None and stability < 0.45:
            suggestions.append(
                "**Stability ({:.0f}% — below 45% threshold):**\n"
                "  - Reduce Gly/Pro content (breaks helical packing)\n"
                "  - Add Ala, Glu, Leu (strong helix-forming residues)\n"
                "  - Constraint: `optimize for thermostability`".format(stability * 100)
            )

        # Solubility
        if solubility is not None and solubility < 0.40:
            suggestions.append(
                "**Solubility ({:.0f}% — below 40% threshold):**\n"
                "  - Add D/E/K/R residues to break hydrophobic patches\n"
                "  - Reduce ILFVWM content below 35%\n"
                "  - Constraint: `high solubility`".format(solubility * 100)
            )

        # All metrics good — suggest advanced refinements
        if not suggestions:
            suggestions.append(
                "All major metrics are at or above threshold. Advanced refinements:\n"
                "  - Run with `optimize for selectivity` to increase on/off-target ratio\n"
                "  - Try a longer sequence (add 5 residues) for more binding surface\n"
                "  - Introduce `cyclic peptide` modality for improved serum stability\n"
                "  - Add `low immunogenicity` constraint to reduce MHC anchor risk"
            )

        lines = [
            f"**Improvement suggestions for `{seq}`**",
            "",
        ] + suggestions + [
            "",
            "*To apply any of these, type a design command such as:*",
            "*'design with high solubility' or 'optimize for selectivity' or 'run MCMC again'*",
        ]

        return "\n".join(lines)

    def _show_progression(self, session: DesignSessionContext) -> str:
        rounds_summary = list(session.rounds_summary or [])
        seq = session.best_sequence or ""

        if not rounds_summary:
            return (
                f"**Round progression for `{seq}`**\n\n"
                "Round-by-round data is not attached to the current session. "
                "Run a full design cycle — the iteration history table will appear in the chat "
                "and subsequent progression questions will be answered with actual round data."
            )

        lines = [
            f"**Design progression across {len(rounds_summary)} round(s)**",
            "",
            "| Round | ΔG (kcal/mol) | Kd (nM) | Lab Score | Best |",
            "|-------|---------------|---------|-----------|------|",
        ]

        for r in rounds_summary:
            dg_val = r.get("delta_g_binding_kcal_mol")
            kd_val = r.get("kd_nM")
            lab_val = r.get("lab_viability_score")
            dg_str = f"{dg_val:.2f}" if dg_val is not None else "—"
            kd_str = f"{kd_val:.0f}" if kd_val is not None else "—"
            lab_str = f"{lab_val:.0f}" if lab_val is not None else "—"
            star = "best" if r.get("is_best") else ""
            lines.append(f"| {r.get('round', '?')} | {dg_str} | {kd_str} | {lab_str} | {star} |")

        lines += [
            "",
            "Each round seeds from the best candidate of the previous round, with more MCMC steps "
            "and parallel chains for progressively finer convergence.",
        ]

        return "\n".join(lines)

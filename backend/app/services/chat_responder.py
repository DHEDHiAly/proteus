import re
from typing import Optional, Dict, List


class ChatResponder:
    """
    Provides targeted, data-driven answers to user queries about design results.
    Replaces generic echo responses with specific explanations grounded in run data.
    """

    # SOTA binder reference data for comparison queries
    _SOTA: Dict[str, Dict] = {
        'egfrviii': {'drug': 'Erlotinib',       'delta_g': -6.2, 'kd_nM': 120},
        '3gp1':     {'drug': 'Erlotinib',       'delta_g': -6.2, 'kd_nM': 120},
        'pd-l1':    {'drug': 'Pembrolizumab',   'delta_g': -7.1, 'kd_nM': 55},
        '4zqk':     {'drug': 'Pembrolizumab',   'delta_g': -7.1, 'kd_nM': 55},
        'kras_g12c':{'drug': 'Sotorasib',       'delta_g': -7.4, 'kd_nM': 30},
        '6oim':     {'drug': 'Sotorasib',       'delta_g': -7.4, 'kd_nM': 30},
    }

    def respond_to_query(
        self,
        query: str,
        current_run: Optional[dict] = None,
        session_context: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Return a targeted answer if the query matches a result-specific topic,
        else return None (let the caller fall through to Ollama / QA_PAIRS).
        Only activates when we have run data to ground the answer in.
        """
        if not current_run and not session_context:
            return None  # no run data; fall through to generic QA

        q = query.lower()

        if re.search(r'\bwhy\b.*\b(binding|affinity|delta|dg|kcal)\b|'
                     r'\bexplain\b.*\b(binding|affinity|score|result)\b|'
                     r'\bbreakdown\b|\bdecompos\b', q):
            return self._explain_binding(current_run, session_context)

        if re.search(r'\bcompar\b|\bvs\b|\bversus\b|\bbetter\b|\bworse\b|'
                     r'\berlotinib\b|\bpembrolizumab\b|\bsotorasib\b|\bsota\b', q):
            return self._compare_to_sota(current_run, session_context)

        if re.search(r'\bsynthesize|\bsynth\b|\bfeasib|\blab\b|\bcost\b|'
                     r'\btime\b|\bproduc|\bspps\b|\bmake\b', q):
            return self._assess_feasibility(current_run, session_context)

        if re.search(r'\bdelivery\b|\bcell\b|\bnuclear\b|\bpenetrat\b|'
                     r'\bcpp\b|\bnls\b|\bserum\b|\bhalf.life\b', q):
            return self._delivery_guidance(current_run, session_context)

        if re.search(r'\bmutation\b|\bresidue\b|\bposition\b|\bwhich\s+aa\b|'
                     r'\bwhy\s+\w\d\w\b|\banchor\b|\bsalt\s+bridge\b', q):
            return self._explain_mutations(current_run, session_context)

        return None  # no strong match; let caller handle

    # ──────────────────────────────────────────────────────────────────────
    # Private answer builders
    # ──────────────────────────────────────────────────────────────────────

    def _explain_binding(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, components = self._extract_best(run, session)
        if not seq:
            return ("No design results yet. Run a design cycle first to see "
                    "binding affinity predictions.")

        threshold = "✓ meets lab-worthy threshold (< −6.0 kcal/mol)" if dg < -6.0 \
            else "✗ below lab-worthy threshold (< −6.0 kcal/mol needed)"

        vdw  = components.get('delta_g_vdw', 'n/a')
        elec = components.get('delta_g_electrostatic', 'n/a')
        solv = components.get('delta_g_solvation_docking', 'n/a')
        hbe  = components.get('physics_hbond_energy', 'n/a')
        hbc  = components.get('physics_hbond_count', components.get('hbond_count', 'n/a'))
        conf = components.get('docking_confidence', 'geometric approximation')

        def fmt(v):
            return f"{v:.1f}" if isinstance(v, (int, float)) else str(v)

        return (
            f"**Binding Affinity Breakdown for `{seq}`**\n\n"
            f"**Total ΔG: {dg:.1f} kcal/mol** — {threshold}\n\n"
            f"**Energy Components** ({conf}):\n"
            f"• Van der Waals / hydrophobic packing: {fmt(vdw)} kcal/mol\n"
            f"• Electrostatic / salt bridges: {fmt(elec)} kcal/mol\n"
            f"• Solvation (water displacement): {fmt(solv)} kcal/mol\n"
            f"• H-bond energy ({fmt(hbc)} bonds): {fmt(hbe)} kcal/mol\n\n"
            f"**Interpretation:** More negative ΔG = tighter binding. "
            f"AutoDock Vina convention treats ≈ −6 kcal/mol as the lab-ordering threshold. "
            f"These are in-silico estimates; validate with SPR/ITC."
        )

    def _compare_to_sota(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design yet. Run a cycle to get comparisons."

        target_key = ""
        if run:
            target_key = (run.get('target_name') or run.get('target') or '').lower().replace('-', '').replace('_', '')
        elif session:
            target_key = (session.get('target_name') or '').lower().replace('-', '').replace('_', '')

        sota = None
        for key, data in self._SOTA.items():
            if key in target_key or target_key in key:
                sota = data
                break

        if not sota:
            return (
                f"**Your design:** ΔG = {dg:.1f} kcal/mol (`{seq}`)\n\n"
                "No SOTA binder on record for this target. "
                "Compare to published IC50/Kd data for the specific protein."
            )

        sota_dg = sota['delta_g']
        diff = sota_dg - dg  # negative = our design is better (more negative)
        pct = abs(diff / abs(sota_dg)) * 100
        direction = "stronger" if diff < 0 else "weaker"

        return (
            f"**Comparison to {sota['drug']}**\n\n"
            f"| | ΔG (kcal/mol) | Kd |\n"
            f"|---|---|---|\n"
            f"| Your design | {dg:.1f} | (modelled) |\n"
            f"| {sota['drug']} | {sota_dg:.1f} | {sota['kd_nM']} nM |\n\n"
            f"**Result:** {pct:.0f}% {direction} binding than {sota['drug']}.\n\n"
            f"**Important:** this is a computational estimate. "
            f"Actual binding must be validated in wet-lab (SPR, ITC, or competitive binding assay)."
        )

    def _assess_feasibility(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, components = self._extract_best(run, session)
        if not seq:
            return "No design yet. Run a cycle to assess lab feasibility."

        synth_score = components.get('synthesis_feasibility_score',
                                     components.get('lab_viability_score', 0))
        issues       = components.get('synthesis_issues', [])
        recs         = components.get('synthesis_recommendations', [])
        time_d       = components.get('estimated_synthesis_time_days')
        cost_usd     = components.get('estimated_synthesis_cost_usd')

        time_str = f"{time_d} days" if time_d is not None else "~3–7 days (estimate)"
        cost_str = f"${cost_usd:,}" if cost_usd is not None else "~$1,000–3,000 (estimate)"

        issues_text = '\n'.join(f"• {i}" for i in issues[:4]) if issues else "• None identified"
        recs_text   = '\n'.join(f"• {r}" for r in recs[:3]) if recs else "• Proceed to synthesis"

        return (
            f"**Lab Synthesis Feasibility: {synth_score:.0f}/100**\n\n"
            f"⏱ Estimated synthesis time: {time_str}\n"
            f"💰 Estimated cost: {cost_str}\n\n"
            f"**Issues to resolve:**\n{issues_text}\n\n"
            f"**Recommendations:**\n{recs_text}\n\n"
            f"*Costs based on standard SPPS; recombinant expression or fragment ligation "
            f"may differ. Consult your synthesis provider.*"
        )

    def _delivery_guidance(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, components = self._extract_best(run, session)
        target = ""
        if run:
            target = (run.get('target_name') or '').upper()
        elif session:
            target = (session.get('target_name') or '').upper()

        net_charge = components.get('net_charge', 0)
        serum_hl   = components.get('serum_half_life_min', 'n/a')

        # Nuclear/cytoplasmic delivery note
        nuclear_targets = {'EGFRVIII', 'C-MYC', 'P53', 'KRAS_G12C'}
        is_nuclear = any(nt in target for nt in nuclear_targets)
        nuclear_note = (
            "**Nuclear delivery needed:** This target resides in the cytoplasm/nucleus. "
            "Conjugate a nuclear localisation signal (NLS, e.g. PKKKRKV) or use "
            "endosome-escaping lipid nanoparticles (LNPs).\n"
        ) if is_nuclear else ""

        hl_str = f"{serum_hl:.0f} min" if isinstance(serum_hl, (int, float)) else str(serum_hl)

        return (
            f"**Delivery Considerations for {target or 'this target'}**\n\n"
            f"{nuclear_note}"
            f"**Serum stability:** estimated half-life {hl_str} "
            f"(unmodified linear peptides typically <20 min).\n\n"
            f"**Recommended delivery enhancements:**\n"
            f"• Cyclisation (disulfide or head-to-tail) — protease resistance\n"
            f"• D-amino acid substitutions at P1/P1ʹ sites — serine protease block\n"
            f"• CPP fusion (TAT, poly-Arg) — cellular uptake\n"
            f"• PEGylation — renal clearance reduction, longer circulation\n\n"
            f"Net charge of current design: {net_charge:+.1f}. "
            f"{'Positive charge supports membrane crossing.' if net_charge > 0 else 'Anionic peptides typically need CPP conjugation.'}"
        )

    def _explain_mutations(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet."

        mutation_lines = []
        if run and run.get('mutations'):
            for m in run['mutations'][:5]:
                f, t, pos = m.get('from', '?'), m.get('to', '?'), m.get('position', '?')
                mutation_lines.append(f"• **{f}{pos}{t}**: {m.get('explanation', 'see physics justification')}")
        elif session and session.get('mutations'):
            for m in session['mutations'][:5]:
                f, t, pos = m.get('from', '?'), m.get('to', '?'), m.get('position', '?')
                mutation_lines.append(f"• **{f}{pos}{t}**: {m.get('explanation', 'see physics justification')}")

        if not mutation_lines:
            return (
                f"**Design `{seq}`** — no mutation log available for this session. "
                "Run a fresh design cycle and mutations will be shown per-round with "
                "BLOSUM62 conservatism scores and energy deltas."
            )

        # AA-specific notes
        notes = []
        if 'W' in seq:
            notes.append(f"Trp (W) ×{seq.count('W')}: hydrophobic anchor via π-stacking with pocket aromatics")
        if seq.count('K') + seq.count('R') > 1:
            notes.append(f"Lys/Arg ×{seq.count('K')+seq.count('R')}: salt bridges with target acidic residues")
        if seq.count('C') >= 2:
            notes.append("Cys pair: enables disulfide cyclisation → reduced conformational entropy")

        return (
            f"**Mutation rationale for `{seq}`** (ΔG {dg:.1f} kcal/mol):\n\n"
            + '\n'.join(mutation_lines)
            + ('\n\n**Key residue roles:**\n' + '\n'.join(f"• {n}" for n in notes) if notes else '')
        )

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _extract_best(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ):
        """Return (sequence, delta_g, full_components_dict)."""
        seq = dg = None
        components: dict = {}

        if run:
            best = run.get('best_candidate') or (run.get('candidates') or [{}])[0]
            seq = best.get('sequence') or run.get('best_sequence')
            dg  = best.get('delta_g_binding_kcal_mol') or run.get('delta_g_binding_kcal_mol')
            components = dict(best)
            # Merge run-level keys so they're accessible in components too
            components.update({k: v for k, v in run.items() if k not in components})

        if not seq and session:
            seq = session.get('best_sequence')
            dg  = session.get('delta_g_kcal_mol')
            # Use session as component source when no run is available
            components = dict(session)

        if dg is None:
            dg = -5.5  # safe fallback

        return seq, float(dg), components

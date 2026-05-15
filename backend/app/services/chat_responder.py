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
                     r'\bbreakdown\b|\bdecompos\b|'
                     r'\bkcal\b|\bdelta[_\s]*g\b|\bdg\b|'
                     r'\bwhat\b.*\b(binding\s+affinity|affinity|delta|energy)\b|'
                     r'\bbinding\s+(affinity|energy|strength)\b', q):
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

        if re.search(r'\bselect|\boff.target|\btoxic|\breaction\b', q):
            return self._assess_selectivity(current_run, session_context)

        if re.search(r'\bescape|\bresist|\bmutation\s+resistant\b|\bhard.to|robustness\b', q):
            return self._assess_escape_resistance(current_run, session_context)

        if re.search(r'\bpk\b|\bpd\b|\bpharmaco|\bhalf.life|stability\b|circulation\b', q):
            return self._assess_pk_pd(current_run, session_context)

        if re.search(r'\bimmun|\bathigen|\bepitope|\bmhc\b|\bflag\b', q):
            return self._assess_immunogenicity(current_run, session_context)

        if re.search(r'\bcost|\bprice|\bbudget|\bafford|\bcheap|\bexpensive\b', q):
            return self._assess_cost_optimization(current_run, session_context)

        if re.search(r'\bconstraint|\bfixed|\brequire|\bforbid|\bstructural\b', q):
            return self._assess_constraint_satisfaction(current_run, session_context)

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
                if isinstance(m, dict):
                    f, t, pos = m.get('from', '?'), m.get('to', '?'), m.get('position', '?')
                    mutation_lines.append(f"• **{f}{pos}{t}**: {m.get('explanation', 'see physics justification')}")
                elif isinstance(m, str):
                    mutation_lines.append(f"• **{m}**")
        elif session and session.get('mutations'):
            for m in session['mutations'][:5]:
                if isinstance(m, dict):
                    f, t, pos = m.get('from', '?'), m.get('to', '?'), m.get('position', '?')
                    mutation_lines.append(f"• **{f}{pos}{t}**: {m.get('explanation', 'see physics justification')}")
                elif isinstance(m, str):
                    mutation_lines.append(f"• **{m}**")

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

    def _assess_selectivity(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle to assess selectivity."

        selectivity_score = (run or session or {}).get('selectivity_score', 50.0)
        problematic = (run or session or {}).get('problematic_off_targets', [])
        escape_resistant = (run or session or {}).get('is_escape_resistant', False)

        status_emoji = "✓" if selectivity_score >= 70 else "⚠" if selectivity_score >= 50 else "✗"
        status_text = "strong" if selectivity_score >= 70 else "moderate" if selectivity_score >= 50 else "weak"

        return (
            f"**Selectivity Profile: {selectivity_score:.0f}/100** ({status_emoji} {status_text})\n\n"
            f"**Target binding:** ΔG = {dg:.1f} kcal/mol\n\n"
            f"**Problematic off-targets:** {', '.join(problematic) if problematic else 'None identified'}\n\n"
            f"**Interpretation:** Selectivity score measures preference for on-target over 20+ reference off-targets "
            f"(kinases, related proteins). "
            f"{'⚠ High cross-reactivity risk — consider pocket-specificity optimization.' if problematic else '✓ No major off-target liabilities.'}\n\n"
            f"**Recommendation:** Validate selectivity experimentally (kinase panel, SPR multi-target) "
            f"before advancing to in-vivo studies."
        )

    def _assess_escape_resistance(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle to assess escape resistance."

        escape_score = (run or session or {}).get('escape_score', 0.5)
        is_resistant = (run or session or {}).get('is_escape_resistant', False)
        top_escapes = (run or session or {}).get('top_escape_variants', [])

        status_text = "hard to escape" if is_resistant else "moderate escape risk"
        status_emoji = "✓" if is_resistant else "⚠"

        escape_lines = []
        for i, escape in enumerate(top_escapes[:5], 1):
            pos = escape.get('position', '?')
            mut = escape.get('mutation', '?')
            escape_lines.append(f"{i}. **{mut}** (position {pos})")

        return (
            f"**Escape Resistance: {escape_score:.2f}/1.0** ({status_emoji} {status_text})\n\n"
            f"**Design sequence:** `{seq}` (ΔG {dg:.1f} kcal/mol)\n\n"
            f"**Top single-mutation escape variants:**\n"
            + ('\n'.join(f"• {line}" for line in escape_lines) if escape_lines else "• None found (highly robust)")
            + f"\n\n**Interpretation:** Escape score (0–1) quantifies how many positions can tolerate mutations "
            f"while maintaining on-target binding. "
            f"{'Lower scores = harder to escape (better for cancer therapy).' if is_resistant else 'Consider design iteration for improved resistance.'}\n\n"
            f"**Recommendations:**\n"
            f"• Target escape-sensitive positions (low mutational tolerance) for binding lock-down\n"
            f"• Screen resistance against known kinase mutations from your disease model"
        )

    def _assess_pk_pd(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle to assess PK/PD properties."

        serum_hl = (run or session or {}).get('estimated_serum_half_life_min', 20.0)
        bbb_feasible = (run or session or {}).get('bbb_penetration_feasible', False)
        tissue_risk = (run or session or {}).get('tissue_accumulation_risk', False)
        net_charge = (run or session or {}).get('net_charge', 0)

        hl_category = "very short" if serum_hl < 20 else "short" if serum_hl < 60 else "moderate" if serum_hl < 120 else "long"

        bbb_status = "Yes — potential CNS target engagement" if bbb_feasible else "No — requires peripheral targeting strategy"
        tissue_status = "⚠ Yes — monitor liver/spleen accumulation" if tissue_risk else "✓ No — distributed clearance expected"

        return (
            f"**Pharmacokinetics: `{seq}`**\n\n"
            f"**Serum half-life:** ~{serum_hl:.0f} min ({hl_category})\n"
            f"• Unmodified linear peptides: <20 min (protease degradation)\n"
            f"• Cyclization (disulfide, if Cys ≥2): +50–200% boost\n"
            f"• PEGylation (if charge-neutral): +300% boost to circulation\n\n"
            f"**BBB penetration feasible:** {bbb_status}\n\n"
            f"**Tissue accumulation risk:** {tissue_status}\n\n"
            f"**Net charge:** {net_charge:+.0f} — "
            f"{'Positive charge supports membrane crossing.' if net_charge > 0 else 'Anionic; needs CPP/NLS for intracellular delivery.' if net_charge < 0 else 'Neutral charge; consider CPP fusion for uptake.'}\n\n"
            f"**Recommended modifications for clinical PK:**\n"
            f"• Disulfide cyclization (if Cys ≥2): protease resistance\n"
            f"• D-amino acid substitutions: serine protease block\n"
            f"• C-terminal 40-kDa PEGylation: 2–4 hour serum half-life target\n"
            f"• CPP fusion (TAT, poly-Arg): cellular uptake in target cells"
        )

    def _assess_immunogenicity(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle to assess immunogenicity."

        immuno_score = (run or session or {}).get('immunogenicity_score', 0.0)
        high_risk = (run or session or {}).get('is_high_immunogenic_risk', False)
        motifs = (run or session or {}).get('immunogenic_motifs_found', [])
        mhc_risk = (run or session or {}).get('mhc_epitope_risk', 'low')

        status_emoji = "✓" if immuno_score < 30 else "⚠" if immuno_score < 60 else "✗"
        status_text = "low" if immuno_score < 30 else "moderate" if immuno_score < 60 else "high"

        return (
            f"**Immunogenicity Risk: {immuno_score:.0f}/100** ({status_emoji} {status_text})\n\n"
            f"**Design sequence:** `{seq}` (ΔG {dg:.1f} kcal/mol)\n\n"
            f"**MHC epitope risk:** {mhc_risk}\n"
            f"**Immunogenic motifs found:** {', '.join(motifs) if motifs else 'None'}\n\n"
            f"**Interpretation:** High immunogenicity score (>60) indicates strong T-cell epitope potential "
            f"or innate immunity triggers (toll-like receptors, protease motifs, aggregation risk).\n\n"
            f"**Risk factors:**\n"
            f"• MHC-binding anchors (hydrophobic K/R/W clusters)\n"
            f"• Known immunogenic peptide motifs (LMWKY, FPWRK, etc.)\n"
            f"• Protease-sensitive sequences (GLG, RXR patterns → activate innate immunity)\n"
            f"• Immunogenic tags (FLAG, His-tag, HA)\n\n"
            f"**De-risking strategies:**\n"
            f"• Disrupt MHC anchors: substitute K/R → S/T at high-risk positions\n"
            f"• Add N-glycosylation sites (NXS/NXT) for immune masking\n"
            f"• Balance charge (target net +0 to +3) to reduce aggregation\n"
            f"• Remove protease-sensitive motifs (add D-amino acids)\n"
            f"• Humanization: replace rodent-specific motifs with human codon usage\n\n"
            f"**Next step:** Validate with MHC-peptide binding prediction (NetMHC, MHCflurry) "
            f"and immunology assays (T-cell activation, cytokine response)."
        )

    def _assess_cost_optimization(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle for cost analysis."

        cost_usd = (run or session or {}).get('estimated_synthesis_cost_usd', 1000.0)
        cost_score = (run or session or {}).get('cost_score', 50.0)
        affinity_cost_ratio = (run or session or {}).get('affinity_cost_ratio', 0.0)
        pareto_rec = (run or session or {}).get('pareto_recommendation', '')
        lab_score = (run or session or {}).get('lab_viability_score', 0.0)

        dg_absolute = abs(dg)
        value_per_dollar = dg_absolute / (cost_usd / 1000.0) if cost_usd > 0 else 0

        return (
            f"**Cost-Affinity Trade-off Analysis**\n\n"
            f"**Design:** `{seq}` (ΔG {dg:.1f} kcal/mol | Lab viability {lab_score:.0f}/100)\n\n"
            f"**Estimated synthesis cost:** ${cost_usd:,.0f}\n"
            f"**Cost efficiency score:** {cost_score:.0f}/100 (100 = cheapest)\n"
            f"**Affinity per dollar:** {value_per_dollar:.3f} kcal/mol per $1k\n"
            f"**Pareto recommendation:** {pareto_rec}\n\n"
            f"**Cost drivers:**\n"
            f"• Sequence length: +$20/aa (standard SPPS rate)\n"
            f"• Cysteines: +30% (disulfide management)\n"
            f"• Prolines: +20% (coupling delays)\n"
            f"• Aromatics (W/F/Y): +15% (purification difficulty)\n\n"
            f"**Budget scenarios:**\n"
            f"• <$1k: Optimal for academic discovery; limited iterations\n"
            f"• $1–2k: Commercial sweet spot; balances affinity + feasibility\n"
            f"• >$2k: Premium affinity; consider recombinant expression for <30 aa\n\n"
            f"**Optimization for cost:**\n"
            f"• Replace W → Y, F → L (reduce aromatics)\n"
            f"• Avoid Cys unless disulfide lock essential\n"
            f"• Keep length ≤15 aa (under $800)\n"
            f"• Replace Pro with A/G if flexibility acceptable"
        )

    def _assess_constraint_satisfaction(
        self,
        run: Optional[dict],
        session: Optional[dict],
    ) -> str:
        seq, dg, _ = self._extract_best(run, session)
        if not seq:
            return "No design results yet. Run a design cycle to check constraints."

        constraint_score = (run or session or {}).get('constraint_satisfaction_score', 100.0)
        all_satisfied = (run or session or {}).get('all_constraints_satisfied', True)
        num_violations = (run or session or {}).get('num_constraint_violations', 0)

        status_emoji = "✓" if all_satisfied else "⚠" if constraint_score > 50 else "✗"

        return (
            f"**Structural Constraint Satisfaction: {constraint_score:.0f}/100** ({status_emoji})\n\n"
            f"**Design sequence:** `{seq}` (ΔG {dg:.1f} kcal/mol)\n\n"
            f"**Constraint violations:** {num_violations}\n"
            f"**All constraints satisfied:** {'Yes ✓' if all_satisfied else 'No — see violations below'}\n\n"
            f"**Interpretation:** Constraint satisfaction score measures how well the design respects "
            f"user-specified structural requirements (fixed residues, forbidden positions, motif requirements, "
            f"secondary structure preference).\n\n"
            f"**To add constraints for next round:**\n"
            f"• Fixed residues: \"Keep K5 and R12 constant\"\n"
            f"• Forbidden positions: \"No Pro in positions 3–7\"\n"
            f"• Required motifs: \"Must contain WXXK\"\n"
            f"• Secondary structure: \"Prefer α-helix\" or \"Require β-sheet at C-terminus\"\n"
            f"• Length: \"Target 12–15 amino acids\"\n\n"
            f"**Note:** Constraints guide MCMC sampling but are enforced post-design. "
            f"If satisfied score is low, the design space may not support all constraints simultaneously; "
            f"consider relaxing least-critical requirements."
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

import { useState, useRef, useEffect, FormEvent, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { PatientInfo, AgentMessage, AgentRunResponse, DesignSessionContext } from '../types/agent';
import { agentApi } from '../services/agent';
import { useAuth } from '../hooks/useAuth';
import PatientForm from '../components/PatientForm';
import FileUpload from '../components/FileUpload';
import ResultsPanel from '../components/ResultsPanel';
import DesignCycleSummary from '../components/DesignCycleSummary';
import BenchmarkGraphs from '../components/BenchmarkGraphs';
import CommandPalette, { useCommandPalette } from '../components/CommandPalette';
import OptimizationTrace from '../components/OptimizationTrace';
import { savedDesignsService } from '../services/savedDesigns';
import type { SavedDesign } from '../services/savedDesigns';

// ── Frontend Q&A routing ──────────────────────────────────────────────────────
// Architecture:
//  1. DESIGN_RE match  → call backend (MCMC) — design requests only
//  2. QA_PAIRS match   → answer locally (biophysics education, no session needed)
//  3. Session present  → buildSessionReply() with actual session data
//  4. Fallback         → call backend for static QA (no session, unknown topic)
// This means conversational messages NEVER trigger MCMC regardless of backend state.

// Mirrors backend _DESIGN_TRIGGERS.  Only messages matching this start an MCMC cycle.
const DESIGN_RE = /\bdesign\b|\boptimize\b|\bgenerate\b|\bcreate\b|\brun\s+(mcmc|again|another|more|a\s+new)\b|\bmake\s+.{0,20}(protein|peptide|sequence|candidate)\b|\bfind\s+.{0,20}(binder|sequence|candidate)\b|\btry\s+(again|another|with|a\s+different)\b|\bstart\s+(over|again|a\s+new)\b|\bnew\s+(candidate|sequence)\b/i;

const QA_PAIRS: [RegExp, string][] = [
  [/how\s+does\s+(this|the|your|that)\s+treatment\s+work|how\s+does\s+treatment\s+work|treatment\s+work\??|what\s+is\s+(this|the)\s+treatment|clinical\s+treatment\s+plan|how\s+would\s+treatment\s+(work|go)|mechanism\s+of\s+(the\s+)?treatment/i,
    "**What \"treatment\" means in Proteus**\n\nProteus does **not** prescribe real-world therapy. It proposes **in-silico** peptide sequences and scores for **research only**.\n\n**Molecule intent:** sequences target the protein in the viewer; wet-lab validation is required.\n\n**Patient care:** only clinicians can plan real treatment.\n\nTo run another design pass, say **design a peptide** or **optimise for solubility**."],
  [/what\s+(can|does|is|do)\s+(you|it|this|proteus)\b|what\s+do\s+you\s+do|how\s+to\s+use|tell\s+me\s+about\s+(yourself|proteus|this)/i,
    "**What Proteus Does**\n\nGiven patient clinical information, Proteus:\n- Resolves the molecular target (EGFRvIII, PD-L1, KRAS G12C, SARS-CoV-2 3CL)\n- Runs 3 rounds of MCMC design across parallel temperature chains\n- Scores each candidate on 8+ biophysical objectives (ΔG, Kd, stability, solubility, selectivity, immunogenicity, aggregation, half-life)\n- Returns the best sequence with full mutation rationale and Triple-Gate physics checks\n\nTo start a design run, say something like 'design a peptide' or 'optimize for high solubility'."],
  [/delta\s*g|binding\s+free\s+energ|\bdg\b.*binding/i,
    "**ΔG Binding** — Gibbs free energy of binding (kcal/mol). More negative = stronger:\n- < −9: strong  ·  −7 to −9: good  ·  −6 to −7: promising  ·  > −6: weak\nCalculated as ΔG = RT·ln(Kd) at body temperature (310 K)."],
  [/how\s+does\s+(it|this|the\s+platform|the\s+system|everything)\s+work/i,
    "**How Proteus works**\n\n1. Clinical context → resolved target (built-in or custom PDB).\n2. Several MCMC rounds (Metropolis–Hastings + parallel tempering) mutate the sequence.\n3. A composite oracle scores binding proxy, stability, solubility, charge, aggregation, etc.\n4. You get ranked sequences, mutations, and a 3D viewer — not a clinical plan.\n\n**Note:** in-silico scores are hypotheses until validated (e.g. SPR/ITC). Many docking workflows treat ~−6 kcal/mol or better as worth ordering for follow-up."],
  [/\bkd\b|dissociation\s+constant|binding\s+affinity/i,
    "**Kd (Dissociation Constant)** — lower = tighter binding:\n- < 1 nM: ultra-high  ·  1–10 nM: drug-like  ·  10–100 nM: high  ·  > 1 μM: weak\nProteus estimates Kd from ΔG = RT·ln(Kd) via the multi-objective energy oracle."],
  [/\bmcmc\b|markov\s+chain|monte\s+carlo|how\s+does\s+(proteus|mcmc)\s+work/i,
    "**How Proteus works**\nMetropolis-Hastings MCMC across parallel temperature chains (0.5 → 10):\n1. Proposes residue mutations at each step\n2. Accepts improvements greedily; accepts bad moves probabilistically at high temperature\n3. Runs 3 rounds; returns the best candidate across all chains\nR-hat < 1.05 = converged. ESS measures chain mixing quality."],
  [/\bplddt\b|structural\s+confidence/i,
    "**pLDDT** — structural confidence proxy (0–100):\n- > 90: ordered  ·  70–90: confident  ·  50–70: partly disordered  ·  < 50: likely disordered"],
  [/\bddg\b|thermostab/i,
    "**Stability** — secondary structure propensity (helix + sheet content, %). ΔΔG < 0 = more stable than unfolded. Use 'thermostable' constraint to increase the stability weight."],
  [/\bselectivit\b|off.target/i,
    "**Selectivity ratio** = on-target / off-target binding. > 5x: highly selective  ·  2–5x: acceptable  ·  < 2x: toxicity flag raised."],
  [/triple.gate|gate\s*[123]|enthalpic|solvation\s+gate|entropic/i,
    "**Triple-Gate Physics Model**\n- Gate 1 Enthalpic Locking: surface complementarity Sc ≥ 0.4\n- Gate 2 Solvation: ΔG_solv ≤ 0 kcal/mol\n- Gate 3 Entropic Penalty: −TΔS ≤ 3.5 kcal/mol\nAll three must pass for a lab-worthy candidate."],
  [/\br.hat\b|rhat|convergence|ess\b|effective\s+sample/i,
    "**Convergence diagnostics**\n- R-hat < 1.05 = chains converged  ·  > 1.1 = not converged\n- ESS (Effective Sample Size): higher = better mixing. ESS/steps > 0.1 is acceptable."],
  [/\baggregat\b/i,
    "**Aggregation** — estimated from hydrophobic stretch length (I/L/F/V/W/M runs ≥ 4 residues). Use 'low aggregation' constraint to increase the penalty."],
  [/\bimmunogen\b|\bmhc\b|immune/i,
    "**Immunogenicity** — estimated from MHC anchor motif frequency. High K/R + F/Y/W at anchor positions = higher risk. Use 'low immunogenicity' constraint."],
  [/serum\s+half.life|half.life|\bt1\/2\b|pharmacokinetic/i,
    "**Serum half-life** — estimated from sequence length and composition:\n- Peptides < 10 AA: 10–30 min  ·  Miniproteins: 30–120 min  ·  Nanobodies: 60–240 min"],
];

// Returns a local answer for known biophysics topics; null → goes to session reply or backend.
function getQAAnswer(msg: string): string | null {
  for (const [pattern, answer] of QA_PAIRS) {
    if (pattern.test(msg)) return answer;
  }
  return null;
}

// ── Session-grounded chat responses ───────────────────────────────────────────
// These use the actual designSession data to answer questions about the current
// peptide without a backend round-trip (and therefore cannot trigger MCMC).

function _dgLabel(dg: number): string {
  if (dg <= -9) return 'strong binder';
  if (dg <= -7) return 'good binder';
  if (dg <= -6) return 'promising — meets the −6 kcal/mol lab-ordering threshold';
  return 'weak binder — below the −6 kcal/mol lab threshold';
}
function _kdLabel(kd: number): string {
  if (kd < 1) return 'ultra-high affinity';
  if (kd < 10) return 'drug-like affinity';
  if (kd < 100) return 'high affinity';
  if (kd < 1000) return 'moderate affinity';
  return 'weak affinity';
}

function buildFullSummary(session: DesignSessionContext, patient: PatientInfo | null): string {
  const seq = session.best_sequence || '';
  const target = session.target_name || patient?.tumor_markers || patient?.cancer_type || 'target';
  const dg = (session.delta_g_kcal_mol && session.delta_g_kcal_mol !== 0) ? session.delta_g_kcal_mol : null;
  const binding = session.binding_score;
  const kd = session.kd_nM && session.kd_nM !== 0 ? session.kd_nM : null;
  const stab = session.stability_score;
  const sol = session.solubility_score;
  const lab = session.lab_viability_score;

  const lines: string[] = [`**Current design: \`${seq}\` targeting ${target}**`, ''];

  if (dg !== null) {
    lines.push(`- **ΔG binding:** ${dg.toFixed(2)} kcal/mol — ${_dgLabel(dg)}`);
  } else if (binding !== null && binding !== undefined) {
    // Binding proxy is a 0–1 relative score from the MCMC oracle
    const pct = (binding * 100).toFixed(1);
    const grade = binding >= 0.8 ? 'strong' : binding >= 0.65 ? 'good' : binding >= 0.5 ? 'moderate' : 'weak';
    lines.push(`- **Binding proxy:** ${pct}% — ${grade} (oracle's relative on-target score; ΔG not computed for this run)`);
  }

  if (kd !== null) {
    lines.push(`- **Kd:** ${kd.toFixed(0)} nM — ${_kdLabel(kd)}`);
  }

  if (stab !== null && stab !== undefined) {
    const stabPct = (stab * 100).toFixed(0);
    const stabFlag = stab >= 0.5 ? 'adequate' : 'low — consider adding the **thermostable** constraint';
    lines.push(`- **Stability:** ${stabPct}% secondary structure propensity (${stabFlag})`);
  }

  if (sol !== null && sol !== undefined) {
    const solPct = (sol * 100).toFixed(0);
    const solFlag = sol >= 0.5 ? 'adequate' : 'low — consider **high solubility** constraint';
    lines.push(`- **Solubility:** ${solPct}% GRAVY-based estimate (${solFlag})`);
  }

  if (lab !== null && lab !== undefined) {
    const verdict = lab >= 70 ? 'lab-worthy — proceed to synthesis' : lab >= 50 ? 'borderline — address failing Triple-Gate checks first' : 'below threshold — significant optimization required';
    lines.push(`- **Lab viability:** ${lab.toFixed(0)}/100 — ${verdict}`);
  }

  if (dg !== null && kd !== null) {
    lines.push('', '**Relationship:** ΔG = RT·ln(Kd) at 310 K. More negative ΔG = lower Kd = tighter binding.');
  }

  lines.push('', '*Scores are in-silico estimates from the MCMC oracle. Validate with SPR, ITC, or a competitive binding assay before lab hand-off.*');
  lines.push('', 'To improve: say **optimize for binding**, **high solubility**, **thermostable**, or **run MCMC again**.');
  return lines.join('\n');
}

function buildMutationReply(session: DesignSessionContext, patient: PatientInfo | null): string {
  const seq = session.best_sequence || '';
  const seed = session.seed_sequence || '';
  const target = session.target_name || patient?.tumor_markers || patient?.cancer_type || 'target';
  const muts = session.mutations_from_seed || [];

  if (!seq) return 'No design session active. Run a design cycle first.';

  const lines: string[] = [`**Mutations in \`${seq}\` vs seed (${target})**`, ''];

  if (muts.length === 0) {
    lines.push('No mutations recorded — sequence matches seed exactly, or mutation data was not captured for this run.');
  } else {
    lines.push(`${muts.length} mutation${muts.length !== 1 ? 's' : ''} from seed${seed ? ` (\`${seed}\`)` : ''}:`);
    muts.forEach((m) => lines.push(`- **${m}**`));
    lines.push('', 'Each mutation was accepted by the MCMC sampler because it improved the composite energy score (binding + stability + solubility + penalties).');
  }

  lines.push('', 'To explore different mutations, say **optimize for binding** or **run MCMC again**.');
  return lines.join('\n');
}

function buildImprovementReply(session: DesignSessionContext, _patient: PatientInfo | null): string {
  const dg = (session.delta_g_kcal_mol && session.delta_g_kcal_mol !== 0) ? session.delta_g_kcal_mol : null;
  const binding = session.binding_score;
  const stab = session.stability_score ?? 0;
  const sol = session.solubility_score ?? 0;
  const lab = session.lab_viability_score ?? 0;

  const suggestions: string[] = [];

  // Rank the weakest area
  if (dg !== null && dg > -6) {
    suggestions.push('**Binding** is below the −6 kcal/mol lab-ordering threshold. Try: **optimize for binding** or increase aromatic/hydrophobic residue content (W, F, Y at binding-pocket positions).');
  } else if (binding !== null && binding !== undefined && binding < 0.65) {
    suggestions.push('**Binding proxy** is moderate. Try: **optimize for binding** or say **run MCMC again** with a longer run.');
  }

  if (stab < 0.5) {
    suggestions.push('**Stability** is low. Try: add **thermostable** constraint, or reduce flexible Gly/Pro content in the middle of the sequence.');
  }

  if (sol < 0.5) {
    suggestions.push('**Solubility** is low. Try: add **high solubility** constraint to increase D/E/K/R content and reduce hydrophobic stretches.');
  }

  if (lab < 70) {
    const msg = lab < 50
      ? '**Lab viability** is below threshold. Check Triple-Gate physics: surface complementarity, solvation ΔG, and entropic penalty. Try: **optimize for binding** with the thermostable + high solubility constraints together.'
      : '**Lab viability** is borderline (50–70). One or more Triple-Gate checks are failing. Try a focused re-run: **optimize for solubility** or **optimize for stability**.';
    suggestions.push(msg);
  }

  if (suggestions.length === 0) {
    return `**This design looks solid across all metrics.** To push further:\n- Say **run MCMC again** for another optimization pass\n- Try **optimize for binding** with a tighter temperature schedule\n- Consider ordering for wet-lab validation (SPR binding assay, thermal shift, SPPS synthesis)`;
  }

  return `**Suggested improvements for the current design:**\n\n${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n\n')}`;
}

function buildViabilityReply(session: DesignSessionContext, _patient: PatientInfo | null): string {
  const lab = session.lab_viability_score;
  const seq = session.best_sequence || '';

  if (lab === null || lab === undefined) {
    return `No lab viability score available for \`${seq}\`. Run a design cycle first.`;
  }

  let verdict: string;
  if (lab >= 70) {
    verdict = `**Lab-worthy.** Score ${lab.toFixed(0)}/100 — this candidate passes the lab viability threshold. It is a reasonable candidate for SPPS synthesis, SPR binding assay, and cell-based validation.`;
  } else if (lab >= 50) {
    verdict = `**Borderline.** Score ${lab.toFixed(0)}/100 — one or more Triple-Gate physics checks are likely failing. Address stability or solubility before ordering synthesis. Try **optimize for solubility** or **thermostable** constraint.`;
  } else {
    verdict = `**Below threshold.** Score ${lab.toFixed(0)}/100 — significant optimization required before lab consideration. Try **optimize for binding** with high solubility and thermostable constraints together.`;
  }

  return `**Lab viability for \`${seq}\`**\n\n${verdict}\n\n*Triple-Gate checks: (1) surface complementarity ≥ 0.4, (2) solvation ΔG ≤ 0, (3) entropic penalty ≤ 3.5 kcal/mol. All three must pass for a lab-worthy score.*`;
}

/**
 * Returns a session-grounded reply for conversational questions about the current
 * design.  Returns null for questions that should go to the backend (mechanism,
 * general biophysics education, etc.) or when no session is active.
 */
function buildSessionReply(
  msg: string,
  session: DesignSessionContext | null,
  patient: PatientInfo | null,
): string | null {
  if (!session?.best_sequence) return null;

  const lower = msg.toLowerCase();

  // Score / metric / binding / result questions
  if (/\bscore[s]?\b|\bmetric[s]?\b|\bresult[s]?\b|\bvalue[s]?\b|\bkcal\b|\bdelta[_\s]*g\b|\bdg\b|\bkd\b|\bdissociation\b|\baffinity\b|\bbinding\b|\bstabilit\b|\bsolubil\b|\blab\s*(viab|worth|score)\b|\bviability\b|\bnumber[s]?\b|\bstat[s]?\b|\bsummar\b|\boverview\b|\breport\b/.test(lower)) {
    // Route sub-topics
    if (/\bviab|\blab.?(worth|score)\b/.test(lower) && !/\bscore[s]?\b|\bmetric[s]?\b|\bkcal\b|\bdelta[_\s]*g\b|\bkd\b/.test(lower)) {
      return buildViabilityReply(session, patient);
    }
    if (/\bsolubil\b/.test(lower) && !/\bscore[s]?\b|\bmetric[s]?\b|\bkcal\b|\bdelta[_\s]*g\b/.test(lower)) {
      const sol = session.solubility_score;
      if (sol !== null && sol !== undefined) {
        const pct = (sol * 100).toFixed(0);
        const flag = sol >= 0.5 ? 'adequate' : 'low — consider **high solubility** constraint';
        return `**Solubility for \`${session.best_sequence}\`:** ${pct}% (GRAVY-based estimate — ${flag})\n\nHigh D/E/K/R content improves solubility. Hydrophobic stretches (I/L/F/V/W/M ≥ 4 residues) reduce it.\n\nTo improve: say **optimize for high solubility**.`;
      }
    }
    if (/\bstabilit\b/.test(lower) && !/\bscore[s]?\b|\bmetric[s]?\b|\bkcal\b|\bdelta[_\s]*g\b/.test(lower)) {
      const stab = session.stability_score;
      if (stab !== null && stab !== undefined) {
        const pct = (stab * 100).toFixed(0);
        const flag = stab >= 0.5 ? 'adequate' : 'low — consider **thermostable** constraint';
        return `**Stability for \`${session.best_sequence}\`:** ${pct}% secondary structure propensity (${flag})\n\nSecondary structure content (helix + sheet) is used as a stability proxy. Low Gly/Pro content and balanced hydrophobic core improve it.\n\nTo improve: say **thermostable** in your next design request.`;
      }
    }
    return buildFullSummary(session, patient);
  }

  // Mutation questions
  if (/\bmutation[s]?\b|\bchanged?\b|\bmodif\b|\bdiff(er)?\b|\bresidue[s]?\b|\bsubstitut\b|\bwhat\s+(were|are|is)\s+the\s+(change|mutation|residue)\b/.test(lower)) {
    return buildMutationReply(session, patient);
  }

  // Improvement / next-steps questions
  if (/\bimprove?\b|\boptimize?\b|\benhance\b|\bbetter\b|\bboost\b|\bnext\s+step[s]?\b|\bwhat\s+(can|should|would|could)\b/.test(lower) && !/\bdesign\b|\brun\b|\bgenerate\b/.test(lower)) {
    return buildImprovementReply(session, patient);
  }

  // Lab / synthesis readiness
  if (/\blab\s*(read|worth|viab|synth)\b|\bsynth\b|\bspps\b|\border\b|\bfeasib\b|\bready\b/.test(lower)) {
    return buildViabilityReply(session, patient);
  }

  // General "tell me about this" / "what is the current design" / "how is it doing"
  if (/\b(current|best|latest|this)\s+(design|peptide|candidate|sequence)\b|\btell\s+me\b|\bhow\s+is\s+(it|this|the\s+(design|peptide|candidate))\b|\bwhat\s+(is\s+)?(the\s+)?(current|best|latest)\b/.test(lower)) {
    return buildFullSummary(session, patient);
  }

  return null; // Let QA_PAIRS or backend handle it
}
// ─────────────────────────────────────────────────────────────────────────────

type Candidate = {
  rank: number; sequence: string; binding_score: number;
  stability_score: number; solubility_score: number; total_energy?: number;
  num_mutations_from_seed?: number; kd_nM?: number;
  delta_g_binding_kcal_mol?: number;
  serum_half_life_min?: number; selectivity_ratio?: number; toxicity_flag?: boolean;
};

// ── Inline markdown renderer ─────────────────────────────────────────────────
// Handles **bold**, *italic*, and `code` spans within a single line of text.
function renderInline(text: string): React.ReactNode {
  const segments: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) segments.push(text.slice(last, match.index));
    const m = match[0];
    if (m.startsWith('**')) {
      segments.push(<strong key={match.index} className="text-white font-semibold">{m.slice(2, -2)}</strong>);
    } else if (m.startsWith('*')) {
      segments.push(<em key={match.index} className="text-gray-300 italic">{m.slice(1, -1)}</em>);
    } else {
      segments.push(<code key={match.index} className="font-mono text-[9px] bg-white/5 px-0.5 rounded text-gray-300">{m.slice(1, -1)}</code>);
    }
    last = match.index + m.length;
  }
  if (last < text.length) segments.push(text.slice(last));
  return <>{segments}</>;
}

// ── Simplified message renderer ──────────────────────────────────────────────
function AgentMessageCard({ msg, onSave }: { msg: AgentMessage; onSave?: (best: any, target: string) => void }) {
  const d = msg.data;
  const [saved, setSaved] = useState(false);

  // User bubble
  if (msg.role === 'user') {
    return (
      <div className="bg-white/[0.06] rounded-lg px-3 py-2 text-xs text-white leading-relaxed">
        {msg.content}
      </div>
    );
  }

  // Round complete — metric card
  if (d?.status === 'round_complete') {
    const scores = (d.scores || {}) as Record<string, any>;
    const dg: number | null = scores.delta_g_binding_kcal_mol ?? null;
    const kd = scores.kd_nM;
    const gate1: boolean | undefined = scores.gate1_pass;
    const gate2: boolean | undefined = scores.gate2_pass;
    const gate3: boolean | undefined = scores.gate3_pass;
    const lab: number | undefined = scores.lab_viability_score;
    const seq: string = d.sequence || '';
    const muts = (d.mutations || []).slice(0, 4);
    const gateColor = (pass: boolean | undefined) =>
      pass === true ? 'bg-green-500' : pass === false ? 'bg-red-500' : 'bg-gray-600';
    return (
      <div className="rounded-lg border border-[#222] bg-[#0a0a0a] overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#1a1a1a]">
          <span className="text-[9px] text-gray-500 uppercase tracking-wider font-medium">Round {d.round}</span>
          <div className="flex items-center space-x-1.5">
            {gate1 !== undefined && (
              <span className="flex items-center space-x-0.5 text-[8px] text-gray-500">
                <span className={`w-1.5 h-1.5 rounded-full ${gateColor(gate1)}`} title="Gate 1: Enthalpic Locking (Sc)" />
                <span className={gate1 ? 'text-green-500' : 'text-red-400'}>G1</span>
              </span>
            )}
            {gate2 !== undefined && (
              <span className="flex items-center space-x-0.5 text-[8px] text-gray-500">
                <span className={`w-1.5 h-1.5 rounded-full ${gateColor(gate2)}`} title="Gate 2: Solvation ΔG" />
                <span className={gate2 ? 'text-green-500' : 'text-red-400'}>G2</span>
              </span>
            )}
            {gate3 !== undefined && (
              <span className="flex items-center space-x-0.5 text-[8px] text-gray-500">
                <span className={`w-1.5 h-1.5 rounded-full ${gateColor(gate3)}`} title="Gate 3: Entropic Penalty" />
                <span className={gate3 ? 'text-green-500' : 'text-red-400'}>G3</span>
              </span>
            )}
            {d.target && <span className="text-[9px] text-gray-600 font-mono ml-1">{d.target}</span>}
          </div>
        </div>
        <div className="px-3 py-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-gray-500">ΔG Binding</span>
            <span className="font-bold text-white font-mono">
              {dg !== null ? dg.toFixed(2) + ' kcal/mol' : (scores.binding_score != null ? (scores.binding_score * 100).toFixed(1) + '%' : '—')}
            </span>
          </div>
          {kd != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Kd</span>
              <span className="font-bold text-white font-mono">
                {kd < 1000 ? kd.toFixed(0) + ' nM' : (kd / 1000).toFixed(1) + ' μM'}
              </span>
            </div>
          )}
          {lab != null && (
            <div className="flex items-center justify-between col-span-2">
              <span className="text-gray-500">Lab viability</span>
              <span className={`font-mono font-bold ${lab >= 70 ? 'text-green-400' : lab >= 50 ? 'text-yellow-500' : 'text-red-400'}`}>
                {lab.toFixed(0)}/100
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Stability</span>
            <span className="font-mono text-gray-300">{scores.stability != null ? (scores.stability * 100).toFixed(0) + '%' : '—'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Energy</span>
            <span className="font-mono text-gray-300">{scores.energy != null ? scores.energy.toFixed(3) : '—'}</span>
          </div>
          {scores.selectivity_ratio != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Select.</span>
              <span className={`font-mono ${scores.toxicity_flag ? 'text-red-400' : scores.selectivity_ratio >= 5 ? 'text-green-400' : 'text-yellow-500'}`}>
                {(scores.selectivity_ratio as number).toFixed(1)}x
              </span>
            </div>
          )}
          {scores.serum_half_life_min != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">t½</span>
              <span className="font-mono text-gray-300">{(scores.serum_half_life_min as number).toFixed(0)} min</span>
            </div>
          )}
        </div>
        {seq && (
          <div className="px-3 pb-1.5">
            <span className="font-mono text-[9px] text-gray-500 tracking-wider">{seq}</span>
          </div>
        )}
        {muts.length > 0 && (
          <div className="px-3 pb-2 flex flex-wrap gap-1">
            {muts.map((m: any, i: number) => (
              <span key={i} className="text-[8px] font-mono bg-red-900/30 text-red-300 px-1 py-0.5 rounded">
                {m.from}{m.position}{m.to}
              </span>
            ))}
            {(d.mutations || []).length > 4 && (
              <span className="text-[8px] text-gray-600">+{(d.mutations || []).length - 4}</span>
            )}
          </div>
        )}
        {d.trace && d.trace.length > 0 && (
          <div className="px-2 pb-2">
            <OptimizationTrace trace={d.trace} round={d.round} />
          </div>
        )}
      </div>
    );
  }

  // Design complete — summary card
  if (d?.status === 'complete' && d.rounds && d.rounds.length > 0) {
    const best = [...d.rounds].sort((a: any, b: any) => b.binding_score - a.binding_score)[0] as any;
    const totalRounds = d.rounds.length;
    const kd = best.kd_nM;
    const dg: number | null = best.delta_g_binding_kcal_mol ?? null;
    const gate1: boolean | undefined = best.gate1_pass;
    const gate2: boolean | undefined = best.gate2_pass;
    const gate3: boolean | undefined = best.gate3_pass;
    const lab: number | undefined = best.lab_viability_score;
    const gateColor = (pass: boolean | undefined) =>
      pass === true ? 'bg-green-500' : pass === false ? 'bg-red-500' : 'bg-gray-600';
    const gateLabel = (name: string, pass: boolean | undefined) =>
      pass === true ? name + ' PASS' : pass === false ? name + ' FAIL' : name;
    const notes3d: string[] = (d as any).notes_3d || [];
    const solTags: string[] = (d as any).solubility_tags || [];
    return (
      <div className="rounded-lg border border-green-900/40 bg-green-950/10 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-green-900/20">
          <span className="text-[9px] text-green-500 uppercase tracking-wider font-medium">Design Complete</span>
          <div className="flex items-center space-x-2">
            <span className="text-[9px] text-gray-600">{totalRounds} rounds · {d.total_time?.toFixed(1)}s</span>
            {onSave && (
              <button
                onClick={() => { onSave(best, d.target || ''); setSaved(true); }}
                disabled={saved}
                className={`text-[8px] px-2 py-0.5 rounded border transition-all ${
                  saved
                    ? 'border-green-700 bg-green-900/40 text-green-400 cursor-default'
                    : 'border-white/20 bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                {saved ? 'Saved' : 'Save'}
              </button>
            )}
          </div>
        </div>
        {/* Gate indicators row */}
        {(gate1 !== undefined || gate2 !== undefined || gate3 !== undefined) && (
          <div className="px-3 py-1.5 border-b border-[#1a1a1a] flex items-center space-x-3 text-[9px]">
            <span className="text-gray-600 uppercase tracking-wider">Triple-Gate:</span>
            {gate1 !== undefined && (
              <span className="flex items-center space-x-1">
                <span className={`w-2 h-2 rounded-full ${gateColor(gate1)}`} />
                <span className={gate1 ? 'text-green-400' : 'text-red-400'}>{gateLabel('G1', gate1)}</span>
              </span>
            )}
            {gate2 !== undefined && (
              <span className="flex items-center space-x-1">
                <span className={`w-2 h-2 rounded-full ${gateColor(gate2)}`} />
                <span className={gate2 ? 'text-green-400' : 'text-red-400'}>{gateLabel('G2', gate2)}</span>
              </span>
            )}
            {gate3 !== undefined && (
              <span className="flex items-center space-x-1">
                <span className={`w-2 h-2 rounded-full ${gateColor(gate3)}`} />
                <span className={gate3 ? 'text-green-400' : 'text-red-400'}>{gateLabel('G3', gate3)}</span>
              </span>
            )}
          </div>
        )}
        <div className="px-3 py-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
          <div className="flex items-center justify-between col-span-2">
            <span className="text-gray-500">Best sequence</span>
            <span className="font-mono text-[9px] text-white">{best.sequence}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">ΔG Binding</span>
            <span className="font-bold text-green-400 font-mono">
              {dg !== null ? dg.toFixed(2) + ' kcal/mol' : (best.binding_score * 100).toFixed(1) + '%'}
            </span>
          </div>
          {kd != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Kd</span>
              <span className="font-bold text-green-400 font-mono">
                {kd < 1000 ? kd.toFixed(0) + ' nM' : (kd / 1000).toFixed(1) + ' μM'}
              </span>
            </div>
          )}
          {lab != null && (
            <div className="flex items-center justify-between col-span-2">
              <span className="text-gray-500">Lab viability</span>
              <span className={`font-mono font-bold ${lab >= 70 ? 'text-green-400' : lab >= 50 ? 'text-yellow-500' : 'text-red-400'}`}>
                {lab.toFixed(0)}/100
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Stability</span>
            <span className="font-mono text-gray-300">{(best.stability_score * 100).toFixed(0)}%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Energy</span>
            <span className="font-mono text-gray-300">{best.total_energy?.toFixed(3) ?? '—'}</span>
          </div>
          {best.selectivity_ratio != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Select.</span>
              <span className={`font-mono ${best.toxicity_flag ? 'text-red-400' : best.selectivity_ratio >= 5 ? 'text-green-400' : 'text-yellow-500'}`}>
                {best.selectivity_ratio.toFixed(1)}x
              </span>
            </div>
          )}
          {best.serum_half_life_min != null && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">t½</span>
              <span className="font-mono text-gray-300">{best.serum_half_life_min.toFixed(0)} min</span>
            </div>
          )}
        </div>
        {/* Solubility tags */}
        {solTags.length > 0 && (
          <div className="px-3 pb-2 flex flex-wrap gap-1">
            {solTags.map((tag: string, i: number) => (
              <span key={i} className="text-[8px] bg-yellow-900/30 text-yellow-400 border border-yellow-900/40 px-1.5 py-0.5 rounded leading-tight">
                {tag.split(' — ')[0]}
              </span>
            ))}
          </div>
        )}
        {/* 3D inspection notes */}
        {notes3d.length > 0 && (
          <div className="px-3 pb-2 border-t border-[#1a1a1a] pt-2">
            <div className="text-[8px] text-gray-600 uppercase tracking-wider mb-1">3D Viewer Notes</div>
            <div className="space-y-1">
              {notes3d.map((note: string, i: number) => (
                <div key={i} className="text-[8px] text-gray-500 leading-relaxed">
                  {note}
                </div>
              ))}
            </div>
          </div>
        )}
        {d.trace && d.trace.length > 0 && (
          <div className="px-2 pb-2">
            <OptimizationTrace trace={d.trace} />
          </div>
        )}
      </div>
    );
  }

  // Running / phase indicator
  if (d?.status === 'running') {
    const phaseLabel: Record<string, string> = {
      research: 'Researching target',
      generate: 'Generating candidates',
      fold: 'Folding structure',
      evaluate: 'Evaluating metrics',
    };
    return (
      <div className="flex items-center space-x-2 text-[10px] text-gray-500 py-1">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
        <span>{d.phase ? phaseLabel[d.phase] || d.phase : 'Running MCMC...'}</span>
      </div>
    );
  }

  // Error
  if (d?.status === 'error') {
    return (
      <div className="text-[10px] text-red-400 bg-red-900/10 border border-red-900/30 rounded-lg px-3 py-2">
        {msg.content.replace(/^Error:\s*/i, '')}
      </div>
    );
  }

  // Fallback — full-content renderer: per-line bullet/header formatting
  const allLines = msg.content.split('\n');
  return (
    <div className="text-[10px] leading-relaxed space-y-0.5">
      <div className="flex items-center space-x-1 mb-1">
        <span className="text-[8px] text-gray-600 uppercase tracking-wider">Proteus</span>
      </div>
      {allLines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1" />;
        // Separator lines (=== or ---)
        if (/^[=]{3,}$/.test(trimmed) || /^[-]{3,}$/.test(trimmed)) {
          return <div key={i} className="border-t border-[#1e1e1e] my-0.5" />;
        }
        // Markdown heading (### or ##)
        if (/^#{2,}\s/.test(trimmed)) {
          return <div key={i} className="text-gray-300 font-medium mt-1">{trimmed.replace(/^#+\s*/, '')}</div>;
        }
        // Code fence (```) — skip the fence line itself
        if (trimmed === '```' || trimmed.startsWith('```')) {
          return <div key={i} className="text-gray-600 text-[8px] font-mono">{trimmed.startsWith('```') && trimmed.length > 3 ? trimmed.slice(3) : ''}</div>;
        }
        // Table row (|...|)
        if (trimmed.startsWith('|')) {
          return <div key={i} className="font-mono text-gray-600 text-[8px] overflow-x-auto whitespace-nowrap">{trimmed}</div>;
        }
        // Bullet line (- ...)
        if (trimmed.startsWith('- ')) {
          return (
            <div key={i} className="flex space-x-1.5 text-gray-400">
              <span className="text-gray-600 flex-shrink-0 mt-px">·</span>
              <span>{renderInline(trimmed.slice(2))}</span>
            </div>
          );
        }
        // Header line: fully wrapped in ** (e.g. **Title**)
        if (trimmed.startsWith('**') && trimmed.endsWith('**') && trimmed.length > 4) {
          return <div key={i} className="text-gray-300 font-medium mt-1">{trimmed.slice(2, -2)}</div>;
        }
        // Any line containing inline markdown
        if (/\*\*|`/.test(trimmed)) {
          return <div key={i} className="text-gray-400">{renderInline(trimmed)}</div>;
        }
        // Plain text
        return <div key={i} className="text-gray-500">{trimmed}</div>;
      })}
    </div>
  );
}
// ─────────────────────────────────────────────────────────────────────────────

export default function AgentPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'landing' | 'workspace'>('landing');
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  const [patient, setPatient] = useState<PatientInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | undefined>();
  const [isRunning, setIsRunning] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [seed, setSeed] = useState<string | undefined>();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [activeViewerPdb, setActiveViewerPdb] = useState<string>('6LU7');
  const [activeViewerMuts, setActiveViewerMuts] = useState<any[]>([]);
  const [hoveredTarget, setHoveredTarget] = useState<number | null>(null);
  const [designRounds, setDesignRounds] = useState<any[]>([]);
  const [designTime, setDesignTime] = useState(0);
  const [designTarget, setDesignTarget] = useState('');
  const [comparisonMode, setComparisonMode] = useState(false);
  const [saveToast, setSaveToast] = useState(false);
  const [designSession, setDesignSession] = useState<DesignSessionContext | undefined>(undefined);
  const [streamStatus, setStreamStatus] = useState<string>('');
  const [esmfoldPdb, setEsmfoldPdb] = useState<string | null>(null);

  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(300);
  const chatEnd = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { isOpen: paletteOpen, setIsOpen: setPaletteOpen } = useCommandPalette();

  const handleLogout = () => { logout(); navigate('/login'); };

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // Drag-to-resize sidebar
  const onDragStart = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    dragStartX.current = e.clientX;
    dragStartWidth.current = sidebarWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [sidebarWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = e.clientX - dragStartX.current;
      setSidebarWidth(Math.min(640, Math.max(200, dragStartWidth.current + delta)));
    };
    const onUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  const enterWorkspace = useCallback((info: PatientInfo) => {
    setError(null); setPatient(info); setMode('workspace');
    const parts: string[] = ['- Condition: ' + info.cancer_type];
    if (info.cancer_stage) parts.push('- Stage: ' + info.cancer_stage);
    if (info.tumor_markers) parts.push('- Markers: ' + info.tumor_markers);
    if (info.previous_treatments) parts.push('- Prior treatments: ' + info.previous_treatments);
    if (info.modality) parts.push('- Modality: ' + info.modality);
    setMessages([{
      role: 'agent',
      content: 'Ready\n' + parts.join('\n'),
    }]);
    setTimeout(() => inputRef.current?.focus(), 300);
  }, []);

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || !patient || loading) return;
    setError(null);
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    const userMessage = input;
    setInput('');

    // ── Tier 1: Design request → MCMC backend (streaming SSE) ────────────────
    // Only messages that explicitly ask for a new design/optimization run hit the backend.
    if (DESIGN_RE.test(userMessage)) {
      setLoading(true);
      setIsRunning(true);
      setStreamStatus('Initialising...');
      setEsmfoldPdb(null);
      try {
        const token = localStorage.getItem('proteus_access_token') || '';
        const response = await fetch('/api/v1/agent/design/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            patient,
            message: userMessage,
            ...(designSession ? { session: designSession } : {}),
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Server returned ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop()!;

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            let event: any;
            try { event = JSON.parse(line.slice(6)); } catch { continue; }

            if (event.type === 'progress') {
              setStreamStatus(
                `Chain ${(event.chain_index ?? 0) + 1} · step ${event.step}/${event.total_steps} · energy ${event.best_energy != null ? event.best_energy.toFixed(4) : '—'}`
              );
            } else if (event.type === 'epoch_complete') {
              setStreamStatus(
                `Epoch ${(event.epoch ?? 0) + 1}/${event.num_epochs} · best energy ${event.best_energy != null ? event.best_energy.toFixed(4) : '—'}`
              );
            } else if (event.type === 'error') {
              throw new Error(event.detail || 'Streaming error');
            } else if (event.type === 'complete') {
              setStreamStatus('');
              const data: AgentRunResponse = event.result;

              // Only append agent messages — user message was already added optimistically.
              const agentMessages = data.messages.filter((m) => m.role === 'agent');
              setMessages((prev) => [...prev, ...agentMessages]);
              setIsRunning(false);
              if (data.run_id) setCurrentRunId(data.run_id);

              // Store ESMFold PDB string if structure prediction succeeded
              if (data.pdb_string) setEsmfoldPdb(data.pdb_string);

              const rounds = data.messages
                ?.filter((m) => m.data?.status === 'round_complete' || m.data?.status === 'complete')
                .map((m) => m.data?.rounds)
                .flat()
                .filter(Boolean) || [];

              const lastComplete = data.messages?.filter((m) => m.data?.status === 'complete').pop();
              const totalTime = lastComplete?.data?.total_time || 0;

              if (rounds.length > 0) {
                const withMuts = data.messages?.filter((m) => m.data?.mutations).map((m) => m.data?.mutations).flat() || [];
                const roundData = rounds.map((r: any, i: number) => ({
                  round: i + 1,
                  sequence: r.sequence || '',
                  binding_score: r.binding_score || 0,
                  stability_score: r.stability_score || 0,
                  solubility_score: r.solubility_score || 0,
                  total_energy: r.total_energy || 0,
                  mutations: withMuts.filter((m: any) => m) as { position: number; from: string; to: string }[],
                }));
                setDesignRounds(roundData);
                setDesignTime(totalTime);
                setDesignTarget(lastComplete?.data?.target || patient?.tumor_markers || patient?.cancer_type || '');
              }

              if (data.candidate_sequence) {
                setCandidates((prev) => {
                  const ranked = (data.messages
                    .filter((m) => m.data?.status === 'round_complete' || m.data?.status === 'complete')
                    .flatMap((m) => m.data?.rounds || [])
                    .map((r: any, i: number) => ({
                      rank: i + 1, sequence: r.sequence || '',
                      binding_score: r.binding_score || 0, stability_score: r.stability_score || 0,
                      solubility_score: r.solubility_score || 0, total_energy: r.total_energy,
                      kd_nM: r.kd_nM, delta_g_binding_kcal_mol: r.delta_g_binding_kcal_mol,
                      serum_half_life_min: r.serum_half_life_min,
                      selectivity_ratio: r.selectivity_ratio, toxicity_flag: r.toxicity_flag,
                    })) as Candidate[]);
                  return ranked.length > 0 ? ranked : prev;
                });
                const last = data.messages[data.messages.length - 1];
                if (last?.data?.pdb_id) {
                  setActiveViewerPdb(last.data.pdb_id);
                  setActiveViewerMuts(data.mutations || []);
                  setSeed(last.data.seed || data.candidate_sequence);
                }

                // Build designSession from best round so follow-up chat is grounded in actual results
                if (lastComplete?.data?.status === 'complete') {
                  const bestRound = (lastComplete.data.rounds as any[])
                    ?.sort((a: any, b: any) => b.binding_score - a.binding_score)[0];
                  if (bestRound) {
                    const seedSeq: string = lastComplete.data.seed || '';
                    const bestSeq: string = bestRound.sequence || '';
                    const mutationsFromSeed: string[] = [];
                    for (let i = 0; i < Math.min(seedSeq.length, bestSeq.length); i++) {
                      if (seedSeq[i] !== bestSeq[i]) {
                        mutationsFromSeed.push(`${seedSeq[i]}${i + 1}${bestSeq[i]}`);
                      }
                    }
                    if (bestSeq.length !== seedSeq.length && seedSeq) {
                      mutationsFromSeed.push(`len ${seedSeq.length}→${bestSeq.length}`);
                    }
                    const roundsSummary = (lastComplete.data.rounds as any[])?.map((r: any) => ({
                      round: r.round,
                      sequence: r.sequence,
                      binding_score: r.binding_score,
                      delta_g_binding_kcal_mol: r.delta_g_binding_kcal_mol,
                      kd_nM: r.kd_nM,
                      lab_viability_score: r.lab_viability_score,
                      is_best: r.is_best,
                    })) || [];
                    setDesignSession({
                      target_name: lastComplete.data.target || patient?.cancer_type || '',
                      pdb_id: lastComplete.data.pdb_id || '',
                      best_sequence: bestSeq,
                      seed_sequence: seedSeq,
                      binding_score: bestRound.binding_score,
                      delta_g_kcal_mol: bestRound.delta_g_binding_kcal_mol,
                      kd_nM: bestRound.kd_nM,
                      stability_score: bestRound.stability_score,
                      solubility_score: bestRound.solubility_score,
                      total_energy: bestRound.total_energy,
                      lab_viability_score: bestRound.lab_viability_score,
                      mutations_from_seed: mutationsFromSeed,
                      rounds_summary: roundsSummary,
                    });
                  }
                }
              }
            }
          }
        }
      } catch (err: any) {
        const detail = err?.message || 'Request failed';
        setError(detail);
        setMessages((prev) => [...prev, { role: 'agent', content: `Error: ${detail}`, data: { status: 'error' } }]);
        setIsRunning(false);
        setStreamStatus('');
      }
      setLoading(false);
      return;
    }

    // ── Tier 2: Known biophysics topic → local static QA (instant, no backend) ─
    const qaAnswer = getQAAnswer(userMessage);
    if (qaAnswer !== null) {
      setMessages((prev) => [...prev, { role: 'agent', content: qaAnswer }]);
      return;
    }

    // ── Tier 3: Active session → grounded conversational reply (instant) ───────
    const sessionReply = buildSessionReply(userMessage, designSession ?? null, patient);
    if (sessionReply !== null) {
      setMessages((prev) => [...prev, { role: 'agent', content: sessionReply }]);
      return;
    }

    // ── Tier 4: Unknown topic → backend static QA fallback (no MCMC) ──────────
    // Backend's _is_design_request() won't match; returns a conversational answer.
    setLoading(true);
    setIsRunning(true);
    try {
      const res = await agentApi.design(patient, userMessage, designSession);
      const agentMessages = res.data.messages.filter((m) => m.role === 'agent');
      setMessages((prev) => [...prev, ...agentMessages]);
      setIsRunning(false);
      if (res.data.run_id) setCurrentRunId(res.data.run_id);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Request failed';
      setError(detail);
      setMessages((prev) => [...prev, { role: 'agent', content: `Error: ${detail}`, data: { status: 'error' } }]);
      setIsRunning(false);
    }
    setLoading(false);
  };

  const handleExport = (seq: string, format: string) => {
    const blob = new Blob([seq], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `proteus-${seq.slice(0, 6)}.${format.toLowerCase()}`;
    a.click();
  };

  const handleSaveDesign = (best: any, target: string) => {
    const designTarget = target || patient?.tumor_markers || patient?.cancer_type || 'Unknown';
    const name = `${designTarget} · ${new Date().toLocaleDateString()}`;
    savedDesignsService.save({
      name,
      target: designTarget,
      sequence: best.sequence || '',
      bindingScore: best.binding_score ?? 0,
      kd_nM: best.kd_nM,
      stabilityScore: best.stability_score ?? 0,
      solubilityScore: best.solubility_score ?? 0,
      totalEnergy: best.total_energy,
      labViabilityScore: best.lab_viability_score,
      selectivityRatio: best.selectivity_ratio,
      serumHalfLifeMin: best.serum_half_life_min,
      patient: patient
        ? { cancerType: patient.cancer_type, cancerStage: patient.cancer_stage }
        : undefined,
    });
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2000);
  };

  const handleSaveCandidate = (c: Candidate) => {
    const designTarget = patient?.tumor_markers || patient?.cancer_type || 'Unknown';
    savedDesignsService.save({
      name: `${designTarget} · Rank ${c.rank} · ${new Date().toLocaleDateString()}`,
      target: designTarget,
      sequence: c.sequence,
      bindingScore: c.binding_score,
      kd_nM: c.kd_nM,
      stabilityScore: c.stability_score,
      solubilityScore: c.solubility_score,
      totalEnergy: c.total_energy,
      selectivityRatio: c.selectivity_ratio,
      serumHalfLifeMin: c.serum_half_life_min,
      patient: patient
        ? { cancerType: patient.cancer_type, cancerStage: patient.cancer_stage }
        : undefined,
    });
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2000);
  };

  const paletteCommands = [
    { id: 'new-run', label: 'New design run', category: 'Run', action: () => { setMode('landing'); setMessages([]); setCandidates([]); } },
    { id: 'compare', label: 'Toggle comparison mode', category: 'View', action: () => setComparisonMode((p) => !p) },
    { id: 'export-all', label: 'Export all candidates as FASTA', category: 'Export', action: () => candidates.forEach((c) => handleExport(c.sequence, 'fasta')) },
    { id: 'toggle-sidebar', label: 'Toggle chat sidebar', category: 'View', action: () => setSidebarOpen((p) => !p) },
  ];

  if (mode === 'landing') {
    return (
      <div className="min-h-screen flex flex-col bg-black text-white">
        {/* Top nav for landing mode */}
        <nav className="border-b border-[#1a1a1a] flex-shrink-0">
          <div className="max-w-5xl mx-auto px-4 h-12 flex items-center justify-between">
            <div className="flex items-center space-x-5">
              <span className="text-sm font-bold tracking-tight">Proteus</span>
              <div className="flex items-center space-x-1">
                <Link to="/agent" className="px-3 py-1.5 rounded text-[11px] font-medium bg-white/10 text-white">Workspace</Link>
                <Link to="/benchmarks" className="px-3 py-1.5 rounded text-[11px] font-medium text-gray-500 hover:text-white hover:bg-white/5 transition-colors">Benchmarks</Link>
                <Link to="/comparisons" className="px-3 py-1.5 rounded text-[11px] font-medium text-gray-500 hover:text-white hover:bg-white/5 transition-colors">Comparisons</Link>
                <Link to="/dashboard" className="px-3 py-1.5 rounded text-[11px] font-medium text-gray-500 hover:text-white hover:bg-white/5 transition-colors">History</Link>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Link to="/profile" className="text-[11px] text-gray-500 hover:text-white transition-colors">{user?.full_name}</Link>
              <button onClick={handleLogout} className="text-[11px] text-gray-600 hover:text-white transition-colors">Logout</button>
            </div>
          </div>
        </nav>
        <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-3xl space-y-6 animate-fade-in">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4">
              <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                <defs><linearGradient id="dl" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#fff"/><stop offset="50%" stopColor="#666"/><stop offset="100%" stopColor="#fff"/>
                </linearGradient></defs>
                <g stroke="url(#dl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
                  <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
                  <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
                  <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
                  <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
                  <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
                  <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
                </g>
              </svg>
            </div>
            <h1 className="text-3xl font-bold tracking-tight">Proteus</h1>
            <p className="text-gray-500 text-sm mt-2 max-w-lg mx-auto leading-relaxed">
              Describe a condition and Proteus researches the target, then designs, folds, and evaluates
              candidate protein therapeutics — autonomously.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="md:col-span-3 bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Describe Patient</h2>
                <span className="flex items-center space-x-1.5 text-[9px] text-gray-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500/60 animate-pulse" />
                  <span>Ready</span>
                </span>
              </div>
              <p className="text-[11px] text-gray-600 mb-3 leading-relaxed">Start with the clinical presentation. Genetic details can be added after.</p>
              <PatientForm onSubmit={enterWorkspace} />
            </div>
            <div className="md:col-span-2 space-y-3">
              <div className="bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up" style={{animationDelay:'80ms'}}>
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">Upload Target</h2>
                <p className="text-[10px] text-gray-600 mb-2">Upload any PDB file or enter a PDB ID to design against any target.</p>
                <FileUpload
                  onPDBUpload={(pdbId) => setActiveViewerPdb(pdbId)}
                  onSequenceInput={(seq) => enterWorkspace({
                    full_name: 'Researcher', age: 0, cancer_type: 'Custom sequence uploaded',
                    cancer_stage: '', tumor_markers: '', previous_treatments: '',
                    brain_metastasis: false, notes: `Custom seed: ${seq}`, modality: '',
                  })}
                />
              </div>
              <div className="bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up" style={{animationDelay:'160ms'}}>
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Example Targets</h2>
                <p className="text-[10px] text-gray-600 mb-2">Click any to try a demo. You can design <span className="text-white/60">against any PDB target</span>.</p>
                <div className="space-y-1.5 text-xs">
                  {[
                    { name: 'EGFRvIII', pdb: '3gp1', tag: 'Receptor' },
                    { name: 'PD-L1', pdb: '4zqk', tag: 'Checkpoint' },
                    { name: 'KRAS G12C', pdb: '6OIM', tag: 'Oncoprotein' },
                    { name: '3CL Protease', pdb: '6LU7', tag: 'Viral' },
                  ].map((t, idx) => (
                    <button key={t.name}
                      onMouseEnter={() => setHoveredTarget(idx)}
                      onMouseLeave={() => setHoveredTarget(null)}
                      onClick={() => enterWorkspace({ full_name: 'Demo', age: 55, cancer_type: t.name, cancer_stage: 'IV', tumor_markers: t.name, previous_treatments: '', brain_metastasis: false, notes: '', modality: '' })}
                      className={`group w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-all duration-200 ${hoveredTarget === idx ? 'border-white/30 bg-white/[0.03] translate-x-0.5' : 'border-[#222]'}`}>
                      <div>
                        <div className="font-medium text-white text-[12px]">{t.name}</div>
                        <div className="text-gray-600 text-[9px]">{t.pdb} — {t.tag}</div>
                      </div>
                      <span className={`text-[10px] transition-all duration-200 ${hoveredTarget === idx ? 'text-white' : 'text-gray-700'}`}>→</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="pt-6">
            <div className="border-t border-[#1a1a1a] pt-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Proteus vs Other Methods</h2>
                <a href="/benchmarks" className="text-[9px] text-gray-600 hover:text-white transition-colors underline">View full dashboard →</a>
              </div>
              <BenchmarkGraphs />
            </div>
          </div>

          <p className="text-center text-[10px] text-gray-600">FOR RESEARCH USE ONLY. Not a medical device.</p>
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-black text-white overflow-hidden">
      {/* Top Nav */}
      <nav className="flex items-center justify-between px-4 h-11 border-b border-[#1a1a1a] flex-shrink-0">
        <div className="flex items-center space-x-3">
          <button onClick={() => setSidebarOpen((p) => !p)}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors text-xs"
            aria-label="Toggle sidebar">☰</button>
          <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-5 h-5">
            <defs><linearGradient id="nl" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#fff"/><stop offset="50%" stopColor="#666"/><stop offset="100%" stopColor="#fff"/>
            </linearGradient></defs>
            <g stroke="url(#nl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
              <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
              <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
              <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
              <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
              <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
              <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
            </g>
          </svg>
          <span className="text-sm font-bold tracking-tight">Proteus</span>
          {patient && (
            <span className="text-[10px] text-gray-600 ml-2 hidden sm:inline">
              {patient.cancer_type} {patient.tumor_markers && `· ${patient.tumor_markers}`}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <span className={`flex items-center space-x-1 text-[10px] px-2 py-0.5 rounded-full ${
            isRunning ? 'bg-green-900/30 text-green-400 border border-green-900/50' :
            candidates.length > 0 ? 'bg-white/5 text-gray-400 border border-[#222]' :
            'text-gray-600'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-green-400 animate-pulse' : candidates.length > 0 ? 'bg-gray-500' : 'bg-gray-700'}`} />
            {isRunning ? 'Running' : candidates.length > 0 ? 'Complete' : 'Ready'}
          </span>
          <button onClick={() => setComparisonMode((p) => !p)}
            className={`text-[10px] px-2 py-1 rounded border transition-all ${
              comparisonMode ? 'border-white/40 bg-white/10 text-white' : 'border-[#222] text-gray-500 hover:text-white hover:border-[#444]'
            }`}>⇄ Compare</button>
          <button onClick={() => setMode('landing')}
            className="text-[10px] text-gray-600 hover:text-white transition-colors">Exit</button>
        </div>
      </nav>

      <div className="flex-shrink-0 border-b border-[#1a1a1a] bg-[#080808] px-3 py-1 text-center">
        <p className="text-[9px] text-gray-600 leading-snug">
          Research use only — sequences are computational hypotheses, not prescriptions.
          Ask questions in plain English; say <span className="text-gray-500">design a peptide</span> to run a new MCMC cycle.
        </p>
      </div>

      {/* Main 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat sidebar — resizable */}
        {sidebarOpen && (
          <>
            <aside style={{ width: sidebarWidth }} className="flex-shrink-0 border-r border-[#1a1a1a] flex flex-col bg-[#050505]">
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {designRounds.length > 0 && (
                  <div className="mb-3">
                    <DesignCycleSummary rounds={designRounds} totalTime={designTime} targetName={designTarget} />
                  </div>
                )}
                {messages.length === 0 && (
                  <div className="text-center py-16 text-gray-600">
                    <p className="text-xs">Ready to design</p>
                    <div className="flex flex-col gap-1.5 mt-4">
                      {['Design a peptide', 'Explain the process', 'What target?'].map((a) => (
                        <button key={a} onClick={() => { setInput(a); setTimeout(() => inputRef.current?.focus(), 50); }}
                          className="text-[10px] border border-[#222] hover:border-white/30 text-gray-400 hover:text-white px-3 py-1.5 rounded-full transition-all">
                          {a}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <AgentMessageCard key={i} msg={msg} onSave={handleSaveDesign} />
                ))}
                {streamStatus && (
                  <div className="flex items-center space-x-2 px-1 py-1 text-[10px] text-gray-500 font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse flex-shrink-0" />
                    <span>{streamStatus}</span>
                  </div>
                )}
                {esmfoldPdb && !streamStatus && (
                  <div className="border border-[#1a1a1a] rounded-lg px-2.5 py-2 text-[10px] text-gray-400 flex items-center justify-between">
                    <span>ESMFold structure predicted</span>
                    <button
                      onClick={() => {
                        const blob = new Blob([esmfoldPdb], { type: 'chemical/x-pdb' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `proteus-esmfold-${designSession?.best_sequence?.slice(0, 8) || 'peptide'}.pdb`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      className="text-white underline underline-offset-2 hover:text-gray-300 transition-colors"
                    >
                      Download PDB
                    </button>
                  </div>
                )}
                <div ref={chatEnd} />
              </div>
              <div className="p-3 border-t border-[#1a1a1a]">
                <form onSubmit={handleSend} className="flex space-x-1.5">
                  <input ref={inputRef} type="text" value={input} onChange={(e) => setInput(e.target.value)}
                    placeholder="Message..." className="flex-1 bg-[#111] border border-[#222] rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-[#444]" disabled={loading} />
                  <button type="submit" disabled={loading || !input.trim()}
                    className="px-3 py-1.5 bg-white text-black rounded-lg text-[10px] font-medium disabled:opacity-30">→</button>
                </form>
              </div>
            </aside>
            {/* Drag-to-resize handle */}
            <div
              onMouseDown={onDragStart}
              className="w-1 flex-shrink-0 cursor-col-resize hover:bg-white/20 transition-colors bg-transparent"
            />
          </>
        )}

        {/* Center: 3D Viewer */}
        <main className={`flex-1 flex flex-col min-w-0 ${comparisonMode ? 'w-1/2' : ''}`}>
          <div className="flex-1 relative bg-[#000]">
            <div className="absolute inset-3">
              <div className="h-full rounded-xl border border-[#1a1a1a] overflow-hidden bg-[#050505] relative">
                {activeViewerPdb && (
                  <iframe
                    src={`https://www.rcsb.org/3d-view/${activeViewerPdb}?style=stick&color=spectrum`}
                    style={{ width: '100%', height: '100%', border: 'none', background: '#000' }}
                    title="Protein structure"
                  />
                )}
                {/* Binding site annotation panel */}
                {activeViewerMuts.length > 0 && (
                  <div className="absolute top-3 right-3 w-44 bg-black/80 border border-[#222] rounded-lg p-2.5 backdrop-blur-sm text-[9px]">
                    <div className="text-gray-500 uppercase tracking-wider font-medium mb-2">
                      Binding Site Mutations
                    </div>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {activeViewerMuts.map((m: any, i: number) => (
                        <div key={i} className="flex items-center justify-between">
                          <span className="font-mono bg-red-900/40 text-red-300 px-1 py-0.5 rounded text-[8px]">
                            {m.from}{m.position}{m.to}
                          </span>
                          <span className="text-gray-600 text-[8px] ml-1 truncate">
                            {m.from !== m.to ? 'substitution' : 'conserved'}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 pt-2 border-t border-[#1a1a1a] text-gray-600 text-[7px] leading-relaxed">
                      Red = mutations from seed. Mutations are concentrated at predicted binding pocket residues.
                    </div>
                  </div>
                )}
                {/* PDB label */}
                <div className="absolute bottom-3 left-3 flex items-center space-x-2">
                  <span className="text-[8px] text-gray-600 bg-black/60 px-2 py-0.5 rounded font-mono">
                    PDB: {activeViewerPdb}
                  </span>
                  {activeViewerMuts.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {activeViewerMuts.slice(0, 6).map((m: any, i: number) => (
                        <span key={i} className="text-[8px] font-mono bg-red-900/60 text-red-300 px-1.5 py-0.5 rounded">
                          {m.from}{m.position}{m.to}
                        </span>
                      ))}
                      {activeViewerMuts.length > 6 && (
                        <span className="text-[8px] text-gray-600 px-1">+{activeViewerMuts.length - 6}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Right: Results panel */}
        <aside className="w-[300px] flex-shrink-0 border-l border-[#1a1a1a] bg-[#050505] overflow-y-auto">
          <div className="p-3 border-b border-[#1a1a1a] flex items-center justify-between">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Candidates</span>
            {candidates.length > 0 && (
              <span className="text-[9px] text-gray-600">{candidates.length} results</span>
            )}
          </div>
          <div className="p-2">
            <ResultsPanel
              candidates={candidates}
              seed={seed}
              onInspect={(seq) => {
                const c = candidates.find((x) => x.sequence === seq);
                if (c) setActiveViewerMuts(seed ? seed.split('').map((a, i) => ({ from: a, to: seq[i] || a, position: i + 1 })).filter((m) => m.from !== m.to) : []);
              }}
              onExport={handleExport}
              onSave={handleSaveCandidate}
            />
          </div>
        </aside>
      </div>

      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} commands={paletteCommands} />

      {/* Save toast */}
      {saveToast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-[#111] border border-green-800/60 text-green-400 text-[11px] px-4 py-2 rounded-lg shadow-xl pointer-events-none">
          Saved to History
        </div>
      )}
    </div>
  );
}

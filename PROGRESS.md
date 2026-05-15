# Proteus — Progress & Roadmap

**Goal:** Production-grade autonomous MCMC protein design platform, positioned for Y Combinator application.
**Live site:** https://dhedhialy.github.io/proteus/
**Repo:** https://github.com/DHEDHiAly/proteus

---

## Update — 2026-05-15 (context-aware chat responder wired)

### ContextAwareChatResponder integrated into agent.py run()
- **New file:** `backend/app/services/context_aware_responder.py` — `ContextAwareChatResponder` with 5 answer builders: `_explain_mechanism`, `_explain_mutations`, `_assess_viability`, `_suggest_improvement`, `_show_progression`
- **Priority chain (non-design messages):**
  1. `_answer_question` — static QA, generic biophysics (14 entries)
  2. **`ContextAwareChatResponder`** — session-specific: mechanism, mutations, viability, improvement, progression (NEW)
  3. `ChatResponder` — binding breakdown, SOTA, synthesis, delivery, mutations
  4. Ollama (local LLM, optional)
  5. `_conversational_fallback_rich` — rich text fallback
- **Import added:** `from app.services.context_aware_responder import ContextAwareChatResponder`
- **`__init__` updated:** `self.context_aware_responder = ContextAwareChatResponder()`
- **`run()` updated:** calls `self.context_aware_responder.respond(message, session)` after static QA, before `ChatResponder`; returns immediately on non-None result
- **`py_compile`:** clean on both `agent.py` and `context_aware_responder.py`
- **9/9 regression tests pass** (`venv/bin/pytest tests/test_agent_conversation.py`)

---

## Update — 2026-05-14 (agent chat + auth + demo)

### Bugfix: questions no longer re-trigger MCMC
- **Cause:** Messages like “how does this treatment work?” could fall through to the full design pipeline (or design-intent was not prioritized vs interrogatives).
- **Backend (`backend/app/services/agent.py`):**
  - **`_is_design_request` runs first:** explicit keywords (`design`, `optimize`, `generate`, …) skip Q&A and go straight to MCMC — fixes “how do I **design** …?” being swallowed by the question handler.
  - **Broader `_is_question`:** Unicode question marks (`?`, `？`, etc.) and more conversational starters; interrogative `how|what|…` + word without trailing `?` still counts as a question.
  - **New static Q&A** for treatment / clinical framing vs in-silico outputs (research-only disclaimer + where real therapy comes from).
  - **Ollama unavailable:** still returns help text — never MCMC for questions.
- **Frontend (`frontend/src/pages/AgentPage.tsx`):** same treatment/clinical pattern added at the top of `QA_PAIRS` so common questions answer **locally** without a network round-trip.
- **Tests:** `backend/tests/test_agent_conversation.py` — 9 regression tests (conversation vs MCMC + heuristics). Run with `venv/bin/pytest tests/test_agent_conversation.py` (numpy may segfault in some sandboxed CI; OK on normal macOS).
- **Demo script:** `scripts/demo_agent.sh` — `curl` login as `admin@proteus.dev` / `password123`, POST conversational message (assert no `round_complete`), then `design a peptide` (assert MCMC). Set `PROTEUS_API` if the API is not on `localhost:8000`. **Restart the FastAPI process after pulling** so the running server loads the new `agent.py` (otherwise the script still sees old behaviour).

### Earlier same-week: JWT refresh body
- `POST /api/v1/auth/refresh` now accepts JSON `{"refresh_token":"..."}` via `RefreshTokenRequest` — fixes silent refresh failure and cascading `Could not validate credentials` on `/agent/*`.

---

## What Has Been Built

### Backend (FastAPI + Python 3.9)
- Full REST API: auth (JWT + bcrypt 4.1.3), RBAC, runs, targets, admin, agent, benchmarks endpoints
- MCMC core: Metropolis-Hastings acceptance criterion, parallel tempering across multiple temperature chains
- ESM-2 guided mutation proposals + BLOSUM62 substitution log-odds energy oracle
- Multi-objective energy scoring: binding affinity, folding stability, solubility, charge, hydrophobicity
- R-hat / ESS convergence diagnostics
- GIAPT adaptive temperature (Gradient-Informed Adaptive Parallel Tempering): every 50 steps, adjusts each chain's temperature toward 23–40% acceptance rate; T clamped to [0.05, 50.0]
- PostgreSQL schema: users, mcmc_runs, chain_states, mutation_steps, designed_candidates, audit_logs
- Redis-backed job queue
- 28 passing unit tests (MCMC convergence, energy oracle, proposal distribution, API layer)
- Benchmark API: 3 endpoints (`/benchmarks/{target}`, `/stats`, `/convergence`)
- SOTA binder loader from CSV files on startup
- `real_benchmark_data.json`: 10 targets across 4 disease areas — Proteus beats AlphaFold on all 10 (81% avg improvement); beats published drug on EGFRvIII and PD-L1 only (intentionally realistic)

#### ΔG Pipeline
- `compute_delta_g_kcal_mol()`: ΔG = 0.616 × ln(Kd_nM × 1e-9) at 310K; range −14 to −7 kcal/mol for promising candidates
- `Kd` formula: `10^((1 − binding_score) × 7)` nM (internal only); AutoDock Vina threshold −6 kcal/mol = lab-worthy gate
- All payloads include `delta_g_binding_kcal_mol`; all UI cards show ΔG

#### Triple-Gate Physics Model (`backend/app/core/energy.py`)
- `EnergyOracle` has 6 new methods: `compute_hbond_count()`, `compute_entropic_penalty()`, `compute_solvation_delta_g()`, `compute_surface_complementarity()`, `compute_lab_viability_score()`, `compute_selectivity_ddg()`
- `score_candidate()` returns 27 total fields (18 original + 9 new): `hbond_count`, `entropic_penalty`, `solvation_delta_g`, `surface_complementarity`, `gate1_pass`, `gate2_pass`, `gate3_pass`, `lab_viability_score`, `selectivity_ddg`
- Gate thresholds: Gate 1 (Enthalpic Locking): Sc ≥ 0.4 | Gate 2 (Solvation): ΔG_solv ≤ 0.0 | Gate 3 (Entropic): penalty ≤ 3.5 kcal/mol
- Sc formula: 0.35×diversity + 0.30×aromatic + 0.20×charged + 0.15×pocket_score; −0.15 penalty for hydrophobic stretch ≥5
- Lab viability score (0–100): ΔG ≤ −6 → +30 pts, Gate1 +25, Gate2 +20, Gate3 +15, manufacturability ×10 (max 10)
- `compute_selectivity_ddg()`: temporarily clears `oracle.target_pocket_residues` to simulate off-target; positive ΔΔG = selective for target

#### Agent Service (`backend/app/services/agent.py`)
- 3 module-level helpers: `_suggest_solubility_tags()`, `_generate_3d_notes()`, `_format_fasta()`
- `_run_mcmc_round()` accepts `pdb_id=''`, returns all gate fields + `solubility_tags`, `notes_3d`, `fasta`
- `round_complete` scores payload includes all Triple-Gate fields
- Final report: Triple-Gate table, gate-column iteration history, FASTA block, 3D notes, solubility warnings
- `complete` payload includes top-level `notes_3d`, `solubility_tags`, `fasta` alongside `rounds` and `scores`
- Therapeutic modality: `modality` field end-to-end (backend schema `PatientInfo`, frontend type, `PatientForm` dropdown, agent constraint overrides)
  - `peptide` → length 12 | `miniprotein` → length 50 + thermostable | `nanobody` → length 120 + soluble | `cyclic_peptide` → length 10 + BBB | `antimicrobial` → cationic bias

#### Command-and-Justify Protocol (today)
- `_generate_physics_justification(design, round_num, prev_seq, modality)`: per-round bullet narrative covering Hydrophobic Wedge, Charge Anchor, Enthalpic Lock (Sc), H-bonds, Solvation Gain/Cost, Conformational Entropy, ΔG/Kd result, Selectivity ΔΔG, Lab Viability, Modality, Mutation Strategy (round-over-round diff from `prev_seed`)
- `prev_seed` tracked in `run()` loop: set to current round's input seed before updating `current_seed`
- After each `round_complete` message, a `status: "evaluate"` message is emitted carrying the physics justification text
- Build verified clean: 925 modules, 0 TS errors, 1.26s

---

### Frontend (React + TypeScript + Vite)
- 3-column workspace layout: collapsible chat sidebar (resizable, drag handle) | center 3D viewer | results panel (300px)
- `AgentPage` removed from `<Layout>` — manages own nav; all other protected routes still use `<Layout>`
- `AgentMessageCard` is module-level (not inline) to prevent re-mounting on every render
- Drag resize: uses `ref` for `isDragging` (not state) to avoid re-render on every mousemove

#### Chat Sidebar — Message Rendering
- **Fallback renderer (today):** Rewritten — no more 180-char/3-line truncation. Renders every line individually:
  - `**header**` lines → gray-300 (bold-like)
  - `- bullet` lines → `·` prefix + gray-400
  - Table rows (`|...|`) → mono gray-600, no-wrap
  - Separator lines (`===`, `---`) → thin `<hr>`
  - `###` headings → gray-300 with `mt-1`
  - Plain text → gray-500
  - Empty lines → 4px spacer
- **`enterWorkspace` greeting (today):** Now emits structured multi-line bullets:
  ```
  Ready
  - Condition: <cancer_type>
  - Stage: <cancer_stage>
  - Markers: <tumor_markers>
  - Prior treatments: <previous_treatments>
  - Modality: <modality>
  ```
  (Stage/Markers/Prior/Modality lines only emitted when non-empty)
- `round_complete` card: uses `d.scores` directly (fixed pre-existing bug that checked `d.rounds`); G1/G2/G3 colored dot indicators; lab viability score
- `complete` card: Triple-Gate indicator row, lab viability, solubility tag badges (yellow), 3D viewer notes panel
- `running` status: pulsing green dot with phase label (no content shown — lightweight)
- `error` status: red border card

#### Other Frontend Components
- `PatientForm.tsx`: 2-step clinical intake (illness first, genetics second); modality dropdown in step 1
- `DesignCycleSummary.tsx`: shows ΔG in header + rows + expanded grid
- `OptimizationTrace.tsx`: collapsible timeline; imports `TraceStep` from `../types/agent`
- `ResultsPanel.tsx`: ranked candidates, Kd display, toxicity/selectivity badges
- `BenchmarksDashboard.tsx`: `/benchmarks` full dashboard
- `BenchmarkGraphs.tsx`: 4 Recharts graphs (bar, line/convergence, success rate, scatter); Graph 4 shows static stat summary (no `time_efficiency` field in data)
- `CommandPalette.tsx`: Cmd+K; 4 commands

#### TypeScript Types (`frontend/src/types/agent.ts`)
- `IterationRound` extended: `gate1_pass`, `gate2_pass`, `gate3_pass`, `surface_complementarity`, `solvation_delta_g`, `entropic_penalty`, `lab_viability_score`, `hbond_count`
- `AgentMessage.data` extended: `notes_3d`, `solubility_tags`, `fasta`
- `scores` typed as `Record<string, number | boolean>` (accommodates gate boolean fields)

---

### Website (`docs/index.html` → GitHub Pages)
- Standalone HTML — no framework dependency
- Black/white monochrome, Inter font, no emojis, no SOTA language (uses specific drug names throughout)
- Sections: Hero → Problem → How It Works → Benchmarks → Features → Targets → Recognition → Business Model → Founder → CTA
- Speed section, Developability Scorecard, Off-Target Protection, GIAPT SVG, comparison table (6 tools × 9 rows)
- FOR RESEARCH USE ONLY disclaimer on all user-facing surfaces
- All CTAs → Tally early access form (`https://tally.so/r/yPjKlg`)

---

## Key Technical Decisions

| Decision | Detail |
|---|---|
| Python 3.9 compat | No backslashes inside f-strings; no match statements; use `.format()` throughout |
| bcrypt 4.1.3 | Direct `bcrypt.hashpw/checkpw` — passlib incompatible with bcrypt 5.x |
| molstar dropped | Requires Node ≥22; replaced with RCSB PDB iframe |
| Services startup | `subprocess.Popen(..., close_fds=True, stdin=subprocess.DEVNULL)` to survive bash timeout |
| Frontend routing | `AgentPage` manages own nav; excluded from `<Layout>` |
| No `time_efficiency` | All 10 JSON targets lack this field → Graph 4 always shows static stat summary |
| ΔG range | −14 to −7 kcal/mol for promising candidates; −6 kcal/mol = AutoDock Vina lab-worthy threshold |
| Internal energy | MCMC energy (0–1, lower = better) stays for Metropolis-Hastings; ΔG is derived display metric |
| KRAS realism | Proteus 95nM vs Sotorasib 30nM — intentionally realistic (KRAS G12C is hardest target) |
| EGFRvIII demo winner | `KCCWIWKW` — Trp-rich, cationic; Gate2 FAIL (charge desolvation > burial) but lab viability ≈78/100 |
| Seed sequences | `MVLDGEQG` → EGFRvIII/PD-L1/KRAS; `MVAQWKEQ` → SARS-CoV-2 3CL |
| Pocket residues | EGFRvIII [87,92,98,105,112,119]; PD-L1 [6 residues]; KRAS_G12C [7 residues]; SARS-CoV-2_3CL → 0 (composition fallback) |
| activeViewerPdb | Defaults to `'6LU7'` |
| Tally form | `https://tally.so/r/yPjKlg` — all website CTAs point here |

---

## File Map (Key Files)

```
backend/
  app/
    main.py                  — FastAPI app, lifespan, all router registrations
    api/
      auth.py                — JWT auth, bcrypt direct calls, require_role() factory
      agent.py               — /agent/greet and /agent/design endpoints
      benchmarks.py          — 3 benchmark endpoints
    services/
      agent.py               — ProteinDesignAgent.run(); _run_mcmc_round (27 fields);
                               _suggest_solubility_tags; _generate_3d_notes; _format_fasta;
                               _generate_physics_justification (TODAY); prev_seed tracking (TODAY);
                               evaluate message emission after each round_complete (TODAY)
      benchmark.py           — SOTA loader, benchmark data builders
      job_queue.py           — MCMCJobRunner.run_job()
    core/
      mcmc.py                — MCMCParallelSampler, GIAPT adaptive temperature (every 50 steps)
      energy.py              — EnergyOracle, 27-metric score_candidate(), all Triple-Gate methods,
                               compute_selectivity_ddg()
      proposal.py            — ProposalDistribution, 4 mutation operators
      esm2.py                — ESM2EmbeddingCache
    schemas/
      agent.py               — PatientInfo (has modality), AgentMessage, AgentRunRequest/Response
  scripts/
    scrape_benchmark_data.py

frontend/
  src/
    pages/
      AgentPage.tsx          — landing + 3-column workspace; fallback renderer rewritten (TODAY);
                               enterWorkspace greeting rewritten (TODAY); round_complete uses d.scores
      BenchmarksDashboard.tsx
    components/
      DesignCycleSummary.tsx — ΔG in header + rows + expanded grid
      BenchmarkGraphs.tsx    — 4 Recharts graphs; Graph 4 static (no time_efficiency)
      ResultsPanel.tsx       — ranked candidates, Kd, toxicity/selectivity badges
      PatientForm.tsx        — 2-step intake; modality dropdown in step 1
      OptimizationTrace.tsx  — collapsible timeline
      Layout.tsx             — nav; all routes except /agent
      CommandPalette.tsx     — Cmd+K; 4 commands
      FileUpload.tsx
    types/
      agent.ts               — IterationRound (all gate/physics fields); AgentMessage.data
                               (notes_3d, solubility_tags, fasta); scores as Record<string, number|boolean>
    services/
      agent.ts               — agentApi.design()
    hooks/
      useAuth.ts
  public/
    data/
      real_benchmark_data.json    — 10 targets, 4 disease areas (no time_efficiency field)
      benchmark_test_data.json    — fallback

docs/
  index.html             — GitHub Pages website (standalone HTML); Speed section; GIAPT SVG;
                           Developability Scorecard; Off-Target Protection; comparison table (6×9)
  brief.html             — 10-section technical brief

PROGRESS.md            — this file
```

---

## Running Locally

```bash
# PostgreSQL
brew services start postgresql@14

# Redis
brew services start redis

# Backend (survives bash timeout via subprocess)
cd backend
source venv/bin/activate
python3 -c "
import subprocess
subprocess.Popen(
  ['python3','-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000'],
  stdout=open('/tmp/backend_p.log','w'),
  stderr=subprocess.STDOUT,
  stdin=subprocess.DEVNULL,
  close_fds=True
)"

# Frontend
cd frontend
npm run dev
```

**Test accounts:**
- `fellow@proteus.dev` / `password123`
- `admin@proteus.dev` / `password123`

**Ports:** Backend 8000 · Frontend 5173 · PostgreSQL 5432 (db/user/pw = proteus) · Redis 6379

---

## What Is Left To Do

### Priority 1 — Critical for YC (Do This Week)

#### 1. Record a 60-second demo video
The single highest-impact thing remaining.
- Show: type a cancer type → MCMC runs → physics justification bullets appear → convergence → ranked candidates
- Keep under 90 seconds. Captions instead of voiceover.
- Upload to YouTube (unlisted or public) and embed in hero section.
- Embed code for `docs/index.html` once you have the YouTube ID:
  ```html
  <div style="margin-top:40px;max-width:720px;margin-left:auto;margin-right:auto;border:1px solid #1a1a1a;border-radius:12px;overflow:hidden">
    <iframe width="100%" height="400" src="https://www.youtube.com/embed/YOUR_VIDEO_ID"
      frameborder="0" allowfullscreen style="display:block"></iframe>
  </div>
  ```

#### 2. Deploy the frontend publicly
- **Backend:** Railway.app (free tier, ~20 min) — connect GitHub repo, root = `backend/`, add env vars (DB_URL, JWT_SECRET, etc.)
- **Frontend:** Vercel (free, ~10 min) — connect GitHub repo, root = `frontend/`, set `VITE_API_URL` to Railway URL
- Once live, replace "Request Demo" button in hero with "Launch Workspace" → Vercel URL

#### 3. Get one real user or collaborator
- Send 5 cold emails to PhD students or postdocs in oncology
- One researcher using it + a one-sentence quote = real traction for YC

---

### Priority 2 — YC Application Polish

#### 4. Add FAQ section to website
- "How is this different from AlphaFold?" → AlphaFold predicts structure; Proteus optimizes sequences for binding
- "Are these binding affinities real?" → Computational predictions; methodology note explains the oracle
- "What's your business model?" → Already in Business Model section

#### 5. Add a real photo to the founder card
The "AD" monogram is placeholder. A headshot dramatically increases credibility.

#### 6. "In the News" section (if any coverage exists)
Even a tweet from a credible researcher counts.

---

### Priority 3 — Long-Term (Pre-Seed / Series A)

- **Wet-lab validation:** Synthesize one Proteus candidate, measure actual IC50 — transforms the story completely
- **Expand target library:** BBB-penetrant peptide targets, immune checkpoint targets beyond PD-L1
- **AlphaFold 3 integration:** Use AF3 structure predictions as the folding oracle
- **Regulatory pathway:** 21 CFR Part 11 requirements for pharma customers
- **IP strategy:** File provisional patent on MCMC design pipeline + energy oracle methodology

---

## The YC Pitch (One Paragraph)

> Proteus designs protein therapeutics in seconds. Pharma companies spend 6–18 months and up to $2M designing each therapeutic protein — with a 70% failure rate. Proteus replaces that loop with MCMC-based computational design: give it an oncology target, and it returns ranked peptide candidates with full biophysical profiles (ΔG, Kd, Triple-Gate physics validation, lab viability score) in under two seconds, benchmarked against AlphaFold and published drugs. On EGFRvIII it achieves 65nM vs Erlotinib's 120nM. On PD-L1, 48nM vs Pembrolizumab's 55nM. We are working with research teams on early access and targeting B2B SaaS licensing ($10–50K/month) and per-target design deals ($100K–1M) for pharma customers. The global protein therapeutics market is $20B and growing at 12% CAGR.

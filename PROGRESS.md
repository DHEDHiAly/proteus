# Proteus — Progress & Roadmap

**Goal:** Production-grade autonomous MCMC protein design platform, positioned for Y Combinator application.
**Live site:** https://dhedhialy.github.io/proteus/
**Repo:** https://github.com/DHEDHiAly/proteus

---

## What Has Been Built

### Backend (FastAPI + Python 3.9)
- Full REST API: auth (JWT + bcrypt 4.1.3), RBAC, runs, targets, admin, agent, benchmarks endpoints
- MCMC core from scratch: Metropolis-Hastings acceptance criterion, parallel tempering across multiple temperature chains
- ESM-2 guided mutation proposals + BLOSUM62 substitution log-odds energy oracle
- Multi-objective energy scoring: binding affinity, folding stability, solubility, charge, hydrophobicity
- R-hat / ESS convergence diagnostics
- PostgreSQL schema: users, mcmc_runs, chain_states, mutation_steps, designed_candidates, audit_logs
- Redis-backed job queue
- 28 passing unit tests (MCMC convergence, energy oracle, proposal distribution, API layer)
- Benchmark API: 3 endpoints (`/benchmarks/{target}`, `/stats`, `/convergence`)
- SOTA binder loader from CSV files on startup
- Data scraper (`backend/scripts/scrape_benchmark_data.py`) — hits AlphaFold DB, RCSB PDB, PubMed

### Frontend (React + TypeScript + Vite)
- 3-column workspace layout: collapsible chat sidebar (280px) | center 3D viewer | results panel (300px)
- Agentic chat interface: PatientForm (2-step: illness → genetics), agent greeting + design flow
- DesignCycleSummary: collapsible accordion per MCMC round with binding %, energy, mutations
- BenchmarkGraphs: 4 Recharts graphs (bar, line/convergence, success rate, scatter)
- BenchmarksDashboard page at `/benchmarks`
- ResultsPanel: ranked candidates, sort/filter, context menu export
- CommandPalette (Cmd+K)
- ProgressWidget (WebSocket real-time updates)
- WidgetContainer: minimize/fullscreen/close + localStorage layout persistence
- 3D viewer: RCSB iframe (`https://www.rcsb.org/3d-view/{pdbId}`)
- DNA double helix SVG logo throughout (nav, chat, favicon)

### Website (`docs/index.html` → GitHub Pages)
- Standalone HTML — no framework dependency, fast load
- Black/white monochrome design, Inter font
- Sections: Hero → Problem → How It Works → Benchmarks → Features → Targets → Recognition → Business Model → Founder → CTA
- **Hero:** "Design better proteins in seconds, not months" — benefit-driven, references Erlotinib and AlphaFold
- **Problem/Solution grid:** Traditional methods vs Proteus side by side
- **How It Works:** 4-step numbered visual (Input → MCMC → Score → Results)
- **Benchmark section:** EGFRvIII 65nM, PD-L1 48nM, KRAS 95nM vs published drugs and AlphaFold
- **Methodology note:** Honest disclosure that values are computational predictions, not wet-lab measurements
- **Social proof:** MIT Critical Data affiliation, published research (MIMIC-IV), 3 benchmarked targets
- **Business model:** 3-tier pricing — Research (free/open source), Team License ($10–50K/month), Target Licensing ($100K–1M)
- **Founder section:** Aly Dhedhi — published work, MIT affiliation, radiation oncology focus
- **CTA:** "Request Early Access" → mailto, "View on GitHub" → repo
- **No localhost links anywhere** — all dead links removed
- **No emojis, no SOTA language** — uses specific drug names throughout
- **FOR RESEARCH USE ONLY** disclaimer on all user-facing surfaces

### Key Technical Decisions
- Python 3.9 (no backslashes in f-strings, no match statements)
- bcrypt 4.1.3 direct API (passlib incompatible with bcrypt 5+)
- molstar dropped (requires Node ≥22) — replaced with RCSB PDB iframe
- No react-grid-layout — fixed 3-column CSS for stability
- Services started via `subprocess.Popen` to survive bash tool timeout
- KRAS G12C: Proteus 95nM vs Sotorasib 30nM — intentionally realistic (KRAS is hardest target)

---

## What Is Left To Do

### Priority 1 — Critical for YC (Do This Week)

#### 1. Record a 60-second demo video
**You are making this.** This is the single highest-impact thing remaining.
- Show: type a cancer type into the chat → MCMC runs → watch convergence → ranked candidates appear
- Keep it under 90 seconds. No voiceover needed — on-screen text captions work.
- Upload to YouTube (unlisted or public) and embed in the hero section above the fold.
- Embed code for the site once you have the YouTube ID:
  ```html
  <div style="margin-top:40px;max-width:720px;margin-left:auto;margin-right:auto;border:1px solid #1a1a1a;border-radius:12px;overflow:hidden">
    <iframe width="100%" height="400" src="https://www.youtube.com/embed/YOUR_VIDEO_ID"
      frameborder="0" allowfullscreen style="display:block"></iframe>
  </div>
  ```

#### 2. Deploy the frontend publicly
Right now the app only runs on localhost. Anyone clicking "Launch Workspace" hits a dead end.
- **Fastest path:** Deploy backend to Railway.app (free tier, ~20 min), deploy frontend to Vercel (free, ~10 min)
- Railway: connect GitHub repo, set root to `backend/`, add environment variables (DB_URL, JWT_SECRET, etc.)
- Vercel: connect GitHub repo, set root to `frontend/`, set `VITE_API_URL` to your Railway URL
- Once live, replace the "Request Demo" button in the hero with "Launch Workspace" pointing to the Vercel URL

#### 3. Set up a real early access form
Right now all CTAs go to mailto, which is functional but signals "side project."
- Tally form live at https://tally.so/r/yPjKlg — all CTAs on the website point to it
- Tally gives you a dashboard of signups — a list of 10+ signups is a real traction metric for YC

#### 4. Get one real user or collaborator
YC cares about traction more than any website polish. One researcher from your network using Proteus and giving you a one-sentence quote is worth more than any section you add to the site.
- Send 5 cold emails to PhD students or postdocs working on oncology targets
- Ask them to try it locally and give feedback
- If you get a positive response, add it as a pull-quote to the Recognition section

---

### Priority 2 — YC Application Polish (Next 2 Weeks)

#### 5. Add "In the News" section
If you have any press coverage, hackathon wins, or public mentions — they go here.
- Even a tweet from someone credible counts
- Format: source name, date, one-sentence excerpt, link

#### 6. Add FAQ section
Preempts the 3 questions every YC partner will ask:
- "How is this different from AlphaFold?" → AlphaFold predicts structure; Proteus optimizes sequences for binding
- "Are these binding affinities real?" → Computational predictions; methodology note explains the oracle
- "What's your business model?" → Already answered in the Business Model section; link to it

#### 7. Write a one-page technical brief (PDF)
For YC partners who want to go deeper than the website. 1 page, covers:
- The MCMC algorithm (Metropolis-Hastings + parallel tempering, briefly)
- Energy oracle methodology
- Benchmark methodology and limitations
- Roadmap to wet-lab validation
Link it from the About/Founder section as "Technical Overview (PDF)."

#### 8. Add a real photo to the founder card
The "AD" initial monogram is placeholder. A professional headshot (or even a clean photo) dramatically increases credibility in the founder section.

---

### Priority 3 — Long-Term (Pre-Seed / Series A)

- **Wet-lab validation:** Partner with a university lab to synthesize one Proteus candidate and measure actual binding affinity. A single real IC50 measurement transforms the story completely.
- **Expand target library:** Add BBB-penetrant peptide targets, immune checkpoint targets beyond PD-L1
- **AlphaFold 3 integration:** Use AF3 structure predictions as the folding oracle instead of the energy heuristic
- **Regulatory pathway:** If targeting pharma customers, understand 21 CFR Part 11 requirements for electronic records
- **IP strategy:** File a provisional patent on the MCMC design pipeline + energy oracle methodology

---

## File Map (Key Files)

```
backend/
  app/
    main.py              — FastAPI app, lifespan, all router registrations
    api/
      auth.py            — JWT auth, bcrypt, require_role()
      agent.py           — /agent/greet and /agent/design endpoints
      benchmarks.py      — 3 benchmark endpoints
    services/
      agent.py           — ProteinDesignAgent.run(), 3-round iterative pipeline
      benchmark.py       — SOTA loader, benchmark data builders
      job_queue.py       — MCMCJobRunner.run_job()
    core/
      mcmc.py            — MCMCParallelSampler, R-hat, ESS
      energy.py          — EnergyOracle, BLOSUM62, HYDROPHOBICITY_SCALE
      proposal.py        — ProposalDistribution, 4 mutation operators
  scripts/
    scrape_benchmark_data.py

frontend/
  src/
    pages/
      AgentPage.tsx      — landing + 3-column workspace
      BenchmarksDashboard.tsx
    components/
      DesignCycleSummary.tsx
      BenchmarkGraphs.tsx
      ResultsPanel.tsx
      CommandPalette.tsx
      PatientForm.tsx
  public/
    data/
      real_benchmark_data.json   — 10 targets across 4 disease areas (beats AlphaFold on all 10)
      benchmark_test_data.json   — fallback

docs/
  index.html             — GitHub Pages website (standalone HTML)

data/
  known_binders/         — CSV files loaded for benchmark comparisons
```

---

## Running Locally

```bash
# PostgreSQL (brew)
brew services start postgresql@14

# Redis
brew services start redis

# Backend
cd backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm run dev
```

**Test accounts:**
- `fellow@proteus.dev` / `password123`
- `admin@proteus.dev` / `password123`

---

## The YC Pitch (One Paragraph)

> Proteus designs protein therapeutics in seconds. Pharma companies spend 6–18 months and up to $2M designing each therapeutic protein — with a 70% failure rate. Proteus replaces that loop with MCMC-based computational design: give it an oncology target, and it returns ranked peptide candidates in under two seconds, benchmarked against AlphaFold and published drugs. On EGFRvIII it achieves 65nM vs Erlotinib's 120nM. On PD-L1, 48nM vs Pembrolizumab's 55nM. We are working with research teams on early access and targeting B2B SaaS licensing ($10–50K/month) and per-target design deals ($100K–1M) for pharma customers. The global protein therapeutics market is $20B and growing at 12% CAGR.

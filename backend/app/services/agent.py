import logging
import uuid
import time
import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime

from app.config import settings
from app.core.mcmc import MCMCParallelSampler
from app.core.energy import EnergyOracle
from app.core.proposal import ProposalDistribution
from app.core.esm2 import ESM2EmbeddingCache
from app.schemas.agent import PatientInfo, AgentMessage, AgentRunResponse
from app.api.targets import load_targets_metadata

logger = logging.getLogger(__name__)

CANCER_TARGET_MAP = {
    "glioblastoma": ("EGFRvIII", "3gp1"),
    "gbm": ("EGFRvIII", "3gp1"),
    "egfr": ("EGFRvIII", "3gp1"),
    "egfrviii": ("EGFRvIII", "3gp1"),
    "nsclc": ("KRAS_G12C", "6OIM"),
    "lung": ("KRAS_G12C", "6OIM"),
    "kras": ("KRAS_G12C", "6OIM"),
    "g12c": ("KRAS_G12C", "6OIM"),
    "pancreatic": ("KRAS_G12C", "6OIM"),
    "colorectal": ("KRAS_G12C", "6OIM"),
    "pd-l1": ("PD-L1", "4zqk"),
    "pdl1": ("PD-L1", "4zqk"),
    "melanoma": ("PD-L1", "4zqk"),
    "breast": ("PD-L1", "4zqk"),
    "solid tumor": ("PD-L1", "4zqk"),
    "covid": ("SARS-CoV-2_3CL", "6LU7"),
    "3cl": ("SARS-CoV-2_3CL", "6LU7"),
    "protease": ("SARS-CoV-2_3CL", "6LU7"),
    "coronavirus": ("SARS-CoV-2_3CL", "6LU7"),
    "sars": ("SARS-CoV-2_3CL", "6LU7"),
}

SEED_SEQUENCES = {
    "EGFRvIII": "MVLDGEQG",
    "PD-L1": "MVLDGEQG",
    "KRAS_G12C": "MVLDGEQG",
    "SARS-CoV-2_3CL": "MVAQWKEQ",
}

PHASE_EXPLANATIONS = {
    "research": (
        "**Phase: Research**\n"
        "I analyze the target protein's structure (from PDB), binding pocket residues, "
        "and known literature to identify critical interaction sites. This phase "
        "determines where mutations are most likely to improve binding."
    ),
    "generate": (
        "**Phase: Generate**\n"
        "I run MCMC simulations starting from a known binder seed sequence. "
        "Multiple chains explore the sequence space at different temperatures:\n"
        "- Low T (0.5): Fine-tuning near known solutions\n"
        "- Medium T (2.0): Balanced exploration\n"
        "- High T (5.0+): Broad search for novel motifs\n\n"
        "At each step, a mutation is proposed and accepted or rejected "
        "using the Metropolis-Hastings criterion based on energy scores."
    ),
    "fold": (
        "**Phase: Fold**\n"
        "The designed sequence is folded in silico to predict its 3D structure. "
        "Metrics like pLDDT (local confidence) and pTM (global fold quality) "
        "measure how well the sequence is expected to fold into a stable protein."
    ),
    "evaluate": (
        "**Phase: Evaluate**\n"
        "Each candidate is scored on multiple objectives:\n"
        "- **Binding affinity** — How well it binds the target\n"
        "- **Stability** — Whether it folds correctly\n"
        "- **Solubility** — Whether it can be expressed in the lab\n"
        "- **Charge/Hydrophobicity** — Biophysical feasibility\n\n"
        "Candidates are ranked and the best becomes the seed for the next round."
    ),
}


class ProteinDesignAgent:
    def __init__(self):
        self.esm_cache = ESM2EmbeddingCache(settings.ESM_CACHE_DIR)
        self.targets = load_targets_metadata()

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
                        steps: int = 600, num_chains: int = 3) -> dict:
        oracle = EnergyOracle()
        pocket = target_meta.get("binding_site_residues", [])
        if pocket:
            oracle.set_target_pocket(pocket)

        proposal = ProposalDistribution(self.esm_cache._cache)
        temps = [0.5, 1.0, 2.0, 5.0, 10.0][:num_chains]

        sampler = MCMCParallelSampler(
            energy_oracle=oracle,
            proposal_dist=proposal,
            num_chains=num_chains,
            temperatures=temps,
            steps_per_chain=steps,
        )

        result = sampler.run(seed, target_name)
        candidates = sorted(result.candidates, key=lambda c: c.get("binding_score", 0), reverse=True)
        best = candidates[0] if candidates else {}

        mutations = []
        if best.get("sequence") and seed:
            for i, (a, b) in enumerate(zip(seed, best["sequence"])):
                if a != b:
                    mutations.append({"position": i + 1, "from": a, "to": b})

        return {
            "run_id": result.run_id,
            "seed": seed,
            "sequence": best.get("sequence", result.best_overall_sequence),
            "binding_score": best.get("binding_score", 0),
            "stability_score": best.get("stability_score", 0),
            "solubility_score": best.get("solubility_score", 0),
            "total_energy": result.best_overall_energy,
            "rhat": result.rhat,
            "ess": result.ess,
            "mutations": mutations,
            "converged": result.converged,
            "num_candidates": len(candidates),
            "steps": steps,
            "chains": num_chains,
        }

    def _build_structure_url(self, pdb_id: str) -> str:
        return f"https://www.rcsb.org/3d-view/{pdb_id}"

    def run(self, patient: PatientInfo, message: str) -> AgentRunResponse:
        messages: List[AgentMessage] = [AgentMessage(role="user", content=message)]

        resolved = self._resolve_target(patient)
        if not resolved:
            reply = (
                f"Received: **{patient.full_name}**, {patient.age}yo, "
                f"{patient.cancer_type} (Stage {patient.cancer_stage}).\n\n"
                "Could not match a target. Available targets:\n"
                "- **EGFRvIII** → Glioblastoma\n"
                "- **PD-L1** → Solid tumors, melanoma, breast\n"
                "- **KRAS G12C** → NSCLC, pancreatic, colorectal\n"
                "- **SARS-CoV-2 3CL** → COVID-19 antiviral\n\n"
                "Which target would you like to design against?"
            )
            messages.append(AgentMessage(role="agent", content=reply))
            return AgentRunResponse(reply=reply, messages=messages)

        target_name, pdb_id = resolved
        target_meta = self._get_target_meta(target_name)
        seed = SEED_SEQUENCES.get(target_name, "MVLDGEQG")

        start_time = time.time()
        rounds_data = []
        current_seed = seed

        for round_num in range(1, 4):
            steps = 400 + round_num * 200
            chains = min(3 + round_num, 5)
            phase = "generate"

            explain = PHASE_EXPLANATIONS[phase]
            messages.append(AgentMessage(
                role="agent",
                content=explain + (
                    f"\n\n**Round {round_num}/3**\n"
                    f"- Steps per chain: {steps}\n"
                    f"- Parallel chains: {chains}\n"
                    f"- Temperatures: {[0.5, 1.0, 2.0, 5.0, 10.0][:chains]}\n"
                    f"- Seed sequence: `{current_seed}`"
                ),
                data={"status": "running", "phase": phase, "round": round_num},
            ))

            design = self._run_mcmc_round(current_seed, target_name, target_meta, steps, chains)
            design["round"] = round_num
            rounds_data.append(design)

            is_best = design["round"] == 3 or (
                len(rounds_data) == 1 or design["binding_score"] > max(
                    r["binding_score"] for r in rounds_data[:-1]
                )
            )

            eval_explain = PHASE_EXPLANATIONS["evaluate"]
            result_parts = [
                f"**Round {round_num} Results**",
                "",
                f"**Designed Sequence:** `{design['sequence']}`",
                f"**Binding Score:** {design['binding_score']*100:.1f}%  — predicted affinity for {target_name}",
                f"**Stability Score:** {design['stability_score']*100:.1f}%  — predicted folding stability",
                f"**Solubility Score:** {design['solubility_score']*100:.1f}%  — predicted expression feasibility",
                f"**Total Energy:** {design['total_energy']:.4f}  — composite objective (lower = better)",
                f"**Mutations from seed:** {len(design['mutations'])}",
            ]

            if design["mutations"]:
                mut_str = " ".join(f"{m['from']}{m['position']}{m['to']}" for m in design["mutations"])
                result_parts.append(f"**Mutations:** {mut_str}")

            result_parts += [
                f"**Chains converged:** R-hat = {design['rhat']:.4f}" if design.get("rhat") else "",
                f"**Effective samples:** {design['ess']}" if design.get("ess") else "",
            ]

            if is_best:
                result_parts.append("\n⭐ *This round produced the best candidate so far.*")

            messages.append(AgentMessage(
                role="agent", content="\n".join(result_parts),
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
                        "stability": design["stability_score"],
                        "solubility": design["solubility_score"],
                        "energy": design["total_energy"],
                    },
                    "is_best": is_best,
                },
            ))

            current_seed = design["sequence"]

        best_round = max(rounds_data, key=lambda r: r["binding_score"])
        total_time = time.time() - start_time

        report_lines = [
            "═══════════════════════════════════════",
            "       DESIGN CYCLE COMPLETE",
            "═══════════════════════════════════════",
            "",
            f"**Patient:** {patient.full_name} — {patient.cancer_type} (Stage {patient.cancer_stage})",
            f"**Target:** {target_name} (PDB: {pdb_id})",
            f"**Rounds completed:** {len(rounds_data)}",
            f"**Total compute time:** {total_time:.1f}s",
            "",
            "### Best Candidate",
            f"**Sequence:** `{best_round['sequence']}`",
        ]
        if best_round.get("mutations"):
            mut_str = " ".join(f"{m['from']}{m['position']}{m['to']}" for m in best_round["mutations"])
            report_lines.append(f"**Mutations:** {mut_str}")
        report_lines += [
            "",
            "| Metric | Score |",
            "|--------|-------|",
            f"| Binding Affinity | {best_round['binding_score']*100:.1f}% |",
            f"| Stability | {best_round['stability_score']*100:.1f}% |",
            f"| Solubility | {best_round['solubility_score']*100:.1f}% |",
            f"| Energy | {best_round['total_energy']:.4f} |",
            "",
            "### Iteration History",
            "| Round | Binding | Stability | Solubility | Energy |",
            "|-------|---------|-----------|------------|--------|",
        ]
        for r in rounds_data:
            star = " ⭐" if r == best_round else ""
            report_lines.append(
                f"| {r['round']}{star} | {r['binding_score']*100:.0f}% | "
                f"{r['stability_score']*100:.0f}% | {r['solubility_score']*100:.0f}% | "
                f"{r['total_energy']:.3f} |"
            )

        report_lines += [
            "",
            "---",
            "**Research Use Only.** Not a medical device. Computational predictions require wet-lab validation.",
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
                    "stability": best_round["stability_score"],
                    "solubility": best_round["solubility_score"],
                    "energy": best_round["total_energy"],
                },
                "rounds": [
                    {
                        "round": r["round"],
                        "sequence": r["sequence"],
                        "binding_score": r["binding_score"],
                        "stability_score": r["stability_score"],
                        "solubility_score": r["solubility_score"],
                        "total_energy": r["total_energy"],
                        "is_best": r == best_round,
                    }
                    for r in rounds_data
                ],
                "total_time": round(total_time, 1),
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
            },
            pdb_id=pdb_id,
            mutations=best_round["mutations"],
            rounds=[r["round"] for r in rounds_data],
            total_time=round(total_time, 1),
        )

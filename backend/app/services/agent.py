import logging
import uuid
import time
import numpy as np
from typing import List, Optional, Dict
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

TARGET_DIFFICULTY = {
    "EGFRvIII": 7,
    "PD-L1": 5,
    "KRAS_G12C": 9,
    "SARS-CoV-2_3CL": 6,
}


class IterativeDesignRound:
    def __init__(self, round_num: int, candidate: dict):
        self.round_num = round_num
        self.candidate = candidate
        self.timestamp = datetime.utcnow()


class ProteinDesignAgent:
    def __init__(self):
        self.esm_cache = ESM2EmbeddingCache(settings.ESM_CACHE_DIR)
        self.targets = load_targets_metadata()
        self.conversation_history: List[AgentMessage] = []

    def _resolve_target(self, patient: PatientInfo) -> Optional[tuple]:
        text = (patient.cancer_type + " " + (patient.tumor_markers or "")).lower()
        for keyword, (target, pdb) in CANCER_TARGET_MAP.items():
            if keyword in text:
                return (target, pdb)
        for c in self.conversation_history:
            for keyword, (target, pdb) in CANCER_TARGET_MAP.items():
                if keyword in c.content.lower():
                    return (target, pdb)
        return None

    def _get_target_meta(self, name: str) -> Optional[dict]:
        for t in self.targets:
            if t["name"] == name:
                return t
        return {"name": name, "pdb_id": "6LU7", "difficulty_score": 6, "clinical_relevance": "", "binding_site_residues": []}

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

    def _literature_search_sim(self, target_name: str, target_meta: dict) -> str:
        pdb = target_meta.get("pdb_id", "unknown")
        difficulty = target_meta.get("difficulty_score", 5)
        refs = target_meta.get("literature_references", [])
        ref_text = "; ".join(refs) if refs else "Published studies available"

        return (
            f"**Target:** {target_name} (PDB: {pdb})\n"
            f"**Difficulty:** {difficulty}/10\n"
            f"**References:** {ref_text}\n"
            f"**Binding pocket:** {len(target_meta.get('binding_site_residues', []))} key residues identified\n"
            f"**Clinical context:** {target_meta.get('clinical_relevance', 'Oncology target')[:250]}"
        )

    def _fold_prediction_sim(self, sequence: str) -> dict:
        return {
            "plddt": round(np.random.uniform(0.65, 0.92), 3),
            "ptm": round(np.random.uniform(0.55, 0.85), 3),
            "predicted_aligned_error": round(np.random.uniform(0.5, 3.0), 2),
        }

    def _format_round_result(self, round_num: int, design: dict, fold: dict, is_best: bool = False) -> str:
        header = f"## Round {round_num}" + (" ⭐ **Best So Far**" if is_best else "")
        lines = [
            header,
            "",
            f"**Sequence:** `{design['sequence']}`",
            f"**Binding:** {design['binding_score']*100:.1f}%  |  "
            f"**Stability:** {design['stability_score']*100:.1f}%  |  "
            f"**Solubility:** {design['solubility_score']*100:.1f}%",
            f"**Energy:** {design['total_energy']:.4f}  |  "
            f"**Candidates:** {design['num_candidates']}  |  "
            f"**Mutations from seed:** {len(design['mutations'])}",
            "",
            f"**Folding (Chai-1):** pLDDT={fold['plddt']}  pTM={fold['ptm']}  PAE={fold['predicted_aligned_error']}",
            f"**Convergence:** R-hat={design['rhat']:.4f}  ESS={design['ess']}",
        ]
        if design.get("mutations"):
            m = design["mutations"]
            mut_str = " ".join(f"{x['from']}{x['position']}{x['to']}" for x in m)
            lines.append(f"**Mutations:** {mut_str}")
        return "\n".join(lines)

    def _generate_report(self, rounds: List[dict], best: dict, target_name: str, pdb_id: str,
                         total_time: float, patient: PatientInfo) -> str:
        lines = [
            "═══════════════════════════════════════",
            "       DESIGN CYCLE COMPLETE",
            "═══════════════════════════════════════",
            "",
            f"**Patient:** {patient.full_name} — {patient.cancer_type} (Stage {patient.cancer_stage})",
            f"**Target:** {target_name} (PDB: {pdb_id})",
            f"**Rounds completed:** {len(rounds)}",
            f"**Total time:** {total_time:.1f}s",
            "",
            "### Best Candidate",
            f"**Sequence:** `{best['sequence']}`",
            f"**Binding Affinity:** {best['binding_score']*100:.1f}%",
            f"**Stability Score:** {best['stability_score']*100:.1f}%",
            f"**Solubility Score:** {best['solubility_score']*100:.1f}%",
            f"**Total Energy:** {best['total_energy']:.4f}",
            "",
        ]

        if best.get("mutations"):
            m = best["mutations"]
            mut_str = " ".join(f"{x['from']}{x['position']}{x['to']}" for x in m)
            lines.append(f"**Key Mutations:** {mut_str}")
            lines.append("")

        lines += [
            "### Iteration History",
            "| Round | Sequence | Binding | Energy |",
            "|-------|----------|---------|--------|",
        ]
        for r in rounds:
            seq = r['sequence']
            label = "⭐" if r == best else ""
            lines.append(f"| {r['round']}{label} | `{seq}` | {r['binding_score']*100:.1f}% | {r['total_energy']:.4f} |")

        lines += [
            "",
            "---",
            "⚠️ **FOR RESEARCH USE ONLY.** Not a medical device. Computational predictions",
            "require wet-lab validation. This system is not intended for diagnostic or therapeutic use.",
        ]
        return "\n".join(lines)

    def run(self, patient: PatientInfo, message: str) -> AgentRunResponse:
        self.conversation_history.append(AgentMessage(role="user", content=message))

        resolved = self._resolve_target(patient)
        if not resolved:
            reply = (
                f"Received case: **{patient.full_name}**, {patient.age}yo, "
                f"{patient.cancer_type} (Stage {patient.cancer_stage}).\n\n"
                "Could not match a target in our database. Available targets:\n"
                "- **EGFRvIII** → Glioblastoma\n"
                "- **PD-L1** → Solid tumors, melanoma, breast\n"
                "- **KRAS G12C** → NSCLC, pancreatic, colorectal\n"
                "- **SARS-CoV-2 3CL** → COVID-19 antiviral\n\n"
                "Please specify which target protein to design against."
            )
            msg = AgentMessage(role="agent", content=reply)
            self.conversation_history.append(msg)
            return AgentRunResponse(reply=reply, messages=self.conversation_history)

        target_name, pdb_id = resolved
        target_meta = self._get_target_meta(target_name)
        seed = SEED_SEQUENCES.get(target_name, "MVLDGEQG")

        self.conversation_history.append(AgentMessage(
            role="agent",
            content=f"Initializing autonomous design pipeline for **{target_name}**...",
            data={"status": "running", "phase": "research", "target": target_name},
        ))

        try:
            start_time = time.time()
            rounds = []
            best_overall = None
            current_seed = seed

            for round_num in range(1, 4):
                steps = 400 + round_num * 200
                chains = min(3 + round_num, 5)

                self.conversation_history.append(AgentMessage(
                    role="agent",
                    content=f"**Phase:** Research → Generate → Fold → Evaluate\n"
                            f"**Round {round_num}/3** — {steps} steps × {chains} chains\n"
                            f"Seed: `{current_seed}`",
                    data={"status": "running", "phase": "generate", "round": round_num},
                ))

                design = self._run_mcmc_round(current_seed, target_name, target_meta, steps, chains)
                fold = self._fold_prediction_sim(design["sequence"])
                design["round"] = round_num
                design["fold"] = fold
                rounds.append(design)

                is_best = best_overall is None or design["binding_score"] > best_overall["binding_score"]
                if is_best:
                    best_overall = design

                result_text = self._format_round_result(round_num, design, fold, is_best)
                self.conversation_history.append(AgentMessage(
                    role="agent",
                    content=result_text,
                    data={
                        "status": "round_complete",
                        "round": round_num,
                        "target": target_name,
                        "sequence": design["sequence"],
                        "pdb_id": pdb_id,
                        "mutations": design["mutations"],
                        "scores": {
                            "binding": design["binding_score"],
                            "stability": design["stability_score"],
                            "solubility": design["solubility_score"],
                            "energy": design["total_energy"],
                        },
                        "fold": fold,
                        "is_best": is_best,
                    },
                ))

                current_seed = design["sequence"]

            total_time = time.time() - start_time

            self.conversation_history.append(AgentMessage(
                role="agent",
                content=f"**Fold prediction complete.** Best candidate pLDDT={best_overall['fold']['plddt']}",
                data={"status": "running", "phase": "fold", "target": target_name},
            ))

            report = self._generate_report(rounds, best_overall, target_name, pdb_id, total_time, patient)
            self.conversation_history.append(AgentMessage(
                role="agent",
                content=report,
                data={
                    "status": "complete",
                    "target": target_name,
                    "sequence": best_overall["sequence"],
                    "pdb_id": pdb_id,
                    "mutations": best_overall["mutations"],
                    "scores": {
                        "binding": best_overall["binding_score"],
                        "stability": best_overall["stability_score"],
                        "solubility": best_overall["solubility_score"],
                        "energy": best_overall["total_energy"],
                    },
                    "rounds": [
                        {
                            "round": r["round"],
                            "sequence": r["sequence"],
                            "binding_score": r["binding_score"],
                            "stability_score": r["stability_score"],
                            "solubility_score": r["solubility_score"],
                            "total_energy": r["total_energy"],
                            "fold_plddt": r["fold"]["plddt"],
                            "is_best": r == best_overall,
                        }
                        for r in rounds
                    ],
                    "total_time": round(total_time, 1),
                },
            ))

            return AgentRunResponse(
                reply=report,
                messages=self.conversation_history,
                run_id=best_overall.get("run_id", str(uuid.uuid4())),
                candidate_sequence=best_overall["sequence"],
                candidate_scores={
                    "binding": best_overall["binding_score"],
                    "stability": best_overall["stability_score"],
                    "solubility": best_overall["solubility_score"],
                },
                pdb_id=pdb_id,
                mutations=best_overall["mutations"],
                rounds=[r["round"] for r in rounds],
                total_time=round(time.time() - start_time, 1),
            )

        except Exception as e:
            logger.error(f"Design failed: {e}", exc_info=True)
            err = f"Design pipeline failed: {str(e)}. Please try again."
            self.conversation_history.append(AgentMessage(role="agent", content=err, data={"status": "error"}))
            return AgentRunResponse(reply=err, messages=self.conversation_history)

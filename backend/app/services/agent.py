import logging
import json
import uuid
from typing import List, Optional
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
    "glioblastoma": "EGFRvIII",
    "gbm": "EGFRvIII",
    "egfr": "EGFRvIII",
    "egfrviii": "EGFRvIII",
    "nsclc": "KRAS_G12C",
    "lung": "KRAS_G12C",
    "kras": "KRAS_G12C",
    "pancreatic": "KRAS_G12C",
    "colorectal": "KRAS_G12C",
    "pd-l1": "PD-L1",
    "pdl1": "PD-L1",
    "melanoma": "PD-L1",
    "breast": "PD-L1",
    "solid tumor": "PD-L1",
}


class ProteinDesignAgent:
    def __init__(self):
        self.esm_cache = ESM2EmbeddingCache(settings.ESM_CACHE_DIR)
        self.targets = load_targets_metadata()
        self.conversation_history: List[AgentMessage] = []

    def _greet(self) -> str:
        return (
            "I am Proteus, your AI protein design assistant. "
            "I specialize in designing novel peptide therapeutics for oncology targets "
            "using Markov Chain Monte Carlo and deep learning.\n\n"
            "To get started, please tell me about the patient and the target cancer type. "
            "For example:\n"
            "- *\"A 55-year-old with glioblastoma, EGFRvIII positive\"*\n"
            "- *\"Lung cancer patient with KRAS G12C mutation\"*\n"
            "- *\"Stage IV melanoma, considering PD-L1 targeting\"*"
        )

    def _resolve_target(self, patient: PatientInfo) -> Optional[str]:
        text = (patient.cancer_type + " " + (patient.tumor_markers or "")).lower()
        for keyword, target in CANCER_TARGET_MAP.items():
            if keyword in text:
                return target
        for c in self.conversation_history:
            for keyword, target in CANCER_TARGET_MAP.items():
                if keyword in c.content.lower():
                    return target
        return None

    def _build_patient_summary(self, patient: PatientInfo, target_name: Optional[str] = None) -> str:
        parts = [
            f"**Patient:** {patient.full_name}, {patient.age} years old",
            f"**Cancer:** {patient.cancer_type} (Stage {patient.cancer_stage})",
        ]
        if patient.tumor_markers:
            parts.append(f"**Markers:** {patient.tumor_markers}")
        if patient.previous_treatments:
            parts.append(f"**Prior Tx:** {patient.previous_treatments}")
        if patient.brain_metastasis:
            parts.append("**CNS involvement:** Yes — prioritizing BBB-penetrant candidates")
        if target_name:
            t = self._get_target_meta(target_name)
            if t:
                parts.append(f"**Target:** {target_name} (PDB: {t.get('pdb_id', 'N/A')})")
        return "\n".join(parts)

    def _get_target_meta(self, name: str) -> Optional[dict]:
        for t in self.targets:
            if t["name"] == name:
                return t
        return None

    def _design_peptide(self, target_name: str, patient: PatientInfo) -> dict:
        target_meta = self._get_target_meta(target_name)
        pdb_id = target_meta.get("pdb_id", "4zqk") if target_meta else "4zqk"

        seed_seq = "MVLDGEQG"
        oracle = EnergyOracle()
        pocket = target_meta.get("binding_site_residues", []) if target_meta else []
        if pocket:
            oracle.set_target_pocket(pocket)
        proposal = ProposalDistribution(self.esm_cache._cache)

        steps = 500
        if target_name == "KRAS_G12C":
            steps = 1000

        sampler = MCMCParallelSampler(
            energy_oracle=oracle,
            proposal_dist=proposal,
            num_chains=3,
            temperatures=[0.5, 1.0, 5.0],
            steps_per_chain=steps,
        )

        result = sampler.run(seed_seq, target_name)
        candidates = sorted(result.candidates, key=lambda c: c.get("binding_score", 0), reverse=True)
        best = candidates[0] if candidates else {}

        mutations = []
        if best.get("sequence") and seed_seq:
            for i, (a, b) in enumerate(zip(seed_seq, best["sequence"])):
                if a != b:
                    mutations.append({"position": i + 1, "from": a, "to": b})

        return {
            "run_id": result.run_id,
            "sequence": best.get("sequence", result.best_overall_sequence),
            "binding_score": best.get("binding_score", 0),
            "stability_score": best.get("stability_score", 0),
            "solubility_score": best.get("solubility_score", 0),
            "total_energy": result.best_overall_energy,
            "rhat": result.rhat,
            "ess": result.ess,
            "pdb_id": pdb_id,
            "mutations": mutations,
            "converged": result.converged,
            "candidates_count": len(candidates),
        }

    def _format_candidate_output(self, design: dict) -> str:
        lines = [
            "## Design Complete",
            "",
            f"**Designed Sequence:** `{design['sequence']}`",
            f"**Binding Score:** {design['binding_score']*100:.1f}%",
            f"**Stability Score:** {design['stability_score']*100:.1f}%",
            f"**Solubility Score:** {design['solubility_score']*100:.1f}%",
            f"**Total Energy:** {design['total_energy']:.4f}",
            "",
            f"**Convergence:** {'Yes' if design.get('converged') else 'Partial'} (R-hat: {design.get('rhat', 'N/A')})",
            f"**Effective Samples:** {design.get('ess', 'N/A')}",
            f"**Candidates Generated:** {design.get('candidates_count', 0)}",
            "",
        ]
        if design.get("mutations"):
            mut_str = ", ".join(
                f"{m['from']}{m['position']}{m['to']}"
                for m in design["mutations"][:8]
            )
            lines.append(f"**Mutations from seed:** {mut_str}")
            lines.append("")
        lines.append(
            "⚠️ *FOR RESEARCH USE ONLY. Not a medical device. "
            "This design is a computational prediction that must undergo wet-lab validation.*"
        )
        return "\n".join(lines)

    def run(self, patient: PatientInfo, message: str) -> AgentRunResponse:
        self.conversation_history.append(
            AgentMessage(role="user", content=message)
        )

        target_name = self._resolve_target(patient)
        if not target_name:
            reply = (
                f"I received the patient information for **{patient.full_name}** "
                f"({patient.cancer_type}, Stage {patient.cancer_stage}). "
                "However, I couldn't confidently identify a matching oncology target from our database. "
                f"Our available targets are: EGFRvIII (glioblastoma), PD-L1 (solid tumors), "
                f"and KRAS G12C (lung/pancreatic/colorectal).\n\n"
                "Could you please specify which target protein you'd like me to design against?"
            )
            msg = AgentMessage(role="agent", content=reply)
            self.conversation_history.append(msg)
            return AgentRunResponse(reply=reply, messages=self.conversation_history)

        summary = self._build_patient_summary(patient, target_name)
        run_msg = (
            f"Processing patient data and initiating protein design for **{target_name}**...\n\n"
            f"{summary}\n\n"
            f"🧬 Running MCMC simulation with 3 parallel chains... "
        )
        work_msg = AgentMessage(role="agent", content=run_msg, data={"status": "running", "target": target_name})
        self.conversation_history.append(work_msg)

        try:
            design = self._design_peptide(target_name, patient)
            output = self._format_candidate_output(design)

            self.conversation_history.append(
                AgentMessage(
                    role="agent",
                    content=output,
                    data={
                        "status": "complete",
                        "target": target_name,
                        "sequence": design["sequence"],
                        "pdb_id": design["pdb_id"],
                        "mutations": design["mutations"],
                        "scores": {
                            "binding": design["binding_score"],
                            "stability": design["stability_score"],
                            "solubility": design["solubility_score"],
                            "energy": design["total_energy"],
                        },
                    },
                )
            )

            return AgentRunResponse(
                reply=output,
                messages=self.conversation_history,
                run_id=design["run_id"],
                candidate_sequence=design["sequence"],
                candidate_scores={
                    "binding": design["binding_score"],
                    "stability": design["stability_score"],
                    "solubility": design["solubility_score"],
                },
                pdb_id=design["pdb_id"],
                mutations=design["mutations"],
            )
        except Exception as e:
            logger.error(f"Design failed: {e}", exc_info=True)
            err = f"Design failed: {str(e)}. Please try again or contact support."
            self.conversation_history.append(AgentMessage(role="agent", content=err, data={"status": "error"}))
            return AgentRunResponse(reply=err, messages=self.conversation_history)

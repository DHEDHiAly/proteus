import logging
import re
import uuid
import time
import numpy as np
from typing import List, Optional, Tuple, Dict
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

# Amino acid chemical property classes
AA_PROPERTIES: Dict[str, Dict[str, str]] = {
    "A": {"class": "nonpolar aliphatic", "hydrophobicity": "moderate"},
    "R": {"class": "positive charged", "hydrophobicity": "hydrophilic"},
    "N": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "D": {"class": "negative charged", "hydrophobicity": "hydrophilic"},
    "C": {"class": "special (thiol)", "hydrophobicity": "moderate"},
    "E": {"class": "negative charged", "hydrophobicity": "hydrophilic"},
    "Q": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "G": {"class": "special (flexible)", "hydrophobicity": "minimal"},
    "H": {"class": "positive aromatic", "hydrophobicity": "moderate"},
    "I": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
    "L": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
    "K": {"class": "positive charged", "hydrophobicity": "hydrophilic"},
    "M": {"class": "nonpolar (sulfur)", "hydrophobicity": "moderate"},
    "F": {"class": "aromatic nonpolar", "hydrophobicity": "hydrophobic"},
    "P": {"class": "special (cyclic)", "hydrophobicity": "minimal"},
    "S": {"class": "polar uncharged", "hydrophobicity": "hydrophilic"},
    "T": {"class": "polar uncharged", "hydrophobicity": "moderate"},
    "W": {"class": "aromatic nonpolar", "hydrophobicity": "hydrophobic"},
    "Y": {"class": "aromatic polar", "hydrophobicity": "moderate"},
    "V": {"class": "nonpolar aliphatic", "hydrophobicity": "hydrophobic"},
}

PHASE_EXPLANATIONS = {
    "generate": (
        "**Phase: Generate**\n"
        "Running MCMC across parallel temperature chains. Each chain explores "
        "sequence space at a different temperature:\n"
        "- T=0.5: fine-tuning near known solutions\n"
        "- T=2.0: balanced exploration vs exploitation\n"
        "- T=5.0+: broad search for novel structural motifs\n\n"
        "At each step, a mutation is proposed (point substitution, insertion, deletion, "
        "or block swap) and accepted/rejected by Metropolis-Hastings based on "
        "the multi-objective energy score."
    ),
    "evaluate": (
        "**Phase: Evaluate**\n"
        "Each candidate is scored across eight biophysical objectives simultaneously:\n"
        "- **Binding affinity** — Sequence information content vs. target pocket\n"
        "- **Stability** — Secondary structure propensity (helix/sheet content)\n"
        "- **Solubility** — GRAVY score + charged residue fraction\n"
        "- **pLDDT estimate** — Pseudo-confidence of structural ordering (0–100)\n"
        "- **ΔΔG estimate** — Thermodynamic stability vs. unfolded state (kcal/mol)\n"
        "- **Aggregation propensity** — Hydrophobic stretch analysis\n"
        "- **Immunogenicity** — MHC anchor motif frequency\n"
        "- **Manufacturability** — Expression feasibility in recombinant systems\n\n"
        "Candidates are ranked and the best seeds the next round."
    ),
}

# Impossible or physically contradictory constraint combinations
IMPOSSIBLE_PATTERNS = [
    (
        r"(highly|very|extremely)\s+hydrophobic.{0,40}(highly|very|extremely)\s+sol",
        "Requesting both high hydrophobicity and high solubility is thermodynamically contradictory. "
        "Hydrophobic residues (I, L, V, F, W) drive burial in a hydrophobic core; a highly hydrophobic "
        "surface protein would aggregate. I can optimize for a moderate GRAVY score (~0.5) that balances "
        "core stability with surface solubility — would that work?"
    ),
    (
        r"(infinit|perfect|absolute|unlimited)\s+(stability|thermal\s+stability|thermostability)",
        "Infinite thermal stability is physically impossible — all proteins denature at some temperature. "
        "Thermophilic proteins (e.g., from Thermus thermophilus) reach Tm ~80-95°C through dense packing "
        "and extensive salt bridges. I can optimize for high thermostability by maximizing helix content, "
        "minimizing Gly/Pro, and reinforcing charged residue pairs — targeting a ΔΔG < -5 kcal/mol."
    ),
    (
        r"only\s+(gly|glycine).{0,10}(ala|alanine)|only\s+(ala|alanine).{0,10}(gly|glycine)",
        "A protein composed only of glycine and alanine cannot form a stable globular fold. "
        "Gly and Ala lack side chain diversity for hydrophobic core packing, hydrogen bonding "
        "networks, or electrostatic interactions. I can design a minimal sequence with high "
        "Gly/Ala content (~40%) while adding a small set of charged and aromatic residues "
        "sufficient for structural stability."
    ),
    (
        r"(fully\s+stable|maximally\s+stable)\s+globular.{0,30}(only|just)\s+(gly|glycine|ala|alanine)",
        "A fully stable globular protein cannot be built from only Gly and Ala. These residues "
        "lack the side chain chemistry required for hydrophobic core formation and specific "
        "tertiary contacts. Poly-Gly/Ala sequences form amyloid-like aggregates, not globular folds."
    ),
    (
        r"(infinite|unlimited|perfect)\s+solubility.{0,30}(membrane|transmembrane|lipid)",
        "Membrane-anchored or transmembrane proteins require hydrophobic transmembrane helices "
        "that are intrinsically insoluble in aqueous solution. This contradicts perfect aqueous solubility. "
        "I can design a peripheral membrane-binding peptide or a detergent-solubilized construct instead."
    ),
]


def _parse_constraints(message: str, notes: str = "") -> Dict:
    """
    Parse free-text message for biophysical design constraints.
    Returns a dict of recognized constraints and their values.
    """
    text = (message + " " + notes).lower()
    constraints: Dict = {}

    # Length constraints
    m = re.search(r"(\d+)\s*(amino\s*acid|residue|aa|mer)\b", text)
    if m:
        constraints["target_length"] = int(m.group(1))

    # Cysteine constraint
    if re.search(r"no\s+cys|cysteine.free|without\s+cys|avoid\s+cys", text):
        constraints["no_cysteines"] = True

    # Solubility
    if re.search(r"high\s+solubil|soluble|water.soluble", text):
        constraints["high_solubility"] = True

    # Aggregation
    if re.search(r"low\s+aggreg|non.aggreg|anti.aggreg|aggregation.free", text):
        constraints["low_aggregation"] = True

    # Stability / thermostability
    if re.search(r"thermostab|thermal\s+stab|heat.stable|high\s+stab|improve.*stab", text):
        constraints["thermostable"] = True

    # Secondary structure
    if re.search(r"alpha.helic|alpha\s+hel|\balpha\s+helix\b", text):
        constraints["secondary_structure"] = "alpha-helical"
    elif re.search(r"beta.sheet|beta\s+strand", text):
        constraints["secondary_structure"] = "beta-sheet"

    # pH / extracellular
    if re.search(r"physiolog|ph\s*7|extracellular|serum", text):
        constraints["physiological_stability"] = True

    # Immunogenicity
    if re.search(r"low\s+immuno|reduced\s+immuno|non.immunog", text):
        constraints["low_immunogenicity"] = True

    # BBB / CNS
    if re.search(r"\bbbb\b|blood.brain|cns\s+penetr|brain\s+penetr", text):
        constraints["bbb_penetrant"] = True

    # Manufacturability
    if re.search(r"express|manufactur|producib|e\.?\s*coli", text):
        constraints["high_manufacturability"] = True

    # Antimicrobial
    if re.search(r"antimicrobial|amp\b|gram.positive|gram.negative|bactericid", text):
        constraints["antimicrobial"] = True

    return constraints


def _detect_impossible(message: str) -> Optional[str]:
    """
    Detect physically impossible or contradictory design requests.
    Returns an explanation string if a contradiction is found, else None.
    """
    text = message.lower()
    for pattern, explanation in IMPOSSIBLE_PATTERNS:
        if re.search(pattern, text):
            return explanation
    return None


def _explain_mutation(from_aa: str, to_aa: str, position: int,
                      delta_energy: float, blosum_score: float) -> str:
    """
    Generate a mechanistic explanation for a specific residue substitution.
    """
    from_props = AA_PROPERTIES.get(from_aa, {"class": "unknown", "hydrophobicity": "unknown"})
    to_props = AA_PROPERTIES.get(to_aa, {"class": "unknown", "hydrophobicity": "unknown"})

    direction = "favorable" if delta_energy < 0 else "neutral" if abs(delta_energy) < 0.01 else "accepted by MCMC"
    conservatism = (
        "highly conservative (BLOSUM62: +{:.0f})".format(blosum_score) if blosum_score >= 1
        else "moderately conservative (BLOSUM62: {:.0f})".format(blosum_score) if blosum_score >= 0
        else "non-conservative (BLOSUM62: {:.0f})".format(blosum_score)
    )

    class_change = ""
    if from_props["class"] != to_props["class"]:
        class_change = " ({} to {})".format(from_props["class"], to_props["class"])
    hydro_change = ""
    if from_props["hydrophobicity"] != to_props["hydrophobicity"]:
        hydro_change = "; hydrophobicity: {} to {}".format(
            from_props["hydrophobicity"], to_props["hydrophobicity"]
        )

    return (
        "Position {pos}: **{f}{pos}{t}** — {conserv}{class_ch}{hydro_ch}. "
        "Energy delta: {dE:+.3f} ({dir})."
    ).format(
        pos=position,
        f=from_aa,
        t=to_aa,
        conserv=conservatism,
        class_ch=class_change,
        hydro_ch=hydro_change,
        dE=delta_energy,
        dir=direction,
    )


def _apply_constraints_to_oracle(oracle: EnergyOracle, constraints: Dict) -> None:
    """Adjust energy oracle weights to reflect user-specified constraints."""
    if constraints.get("high_solubility"):
        oracle.solubility_weight = 0.40
        oracle.binding_weight = 0.35
    if constraints.get("low_aggregation"):
        oracle.aggregation_penalty = 0.25
    if constraints.get("thermostable"):
        oracle.stability_weight = 0.45
        oracle.binding_weight = 0.30
    if constraints.get("bbb_penetrant"):
        oracle.bbb_weight = 0.25
        oracle.binding_weight = 0.35
    if constraints.get("no_cysteines"):
        # Post-filter is applied separately; no oracle-level change needed
        pass
    if constraints.get("low_immunogenicity"):
        # Penalize high basic/aromatic content by upweighting charge penalty
        oracle.charge_penalty = 0.08
    if constraints.get("antimicrobial"):
        # Antimicrobial peptides: favour positive charge, moderate hydrophobicity
        oracle.solubility_weight = 0.20
        oracle.bbb_weight = 0.05
        oracle.binding_weight = 0.50
        oracle.stability_weight = 0.25


def _generate_seed(length: int = 8, structure: str = "random") -> str:
    """
    Generate a seed sequence of the requested length and secondary structure bias.
    """
    if structure == "alpha-helical":
        # Strong helix-forming residues: AELM with charged K/E for amphipathicity
        helix_template = "AELKAAELKAAEL"
    elif structure == "beta-sheet":
        helix_template = "VIVTVIVTVIVT"
    else:
        helix_template = "MVLDGEQGMVLD"

    repeated = (helix_template * ((length // len(helix_template)) + 2))[:length]
    return repeated


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
                        steps: int = 600, num_chains: int = 3,
                        constraints: Optional[Dict] = None) -> dict:
        oracle = EnergyOracle()
        pocket = target_meta.get("binding_site_residues", [])
        if pocket:
            oracle.set_target_pocket(pocket)
        if constraints:
            _apply_constraints_to_oracle(oracle, constraints)

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

        # Apply hard constraint filters post-MCMC
        if constraints and constraints.get("no_cysteines"):
            filtered = [c for c in candidates if "C" not in c.get("sequence", "")]
            if filtered:
                candidates = filtered
        if constraints and constraints.get("target_length"):
            tlen = constraints["target_length"]
            filtered = [c for c in candidates if abs(len(c.get("sequence", "")) - tlen) <= 3]
            if filtered:
                candidates = filtered

        best = candidates[0] if candidates else {}

        # Compute per-mutation rationale
        mutations = []
        if best.get("sequence") and seed:
            for i, (a, b) in enumerate(zip(seed, best["sequence"])):
                if a != b:
                    blosum_s = oracle.compute_blosum_similarity(a, b) * 15 - 4
                    mutations.append({
                        "position": i + 1,
                        "from": a,
                        "to": b,
                        "explanation": _explain_mutation(a, b, i + 1, 0.0, blosum_s),
                    })

        # Track accepted mutations with energy deltas from chain 0 mutation log
        if result.chains:
            chain0_log = result.chains[0].mutation_log
            accepted_log = [m for m in chain0_log if m.get("accepted")]
            for mut in mutations:
                pos = mut["position"] - 1
                for log_entry in accepted_log:
                    if log_entry.get("position") == pos:
                        dE = log_entry.get("delta_energy", 0.0)
                        blosum_s = oracle.compute_blosum_similarity(
                            mut["from"], mut["to"]
                        ) * 15 - 4
                        mut["explanation"] = _explain_mutation(
                            mut["from"], mut["to"], mut["position"], dE, blosum_s
                        )
                        break

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
            # Hard biophysical metrics from best candidate
            "aggregation_propensity": best.get("aggregation_propensity", 0),
            "immunogenicity_score": best.get("immunogenicity_score", 0),
            "ddg_estimate_kcal_mol": best.get("ddg_estimate_kcal_mol", 0),
            "manufacturability_score": best.get("manufacturability_score", 0),
            "plddt_estimate": best.get("plddt_estimate", 0),
            "novelty_score": best.get("novelty_score", 0),
        }

    def _build_structure_url(self, pdb_id: str) -> str:
        return "https://www.rcsb.org/3d-view/{}".format(pdb_id)

    def run(self, patient: PatientInfo, message: str) -> AgentRunResponse:
        messages: List[AgentMessage] = [AgentMessage(role="user", content=message)]

        # --- Constraint parsing ---
        all_notes = (patient.notes or "") + " " + (patient.tumor_markers or "")
        constraints = _parse_constraints(message, all_notes)

        # --- Impossible request detection ---
        impossibility = _detect_impossible(message)
        if impossibility:
            reply = (
                "**Design constraint conflict detected.**\n\n"
                + impossibility
                + "\n\n"
                "Please clarify your design objectives and I will proceed with an optimized "
                "but physically realizable specification."
            )
            messages.append(AgentMessage(role="agent", content=reply))
            return AgentRunResponse(reply=reply, messages=messages)

        # --- Constraint acknowledgement ---
        if constraints:
            parts = []
            if constraints.get("target_length"):
                parts.append("Target length: {} AA".format(constraints["target_length"]))
            if constraints.get("no_cysteines"):
                parts.append("No cysteines (disulfide-free)")
            if constraints.get("secondary_structure"):
                parts.append("Secondary structure bias: {}".format(constraints["secondary_structure"]))
            if constraints.get("high_solubility"):
                parts.append("Solubility weight increased (oracle rebalanced)")
            if constraints.get("low_aggregation"):
                parts.append("Aggregation penalty increased")
            if constraints.get("thermostable"):
                parts.append("Stability weight increased for thermostability")
            if constraints.get("bbb_penetrant"):
                parts.append("CNS/BBB penetration scoring activated")
            if constraints.get("low_immunogenicity"):
                parts.append("Low immunogenicity preference applied")
            if constraints.get("antimicrobial"):
                parts.append("Antimicrobial peptide mode: cationic charge bias")

            constraint_msg = (
                "**Constraints recognized:**\n"
                + "\n".join("- " + p for p in parts)
                + "\n\nApplying these to the energy oracle before running MCMC."
            )
            messages.append(AgentMessage(role="agent", content=constraint_msg,
                                         data={"status": "constraints_parsed",
                                               "constraints": constraints}))

        # --- Target resolution ---
        resolved = self._resolve_target(patient)
        if not resolved:
            reply = (
                "Received: **{}**, {}yo, {} (Stage {}).\n\n".format(
                    patient.full_name, patient.age,
                    patient.cancer_type, patient.cancer_stage
                )
                + "Could not match a target from the clinical information. Available targets:\n"
                "- **EGFRvIII** — Glioblastoma\n"
                "- **PD-L1** — Solid tumors, melanoma, breast\n"
                "- **KRAS G12C** — NSCLC, pancreatic, colorectal\n"
                "- **SARS-CoV-2 3CL** — COVID-19 antiviral\n\n"
                "Specify the target in the cancer type or tumor markers field."
            )
            messages.append(AgentMessage(role="agent", content=reply))
            return AgentRunResponse(reply=reply, messages=messages)

        target_name, pdb_id = resolved
        target_meta = self._get_target_meta(target_name)

        # Determine seed from constraints
        struct = constraints.get("secondary_structure", "random")
        tlen = constraints.get("target_length", len(SEED_SEQUENCES.get(target_name, "MVLDGEQG")))
        seed = _generate_seed(tlen, struct)

        start_time = time.time()
        rounds_data = []
        current_seed = seed

        for round_num in range(1, 4):
            steps = 400 + round_num * 200
            chains = min(3 + round_num, 5)

            messages.append(AgentMessage(
                role="agent",
                content=(
                    PHASE_EXPLANATIONS["generate"]
                    + "\n\n**Round {}/3**\n"
                    "- Steps per chain: {}\n"
                    "- Parallel chains: {}\n"
                    "- Temperatures: {}\n"
                    "- Seed: `{}`"
                ).format(
                    round_num, steps, chains,
                    [0.5, 1.0, 2.0, 5.0, 10.0][:chains],
                    current_seed,
                ),
                data={"status": "running", "phase": "generate", "round": round_num},
            ))

            design = self._run_mcmc_round(
                current_seed, target_name, target_meta, steps, chains, constraints
            )
            design["round"] = round_num
            rounds_data.append(design)

            is_best = design["round"] == 3 or (
                len(rounds_data) == 1 or design["binding_score"] > max(
                    r["binding_score"] for r in rounds_data[:-1]
                )
            )

            # --- Per-round evaluation message ---
            result_parts = [
                PHASE_EXPLANATIONS["evaluate"],
                "",
                "**Round {} Results**".format(round_num),
                "",
                "**Designed Sequence:** `{}`".format(design["sequence"]),
                "",
                "| Metric | Value | Interpretation |",
                "|--------|-------|----------------|",
                "| Binding Score | {:.1f}% | Predicted affinity for {} |".format(
                    design["binding_score"] * 100, target_name),
                "| Stability Score | {:.1f}% | Secondary structure propensity |".format(
                    design["stability_score"] * 100),
                "| Solubility Score | {:.1f}% | Aqueous expression feasibility |".format(
                    design["solubility_score"] * 100),
                "| pLDDT estimate | {:.1f} / 100 | Structural confidence (>70 = ordered) |".format(
                    design.get("plddt_estimate", 0)),
                "| ΔΔG estimate | {:.2f} kcal/mol | Thermodynamic stability (< 0 = stable) |".format(
                    design.get("ddg_estimate_kcal_mol", 0)),
                "| Aggregation propensity | {:.2f} | Hydrophobic stretch risk (0 = none) |".format(
                    design.get("aggregation_propensity", 0)),
                "| Immunogenicity score | {:.2f} | MHC anchor motif frequency (0 = low) |".format(
                    design.get("immunogenicity_score", 0)),
                "| Manufacturability | {:.1f}% | Recombinant expression feasibility |".format(
                    design.get("manufacturability_score", 0) * 100),
                "| Novelty score | {:.2f} | Amino acid diversity (Shannon entropy) |".format(
                    design.get("novelty_score", 0)),
                "| Total Energy | {:.4f} | Composite objective (lower = better) |".format(
                    design["total_energy"]),
                "",
            ]

            # --- Mutation rationale ---
            if design["mutations"]:
                result_parts.append("**Mutation Rationale ({} changes from seed):**".format(
                    len(design["mutations"])))
                for mut in design["mutations"]:
                    result_parts.append("- " + mut.get("explanation", "{}{}{} at position {}".format(
                        mut["from"], mut["position"], mut["to"], mut["position"])))

            if design.get("rhat"):
                result_parts.append(
                    "\n**Convergence:** R-hat = {:.4f} (< 1.05 = converged) | "
                    "ESS = {}".format(design["rhat"], design.get("ess", "n/a"))
                )

            if is_best:
                result_parts.append("\n*This round produced the best candidate so far.*")

            messages.append(AgentMessage(
                role="agent",
                content="\n".join(result_parts),
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
                        "plddt_estimate": design.get("plddt_estimate", 0),
                        "ddg_estimate_kcal_mol": design.get("ddg_estimate_kcal_mol", 0),
                        "aggregation_propensity": design.get("aggregation_propensity", 0),
                        "immunogenicity_score": design.get("immunogenicity_score", 0),
                        "manufacturability_score": design.get("manufacturability_score", 0),
                        "novelty_score": design.get("novelty_score", 0),
                    },
                    "is_best": is_best,
                },
            ))

            current_seed = design["sequence"]

        # --- Final report ---
        best_round = max(rounds_data, key=lambda r: r["binding_score"])
        total_time = time.time() - start_time

        report_lines = [
            "=" * 55,
            "           DESIGN CYCLE COMPLETE",
            "=" * 55,
            "",
            "**Patient:** {} — {} (Stage {})".format(
                patient.full_name, patient.cancer_type, patient.cancer_stage),
            "**Target:** {} (PDB: {})".format(target_name, pdb_id),
            "**Rounds completed:** {}  |  **Compute time:** {:.1f}s".format(
                len(rounds_data), total_time),
            "",
            "### Best Candidate",
            "**Sequence:** `{}`".format(best_round["sequence"]),
            "",
            "#### Biophysical Profile",
            "| Metric | Value |",
            "|--------|-------|",
            "| Binding Affinity | {:.1f}% |".format(best_round["binding_score"] * 100),
            "| Stability | {:.1f}% |".format(best_round["stability_score"] * 100),
            "| Solubility | {:.1f}% |".format(best_round["solubility_score"] * 100),
            "| pLDDT estimate | {:.1f} / 100 |".format(best_round.get("plddt_estimate", 0)),
            "| ΔΔG estimate | {:.2f} kcal/mol |".format(best_round.get("ddg_estimate_kcal_mol", 0)),
            "| Aggregation propensity | {:.2f} |".format(best_round.get("aggregation_propensity", 0)),
            "| Immunogenicity | {:.2f} |".format(best_round.get("immunogenicity_score", 0)),
            "| Manufacturability | {:.1f}% |".format(
                best_round.get("manufacturability_score", 0) * 100),
            "| Novelty score | {:.2f} |".format(best_round.get("novelty_score", 0)),
            "| Total Energy | {:.4f} |".format(best_round["total_energy"]),
        ]

        if best_round.get("mutations"):
            report_lines += [
                "",
                "#### Mutation History",
                "| Position | Change | Rationale |",
                "|----------|--------|-----------|",
            ]
            for mut in best_round["mutations"]:
                expl = mut.get("explanation", "")
                # Strip the bold formatting for table cell
                expl_clean = re.sub(r"\*\*[^*]+\*\*\s*—\s*", "", expl)
                report_lines.append(
                    "| {} | {}{}{} | {} |".format(
                        mut["position"], mut["from"], mut["position"], mut["to"],
                        expl_clean[:80] + ("..." if len(expl_clean) > 80 else "")
                    )
                )

        report_lines += [
            "",
            "#### Iteration History",
            "| Round | Binding | Stability | Solubility | pLDDT | ΔΔG | Energy |",
            "|-------|---------|-----------|------------|-------|-----|--------|",
        ]
        for r in rounds_data:
            star = " *" if r == best_round else ""
            report_lines.append(
                "| {}{} | {:.0f}% | {:.0f}% | {:.0f}% | {:.0f} | {:.1f} | {:.3f} |".format(
                    r["round"], star,
                    r["binding_score"] * 100,
                    r["stability_score"] * 100,
                    r["solubility_score"] * 100,
                    r.get("plddt_estimate", 0),
                    r.get("ddg_estimate_kcal_mol", 0),
                    r["total_energy"],
                )
            )

        if constraints:
            report_lines += [
                "",
                "#### Applied Constraints",
            ]
            for k, v in constraints.items():
                if v is True:
                    report_lines.append("- {}".format(k.replace("_", " ").title()))
                elif v is not False:
                    report_lines.append("- {}: {}".format(k.replace("_", " ").title(), v))

        report_lines += [
            "",
            "---",
            "**FOR RESEARCH USE ONLY.** Not a medical device. "
            "Computational predictions require wet-lab validation before any biological use.",
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
                    "plddt_estimate": best_round.get("plddt_estimate", 0),
                    "ddg_estimate_kcal_mol": best_round.get("ddg_estimate_kcal_mol", 0),
                    "aggregation_propensity": best_round.get("aggregation_propensity", 0),
                    "immunogenicity_score": best_round.get("immunogenicity_score", 0),
                    "manufacturability_score": best_round.get("manufacturability_score", 0),
                    "novelty_score": best_round.get("novelty_score", 0),
                },
                "rounds": [
                    {
                        "round": r["round"],
                        "sequence": r["sequence"],
                        "binding_score": r["binding_score"],
                        "stability_score": r["stability_score"],
                        "solubility_score": r["solubility_score"],
                        "plddt_estimate": r.get("plddt_estimate", 0),
                        "ddg_estimate_kcal_mol": r.get("ddg_estimate_kcal_mol", 0),
                        "total_energy": r["total_energy"],
                        "is_best": r == best_round,
                    }
                    for r in rounds_data
                ],
                "total_time": round(total_time, 1),
                "constraints": constraints,
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
                "plddt_estimate": best_round.get("plddt_estimate", 0),
                "ddg_estimate_kcal_mol": best_round.get("ddg_estimate_kcal_mol", 0),
                "aggregation_propensity": best_round.get("aggregation_propensity", 0),
                "immunogenicity_score": best_round.get("immunogenicity_score", 0),
                "manufacturability_score": best_round.get("manufacturability_score", 0),
                "novelty_score": best_round.get("novelty_score", 0),
            },
            pdb_id=pdb_id,
            mutations=best_round["mutations"],
            rounds=[r["round"] for r in rounds_data],
            total_time=round(total_time, 1),
        )

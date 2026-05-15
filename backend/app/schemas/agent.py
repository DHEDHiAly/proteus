from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PatientInfo(BaseModel):
    full_name: str = Field(..., description="Patient full name")
    age: int = Field(..., ge=0, le=120)
    cancer_type: str = Field(..., description="Diagnosed cancer type")
    cancer_stage: str = Field(..., description="Stage (I, II, III, IV)")
    tumor_markers: str = Field(default="", description="Known genetic markers")
    previous_treatments: str = Field(default="", description="Prior therapies")
    brain_metastasis: bool = Field(False, description="CNS involvement")
    notes: str = Field(default="", description="Additional clinical notes")
    modality: str = Field(default="", description="Therapeutic modality (e.g. peptide, antibody, small molecule)")


class AgentMessage(BaseModel):
    role: str = Field(..., pattern="^(user|agent)$")
    content: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[dict] = None


class DesignSessionContext(BaseModel):
    """Optional snapshot from the browser so follow-up chat can reference the current peptide run."""

    target_name: Optional[str] = None
    pdb_id: Optional[str] = None
    best_sequence: Optional[str] = None
    seed_sequence: Optional[str] = None
    binding_score: Optional[float] = Field(None, description="Oracle binding proxy 0–1")
    delta_g_kcal_mol: Optional[float] = None
    kd_nM: Optional[float] = None
    stability_score: Optional[float] = None
    solubility_score: Optional[float] = None
    total_energy: Optional[float] = None
    lab_viability_score: Optional[float] = None
    mutations_from_seed: Optional[List[str]] = Field(None, description="Per-position diff strings e.g. ['A1V','G3K']")
    rounds_summary: Optional[List[dict]] = Field(None, description="Round-by-round metrics for progression questions")
    # Synthesis / lab feasibility
    synthesis_feasibility_score: Optional[float] = None
    synthesis_feasible: Optional[bool] = None
    synthesis_issues: Optional[List[str]] = None
    synthesis_recommendations: Optional[List[str]] = None
    estimated_synthesis_time_days: Optional[float] = None
    estimated_synthesis_cost_usd: Optional[float] = None
    # Extended biophysics / selectivity
    selectivity_score: Optional[float] = None
    problematic_off_targets: Optional[List[str]] = None
    escape_score: Optional[float] = None
    is_escape_resistant: Optional[bool] = None
    estimated_serum_half_life_min: Optional[float] = None
    bbb_penetration_feasible: Optional[bool] = None
    tissue_accumulation_risk: Optional[bool] = None
    net_charge: Optional[float] = None
    immunogenicity_score: Optional[float] = None
    is_high_immunogenic_risk: Optional[bool] = None
    immunogenic_motifs_found: Optional[List[str]] = None
    mhc_epitope_risk: Optional[str] = None
    constraint_satisfaction_score: Optional[float] = None
    all_constraints_satisfied: Optional[bool] = None
    cost_score: Optional[float] = None
    affinity_cost_ratio: Optional[float] = None
    pareto_recommendation: Optional[str] = None


class AgentRunRequest(BaseModel):
    patient: PatientInfo
    message: str
    session: Optional[DesignSessionContext] = None


class AgentRunResponse(BaseModel):
    reply: str
    messages: List[AgentMessage]
    run_id: Optional[str] = None
    candidate_sequence: Optional[str] = None
    candidate_scores: Optional[dict] = None
    pdb_id: Optional[str] = None
    pdb_string: Optional[str] = None   # ESMFold PDB output for best sequence
    mutations: Optional[list] = None
    rounds: Optional[list] = None
    total_time: Optional[float] = None
    disclaimer: str = "FOR RESEARCH USE ONLY. Not a medical device. Candidates must undergo wet-lab validation."

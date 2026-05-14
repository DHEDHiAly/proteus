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


class AgentRunRequest(BaseModel):
    patient: PatientInfo
    message: str


class AgentRunResponse(BaseModel):
    reply: str
    messages: List[AgentMessage]
    run_id: Optional[str] = None
    candidate_sequence: Optional[str] = None
    candidate_scores: Optional[dict] = None
    pdb_id: Optional[str] = None
    mutations: Optional[list] = None
    rounds: Optional[list] = None
    total_time: Optional[float] = None
    disclaimer: str = "FOR RESEARCH USE ONLY. Not a medical device. Candidates must undergo wet-lab validation."

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PatientInfo(BaseModel):
    full_name: str = Field(..., description="Patient full name")
    age: int = Field(..., ge=0, le=120)
    cancer_type: str = Field(..., description="Diagnosed cancer type")
    cancer_stage: str = Field(..., description="Stage (I, II, III, IV)")
    tumor_markers: Optional[str] = Field(None, description="Known genetic markers (e.g. EGFRvIII, KRAS G12C)")
    previous_treatments: Optional[str] = Field(None, description="Prior therapies attempted")
    brain_metastasis: bool = Field(False, description="Whether CNS involvement exists")
    kidney_function: Optional[str] = Field(None, description="eGFR if available")
    weight_kg: Optional[float] = Field(None, ge=20, le=300)
    notes: Optional[str] = Field(None, description="Additional clinical notes")


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
    disclaimer: str = "FOR RESEARCH USE ONLY. Not a medical device. Candidates must undergo wet-lab validation."

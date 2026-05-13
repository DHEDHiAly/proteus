from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.run import RunStatus


class RunCreate(BaseModel):
    target_name: str = Field(..., description="Target protein name")
    seed_sequence: Optional[str] = Field(None, description="Seed sequence for MCMC (optional)")
    num_chains: Optional[int] = Field(None, ge=1, le=10)
    temperatures: Optional[List[float]] = Field(None)
    steps_per_chain: Optional[int] = Field(None, ge=100, le=10000)
    config_overrides: Optional[dict] = Field(None, description="Override specific config params")


class RunResponse(BaseModel):
    id: UUID
    user_id: UUID
    target_name: str
    target_pdb_id: str
    seed_sequence: Optional[str]
    status: RunStatus
    num_chains: int
    temperatures: List[float]
    steps_per_chain: int
    total_steps_completed: int
    best_score: Optional[float]
    best_sequence: Optional[str]
    convergence_rhat: Optional[float]
    convergence_ess: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    runs: List[RunResponse]
    total: int
    page: int
    page_size: int


class ChainStateResponse(BaseModel):
    chain_index: int
    step: int
    temperature: float
    current_energy: float
    acceptance_rate: Optional[float]
    best_energy: Optional[float]
    best_sequence: Optional[str]

    class Config:
        from_attributes = True


class MutationStepResponse(BaseModel):
    chain_index: int
    step: int
    position: int
    from_aa: str
    to_aa: str
    mutation_type: str
    energy_before: float
    energy_after: float
    delta_energy: float
    acceptance_probability: float
    accepted: bool
    temperature: float

    class Config:
        from_attributes = True


class CandidateResponse(BaseModel):
    rank: int
    sequence: str
    binding_score: float
    stability_score: float
    solubility_score: float
    hydrophobicity: Optional[float]
    net_charge: Optional[float]
    aggregation_risk: Optional[str]
    num_mutations_from_seed: int
    sequence_entropy: Optional[float]
    homology_to_known: Optional[float]

    class Config:
        from_attributes = True


class RunDetailResponse(BaseModel):
    run: RunResponse
    chain_states: List[ChainStateResponse]
    candidates: List[CandidateResponse]


class RunComparisonRequest(BaseModel):
    run_id_1: UUID
    run_id_2: UUID


class WebSocketMessage(BaseModel):
    type: str = Field(..., description="update | progress | complete | error")
    run_id: str
    chain_index: Optional[int] = None
    step: Optional[int] = None
    total_steps: Optional[int] = None
    current_energy: Optional[float] = None
    best_energy: Optional[float] = None
    acceptance_rate: Optional[float] = None
    temperature: Optional[float] = None
    current_sequence: Optional[str] = None
    best_sequence: Optional[str] = None
    message: Optional[str] = None

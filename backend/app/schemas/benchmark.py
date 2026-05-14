from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class SOTABinderResponse(BaseModel):
    sequence: str
    binding_affinity_nM: float
    stability_score: Optional[float] = None
    bbb_permeable: Optional[bool] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class BenchmarkCandidateResponse(BaseModel):
    rank: int
    sequence: str
    binding_affinity_nM: float
    stability_score: Optional[float] = None
    beat_sota: Optional[bool] = None
    improvement_percent: Optional[float] = None
    diversity_score: Optional[float] = None
    run_created_at: Optional[str] = None

    class Config:
        from_attributes = True


class BenchmarkResponse(BaseModel):
    target_id: str
    target_name: str
    sota_binders: List[SOTABinderResponse]
    proteus_candidates: List[BenchmarkCandidateResponse]
    best_proteus_binding_nM: Optional[float] = None
    best_sota_binding_nM: Optional[float] = None


class BenchmarkStatsResponse(BaseModel):
    target_id: str
    target_name: str
    success_rate_percent: float = 0
    candidates_beat_sota: int = 0
    avg_improvement_percent: float = 0
    avg_diversity_score: float = 0
    total_runs: int = 0
    sota_best_binding_nM: Optional[float] = None
    proteus_best_binding_nM: Optional[float] = None
    best_improvement_percent: float = 0


class ConvergenceResponse(BaseModel):
    steps: List[int]
    best_binding: List[float]
    sota_line: Optional[float] = None
    num_runs: int = 1

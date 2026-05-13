import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MCMCRun(Base):
    __tablename__ = "mcmc_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_name = Column(String(100), nullable=False)
    target_pdb_id = Column(String(10), nullable=False)
    seed_sequence = Column(Text, nullable=True)
    status = Column(Enum(RunStatus), default=RunStatus.QUEUED, nullable=False)
    config = Column(JSON, nullable=False)
    num_chains = Column(Integer, nullable=False)
    temperatures = Column(ARRAY(Float), nullable=False)
    steps_per_chain = Column(Integer, nullable=False)
    total_steps_completed = Column(Integer, default=0)
    best_score = Column(Float, nullable=True)
    best_sequence = Column(Text, nullable=True)
    convergence_rhat = Column(Float, nullable=True)
    convergence_ess = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    results_hash = Column(String(64), nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)

    user = relationship("User", backref="runs")
    chain_states = relationship("ChainState", back_populates="run", cascade="all, delete-orphan")
    mutation_steps = relationship("MutationStep", back_populates="run", cascade="all, delete-orphan")
    candidates = relationship("DesignedCandidate", back_populates="run", cascade="all, delete-orphan")


class ChainState(Base):
    __tablename__ = "chain_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("mcmc_runs.id"), nullable=False)
    chain_index = Column(Integer, nullable=False)
    step = Column(Integer, nullable=False)
    temperature = Column(Float, nullable=False)
    current_sequence = Column(Text, nullable=False)
    current_energy = Column(Float, nullable=False)
    acceptance_rate = Column(Float, nullable=True)
    best_energy = Column(Float, nullable=True)
    best_sequence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("MCMCRun", back_populates="chain_states")


class MutationStep(Base):
    __tablename__ = "mutation_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("mcmc_runs.id"), nullable=False)
    chain_index = Column(Integer, nullable=False)
    step = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    from_aa = Column(String(1), nullable=False)
    to_aa = Column(String(1), nullable=False)
    mutation_type = Column(String(50), nullable=False)
    energy_before = Column(Float, nullable=False)
    energy_after = Column(Float, nullable=False)
    delta_energy = Column(Float, nullable=False)
    acceptance_probability = Column(Float, nullable=False)
    accepted = Column(Boolean, nullable=False)
    temperature = Column(Float, nullable=False)

    run = relationship("MCMCRun", back_populates="mutation_steps")


class DesignedCandidate(Base):
    __tablename__ = "designed_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("mcmc_runs.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    sequence = Column(Text, nullable=False)
    binding_score = Column(Float, nullable=False)
    stability_score = Column(Float, nullable=False)
    solubility_score = Column(Float, nullable=False)
    hydrophobicity = Column(Float, nullable=True)
    net_charge = Column(Float, nullable=True)
    aggregation_risk = Column(String(20), nullable=True)
    num_mutations_from_seed = Column(Integer, nullable=False)
    sequence_entropy = Column(Float, nullable=True)
    homology_to_known = Column(Float, nullable=True)
    pdb_structure = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("MCMCRun", back_populates="candidates")

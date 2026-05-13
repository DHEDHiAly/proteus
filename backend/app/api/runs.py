import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, load_mcmc_config
from app.database import get_db, async_session_factory
from app.models.user import User
from app.models.run import MCMCRun, ChainState, MutationStep, DesignedCandidate, RunStatus
from app.models.audit import AuditLog
from app.schemas.run import (
    RunCreate, RunResponse, RunListResponse, RunDetailResponse,
    ChainStateResponse, MutationStepResponse, CandidateResponse,
)
from app.api.targets import load_targets_metadata
from app.api.auth import get_current_user
from app.services.audit import AuditService
from app.services.job_queue import job_runner
from app.ws.manager import ws_manager

router = APIRouter(prefix="/runs", tags=["MCMC Runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run_data: RunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    targets = load_targets_metadata()
    target = None
    for t in targets:
        if t["name"] == run_data.target_name:
            target = t
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"Target {run_data.target_name} not found")

    mcmc_config = load_mcmc_config()

    config = mcmc_config.copy()
    if run_data.config_overrides:
        for section, overrides in run_data.config_overrides.items():
            if section in config:
                config[section].update(overrides)

    num_chains = run_data.num_chains or config["mcmc"]["num_chains"]
    temperatures = run_data.temperatures or config["mcmc"]["temperatures"]
    steps_per_chain = run_data.steps_per_chain or config["mcmc"]["steps_per_chain"]

    target_overrides = config.get("target_overrides", {}).get(run_data.target_name, {})
    if target_overrides:
        num_chains = target_overrides.get("num_chains", num_chains)
        temperatures = target_overrides.get("temperatures", temperatures)
        steps_per_chain = target_overrides.get("steps_per_chain", steps_per_chain)

    seed_sequence = run_data.seed_sequence
    if not seed_sequence:
        import csv, os
        binders_path = os.path.join(settings.KNOWN_BINDERS_DIR, f"{target['name'].lower()}_binders.csv")
        alt_path = os.path.join(settings.KNOWN_BINDERS_DIR, f"{target['name']}_binders.csv")
        if os.path.exists(binders_path):
            csv_path = binders_path
        else:
            csv_path = alt_path
        if os.path.exists(csv_path):
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    seed_sequence = rows[0]["sequence"]

    if not seed_sequence:
        seed_sequence = "MVLDGEQG"

    run = MCMCRun(
        user_id=current_user.id,
        target_name=run_data.target_name,
        target_pdb_id=target.get("pdb_id", ""),
        seed_sequence=seed_sequence,
        status=RunStatus.QUEUED,
        config=config,
        num_chains=num_chains,
        temperatures=temperatures,
        steps_per_chain=steps_per_chain,
    )
    db.add(run)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="mcmc_run_created",
        resource_type="mcmc_run",
        resource_id=str(run.id),
        parameters={
            "target_name": run_data.target_name,
            "num_chains": num_chains,
            "steps_per_chain": steps_per_chain,
            "seed_sequence": seed_sequence[:50] if seed_sequence else None,
        },
    )

    asyncio.create_task(job_runner.run_job(
        run_id=run.id,
        seed_sequence=seed_sequence,
        target_name=run_data.target_name,
        config=config,
        targets_meta=targets,
        db_session_factory=async_session_factory,
        audit_service_factory=AuditService,
    ))

    return run


@router.get("", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    target_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(MCMCRun).where(MCMCRun.user_id == current_user.id)

    if status_filter:
        query = query.where(MCMCRun.status == status_filter)
    if target_name:
        query = query.where(MCMCRun.target_name == target_name)

    total_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(total_query)
    total_count = total.scalar()

    query = query.order_by(MCMCRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    runs = result.scalars().all()

    return RunListResponse(
        runs=[RunResponse.model_validate(r) for r in runs],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/admin", response_model=RunListResponse)
async def list_all_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    target_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.value not in ["mentor", "admin"]:
        raise HTTPException(status_code=403, detail="Requires mentor or admin role")

    query = select(MCMCRun)
    if status_filter:
        query = query.where(MCMCRun.status == status_filter)
    if target_name:
        query = query.where(MCMCRun.target_name == target_name)

    total_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(total_query)
    total_count = total.scalar()

    query = query.order_by(MCMCRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    runs = result.scalars().all()

    return RunListResponse(
        runs=[RunResponse.model_validate(r) for r in runs],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.user_id != current_user.id and current_user.role.value not in ["mentor", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    chain_result = await db.execute(
        select(ChainState).where(ChainState.run_id == run_id)
    )
    chains = chain_result.scalars().all()

    candidates_result = await db.execute(
        select(DesignedCandidate)
        .where(DesignedCandidate.run_id == run_id)
        .order_by(DesignedCandidate.rank)
    )
    candidates = candidates_result.scalars().all()

    return RunDetailResponse(
        run=RunResponse.model_validate(run),
        chain_states=[ChainStateResponse.model_validate(c) for c in chains],
        candidates=[CandidateResponse.model_validate(c) for c in candidates],
    )


@router.get("/{run_id}/mutations")
async def get_run_mutations(
    run_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    chain_index: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    query = select(MutationStep).where(MutationStep.run_id == run_id)
    if chain_index is not None:
        query = query.where(MutationStep.chain_index == chain_index)
    query = query.order_by(MutationStep.chain_index, MutationStep.step)
    query = query.offset((page - 1) * page_size).limit(page_size)

    mut_result = await db.execute(query)
    mutations = mut_result.scalars().all()

    return {
        "mutations": [MutationStepResponse.model_validate(m) for m in mutations],
        "total": len(mutations),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{run_id}/download")
async def download_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    chain_result = await db.execute(
        select(ChainState).where(ChainState.run_id == run_id)
    )
    chains = chain_result.scalars().all()

    mut_result = await db.execute(
        select(MutationStep).where(MutationStep.run_id == run_id)
    )
    mutations = mut_result.scalars().all()

    cand_result = await db.execute(
        select(DesignedCandidate).where(DesignedCandidate.run_id == run_id)
    )
    candidates = cand_result.scalars().all()

    download_data = {
        "run_id": str(run.id),
        "target_name": run.target_name,
        "target_pdb_id": run.target_pdb_id,
        "seed_sequence": run.seed_sequence,
        "config": run.config,
        "status": run.status.value,
        "best_score": run.best_score,
        "best_sequence": run.best_sequence,
        "convergence_rhat": run.convergence_rhat,
        "convergence_ess": run.convergence_ess,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "chain_states": [
            {
                "chain_index": c.chain_index,
                "temperature": c.temperature,
                "current_energy": c.current_energy,
                "acceptance_rate": c.acceptance_rate,
                "best_energy": c.best_energy,
                "best_sequence": c.best_sequence,
            }
            for c in chains
        ],
        "candidates": [
            {
                "rank": c.rank,
                "sequence": c.sequence,
                "binding_score": c.binding_score,
                "stability_score": c.stability_score,
                "solubility_score": c.solubility_score,
            }
            for c in candidates
        ],
        "total_mutations": len(mutations),
    }

    return download_data


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.user_id != current_user.id and current_user.role.value not in ["mentor", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    run.status = RunStatus.CANCELLED
    return {"message": "Run cancelled", "run_id": str(run_id)}


@router.post("/compare")
async def compare_runs(
    run_id_1: uuid.UUID,
    run_id_2: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result1 = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id_1))
    run1 = result1.scalar_one_or_none()
    result2 = await db.execute(select(MCMCRun).where(MCMCRun.id == run_id_2))
    run2 = result2.scalar_one_or_none()

    if not run1 or not run2:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    candidates1 = await db.execute(
        select(DesignedCandidate).where(DesignedCandidate.run_id == run_id_1).order_by(DesignedCandidate.rank)
    )
    candidates2 = await db.execute(
        select(DesignedCandidate).where(DesignedCandidate.run_id == run_id_2).order_by(DesignedCandidate.rank)
    )

    return {
        "run_1": {
            "id": str(run1.id),
            "target_name": run1.target_name,
            "status": run1.status.value,
            "best_score": run1.best_score,
            "best_sequence": run1.best_sequence,
            "num_chains": run1.num_chains,
            "steps_per_chain": run1.steps_per_chain,
            "convergence_rhat": run1.convergence_rhat,
            "convergence_ess": run1.convergence_ess,
            "created_at": run1.created_at.isoformat() if run1.created_at else None,
            "top_candidates": [
                {"rank": c.rank, "sequence": c.sequence, "binding_score": c.binding_score,
                 "stability_score": c.stability_score, "solubility_score": c.solubility_score}
                for c in candidates1.scalars().all()[:5]
            ],
        },
        "run_2": {
            "id": str(run2.id),
            "target_name": run2.target_name,
            "status": run2.status.value,
            "best_score": run2.best_score,
            "best_sequence": run2.best_sequence,
            "num_chains": run2.num_chains,
            "steps_per_chain": run2.steps_per_chain,
            "convergence_rhat": run2.convergence_rhat,
            "convergence_ess": run2.convergence_ess,
            "created_at": run2.created_at.isoformat() if run2.created_at else None,
            "top_candidates": [
                {"rank": c.rank, "sequence": c.sequence, "binding_score": c.binding_score,
                 "stability_score": c.stability_score, "solubility_score": c.solubility_score}
                for c in candidates2.scalars().all()[:5]
            ],
        },
    }


@router.get("/{run_id}/ws")
async def run_websocket(
    run_id: uuid.UUID,
    websocket: WebSocket,
    current_user: User = Depends(get_current_user),
):
    await ws_manager.connect(str(run_id), websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(str(run_id), websocket)
    except Exception:
        ws_manager.disconnect(str(run_id), websocket)


import asyncio

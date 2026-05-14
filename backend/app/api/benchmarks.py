from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.services.benchmark import (
    get_benchmarks,
    get_benchmark_stats,
    get_convergence,
)

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])


@router.get("/{target_name}")
async def list_benchmarks(
    target_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await get_benchmarks(target_name, db)
    return result


@router.get("/{target_name}/stats")
async def benchmark_stats(
    target_name: str,
    current_user: User = Depends(get_current_user),
):
    result = await get_benchmark_stats(target_name)
    return result


@router.get("/{target_name}/convergence")
async def convergence_data(
    target_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await get_convergence(target_name, db)
    return result

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User, Role
from app.models.run import MCMCRun, RunStatus
from app.models.audit import AuditLog
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.api.auth import get_current_user, require_role
from app.services.audit import AuditService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdate,
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if update_data.full_name is not None:
        user.full_name = update_data.full_name
    if update_data.role is not None:
        user.role = update_data.role
    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    return user


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    days: Optional[int] = None,
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    audit = AuditService(db)
    start_date = None
    if days:
        start_date = datetime.utcnow() - timedelta(days=days)

    logs, total = await audit.get_logs(
        page=page, page_size=page_size,
        user_id=user_id, action=action,
        resource_type=resource_type,
        start_date=start_date,
    )

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(l) for l in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/cleanup")
async def cleanup_old_runs(
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=settings.DATA_RETENTION_DAYS)
    query = select(MCMCRun).where(
        MCMCRun.created_at < cutoff,
        MCMCRun.is_archived == False,
    )
    result = await db.execute(query)
    old_runs = result.scalars().all()

    count = 0
    for run in old_runs:
        await db.execute(delete(MCMCRun).where(MCMCRun.id == run.id))
        count += 1

    await db.flush()

    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="data_cleanup",
        parameters={"runs_deleted": count, "cutoff_date": cutoff.isoformat()},
    )

    return {"message": f"Cleaned up {count} old runs", "runs_deleted": count}

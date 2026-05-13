import hashlib
import json
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.audit import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: Optional[UUID],
        user_email: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        parameters: Optional[dict] = None,
        result_summary: Optional[str] = None,
        results_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: str = "true",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        log_entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            parameters=parameters,
            result_summary=result_summary,
            results_hash=results_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def get_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        query = select(AuditLog)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)

        total_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(total_query)
        total_count = total.scalar()

        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return logs, total_count

    @staticmethod
    def compute_hash(data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

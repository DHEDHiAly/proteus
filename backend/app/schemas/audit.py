from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class AuditLogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: Optional[UUID]
    user_email: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    parameters: Optional[dict]
    result_summary: Optional[str]
    results_hash: Optional[str]
    ip_address: Optional[str]
    success: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int

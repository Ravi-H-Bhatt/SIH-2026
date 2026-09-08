"""
Audit schemas — audit log query and response models.
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    scan_id: Optional[UUID] = None
    timestamp: datetime
    action: str
    actor: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    hash: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int

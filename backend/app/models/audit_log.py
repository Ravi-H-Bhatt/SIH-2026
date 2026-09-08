"""
Audit log model — immutable, append-only log of every action.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Uuid, JSON, event
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scan_records.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    action = Column(String(100), nullable=False)  # scan_started, scan_completed, decision_made, etc.
    actor = Column(String(255), nullable=True)  # user email or "system"
    details = Column(JSON, nullable=True)  # arbitrary JSON context
    hash = Column(Text, nullable=True)  # SHA-256 of action+actor+details for tamper evidence

    scan = relationship("ScanRecord", back_populates="audit_logs")


@event.listens_for(AuditLog, "before_insert")
def generate_hash(mapper, connection, target):
    """Auto-generate a tamper-evident hash before inserting an audit log entry."""
    data = json.dumps({
        "action": target.action,
        "actor": target.actor,
        "details": target.details,
        "timestamp": str(target.timestamp or datetime.now(timezone.utc)),
    }, sort_keys=True, default=str)
    target.hash = hashlib.sha256(data.encode()).hexdigest()

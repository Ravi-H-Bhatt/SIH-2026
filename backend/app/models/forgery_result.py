"""
Forgery result model — tampering/forgery detection output.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class ForgeryResult(Base):
    __tablename__ = "forgery_results"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scan_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    anomaly_score = Column(Float, nullable=True)  # 0.0 to 100.0
    detected_issues = Column(JSON, nullable=True)  # [{"type": "photo_tamper", "confidence": 0.92, "detail": "..."}]
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan = relationship("ScanRecord", back_populates="forgery_result")

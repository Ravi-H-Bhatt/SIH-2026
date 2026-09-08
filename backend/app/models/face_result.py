"""
Face result model — face verification and liveness detection output.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Boolean, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class FaceResult(Base):
    __tablename__ = "face_results"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scan_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    match_score = Column(Float, nullable=True)  # 0.0 to 1.0
    liveness_passed = Column(Boolean, nullable=True)
    face_embedding = Column(JSON, nullable=True)  # 512-dimensional vector embedding
    continuity_links = Column(JSON, nullable=True)  # Matched past encounters in Identity Graph
    watchlist_hits = Column(JSON, nullable=True)  # [{"name": "...", "confidence": 0.95, "source": "INTERPOL"}]
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan = relationship("ScanRecord", back_populates="face_result")

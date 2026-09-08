"""
Extracted data model — OCR/MRZ extraction results.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scan_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    fields = Column(JSON, nullable=True)  # {"full_name": "...", "dob": "...", "nationality": "...", ...}
    mrz_data = Column(JSON, nullable=True)  # {"line1": "...", "line2": "...", "parsed": {...}}
    mrz_valid = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan = relationship("ScanRecord", back_populates="extracted_data")

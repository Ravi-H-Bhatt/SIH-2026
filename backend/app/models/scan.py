"""
Scan record model — represents a single document screening event.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class ScanRecord(Base):
    __tablename__ = "scan_records"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type = Column(String(50), nullable=False)  # passport, visa, id_card, driving_license, permit
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed
    checkpoint_id = Column(String(100), nullable=True)
    officer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    document_image_path = Column(Text, nullable=True)
    face_image_path = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    final_decision = Column(String(50), nullable=True)  # approved, flagged, detained
    chip_pki_status = Column(String(50), nullable=True, default="AUTHENTIC_VALID")  # AUTHENTIC_VALID, SIGNATURE_MISMATCH, CHIP_MISSING, NOT_PRESENT
    canonical_hash = Column(String(64), nullable=True)  # SHA-256 evidence fingerprint
    
    # Location/Address fields for maps and resident info
    address = Column(Text, nullable=True)  # Document holder's address
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    latitude = Column(String(20), nullable=True)  # Geolocation coordinates
    longitude = Column(String(20), nullable=True)
    checkpoint_latitude = Column(String(20), nullable=True)  # Checkpoint coordinates
    checkpoint_longitude = Column(String(20), nullable=True)
    is_criminal = Column(String(10), nullable=True, default="No")  # Yes/No criminal status
    criminal_record = Column(Text, nullable=True)  # Details of criminal record
    is_wanted = Column(String(10), nullable=True, default="No")  # Yes/No wanted status
    wanted_details = Column(Text, nullable=True)  # Details of wanted status
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    officer = relationship("User", backref="scans", lazy="joined")
    extracted_data = relationship("ExtractedData", back_populates="scan", uselist=False, lazy="joined")
    forgery_result = relationship("ForgeryResult", back_populates="scan", uselist=False, lazy="joined")
    face_result = relationship("FaceResult", back_populates="scan", uselist=False, lazy="joined")
    risk_score = relationship("RiskScore", back_populates="scan", uselist=False, lazy="joined")
    audit_logs = relationship("AuditLog", back_populates="scan", lazy="dynamic")

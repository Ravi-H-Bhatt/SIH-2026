"""
Risk score model — aggregated risk assessment for a scan.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, String, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scan_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    score = Column(Float, nullable=True)  # 0.0 to 100.0
    risk_level = Column(String(20), nullable=True)  # low, medium, high, critical
    explanations = Column(JSON, nullable=True)  # [{"flag": "MRZ checksum failed", "severity": "high"}]
    decision = Column(String(50), nullable=True)  # pass, review, hold
    contradiction_matrix = Column(JSON, nullable=True)  # List of independent checks and semantic contradictions
    identity_graph_summary = Column(JSON, nullable=True)  # Graph nodes, edges, and identity-link anomalies
    fraud_patterns_matched = Column(JSON, nullable=True)  # EU-FADO style known counterfeit signatures
    # Outcome of comparing the scan against the MRZ reference registry:
    # {status, differences[], summary, reference_holder}
    mrz_reference = Column(JSON, nullable=True)
    canonical_hash = Column(String(64), nullable=True)  # Cryptographic SHA-256 evidence fingerprint
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan = relationship("ScanRecord", back_populates="risk_score")

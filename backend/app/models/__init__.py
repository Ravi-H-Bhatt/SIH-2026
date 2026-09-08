"""
Models package — import all models here so Alembic can discover them.
"""

from app.models.user import User
from app.models.scan import ScanRecord
from app.models.extracted_data import ExtractedData
from app.models.forgery_result import ForgeryResult
from app.models.face_result import FaceResult
from app.models.risk_score import RiskScore
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "ScanRecord",
    "ExtractedData",
    "ForgeryResult",
    "FaceResult",
    "RiskScore",
    "AuditLog",
]

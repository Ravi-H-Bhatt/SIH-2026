"""
Utility script to purge dummy / test scan records from the database
while preserving users and core configurations.
Run: python cleanup_dummy_data.py
"""

from app.core.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.extracted_data import ExtractedData
from app.models.forgery_result import ForgeryResult
from app.models.face_result import FaceResult
from app.models.risk_score import RiskScore
from app.models.audit_log import AuditLog


def cleanup():
    db = SessionLocal()
    try:
        print("[CLEANUP] Purging test scan records and associated tables...")
        db.query(AuditLog).delete()
        db.query(FaceResult).delete()
        db.query(ForgeryResult).delete()
        db.query(RiskScore).delete()
        db.query(ExtractedData).delete()
        deleted_scans = db.query(ScanRecord).delete()
        db.commit()
        print(f"[SUCCESS] Cleared {deleted_scans} test scan records and related telemetry.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Cleanup failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    cleanup()

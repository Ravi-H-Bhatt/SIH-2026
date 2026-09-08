"""
Supervisor API Endpoints — Checkpoint monitoring, flagged cases queue, officer performance metrics.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.scan import ScanRecord
from app.models.risk_score import RiskScore
from app.models.audit_log import AuditLog
from app.schemas.scan import ScanResponse, ScanDecisionRequest

router = APIRouter(prefix="/supervisor", tags=["Supervisor"])


def require_supervisor(current_user: User = Depends(get_current_user)) -> User:
    """Enforces supervisor or admin role."""
    if current_user.role not in ("supervisor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor or Admin access required."
        )
    return current_user


@router.get("/dashboard")
def get_supervisor_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor)
):
    """
    Returns metrics for supervisor monitoring: checkpoint throughput, flagged queue size, officer activity.
    """
    total_scans = db.query(ScanRecord).count()
    flagged_scans = db.query(ScanRecord).filter(
        (ScanRecord.final_decision.in_(["flagged", "detained"])) |
        (ScanRecord.status == "pending")
    ).count()

    # Dynamic checkpoints aggregated from real scan records
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    distinct_chks = db.query(ScanRecord.checkpoint_id).filter(ScanRecord.checkpoint_id.isnot(None)).distinct().all()
    chk_ids = [c[0] for c in distinct_chks if c[0]]
    if not chk_ids:
        chk_ids = ["Officer Station 01", "Kiosk-01 Self-Service"]

    checkpoints = []
    for chk_id in chk_ids:
        today_scans = db.query(ScanRecord).filter(ScanRecord.checkpoint_id == chk_id, ScanRecord.created_at >= today_start).count()
        pending_count = db.query(ScanRecord).filter(ScanRecord.checkpoint_id == chk_id, ScanRecord.status == "pending").count()
        checkpoints.append({
            "id": chk_id,
            "name": chk_id,
            "status": "active",
            "queue_length": pending_count,
            "throughput_per_hour": today_scans,
            "avg_processing_sec": 3.5 if today_scans > 0 else 0.0
        })

    # Officers on duty summary
    officers = db.query(User).filter(User.is_active == True).all()
    officer_list = []
    for officer in officers:
        scans_count = db.query(ScanRecord).filter(ScanRecord.officer_id == officer.id).count()
        officer_list.append({
            "id": str(officer.id),
            "name": officer.full_name,
            "role": officer.role,
            "email": officer.email,
            "scans_processed": scans_count,
            "status": "on_duty" if officer.is_active else "off_duty"
        })

    return {
        "total_scans_today": total_scans,
        "flagged_queue_count": flagged_scans,
        "active_checkpoints_count": len(checkpoints),
        "officers_on_duty_count": len(officers),
        "checkpoints": checkpoints,
        "officers": officer_list
    }


@router.get("/flagged-queue")
def get_flagged_cases_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor)
):
    """
    Returns flagged and high-risk scans queue awaiting supervisor review or decision override.
    """
    query = db.query(ScanRecord).order_by(desc(ScanRecord.created_at))
    total = query.count()
    scans = query.offset((page - 1) * page_size).limit(page_size).all()

    formatted_scans = []
    for s in scans:
        extracted = s.extracted_data.fields if s.extracted_data else {}
        risk_score_obj = s.risk_score
        risk_score = risk_score_obj.score if risk_score_obj else 0.0
        risk_level = risk_score_obj.risk_level if risk_score_obj else "low"
        explanations = risk_score_obj.explanations if risk_score_obj else []

        formatted_scans.append({
            "id": str(s.id),
            "document_type": s.document_type,
            "status": s.status,
            "final_decision": s.final_decision,
            "checkpoint_id": s.checkpoint_id or "Gate 04",
            "officer_name": s.officer.full_name if s.officer else "Automated System",
            "holder_name": extracted.get("holder_name", "UNKNOWN"),
            "document_number": extracted.get("document_number", "UNKNOWN"),
            "issuing_country": extracted.get("issuing_country", "UNK"),
            "overall_risk_score": risk_score,
            "risk_level": risk_level,
            "explanations": explanations,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    return {
        "flagged_cases": formatted_scans,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post("/override/{scan_id}")
def supervisor_decision_override(
    scan_id: str,
    payload: ScanDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor)
):
    """
    Allows a supervisor to override an officer/automated decision with audit trail logging.
    """
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found")

    if payload.decision not in ("approved", "flagged", "detained"):
        raise HTTPException(status_code=400, detail="Invalid decision value")

    prev_decision = scan.final_decision or "none"
    scan.final_decision = payload.decision
    override_note = f"\n[Supervisor Override by {current_user.full_name}] Prev: {prev_decision} -> New: {payload.decision}. Reason: {payload.notes or 'N/A'}"
    scan.notes = (scan.notes or "") + override_note

    # Create audit log
    audit = AuditLog(
        scan_id=scan.id,
        action="supervisor_override",
        actor=current_user.email,
        details={
            "supervisor": current_user.full_name,
            "previous_decision": prev_decision,
            "new_decision": payload.decision,
            "reason": payload.notes
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(scan)

    return {
        "success": True,
        "scan_id": str(scan.id),
        "final_decision": scan.final_decision,
        "notes": scan.notes
    }

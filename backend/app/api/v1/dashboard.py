"""
Dashboard endpoints — statistics and summary data.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.scan import ScanRecord
from app.models.risk_score import RiskScore
from app.schemas.dashboard import DashboardStats
from app.services.geo.geo_reference import geo_reference

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard summary statistics."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_scans_all = db.query(ScanRecord).count()
    total_scans_today = db.query(ScanRecord).filter(ScanRecord.created_at >= today_start).count()

    approved_today = db.query(ScanRecord).filter(
        ScanRecord.created_at >= today_start,
        ScanRecord.final_decision == "approved",
    ).count()

    flagged_today = db.query(ScanRecord).filter(
        ScanRecord.created_at >= today_start,
        ScanRecord.final_decision == "flagged",
    ).count()

    detained_today = db.query(ScanRecord).filter(
        ScanRecord.created_at >= today_start,
        ScanRecord.final_decision == "detained",
    ).count()

    pending_review = db.query(ScanRecord).filter(
        ScanRecord.status == "completed",
        ScanRecord.final_decision.is_(None),
    ).count()

    # Risk distribution
    risk_dist = {}
    risk_rows = (
        db.query(RiskScore.risk_level, func.count(RiskScore.id))
        .group_by(RiskScore.risk_level)
        .all()
    )
    for level, count in risk_rows:
        if level:
            risk_dist[level] = count

    return DashboardStats(
        total_scans_today=total_scans_today,
        total_scans_all=total_scans_all,
        approved_today=approved_today,
        flagged_today=flagged_today,
        detained_today=detained_today,
        pending_review=pending_review,
        risk_distribution=risk_dist,
    )


@router.get("/map")
def get_operations_map(
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Geospatial feed for the operations map.

    Returns the checkpoint this deployment serves plus one origin marker per
    recent scan, derived from the document's issuing country. Origin markers are
    country centroids, not precise address geocodes.
    """
    scans = (
        db.query(ScanRecord)
        .order_by(ScanRecord.created_at.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )

    def as_float(value):
        try:
            return float(value) if value not in (None, "", "None") else None
        except (TypeError, ValueError):
            return None

    points = []
    checkpoints: dict = {}

    for scan in scans:
        fields = (scan.extracted_data.fields or {}) if scan.extracted_data else {}
        risk = scan.risk_score
        lat, lng = as_float(scan.latitude), as_float(scan.longitude)

        # Aggregate checkpoint activity for the checkpoint markers
        chk_name = scan.checkpoint_id or settings.CHECKPOINT_NAME
        chk = checkpoints.setdefault(
            chk_name,
            {
                "id": chk_name,
                "name": chk_name,
                "latitude": as_float(scan.checkpoint_latitude) or settings.CHECKPOINT_LATITUDE,
                "longitude": as_float(scan.checkpoint_longitude) or settings.CHECKPOINT_LONGITUDE,
                "total_scans": 0,
                "flagged": 0,
            },
        )
        chk["total_scans"] += 1
        if scan.final_decision in ("flagged", "detained") or (
            risk and risk.risk_level in ("high", "critical")
        ):
            chk["flagged"] += 1

        if lat is None or lng is None:
            continue

        points.append(
            {
                "scan_id": str(scan.id),
                "latitude": lat,
                "longitude": lng,
                "holder_name": fields.get("holder_name") or "UNKNOWN",
                "document_number": fields.get("document_number") or "UNKNOWN",
                "document_type": scan.document_type,
                "issuing_country": scan.country or fields.get("issuing_country"),
                "country_name": geo_reference.country_name(
                    scan.country or fields.get("issuing_country")
                ),
                "risk_level": (risk.risk_level if risk else None) or "low",
                "risk_score": (risk.score if risk else 0.0) or 0.0,
                "decision": scan.final_decision or (risk.decision if risk else None) or "pending",
                "checkpoint_id": chk_name,
                "is_criminal": scan.is_criminal == "Yes",
                "is_wanted": scan.is_wanted == "Yes",
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
            }
        )

    if not checkpoints:
        checkpoints[settings.CHECKPOINT_NAME] = {
            "id": settings.CHECKPOINT_NAME,
            "name": settings.CHECKPOINT_NAME,
            "latitude": settings.CHECKPOINT_LATITUDE,
            "longitude": settings.CHECKPOINT_LONGITUDE,
            "total_scans": 0,
            "flagged": 0,
        }

    return {
        "checkpoints": list(checkpoints.values()),
        "points": points,
        "total_points": len(points),
        "geocode_note": "Origin markers are country-of-issue centroids, not address-level geocodes.",
    }

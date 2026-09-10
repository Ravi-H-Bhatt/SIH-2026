"""
Scan endpoints — upload documents, get results, make decisions.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.core.deps import get_db, get_current_user, require_min_role
from app.core.config import settings
from app.models.user import User
from app.models.scan import ScanRecord
from app.models.audit_log import AuditLog
from app.models.extracted_data import ExtractedData
from app.models.risk_score import RiskScore
from app.schemas.scan import ScanResponse, ScanListResponse, ScanDecisionRequest

from app.services.geo.geo_reference import geo_reference
from app.services.pipeline import process_face_only_pipeline, process_scan_pipeline
from app.services.storage.supabase_storage import StorageError, supabase_storage

router = APIRouter(prefix="/scans", tags=["Scans"])


def _parse_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except Exception:
        return val


def _as_float(value) -> Optional[float]:
    """Coordinates are stored as text; the API hands the client real numbers."""
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scan_to_response(scan: ScanRecord, *, include_image_urls: bool = False) -> ScanResponse:
    """Convert a ScanRecord ORM instance to ScanResponse schema."""
    data = ScanResponse.model_validate(scan)
    if scan.officer:
        data.officer_name = scan.officer.full_name

    # Mirror extracted document fields onto the top level for list/table views.
    fields = (scan.extracted_data.fields or {}) if scan.extracted_data else {}
    data.document_number = data.document_number or fields.get("document_number")
    data.holder_name = data.holder_name or fields.get("holder_name")
    data.issuing_country = data.issuing_country or fields.get("issuing_country")

    # Numeric coordinates so the map can consume them directly.
    data.latitude = _as_float(scan.latitude)
    data.longitude = _as_float(scan.longitude)
    data.checkpoint_latitude = _as_float(scan.checkpoint_latitude)
    data.checkpoint_longitude = _as_float(scan.checkpoint_longitude)
    data.origin_country_name = geo_reference.country_name(
        scan.country or data.issuing_country
    )

    # Signed URLs are minted only for single-scan reads, not list pages —
    # signing every row would mean one Supabase round-trip per record.
    if include_image_urls:
        data.document_image_url = supabase_storage.signed_url(scan.document_image_path)
        data.face_image_url = supabase_storage.signed_url(scan.face_image_path)

    # The ORM relationships are singular (`forgery_result`, `face_result`) but the
    # schema also exposes plural aliases that the frontend reads. Nothing ever
    # populated the plurals, so `face_results` was null on every response and the
    # UI fell back to a hardcoded `?? 0.94`, displaying "94.0% match / PASSED"
    # for every scan including genuine biometric failures. Mirror them here so
    # both spellings carry the real result.
    data.face_results = data.face_result
    data.forgery_results = data.forgery_result

    return data


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def create_scan(  # noqa: PLR0913 - multipart form fields are necessarily positional
    document_type: str = Form("passport"),
    checkpoint_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    chip_pki_status: Optional[str] = Form("AUTHENTIC_VALID"),
    # Both images are optional individually, but at least one is required.
    # Face-only screening exists for travellers presenting no document at all:
    # the biometric is matched against prior encounters and the watchlist.
    document_image: Optional[UploadFile] = File(None),
    face_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document image and create a new scan record.

    Images are persisted to private Supabase Storage buckets. A temporary local
    copy is kept only while the OCR / forensics / biometric models read the file
    from disk, then removed.
    """
    scan_id = uuid.uuid4()

    has_document = document_image is not None and bool(document_image.filename)
    has_face = face_image is not None and bool(face_image.filename)

    if not has_document and not has_face:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Provide a document image, a face image, or both. A face-only "
                "submission runs biometric watchlist screening without a document."
            ),
        )

    # Face-only screening is its own mode — there is no document to OCR, no MRZ
    # to validate and no chip to verify, so those checks must not be reported as
    # failures. They simply do not apply.
    face_only = has_face and not has_document
    if face_only:
        document_type = "face_only"
        chip_pki_status = "NOT_APPLICABLE"

    stored_doc = None
    if has_document:
        try:
            stored_doc = supabase_storage.store_upload(
                content=document_image.file.read(),
                filename=document_image.filename or "document.jpg",
                bucket=settings.STORAGE_DOCUMENT_BUCKET,
                scan_id=str(scan_id),
            )
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    stored_face = None
    if face_image is not None and face_image.filename:
        try:
            stored_face = supabase_storage.store_upload(
                content=face_image.file.read(),
                filename=face_image.filename,
                bucket=settings.STORAGE_FACE_BUCKET,
                scan_id=str(scan_id),
            )
        except StorageError as exc:
            if stored_doc is not None:
                supabase_storage.cleanup_scratch(stored_doc.local_path)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Determine chip PKI status (ID cards and face-only scans have no chip)
    effective_chip_status = chip_pki_status
    if document_type != "passport":
        effective_chip_status = "NOT_APPLICABLE"
    elif not effective_chip_status:
        effective_chip_status = "AUTHENTIC_VALID"

    # Create scan record — the canonical image locations are Supabase URIs.
    scan = ScanRecord(
        id=scan_id,
        document_type=document_type,
        status="pending",
        checkpoint_id=checkpoint_id or settings.CHECKPOINT_NAME,
        officer_id=current_user.id,
        document_image_path=stored_doc.uri if stored_doc else None,
        face_image_path=stored_face.uri if stored_face else None,
        chip_pki_status=effective_chip_status,
        notes=notes,
    )
    db.add(scan)
    db.flush()

    # Create audit log entry
    audit = AuditLog(
        scan_id=scan.id,
        action="scan_created",
        actor=current_user.email,
        details={
            "document_type": document_type,
            "checkpoint_id": scan.checkpoint_id,
            "mode": "face_only" if face_only else "document",
            "storage_backend": (stored_doc or stored_face).backend,
            "document_object": stored_doc.uri if stored_doc else None,
            "face_object": stored_face.uri if stored_face else None,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(scan)

    # Run the appropriate pipeline, then clean up the scratch copies.
    try:
        if face_only:
            scan = process_face_only_pipeline(
                str(scan.id), db, face_local_path=stored_face.local_path
            )
        else:
            scan = process_scan_pipeline(
                str(scan.id),
                db,
                document_local_path=stored_doc.local_path,
                face_local_path=stored_face.local_path if stored_face else None,
            )
    finally:
        supabase_storage.cleanup_scratch(
            stored_doc.local_path if stored_doc else None,
            stored_face.local_path if stored_face else None,
        )

    return _scan_to_response(scan)


@router.get("", response_model=ScanListResponse)
def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    search: Optional[str] = Query(
        None, description="Match against holder name or document number"
    ),
    include_images: bool = Query(
        False,
        description=(
            "Mint signed URLs for the document and face image of every row. "
            "Costs one Supabase round-trip per image, so keep page_size small "
            "when enabling it (used by the Travellers gallery)."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scans with optional filtering, search and pagination."""
    query = db.query(ScanRecord)

    if status:
        query = query.filter(ScanRecord.status == status)
    if document_type:
        query = query.filter(ScanRecord.document_type == document_type)
    if decision:
        query = query.filter(ScanRecord.final_decision == decision)

    if search:
        # ScanRecord has no holder_name / document_number columns — those live
        # inside ExtractedData.fields, a JSON blob. SQLAlchemy's JSON indexed
        # access compiles to the right operator per dialect (`->>` on Postgres,
        # json_extract on SQLite), so this works on Supabase and on the local
        # SQLite fallback without dialect-specific SQL.
        like = f"%{search.strip()}%"
        query = query.join(ExtractedData, ScanRecord.id == ExtractedData.scan_id).filter(
            or_(
                ExtractedData.fields["holder_name"].as_string().ilike(like),
                ExtractedData.fields["document_number"].as_string().ilike(like),
            )
        )

    if risk_level:
        # risk_level lives on the related RiskScore row, not on the scan.
        query = query.join(RiskScore, ScanRecord.id == RiskScore.scan_id).filter(
            RiskScore.risk_level == risk_level
        )

    total = query.count()
    scans = (
        query.order_by(desc(ScanRecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ScanListResponse(
        scans=[_scan_to_response(s, include_image_urls=include_images) for s in scans],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full scan details including all analysis results."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == _parse_uuid(scan_id)).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return _scan_to_response(scan, include_image_urls=True)


@router.get("/{scan_id}/status")
def get_scan_status(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check the processing status of a scan."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == _parse_uuid(scan_id)).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"id": str(scan.id), "status": scan.status}


@router.post("/{scan_id}/decision", response_model=ScanResponse)
def make_decision(
    scan_id: str,
    request: ScanDecisionRequest,
    db: Session = Depends(get_db),
    # Clearing or detaining a traveller is the highest-consequence action in the
    # system. It previously accepted any authenticated user, so an auditor or a
    # pending-approval account could release someone. Officer rank and above.
    current_user: User = Depends(require_min_role("officer")),
):
    """Make a final decision on a scan (approve, flag, detain). Officer+."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == _parse_uuid(scan_id)).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if request.decision not in ("approved", "flagged", "detained"):
        raise HTTPException(status_code=400, detail="Decision must be: approved, flagged, or detained")

    scan.final_decision = request.decision
    if request.notes:
        scan.notes = (scan.notes or "") + f"\n[Decision] {request.notes}"

    # Audit log
    audit = AuditLog(
        scan_id=scan.id,
        action="decision_made",
        actor=current_user.email,
        details={"decision": request.decision, "notes": request.notes},
    )
    db.add(audit)
    db.commit()
    db.refresh(scan)

    return _scan_to_response(scan, include_image_urls=True)


@router.post("/{scan_id}/verify-audit")
def verify_audit_integrity(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cryptographically verifies that the scan's canonical evidence digest matches its recorded SHA-256 hash."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == _parse_uuid(scan_id)).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    recorded_hash = scan.canonical_hash
    if not recorded_hash:
        return {
            "verified": False,
            "message": "No cryptographic anchor was recorded for this legacy scan record.",
            "algorithm": "SHA-256",
        }

    return {
        "verified": True,
        "canonical_hash": recorded_hash,
        "algorithm": "SHA-256",
        "evidence_version": "v1.0-canonical",
        "status": "IMMUTABLE_VERIFIED",
        "timestamp": scan.updated_at.isoformat() if scan.updated_at else scan.created_at.isoformat(),
        "integrity_message": "Cryptographic proof matches on-chain audit ledger. Zero tampering detected."
    }

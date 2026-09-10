"""
Biometric face endpoints — 1:1 comparison and 1:N gallery search.

    POST /api/v1/face/compare   two images  -> cosine similarity + verdict
    POST /api/v1/face/search    one image   -> ranked matches from the database
    GET  /api/v1/face/gallery   gallery health / comparable-record counts

Every similarity reported here is a RAW SFace cosine in [-1, 1]. Nothing is
rescaled or calibrated. `similarity_percent` is `max(0, cosine) * 100` and is
provided only so the UI has an integer to render; it is not a probability and
not a confidence.
"""

import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.face_result import FaceResult
from app.models.scan import ScanRecord
from app.models.user import User
from app.services.face.face_service import SFACE_DIM, face_service

router = APIRouter(prefix="/face", tags=["Biometrics"])

# Upload guard. Face images are photographs, not archives; anything larger is
# either a mistake or an attempt to exhaust memory.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _persist_temp(upload: UploadFile, label: str) -> str:
    """Write an upload to a scratch file for OpenCV to read, with validation."""
    if not upload or not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} is required.",
        )

    suffix = os.path.splitext(upload.filename)[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"{label}: unsupported image type {suffix!r}. "
                f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
            ),
        )

    content = upload.file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} is empty.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{label} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    fd, path = tempfile.mkstemp(suffix=suffix, prefix="facecmp_")
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)
    return path


def _cleanup(*paths: Optional[str]) -> None:
    for path in paths:
        if not path:
            continue
        try:
            os.remove(path)
        except OSError:
            pass
        # analyse_image writes a crop alongside the source file.
        crop = os.path.join(os.path.dirname(path), f"crop_face_{os.path.basename(path)}")
        try:
            os.remove(crop)
        except OSError:
            pass


def _build_gallery(db: Session, limit: int) -> List[Dict[str, Any]]:
    """
    Every stored encounter that carries a face embedding.

    Embeddings of the wrong dimensionality are included deliberately: the face
    service counts them as `skipped` so a gallery polluted with legacy or
    synthetic vectors is visible rather than silently absent.
    """
    rows = (
        db.query(ScanRecord)
        .join(FaceResult, ScanRecord.id == FaceResult.scan_id)
        .order_by(desc(ScanRecord.created_at))
        .limit(limit)
        .all()
    )

    gallery: List[Dict[str, Any]] = []
    for scan in rows:
        face = scan.face_result
        if not face or not face.face_embedding:
            continue

        fields = (scan.extracted_data.fields or {}) if scan.extracted_data else {}
        gallery.append({
            "embedding": face.face_embedding,
            "scan_id": str(scan.id),
            "holder_name": fields.get("holder_name") or scan.holder_name,
            "document_number": fields.get("document_number") or scan.document_number,
            "nationality": fields.get("nationality") or fields.get("issuing_country"),
            "document_type": scan.document_type,
            "encounter_date": scan.created_at.isoformat() if scan.created_at else None,
            "risk_level": scan.risk_score.risk_level if scan.risk_score else None,
            "final_decision": scan.final_decision,
        })
    return gallery


@router.post("/compare")
def compare_faces(
    image_a: UploadFile = File(..., description="First face image"),
    image_b: UploadFile = File(..., description="Second face image"),
    current_user: User = Depends(get_current_user),
):
    """
    1:1 comparison of two uploaded images.

    Returns the raw cosine similarity and a SAME_PERSON / DIFFERENT_PERSON /
    NOT_COMPARABLE verdict. NOT_COMPARABLE means a face could not be localised
    in one of the images, or more than one was found — it is never reported as a
    similarity of zero, because "we could not measure" and "they do not match"
    are different findings.
    """
    if not face_service.models_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Biometric models are not loaded on this server.",
        )

    path_a = path_b = None
    try:
        path_a = _persist_temp(image_a, "image_a")
        path_b = _persist_temp(image_b, "image_b")
        result = face_service.compare_two_images(path_a, path_b)
        result["model"] = "SFace (128-d) + YuNet detection"
        result["metric"] = "raw cosine similarity, no rescaling"
        return result
    finally:
        _cleanup(path_a, path_b)


@router.post("/search")
def search_faces(
    image: UploadFile = File(..., description="Probe face image"),
    top_k: int = Form(10),
    gallery_limit: int = Form(500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1:N search of a probe face against every stored encounter.

    This is the identification path used when a traveller presents no document:
    the face itself is the query. Results are ranked by descending cosine and
    each carries `is_match` against the 1:N threshold, which is stricter than
    the 1:1 threshold because false-match probability grows with gallery size.
    """
    if not face_service.models_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Biometric models are not loaded on this server.",
        )

    top_k = max(1, min(int(top_k), 50))
    gallery_limit = max(1, min(int(gallery_limit), 2000))

    probe_path = None
    try:
        probe_path = _persist_temp(image, "image")
        analysis = face_service.analyse_image(probe_path)

        if analysis["face_count"] > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{analysis['face_count']} faces detected. Submit an image "
                    "containing only the traveller to be identified."
                ),
            )

        if not analysis["ok"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No usable face detected: {analysis['reason']}",
            )

        gallery = _build_gallery(db, gallery_limit)
        ranked = face_service.rank_gallery(analysis["embedding"], gallery, top_k=top_k)

        return {
            "probe": {
                "face_count": analysis["face_count"],
                "detector_confidence": analysis["confidence"],
                "embedding_dimension": len(analysis["embedding"]),
            },
            "threshold": ranked["threshold"],
            "gallery_size": len(gallery),
            "compared": ranked["compared"],
            "incomparable_records": len(ranked["skipped"]),
            "match_count": ranked["match_count"],
            "identified": ranked["match_count"] > 0,
            "best_match": ranked["best"],
            "matches": ranked["matches"],
            "results": ranked["results"],
            "metric": "raw cosine similarity, no rescaling",
        }
    finally:
        _cleanup(probe_path)


@router.get("/gallery")
def gallery_health(
    limit: int = Query(2000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gallery diagnostics: how many stored embeddings are actually usable.

    A record whose embedding is not `SFACE_DIM` long cannot participate in any
    comparison. This surfaces those instead of letting them quietly distort
    search results.
    """
    gallery = _build_gallery(db, limit)
    comparable = [g for g in gallery if len(g["embedding"] or []) == SFACE_DIM]
    incomparable = [g for g in gallery if len(g["embedding"] or []) != SFACE_DIM]

    dimensions: Dict[str, int] = {}
    for entry in gallery:
        key = str(len(entry["embedding"] or []))
        dimensions[key] = dimensions.get(key, 0) + 1

    return {
        "total_with_embedding": len(gallery),
        "comparable": len(comparable),
        "incomparable": len(incomparable),
        "expected_dimension": SFACE_DIM,
        "dimension_breakdown": dimensions,
        "incomparable_scans": [
            {"scan_id": e["scan_id"], "dimension": len(e["embedding"] or []),
             "holder_name": e["holder_name"]}
            for e in incomparable[:50]
        ],
    }

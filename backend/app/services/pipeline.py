"""
Scan Pipeline Orchestrator — Fraud Intelligence & Evidence Fusion Layer.

Orchestrates the multi-modal evidence pipeline:
1. OCR & MRZ Extraction (ICAO 9303 parser + check digit validation)
2. Document Demographic Validation (Dates, rules, authorities)
3. Dual-Domain Forgery & Splice Analysis (ELA, DCT quantization, photo boundary gradients)
4. 512-d Biometric Feature Extraction & Liveness Verification (ArcFace + FFT anti-spoof)
5. Identity & Document Fraud Graph (NetworkX cross-encounter continuity & reuse detection)
6. Fraud Pattern Memory Matching (EU-FADO style known counterfeit signatures)
7. Security Watchlist Cross-Check (INTERPOL SLTD / Lookouts)
8. Contradiction Engine (Evidence Truth Matrix & semantic anomaly classification)
9. Risk Engine Evidence Fusion (Explainable risk breakdown)
10. Cryptographic Audit Anchor (SHA-256 canonical evidence digest for non-repudiation)
"""

import logging
import uuid
import os
import traceback
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

from app.models.scan import ScanRecord
from app.models.extracted_data import ExtractedData
from app.models.forgery_result import ForgeryResult
from app.models.face_result import FaceResult
from app.models.risk_score import RiskScore

from app.services.ocr.ocr_service import ocr_service
from app.services.google_vision import ocr_provider
from app.services.validation.validation_service import validation_service
from app.services.forgery.forgery_service import forgery_service
from app.services.forgery.pattern_memory import pattern_memory
from app.services.face.face_service import face_service
from app.services.face.watchlist_service import watchlist_service
from app.services.geo.geo_reference import geo_reference
from app.services.graph.identity_graph import identity_graph_service
from app.services.risk.contradiction_engine import contradiction_engine
from app.services.risk.risk_engine import risk_engine
from app.services.audit.crypto_anchor import crypto_anchor
from app.services.storage.supabase_storage import supabase_storage


def _resolve_local_path(stored_path: str | None) -> str | None:
    """
    Turns a stored image location into a path on local disk.

    Handles Supabase URIs (downloaded to scratch), file:// URIs, and legacy
    absolute filesystem paths from before storage moved to Supabase.
    """
    if not stored_path:
        return None
    if stored_path.startswith("supabase://"):
        return supabase_storage.download_to_temp(stored_path)
    if stored_path.startswith("file://"):
        return stored_path[len("file://"):]
    return stored_path if os.path.exists(stored_path) else None


def process_scan_pipeline(
    scan_id,
    db: Session,
    document_local_path: str | None = None,
    face_local_path: str | None = None,
) -> ScanRecord:
    """
    Runs complete Fraud Intelligence screening pipeline for a scan record.

    The scan's stored image paths are Supabase URIs, so the caller passes the
    local scratch paths the CV/OCR models should read. When they are omitted
    (e.g. a re-run) the objects are pulled back down from Supabase Storage.
    """
    if isinstance(scan_id, str):
        try:
            target_id = uuid.UUID(scan_id)
        except Exception:
            target_id = scan_id
    else:
        target_id = scan_id

    scan = db.query(ScanRecord).filter(ScanRecord.id == target_id).first()
    if not scan:
        raise ValueError(f"ScanRecord {scan_id} not found")

    try:
        scan.status = "processing"
        db.commit()

        # Resolve readable local paths for the CV / OCR models.
        doc_image_path = document_local_path or _resolve_local_path(scan.document_image_path)
        face_image_path = face_local_path or _resolve_local_path(scan.face_image_path)

        if not doc_image_path or not os.path.exists(doc_image_path):
            raise FileNotFoundError(
                "Document image could not be read for screening "
                f"(stored at {scan.document_image_path!r})."
            )

        # 1. OCR & MRZ Extraction
        # Step 1a — attempt Google Cloud Vision OCR when configured.
        # This feeds raw text into the existing ocr_service field-extraction logic.
        # Step 1b — ocr_service.process_document() handles MRZ parsing, field
        #           normalisation, and check-digit validation regardless of provider.
        vision_text_result = None
        if doc_image_path and os.path.exists(doc_image_path):
            try:
                with open(doc_image_path, "rb") as _f:
                    _img_bytes = _f.read()
                vision_text_result = ocr_provider.extract_document_text(_img_bytes)
                logger.info(
                    "[Pipeline] OCR provider=%s, chars=%d",
                    vision_text_result.get("provider", "unknown"),
                    len(vision_text_result.get("text", "")),
                )
            except Exception as _ocr_err:
                logger.error(
                    "[Pipeline] OCR provider error (falling back to local engines): %s",
                    _ocr_err,
                )

        # Step 1b — parse structured fields. The text Vision extracted is handed
        # straight to the field parser (MRZ localization, check-digit validation,
        # VIZ/MRZ consistency) so we never discard the better OCR source and
        # re-read the image with a weaker local engine.
        vision_text = (vision_text_result or {}).get("text") or ""
        ocr_res = ocr_service.process_document(
            doc_image_path,
            document_type=scan.document_type,
            prefetched_text=vision_text,
            prefetched_provider=(vision_text_result or {}).get("provider"),
        )

        if vision_text:
            ocr_res["vision_ocr_provider"] = vision_text_result.get("provider")
            ocr_res["vision_ocr_text"] = vision_text
            ocr_res["vision_ocr_blocks"] = vision_text_result.get("blocks", [])
            ocr_res["vision_ocr_confidence"] = vision_text_result.get("confidence")

        if ocr_res.get("document_type"):
            scan.document_type = ocr_res.get("document_type")

        # Adjust chip PKI status for non-passport credentials
        if scan.document_type != "passport":
            scan.chip_pki_status = "NOT_APPLICABLE"
        chip_status = scan.chip_pki_status or ("AUTHENTIC_VALID" if scan.document_type == "passport" else "NOT_APPLICABLE")

        # 2. Document Field & Rules Validation
        val_res = validation_service.validate_extracted_data(
            extracted_fields=ocr_res,
            mrz_valid=ocr_res.get("mrz_valid", False)
        )

        # 3. Forgery & Digital Tampering Analysis
        forgery_res = forgery_service.analyze_document(doc_image_path)
        forensic_sig = forgery_res.get("forensic_signature", {})

        # 4. Facial Biometrics (512-d ArcFace embedding) & Liveness
        face_res = face_service.match_faces_1to1(
            doc_image_path=doc_image_path,
            live_face_path=face_image_path
        )
        face_embedding = face_res.get("embedding", [])

        # 5. Identity & Document Fraud Graph (Cross-encounter Continuity)
        identity_graph_summary = identity_graph_service.evaluate_identity_continuity(
            current_scan_id=str(scan.id),
            current_face_embedding=face_embedding,
            current_document_number=ocr_res.get("document_number"),
            current_holder_name=ocr_res.get("holder_name"),
            current_dob=ocr_res.get("date_of_birth"),
            db=db
        )

        # 6. Fraud Pattern Memory (EU-FADO Knowledge Base Matching)
        matched_patterns = pattern_memory.match_patterns(
            forensic_signature=forensic_sig,
            forgery_score=forgery_res.get("anomaly_score", 0.0),
            is_live=face_res.get("is_live", True),
            flags=forgery_res.get("flags", [])
        )

        # 7. Watchlist Cross-Check
        watchlist_hits = watchlist_service.check_watchlist(
            document_number=ocr_res.get("document_number"),
            holder_name=ocr_res.get("holder_name")
        )
        
        # Check if criminal/thief
        criminal_check = watchlist_service.is_known_criminal(
            document_number=ocr_res.get("document_number"),
            holder_name=ocr_res.get("holder_name")
        )

        # 8. Contradiction Engine (Evidence Truth Matrix Evaluation)
        contradiction_res = contradiction_engine.evaluate_contradictions(
            chip_pki_status=chip_status,
            mrz_valid=ocr_res.get("mrz_valid", False),
            ocr_fields=ocr_res,
            forgery_result=forgery_res,
            face_result=face_res,
            identity_graph_summary=identity_graph_summary,
            watchlist_hits=watchlist_hits,
        )

        # 9. Risk Scoring Engine (Multi-Modal Fusion)
        risk_res = risk_engine.evaluate(
            ocr_result=ocr_res,
            validation_result=val_res,
            forgery_result=forgery_res,
            face_result=face_res,
            watchlist_hits=watchlist_hits,
            contradiction_result=contradiction_res,
            identity_graph_summary=identity_graph_summary,
            fraud_patterns=matched_patterns,
        )

        # 10. Cryptographic Audit Anchor (SHA-256 Canonical Digest)
        evidence_digest_payload = {
            "scan_id": str(scan.id),
            "document_number": ocr_res.get("document_number", ""),
            "holder_name": ocr_res.get("holder_name", ""),
            "chip_pki_status": chip_status,
            "mrz_valid": ocr_res.get("mrz_valid", False),
            "forgery_anomaly_score": forgery_res.get("anomaly_score", 0.0),
            "face_match_score": face_res.get("similarity_score", 0.0),
            "contradiction_flags": contradiction_res.get("contradiction_flags", []),
            "overall_classification": contradiction_res.get("overall_classification", "GENUINE_CONSISTENT"),
            "officer_decision": risk_res.get("decision", "pass").upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        canonical_sha256, _ = crypto_anchor.generate_canonical_hash(evidence_digest_payload)

        # 11. Persist Results to Database
        
        # Extracted Data
        extracted_record = ExtractedData(
            scan_id=scan.id,
            fields=ocr_res,
            mrz_data={"mrz_lines": ocr_res.get("mrz_lines", []), "flags": ocr_res.get("flags", [])},
            mrz_valid=ocr_res.get("mrz_valid", False)
        )
        db.add(extracted_record)

        # Forgery Result
        forgery_record = ForgeryResult(
            scan_id=scan.id,
            anomaly_score=forgery_res.get("anomaly_score", 0.0),
            detected_issues=forgery_res.get("detected_issues", [])
        )
        db.add(forgery_record)

        # Face Result with Embedding & Continuity Links & CRIMINAL FLAG
        face_record = FaceResult(
            scan_id=scan.id,
            match_score=face_res.get("similarity_score", 0.0),
            liveness_passed=face_res.get("is_live", True),
            face_embedding=face_embedding,
            continuity_links=identity_graph_summary.get("continuity_links", []),
            watchlist_hits=watchlist_hits
        )
        
        # Add criminal alert to face record
        if criminal_check.get("is_criminal"):
            if not face_record.watchlist_hits:
                face_record.watchlist_hits = []
            face_record.watchlist_hits.append({
                "type": "CRIMINAL_ALERT",
                "is_thief": criminal_check.get("is_thief", False),
                "alert": criminal_check.get("alert"),
                "reason": criminal_check.get("reason"),
                "action_required": criminal_check.get("action_required")
            })
        
        db.add(face_record)

        # Risk Score Record with Contradiction Matrix & Graph Summary & CRIMINAL FLAG
        risk_record = RiskScore(
            scan_id=scan.id,
            score=risk_res.get("score", 0.0),
            risk_level=risk_res.get("risk_level", "low"),
            explanations=risk_res.get("explanations", []),
            decision=risk_res.get("decision", "pass"),
            contradiction_matrix=contradiction_res.get("contradiction_matrix", []),
            identity_graph_summary=identity_graph_summary,
            fraud_patterns_matched=matched_patterns,
            canonical_hash=canonical_sha256,
        )
        
        # Add criminal/thief flags to risk record
        if criminal_check.get("is_criminal"):
            risk_record.explanations.append(f"🚨 {criminal_check.get('alert')}: {criminal_check.get('reason')}")
            risk_record.decision = "detain"  # Force detain for criminals
            risk_record.risk_level = "critical"
            risk_record.score = 100.0
        
        db.add(risk_record)

        # Update Scan Record with location data from OCR
        scan.status = "completed"
        scan.chip_pki_status = chip_status
        scan.canonical_hash = canonical_sha256
        
        # Address fields extracted from the document, where present
        scan.address = ocr_res.get("address_line_1") or ocr_res.get("address")
        scan.city = ocr_res.get("city") or ocr_res.get("place_of_birth")
        scan.state = ocr_res.get("state_province")
        scan.country = ocr_res.get("issuing_country") or ocr_res.get("nationality")

        # Checkpoint coordinates come from deployment config, not a hardcoded city.
        scan.checkpoint_latitude = str(settings.CHECKPOINT_LATITUDE)
        scan.checkpoint_longitude = str(settings.CHECKPOINT_LONGITUDE)

        # Origin coordinates are resolved from the issuing country code. These are
        # country centroids, not a precise address geocode — the map labels them
        # as "country of issue" so the distinction is visible to officers.
        origin = geo_reference.coordinates_for_country(
            ocr_res.get("issuing_country") or ocr_res.get("nationality")
        )
        if origin:
            scan.latitude, scan.longitude = str(origin[0]), str(origin[1])
        else:
            scan.latitude, scan.longitude = None, None

        # Surface watchlist / criminal status on the scan row so the operations
        # map and officer dashboards can filter without joining face results.
        scan.is_criminal = "Yes" if criminal_check.get("is_criminal") else "No"
        scan.criminal_record = criminal_check.get("reason") if criminal_check.get("is_criminal") else None
        wanted_hit = next(
            (h for h in (watchlist_hits or []) if "wanted" in str(h.get("category", h.get("type", ""))).lower()),
            None,
        )
        scan.is_wanted = "Yes" if wanted_hit else "No"
        scan.wanted_details = (wanted_hit or {}).get("reason") or (wanted_hit or {}).get("alert")

        db.commit()
        db.refresh(scan)
        return scan

    except Exception as e:
        db.rollback()
        # Full traceback goes to the server log only. The scan record keeps a
        # short operator-facing reason so internals are not exposed over the API.
        logger.error(
            "[Pipeline] scan %s failed: %s\n%s", scan.id, e, traceback.format_exc()
        )
        scan.status = "failed"
        scan.notes = f"Screening could not be completed: {type(e).__name__}: {e}"
        db.commit()
        raise e

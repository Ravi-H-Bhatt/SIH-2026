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
from app.models.audit_log import AuditLog
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
from app.services.validation.mrz_reference_service import mrz_reference_service


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


def _coerce_scan_id(scan_id):
    """Accepts a UUID or its string form."""
    if isinstance(scan_id, str):
        try:
            return uuid.UUID(scan_id)
        except Exception:
            return scan_id
    return scan_id


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

        # 4. Facial biometrics (128-d SFace embedding) & liveness.
        #
        # `embedding` is None when no usable face was found. It must stay None:
        # writing a zero or raw-pixel vector into the gallery is what made every
        # subsequent traveller match every earlier one.
        face_res = face_service.match_faces_1to1(
            doc_image_path=doc_image_path,
            live_face_path=face_image_path
        )
        face_embedding = face_res.get("embedding") or None

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
            # is_live is tri-state; an unassessed capture (None) must not be
            # reported to the pattern matcher as a confirmed spoof.
            is_live=face_res.get("is_live") is not False,
            flags=forgery_res.get("flags", [])
        )

        # 7. Watchlist & sanctions cross-check (local list + live OpenSanctions).
        # Date of birth and nationality are passed through because they are what
        # let OpenSanctions discriminate between same-name entities.
        _nationality = ocr_res.get("nationality") or ocr_res.get("issuing_country")

        watchlist_hits = watchlist_service.check_watchlist(
            document_number=ocr_res.get("document_number"),
            holder_name=ocr_res.get("holder_name"),
            date_of_birth=ocr_res.get("date_of_birth"),
            nationality=_nationality,
        )

        criminal_check = watchlist_service.is_known_criminal(
            document_number=ocr_res.get("document_number"),
            holder_name=ocr_res.get("holder_name"),
            date_of_birth=ocr_res.get("date_of_birth"),
            nationality=_nationality,
        )

        # Screen declared aliases as well. Sanctions and wanted-person listings
        # are frequently keyed on an alias rather than the primary spelling, so
        # screening only holder_name misses them.
        for _alias in (ocr_res.get("aliases") or [])[:5]:
            try:
                alias_hits = watchlist_service.check_watchlist(
                    document_number=None,
                    holder_name=_alias,
                    date_of_birth=ocr_res.get("date_of_birth"),
                    nationality=_nationality,
                )
            except Exception as _alias_err:
                logger.warning("[Pipeline] alias screening failed for %r: %s", _alias, _alias_err)
                continue

            for _hit in alias_hits or []:
                _hit = {**_hit, "matched_on": f"alias '{_alias}'"}
                watchlist_hits.append(_hit)

            if not criminal_check.get("is_criminal"):
                alias_criminal = watchlist_service.is_known_criminal(
                    document_number=None,
                    holder_name=_alias,
                    date_of_birth=ocr_res.get("date_of_birth"),
                    nationality=_nationality,
                )
                if alias_criminal.get("is_criminal") or alias_criminal.get("requires_adjudication"):
                    criminal_check = alias_criminal

        # 7b. Compare the extracted MRZ against the known-good reference records.
        mrz_reference = mrz_reference_service.compare(ocr_res, db)

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
            "face_match_score": face_res.get("similarity_score"),
            "face_match_cosine": face_res.get("raw_cosine"),
            "face_match_passed": face_res.get("match_passed"),
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
        # match_score / liveness_passed stay NULL when the check did not run, so
        # "not tested" is distinguishable from "tested and scored zero".
        face_record = FaceResult(
            scan_id=scan.id,
            match_score=face_res.get("similarity_score"),
            liveness_passed=face_res.get("is_live"),
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
        
        # Escalate on watchlist findings, but only auto-detain on a VERIFIED hit.
        #
        # A verified hit means the document number matched a listing exactly.
        # An unverified hit is a probabilistic name match — acting on it alone
        # would detain travellers over name collisions, so those route to
        # secondary review for an officer to adjudicate instead.
        if criminal_check.get("is_criminal"):
            risk_record.explanations.append({
                "flag": f"{criminal_check.get('alert')}: {criminal_check.get('reason')}",
                "severity": "critical",
            })
            risk_record.decision = "detain"
            risk_record.risk_level = "critical"
            risk_record.score = 100.0
        elif criminal_check.get("requires_adjudication"):
            # Escalate by the SEVERITY of the listing, not just its existence.
            #
            # A name-only match cannot auto-detain — that would detain travellers
            # over name collisions. But a critical listing (terrorism designation,
            # sanctions designation) is not the same as a PEP note, and routing
            # both to a soft "review" understated the first. A critical listing
            # now holds the traveller for adjudication.
            severity = str(criminal_check.get("severity") or "high").lower()
            is_critical_listing = severity == "critical"

            risk_record.explanations.append({
                "flag": (
                    f"UNVERIFIED watchlist lead "
                    f"[{str(criminal_check.get('alert') or 'WATCHLIST').upper()}] "
                    f"({criminal_check.get('hit_count')} candidate match(es) from "
                    f"{', '.join(criminal_check.get('sources', []))}) — "
                    f"{criminal_check.get('reason')}"
                ),
                "severity": "critical" if is_critical_listing else "high",
            })

            # Never downgrade a decision the risk engine already escalated.
            if is_critical_listing:
                if risk_record.decision != "detain":
                    risk_record.decision = "hold"
                risk_record.risk_level = "critical"
                risk_record.score = max(risk_record.score or 0.0, 90.0)
            else:
                if risk_record.decision not in ("detain", "hold"):
                    risk_record.decision = "review"
                if risk_record.risk_level not in ("critical", "high"):
                    risk_record.risk_level = "high"
                risk_record.score = max(risk_record.score or 0.0, 72.0)

        # Surface MRZ reference mismatches — a document whose fields disagree
        # with the issuing authority's record is a strong forgery signal.
        if mrz_reference.get("status") == "mismatch":
            for diff in mrz_reference.get("differences", []):
                risk_record.explanations.append({
                    "flag": (
                        f"Reference mismatch on {diff['field']}: document says "
                        f"{diff['scanned']!r}, reference says {diff['expected']!r}"
                    ),
                    "severity": "critical",
                })
            risk_record.risk_level = "critical"
            risk_record.score = max(risk_record.score or 0.0, 90.0)
            if risk_record.decision not in ("detain",):
                risk_record.decision = "hold"
        elif mrz_reference.get("status") == "not_found" and mrz_reference.get("reference_count"):
            risk_record.explanations.append({
                "flag": (
                    "Document number is not present in the MRZ reference registry "
                    "— cannot be corroborated against a known-good record"
                ),
                "severity": "medium",
            })

        risk_record.mrz_reference = mrz_reference
        
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


def process_face_only_pipeline(
    scan_id,
    db: Session,
    face_local_path: str | None = None,
) -> ScanRecord:
    """
    Screen a traveller who presents no document at all.

    Only biometric evidence exists, so the checks that depend on a document —
    OCR, MRZ check digits, chip PKI, document forensics, reference registry —
    are not run and are recorded as NOT_APPLICABLE rather than as failures.
    Reporting them as failures would make every undocumented traveller look
    like a forgery case.

    What does run:
      1. Face detection, quality assessment and liveness
      2. Identity graph search — does this face match a previous encounter?
      3. Watchlist / OpenSanctions screening on any identity the graph resolved
      4. Risk scoring over biometric evidence alone
      5. Cryptographic evidence anchor
    """
    target_id = _coerce_scan_id(scan_id)
    scan = db.query(ScanRecord).filter(ScanRecord.id == target_id).first()
    if not scan:
        raise ValueError(f"ScanRecord {scan_id} not found")

    try:
        scan.status = "processing"
        db.commit()

        face_path = face_local_path or _resolve_local_path(scan.face_image_path)
        if not face_path or not os.path.exists(face_path):
            raise FileNotFoundError(
                f"Face image could not be read for screening (stored at {scan.face_image_path!r})."
            )

        # 1. Biometric extraction. There is nothing to verify *against* yet, so
        #    the embedding is the product here, not a similarity score.
        analysis = face_service.analyse_image(face_path)

        if analysis["face_count"] > 1:
            raise ValueError(
                f"{analysis['face_count']} faces were detected in the submitted "
                "image. Face-only screening identifies one traveller at a time — "
                "recapture with only the traveller in frame."
            )

        if not analysis["ok"]:
            raise ValueError(
                f"No usable face could be detected in the submitted image "
                f"({analysis['reason']}). Recapture with the face centred, "
                "unobstructed and evenly lit."
            )

        embedding = analysis["embedding"]
        is_live, liveness_flag = face_service.verify_liveness_path(face_path)

        # 2. Identity graph — search prior encounters by biometric similarity.
        identity_summary = identity_graph_service.evaluate_identity_continuity(
            current_scan_id=str(scan.id),
            current_face_embedding=embedding,
            current_document_number=None,
            current_holder_name=None,
            current_dob=None,
            db=db,
        )

        links = identity_summary.get("continuity_links", []) or []

        # 3. Watchlist screening. With no document there is nothing to screen
        #    until the graph resolves a candidate identity from a past encounter.
        watchlist_hits: list = []
        criminal_check = {
            "is_criminal": False,
            "is_thief": False,
            "alert": None,
            "hit_count": 0,
            "requires_adjudication": False,
        }
        # Links are ordered by descending cosine, so the strongest match is the
        # candidate identity. Only resolved identities are considered — a link to
        # a record whose own OCR failed cannot name this traveller.
        best_link = next((l for l in links if l.get("identity_resolved")), None)
        resolved_name = (best_link or {}).get("holder_name")
        resolved_doc = (best_link or {}).get("document_number")

        if resolved_name or resolved_doc:
            watchlist_hits = watchlist_service.check_watchlist(
                document_number=resolved_doc, holder_name=resolved_name
            )
            criminal_check = watchlist_service.is_known_criminal(
                document_number=resolved_doc, holder_name=resolved_name
            )

        # 4. Risk assessment over biometric evidence only.
        explanations: list = [{
            "flag": "Face-only screening — no travel document was presented",
            "severity": "high",
        }]
        score = 55.0          # An undocumented crossing warrants review by default.
        level = "medium"
        decision = "review"

        if is_live is False:
            explanations.append({
                "flag": liveness_flag or "Liveness check failed — possible presentation attack",
                "severity": "high",
            })
            score = max(score, 78.0)
            level = "high"
            decision = "hold"
        elif is_live is None:
            explanations.append({
                "flag": liveness_flag or "Liveness could not be assessed on this capture",
                "severity": "medium",
            })

        if links:
            top = links[0]
            explanations.append({
                "flag": (
                    f"1:N biometric search matched {len(links)} previous "
                    f"encounter(s) at or above cosine "
                    f"{identity_summary.get('match_threshold')}. Strongest: "
                    f"{top.get('holder_name')} ({top.get('document_number')}) "
                    f"at cosine {top.get('cosine_similarity')}"
                    + (f" — identified as {resolved_name}" if resolved_name else
                       " — no resolved identity among the matches")
                ),
                "severity": "info" if resolved_name else "medium",
            })
        else:
            explanations.append({
                "flag": (
                    "1:N biometric search found no prior encounter above cosine "
                    f"{identity_summary.get('match_threshold')} — identity unresolved"
                ),
                "severity": "medium",
            })

        if identity_summary.get("incomparable_records"):
            explanations.append({
                "flag": (
                    f"{identity_summary['incomparable_records']} stored record(s) "
                    "hold embeddings that are not comparable with the current model "
                    "and were excluded from the search"
                ),
                "severity": "low",
            })

        if criminal_check.get("is_criminal"):
            explanations.append({
                "flag": f"{criminal_check.get('alert')}: {criminal_check.get('reason')}",
                "severity": "critical",
            })
            score, level, decision = 100.0, "critical", "detain"
        elif criminal_check.get("requires_adjudication"):
            explanations.append({
                "flag": (
                    f"UNVERIFIED watchlist lead on the resolved identity "
                    f"({criminal_check.get('hit_count')} candidate match(es))"
                ),
                "severity": "high",
            })
            score, level = max(score, 80.0), "high"
            decision = "hold" if decision != "detain" else decision

        # 5. Persist. Only the biometric tables are written — no ExtractedData,
        #    ForgeryResult or reference comparison exists for a face-only scan.
        db.add(FaceResult(
            scan_id=scan.id,
            match_score=None,          # nothing to compare a face against
            liveness_passed=is_live,
            face_embedding=embedding,
            continuity_links=links,
            watchlist_hits=watchlist_hits,
        ))

        digest = {
            "scan_id": str(scan.id),
            "document_number": resolved_doc or "",
            "holder_name": resolved_name or "",
            "chip_pki_status": "NOT_APPLICABLE",
            "mrz_valid": False,
            "forgery_anomaly_score": 0.0,
            "face_match_score": 0.0,
            "contradiction_flags": [e["flag"] for e in explanations],
            "overall_classification": "FACE_ONLY_SCREENING",
            "officer_decision": decision.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        canonical_hash, _ = crypto_anchor.generate_canonical_hash(digest)

        db.add(RiskScore(
            scan_id=scan.id,
            score=score,
            risk_level=level,
            explanations=explanations,
            decision=decision,
            contradiction_matrix=[
                {"category": "Document", "check_name": "Travel document presented",
                 "signal_a": "None submitted", "signal_b": "Required for full screening",
                 "status": "NOT_PERFORMED", "severity": "INFO",
                 "finding": "Face-only screening mode."},
                {"category": "Biometrics", "check_name": "Face detected and live",
                 "signal_a": f"1 face, detector confidence {analysis.get('confidence')}",
                 "signal_b": (
                     "Liveness: live" if is_live is True
                     else "Liveness: FAILED" if is_live is False
                     else "Liveness: not assessed"
                 ),
                 "status": "OK" if is_live is True else "ALERT" if is_live is False else "NOT_PERFORMED",
                 "severity": "INFO" if is_live is True else "HIGH" if is_live is False else "MEDIUM",
                 "finding": "Anti-spoofing assessment of the live capture."},
                {"category": "Identity", "check_name": "1:N prior encounter search",
                 "signal_a": (
                     f"{len(links)} match(es) at cosine >= "
                     f"{identity_summary.get('match_threshold')}"
                 ),
                 "signal_b": resolved_name or "Unresolved",
                 "status": "OK" if links else "NOT_PERFORMED",
                 "severity": "INFO",
                 "finding": "Biometric continuity across past screenings."},
                {"category": "Watchlist", "check_name": "Sanctions / criminal screening",
                 "signal_a": f"{criminal_check.get('hit_count', 0)} hit(s)",
                 "signal_b": "Requires resolved identity",
                 "status": "ALERT" if watchlist_hits else "OK",
                 "severity": "CRITICAL" if criminal_check.get("is_criminal") else "INFO",
                 "finding": "Screened only once the graph resolves an identity."},
            ],
            identity_graph_summary=identity_summary,
            fraud_patterns_matched=[],
            canonical_hash=canonical_hash,
            mrz_reference={
                "status": "not_applicable",
                "summary": "No document was presented, so there is nothing to compare.",
                "differences": [],
            },
        ))

        scan.status = "completed"
        scan.canonical_hash = canonical_hash
        scan.chip_pki_status = "NOT_APPLICABLE"
        scan.checkpoint_latitude = str(settings.CHECKPOINT_LATITUDE)
        scan.checkpoint_longitude = str(settings.CHECKPOINT_LONGITUDE)
        scan.is_criminal = "Yes" if criminal_check.get("is_criminal") else "No"
        scan.criminal_record = (
            criminal_check.get("reason") if criminal_check.get("is_criminal") else None
        )

        db.add(AuditLog(
            scan_id=scan.id,
            action="face_only_screening_completed",
            actor="system",
            details={
                "risk_score": score,
                "decision": decision,
                "biometric_links": len(links),
                "resolved_identity": resolved_name,
                "watchlist_hits": len(watchlist_hits),
            },
        ))

        db.commit()
        db.refresh(scan)
        return scan

    except Exception as e:
        db.rollback()
        logger.error(
            "[FaceOnlyPipeline] scan %s failed: %s\n%s",
            scan.id, e, traceback.format_exc(),
        )
        scan.status = "failed"
        scan.notes = f"Face-only screening could not be completed: {type(e).__name__}: {e}"
        db.commit()
        raise

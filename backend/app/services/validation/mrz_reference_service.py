"""
Compare a scanned document against the MRZ reference registry.

Per-document checks (check digits, ELA, face match) can all pass on a document
that is simply *not the one the issuer issued*. Comparing against a known-good
record is what catches an altered date of birth or an extended expiry on an
otherwise well-formed passport.

Outcome is one of:
  no_reference_data — the registry is empty; nothing to compare against
  not_found         — document number absent from the registry
  match             — every comparable field agrees
  mismatch          — at least one field disagrees (strong forgery signal)
  revoked           — the reference record is revoked or reported stolen
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.mrz_reference import MRZReference
from app.services.face.watchlist_service import (
    name_similarity,
    normalize_doc_number,
    normalize_name,
)

logger = logging.getLogger(__name__)

# Fields compared verbatim after normalisation.
EXACT_FIELDS = (
    ("date_of_birth", "date_of_birth"),
    ("expiry_date", "expiry_date"),
    ("sex", "sex"),
    ("issuing_country", "issuing_country"),
)

# Names are compared by similarity — OCR transcription noise is expected, so an
# exact string comparison would report a mismatch on every real scan.
NAME_MATCH_THRESHOLD = 0.85


class MRZReferenceService:
    def compare(self, ocr_result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Look up and diff the scanned fields against the registry."""
        doc_number = normalize_doc_number(ocr_result.get("document_number"))

        try:
            total = db.query(MRZReference).count()
        except Exception as exc:  # noqa: BLE001 - never break a scan over this
            logger.warning("[MRZReference] registry unavailable: %s", exc)
            return {"status": "no_reference_data", "reference_count": 0, "differences": []}

        if total == 0:
            return {
                "status": "no_reference_data",
                "reference_count": 0,
                "differences": [],
                "summary": "MRZ reference registry is empty — no corroboration possible.",
            }

        if not doc_number:
            return {
                "status": "not_found",
                "reference_count": total,
                "differences": [],
                "summary": "No document number was extracted, so no reference lookup was possible.",
            }

        record: Optional[MRZReference] = (
            db.query(MRZReference)
            .filter(MRZReference.document_number == doc_number)
            .first()
        )

        if record is None:
            return {
                "status": "not_found",
                "reference_count": total,
                "document_number": doc_number,
                "differences": [],
                "summary": (
                    f"Document {doc_number} is not in the reference registry. "
                    "Fields could not be corroborated against a known-good record."
                ),
            }

        differences: List[Dict[str, Any]] = []

        for scanned_key, ref_attr in EXACT_FIELDS:
            scanned = ocr_result.get(scanned_key)
            expected = getattr(record, ref_attr, None)
            # Only compare when both sides hold a value; a field the scan could
            # not read is a gap, not a contradiction.
            if not scanned or not expected:
                continue
            if str(scanned).strip().upper() != str(expected).strip().upper():
                differences.append({
                    "field": scanned_key,
                    "scanned": scanned,
                    "expected": expected,
                    "severity": "critical",
                })

        scanned_name = ocr_result.get("holder_name")
        if scanned_name and record.holder_name:
            similarity = name_similarity(scanned_name, record.holder_name)
            if similarity < NAME_MATCH_THRESHOLD:
                differences.append({
                    "field": "holder_name",
                    "scanned": normalize_name(scanned_name),
                    "expected": normalize_name(record.holder_name),
                    "similarity": similarity,
                    "severity": "critical",
                })

        # Issuer-side status outranks field agreement: a perfectly matching
        # document that has been revoked must not read as "match".
        if record.is_revoked or record.is_reported_stolen:
            return {
                "status": "revoked",
                "reference_count": total,
                "document_number": doc_number,
                "differences": differences,
                "is_revoked": record.is_revoked,
                "is_reported_stolen": record.is_reported_stolen,
                "revocation_reason": record.revocation_reason,
                "reference_holder": record.holder_name,
                "summary": (
                    f"Reference record for {doc_number} is "
                    f"{'reported stolen' if record.is_reported_stolen else 'revoked'}: "
                    f"{record.revocation_reason or 'no reason recorded'}."
                ),
            }

        if differences:
            fields = ", ".join(d["field"] for d in differences)
            return {
                "status": "mismatch",
                "reference_count": total,
                "document_number": doc_number,
                "differences": differences,
                "reference_holder": record.holder_name,
                "summary": (
                    f"Document {doc_number} disagrees with the reference record on: {fields}. "
                    "Consistent with data alteration on a genuine document blank."
                ),
            }

        return {
            "status": "match",
            "reference_count": total,
            "document_number": doc_number,
            "differences": [],
            "reference_holder": record.holder_name,
            "summary": (
                f"All comparable fields agree with the reference record for {doc_number}."
            ),
        }


mrz_reference_service = MRZReferenceService()

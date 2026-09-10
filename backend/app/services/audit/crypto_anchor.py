"""
Cryptographic Audit Anchor Service.

Answers the cybersecurity question:
"Can we prove that the verification evidence recorded at this point in time
has not been silently altered afterward?"

Generates canonical SHA-256 cryptographic fingerprints of verification records
and anchors them as immutable non-repudiation proofs.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _as_float(value: Any, default: float = 0.0) -> float:
    """Coerce to float, falling back to `default` for None or junk."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_optional_float(value: Any) -> Optional[float]:
    """
    Coerce to float but preserve None.

    Distinguishing "not measured" from "measured as zero" matters in an evidence
    digest: coercing a missing biometric to 0.0 would make an unverified scan
    hash identically to one that genuinely scored zero.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CryptoAuditAnchor:
    def generate_canonical_hash(self, evidence_payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Creates a deterministic canonical JSON string and computes its SHA-256 digest.
        """
        canonical_record = {
            "scan_id": str(evidence_payload.get("scan_id", "")),
            "document_number": str(evidence_payload.get("document_number", "")),
            "holder_name": str(evidence_payload.get("holder_name", "")),
            # Absent chip status is UNKNOWN, not "authentic". Defaulting this to
            # AUTHENTIC_VALID meant the signed evidence asserted a valid chip for
            # a document whose chip was never read.
            "chip_pki_status": str(evidence_payload.get("chip_pki_status") or "UNKNOWN"),
            # Absent MRZ result is False (unverified), not True.
            "mrz_valid": bool(evidence_payload.get("mrz_valid") or False),
            "forgery_anomaly_score": _as_float(evidence_payload.get("forgery_anomaly_score")),
            # None means the biometric comparison did not run. It must stay null
            # in the digest rather than being coerced to 0.0, which would be
            # indistinguishable from "compared and scored zero".
            #
            # This previously called float() directly, so a scan with no live
            # capture raised TypeError: float() argument must be ... not
            # 'NoneType', the whole pipeline aborted with a 500, and the browser
            # reported it as "Failed to fetch".
            "face_match_score": _as_optional_float(evidence_payload.get("face_match_score")),
            "face_match_cosine": _as_optional_float(evidence_payload.get("face_match_cosine")),
            "face_match_passed": evidence_payload.get("face_match_passed"),
            "contradiction_flags": sorted(evidence_payload.get("contradiction_flags") or []),
            "overall_classification": str(evidence_payload.get("overall_classification") or "UNCLASSIFIED"),
            "officer_decision": str(evidence_payload.get("officer_decision") or "PENDING"),
            "timestamp": str(evidence_payload.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        }

        # Deterministic JSON encoding: sorted keys, compact separators
        canonical_json = json.dumps(canonical_record, sort_keys=True, separators=(",", ":"))
        sha256_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        return sha256_hash, canonical_json

    def verify_integrity(self, evidence_payload: Dict[str, Any], expected_hash: str) -> bool:
        """
        Verifies that current database state matches the immutable cryptographic hash.
        """
        computed_hash, _ = self.generate_canonical_hash(evidence_payload)
        return computed_hash.lower() == expected_hash.lower()


crypto_anchor = CryptoAuditAnchor()

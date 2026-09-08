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
from typing import Dict, Any, Tuple


class CryptoAuditAnchor:
    def generate_canonical_hash(self, evidence_payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Creates a deterministic canonical JSON string and computes its SHA-256 digest.
        """
        canonical_record = {
            "scan_id": str(evidence_payload.get("scan_id", "")),
            "document_number": str(evidence_payload.get("document_number", "")),
            "holder_name": str(evidence_payload.get("holder_name", "")),
            "chip_pki_status": str(evidence_payload.get("chip_pki_status", "AUTHENTIC_VALID")),
            "mrz_valid": bool(evidence_payload.get("mrz_valid", True)),
            "forgery_anomaly_score": float(evidence_payload.get("forgery_anomaly_score", 0.0)),
            "face_match_score": float(evidence_payload.get("face_match_score", 0.0)),
            "contradiction_flags": sorted(evidence_payload.get("contradiction_flags", [])),
            "overall_classification": str(evidence_payload.get("overall_classification", "GENUINE_CONSISTENT")),
            "officer_decision": str(evidence_payload.get("officer_decision", "PENDING")),
            "timestamp": str(evidence_payload.get("timestamp", datetime.now(timezone.utc).isoformat())),
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

"""
Risk Scoring & Decision Engine.

Aggregates multi-modal evidence:
- Document Validation & Checksums
- Dual-Domain Forgery Forensics
- 512-d Biometric Cosine Similarity & Anti-Spoofing
- Contradiction Engine Evidence Matrix
- Identity Graph Continuity (Cross-encounter reuse)
- Fraud Pattern Memory (EU-FADO style known syndicate matches)
- Security Watchlists (INTERPOL SLTD, Lookouts)
"""

from typing import Dict, Any, List, Optional


class RiskEngine:
    def evaluate(
        self,
        ocr_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        forgery_result: Dict[str, Any],
        face_result: Dict[str, Any],
        watchlist_hits: List[Dict[str, Any]],
        contradiction_result: Optional[Dict[str, Any]] = None,
        identity_graph_summary: Optional[Dict[str, Any]] = None,
        fraud_patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates composite risk score and generates explainable evidentiary payload.
        """
        raw_score = 0.0
        explanations: List[Dict[str, str]] = []

        # 1. Contradiction Engine Findings (Highest Priority)
        if contradiction_result and contradiction_result.get("has_contradictions"):
            raw_score = max(raw_score, contradiction_result.get("escalated_risk_score", 75.0))
            for c_flag in contradiction_result.get("contradiction_flags", []):
                explanations.append({
                    "flag": c_flag,
                    "severity": "critical" if raw_score >= 80.0 else "high"
                })

        # 2. Fraud Pattern Memory Matches (EU-FADO Knowledge Base)
        if fraud_patterns:
            for pattern in fraud_patterns:
                raw_score = max(raw_score, 70.0)
                explanations.append({
                    "flag": f"Known Fraud Signature: {pattern.get('name')} ({int(pattern.get('confidence', 0.9)*100)}% match)",
                    "severity": pattern.get("severity", "high").lower()
                })

        # 3. Identity Graph Continuity Anomalies
        if identity_graph_summary:
            for anomaly in identity_graph_summary.get("anomalies", []):
                raw_score = max(raw_score, 85.0 if anomaly.get("severity") == "CRITICAL" else 65.0)
                explanations.append({
                    "flag": anomaly.get("description", "Identity Graph anomaly detected across historical encounters"),
                    "severity": anomaly.get("severity", "high").lower()
                })

        # 4. Forgery Detection Signal
        anomaly_score = forgery_result.get("anomaly_score", 0.0)
        if anomaly_score > 0:
            forgery_points = anomaly_score * 0.35
            raw_score += forgery_points
            for issue in forgery_result.get("detected_issues", []):
                explanations.append({
                    "flag": f"Forensic Alert: {issue.get('detail', issue.get('type'))}",
                    "severity": "high" if anomaly_score > 50 else "medium"
                })

        # 5. OCR & MRZ Checksum Signal
        #
        # Only penalise a FAILED checksum on a document that is supposed to have
        # one. A national ID card has no MRZ, so `mrz_valid=False` there means
        # "nothing to verify", not "verification failed" — charging it +25 would
        # penalise every ID card for the shape of its own standard.
        #
        # Conversely a passport with an unreadable MRZ is a genuine finding: the
        # single most tamper-resistant part of the document could not be read.
        mrz_valid = ocr_result.get("mrz_valid", False)
        mrz_required = ocr_result.get("mrz_required", True)

        if mrz_required and not mrz_valid:
            raw_score += 25.0
            for flag in ocr_result.get("flags", []):
                explanations.append({
                    "flag": flag,
                    "severity": "high"
                })
        elif not mrz_required:
            # Recorded so the officer can see integrity was never machine-verified
            # on this credential, rather than inferring it from a PASS row.
            explanations.append({
                "flag": (
                    "Document carries no machine-readable zone, so its data "
                    "integrity could not be verified by check digit — fields were "
                    "read by OCR only"
                ),
                "severity": "low",
            })

        # 6. Document Validation Rules Signal
        #
        # Expiry is read from the structured field result rather than by matching
        # the English substring "Expired document" in a human-readable flag.
        # That coupling meant rewording the message in validation_service would
        # silently delete the expiry penalty.
        #
        # An expired travel document is also no longer a mere +30 (which landed
        # at "medium / review"). A document that is not valid for travel is a
        # hard stop, so it floors the score into the reject band.
        if not validation_result.get("is_valid", True):
            field_results = validation_result.get("field_results", {})
            expiry_field = field_results.get("expiry_date", {})
            expired = expiry_field.get("reason") == "Document expired"

            for flag in validation_result.get("flags", []):
                is_expiry_flag = flag.startswith("Expired document")
                if is_expiry_flag and expired:
                    raw_score = max(raw_score, 80.0)
                    explanations.append({
                        "flag": f"{flag} — document is not valid for travel",
                        "severity": "critical",
                    })
                else:
                    raw_score += 15.0
                    explanations.append({"flag": flag, "severity": "medium"})

        # 7. Facial Biometrics & Liveness Signal
        #
        # The verdict comes from face_service via `match_passed`, which is the
        # single source of truth. This block used to re-derive it by testing
        # `similarity_score < 0.70`, duplicating a threshold that lived in three
        # places. Since face_service now reports the raw SFace cosine (where the
        # operating point is ~0.363, not 0.70), that test would have failed
        # every genuine match.
        #
        # Three outcomes are distinguished, because conflating them is what made
        # undocumented or unphotographed travellers look like impostors:
        #   match_passed is None   -> no comparison happened
        #   match_passed is False  -> compared, and the faces differ
        #   match_passed is True   -> compared, and the faces agree
        match_passed = face_result.get("match_passed")
        biometric_performed = face_result.get("biometric_performed", False)
        raw_cosine = face_result.get("raw_cosine")
        threshold = face_result.get("match_threshold")

        if not biometric_performed or match_passed is None:
            raw_score += 20.0
            reason = next(
                (f for f in face_result.get("flags", []) if f),
                "no live capture was supplied",
            )
            explanations.append({
                "flag": (
                    "Biometric 1:1 verification was NOT performed — "
                    f"{reason}. An officer must verify the traveller visually."
                ),
                "severity": "medium",
            })
        elif not match_passed:
            raw_score += 35.0
            detail = (
                f"cosine {raw_cosine:.4f} < required {threshold:.3f}"
                if raw_cosine is not None and threshold is not None
                else "below the required threshold"
            )
            explanations.append({
                "flag": (
                    f"Biometric 1:1 verification FAILED: the live traveller does "
                    f"not match the document portrait ({detail})"
                ),
                "severity": "high",
            })

        # Liveness is tri-state for the same reason: None means "not assessed".
        is_live = face_result.get("is_live")
        if is_live is False:
            raw_score += 45.0
            explanations.append({
                "flag": "Liveness verification failed: potential presentation spoof / screen replay",
                "severity": "critical",
            })
        elif is_live is None and biometric_performed:
            raw_score += 10.0
            explanations.append({
                "flag": "Liveness could not be assessed on the submitted capture",
                "severity": "medium",
            })

        # 8. Watchlist Cross-Check Signal
        if watchlist_hits:
            for hit in watchlist_hits:
                sev = hit.get("severity", "critical")
                points = 85.0 if sev == "critical" else 50.0
                raw_score += points
                explanations.append({
                    "flag": f"WATCHLIST MATCH [{hit.get('category', 'ALERT')}]: {hit.get('reason')}",
                    "severity": sev
                })

        # Cap score between 0.0 and 100.0
        final_score = round(min(100.0, max(0.0, raw_score)), 1)

        # Categorize Risk Level & Recommendation
        if final_score >= 80.0:
            risk_level = "critical"
            decision = "hold"
        elif final_score >= 50.0:
            risk_level = "high"
            decision = "review"
        elif final_score >= 25.0:
            risk_level = "medium"
            decision = "review"
        else:
            risk_level = "low"
            decision = "pass"

        if not explanations:
            explanations.append({
                "flag": "All multi-modal verification streams clean and mutually consistent",
                "severity": "low"
            })

        return {
            "score": final_score,
            "risk_level": risk_level,
            "decision": decision,
            "explanations": explanations,
            "contradiction_matrix": contradiction_result.get("contradiction_matrix", []) if contradiction_result else [],
            "identity_graph_summary": identity_graph_summary or {},
            "fraud_patterns_matched": fraud_patterns or [],
        }


risk_engine = RiskEngine()

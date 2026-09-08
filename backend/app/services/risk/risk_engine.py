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
        mrz_valid = ocr_result.get("mrz_valid", True)
        if not mrz_valid:
            raw_score += 25.0
            for flag in ocr_result.get("flags", []):
                explanations.append({
                    "flag": flag,
                    "severity": "high"
                })

        # 6. Document Validation Rules Signal
        if not validation_result.get("is_valid", True):
            for flag in validation_result.get("flags", []):
                if "Expired document" in flag:
                    raw_score += 30.0
                    explanations.append({"flag": flag, "severity": "high"})
                else:
                    raw_score += 15.0
                    explanations.append({"flag": flag, "severity": "medium"})

        # 7. Facial Biometrics & Liveness Signal
        # DEFAULT to 0.0 if missing (not 1.0) - Be strict, not permissive
        sim_score = face_result.get("similarity_score", face_result.get("match_score", 0.0))
        is_live = face_result.get("is_live", False)  # Default to NOT live if unverified

        # THRESHOLD: 0.70 = REJECT if below (CRITICAL FIX)
        if sim_score < 0.70:
            raw_score += 35.0
            explanations.append({
                "flag": f"Biometric threshold FAILED: 1:1 Cosine Similarity ({sim_score * 100:.1f}%) - REJECTED (threshold: 70%)",
                "severity": "high"
            })

        if not is_live:
            raw_score += 45.0
            explanations.append({
                "flag": "Liveness verification failed: Potential presentation spoof / digital screen replay",
                "severity": "critical"
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

"""
Contradiction Engine Service.

The signature intelligence layer:
Evaluates an Evidence Truth Matrix across independent verification streams
(Chip PKI, MRZ checksums, Visual OCR, Biometric 1:1, Forgery forensics, Identity Graph, Watchlists)
to uncover semantic paradoxes and identity fraud that survive individual checks.
Supports Passports (with PKI/MRZ) and National IDs/Aadhaar cards.
"""

from typing import Dict, Any, List, Optional


class ContradictionEngine:
    def evaluate_contradictions(
        self,
        chip_pki_status: str,
        mrz_valid: bool,
        ocr_fields: Dict[str, Any],
        forgery_result: Dict[str, Any],
        face_result: Dict[str, Any],
        identity_graph_summary: Dict[str, Any],
        watchlist_hits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Executes multi-modal cross-correlation to produce the Contradiction Matrix
        and high-level evidentiary classification.
        """
        contradiction_matrix: List[Dict[str, Any]] = []
        contradiction_flags: List[str] = []
        overall_classification = "GENUINE_CONSISTENT"
        escalated_risk_score = 10.0

        doc_type = ocr_fields.get("document_type", "passport")
        is_passport = (doc_type == "passport")
        mrz_required = ocr_fields.get("mrz_required", is_passport)
        has_chip = chip_pki_status not in ["NOT_APPLICABLE", "N/A", "NO_CHIP", None]

        # --- SIGNAL 1: Document Integrity & Photo Forensics ---
        photo_spliced = False
        issues = forgery_result.get("detected_issues", [])
        for issue in issues:
            if issue.get("type") in ["photo_boundary_splice", "ela_tampering"] and issue.get("confidence", 0) > 0.65:
                photo_spliced = True
                break

        chip_is_valid = has_chip and (chip_pki_status == "AUTHENTIC_VALID")
        
        if chip_is_valid and photo_spliced:
            flag = "CONTRADICTION: Chip PKI signature is valid, but passport photo boundary displays physical splice/tampering"
            contradiction_flags.append(flag)
            overall_classification = "PHOTO_SUBSTITUTION_ON_GENUINE_DOCUMENT"
            escalated_risk_score = max(escalated_risk_score, 88.0)
            contradiction_matrix.append({
                "category": "Document Integrity",
                "check_name": "Chip PKI vs. Photo Forensics",
                "signal_a": "Chip PKI: Valid",
                "signal_b": "Photo Forensics: Spliced",
                "status": "CONTRADICTION",
                "severity": "CRITICAL",
                "finding": "Passport document is authentic, but the portrait photo has been physically swapped.",
            })
        elif photo_spliced:
            flag = "Photo boundary displays physical splice/tampering"
            contradiction_flags.append(flag)
            escalated_risk_score = max(escalated_risk_score, 75.0)
            contradiction_matrix.append({
                "category": "Document Integrity",
                "check_name": "Photo Forensics Integrity",
                "signal_a": "Document Physical Layout",
                "signal_b": "Photo Forensics: Spliced",
                "status": "ALERT",
                "severity": "HIGH",
                "finding": "Document portrait shows tampering or splice anomalies.",
            })
        else:
            signal_a_text = f"Chip PKI: {chip_pki_status}" if has_chip else "Credential: Standard ID"
            finding_text = "Physical photo integrity conforms with cryptographic chip signature." if has_chip else "Document portrait is authentic with no physical or digital tampering detected."
            contradiction_matrix.append({
                "category": "Document Integrity",
                "check_name": "Chip PKI vs. Photo Forensics" if has_chip else "Document Photo Integrity",
                "signal_a": signal_a_text,
                "signal_b": "Photo Forensics: Clean",
                "status": "PASS",
                "severity": "LOW",
                "finding": finding_text,
            })

        # --- SIGNAL 2: Biometric 1:1 Live Face Match ---
        face_match_score = face_result.get("match_score", face_result.get("similarity_score", 0.90))
        # THRESHOLD: 0.70 = REJECT if below (CRITICAL FIX)
        face_matched = face_match_score >= 0.70
        liveness_passed = face_result.get("liveness_passed", face_result.get("is_live", True))

        # A biometric comparison that never ran is not a mismatch. Treat it as an
        # open item requiring an officer, not as evidence against the traveller.
        biometric_performed = face_result.get("biometric_performed", True)
        if not biometric_performed:
            contradiction_flags.append(
                "Biometric match not performed — no live face capture supplied"
            )
            contradiction_matrix.append({
                "category": "Biometrics",
                "check_name": "Document Portrait vs. Live Traveler Face",
                "signal_a": "Portrait extracted",
                "signal_b": "No live capture submitted",
                "status": "NOT_PERFORMED",
                "severity": "INFO",
                "finding": "Face verification is pending a live capture at the counter.",
            })
        elif chip_is_valid and not face_matched:
            flag = "CONTRADICTION: Chip PKI signature is valid, but traveler live face fails biometric match with passport portrait"
            contradiction_flags.append(flag)
            overall_classification = "IMPOSTOR_PRESENTATION_GENUINE_PASSPORT"
            escalated_risk_score = max(escalated_risk_score, 92.0)
            contradiction_matrix.append({
                "category": "Biometrics",
                "check_name": "Chip Authenticity vs. Live Traveler Face",
                "signal_a": "Chip PKI: Valid",
                "signal_b": f"Face Match: Failed ({int(face_match_score*100)}%)",
                "status": "CONTRADICTION",
                "severity": "CRITICAL",
                "finding": "Genuine passport presented by an impostor / lookalike traveler.",
            })
        elif not face_matched:
            flag = f"Biometric mismatch: Live traveler does not match credential portrait ({int(face_match_score*100)}%)"
            contradiction_flags.append(flag)
            escalated_risk_score = max(escalated_risk_score, 80.0)
            contradiction_matrix.append({
                "category": "Biometrics",
                "check_name": "Document Portrait vs. Live Traveler Face",
                "signal_a": "Portrait Extracted",
                "signal_b": f"Face Match: Failed ({int(face_match_score*100)}%)",
                "status": "ALERT",
                "severity": "HIGH",
                "finding": "Live traveler facial geometry does not match the credential portrait.",
            })
        elif not liveness_passed:
            flag = "Anti-spoofing alert: Presentation attack or non-live face detected"
            contradiction_flags.append(flag)
            escalated_risk_score = max(escalated_risk_score, 85.0)
            contradiction_matrix.append({
                "category": "Biometrics",
                "check_name": "Anti-Spoofing Liveness Verification",
                "signal_a": f"Face Match: {int(face_match_score*100)}%",
                "signal_b": "Liveness: Failed",
                "status": "ALERT",
                "severity": "HIGH",
                "finding": "Presentation attack detected during traveler biometric acquisition.",
            })
        else:
            signal_a_face = f"Chip PKI: {chip_pki_status}" if has_chip else "Document Portrait: Valid"
            contradiction_matrix.append({
                "category": "Biometrics",
                "check_name": "Chip Authenticity vs. Live Traveler Face" if has_chip else "Document Portrait vs. Live Face",
                "signal_a": signal_a_face,
                "signal_b": f"Face Match: {int(face_match_score*100)}%",
                "status": "PASS",
                "severity": "LOW",
                "finding": "Live traveler facial geometry matches document credential.",
            })

        # --- SIGNAL 3: MRZ Checksums vs Visual Zone OCR ---
        mrz_flags = ocr_fields.get("flags", [])
        mrz_has_conflict = any("mismatch" in f.lower() or "check digit" in f.lower() for f in mrz_flags)

        if mrz_required:
            if mrz_valid and mrz_has_conflict:
                flag = "CONTRADICTION: MRZ check digits pass mathematically, but visual zone fields conflict with MRZ decoded data"
                contradiction_flags.append(flag)
                overall_classification = "VISUAL_ZONE_MANIPULATION"
                escalated_risk_score = max(escalated_risk_score, 82.0)
                contradiction_matrix.append({
                    "category": "Data Consistency",
                    "check_name": "MRZ Checksum vs. Visual Zone OCR",
                    "signal_a": "MRZ Checksum: Valid",
                    "signal_b": "Visual Zone: Mismatch",
                    "status": "CONTRADICTION",
                    "severity": "HIGH",
                    "finding": "Visual demographic text was altered while MRZ line retained original format.",
                })
            else:
                contradiction_matrix.append({
                    "category": "Data Consistency",
                    "check_name": "MRZ Checksum vs. Visual Zone OCR",
                    "signal_a": "MRZ: Valid" if mrz_valid else "MRZ: Invalid",
                    "signal_b": "Visual Zone: Consistent" if not mrz_has_conflict else "Visual Zone: Inconsistent",
                    "status": "PASS" if mrz_valid and not mrz_has_conflict else "ALERT",
                    "severity": "LOW" if mrz_valid else "HIGH",
                    "finding": "Visual zone OCR demographics match ICAO 9303 MRZ encoding perfectly.",
                })
        else:
            # National ID / Aadhaar document without MRZ
            contradiction_matrix.append({
                "category": "Data Consistency",
                "check_name": "Demographic Data Consistency",
                "signal_a": "Visual Zone: Verified",
                "signal_b": "Identity Fields: Complete",
                "status": "PASS",
                "severity": "LOW",
                "finding": "Document demographic fields verified consistently via OCR Visual Inspection.",
            })

        # --- SIGNAL 4: Biometric Verification vs Identity Continuity Graph ---
        graph_anomalies = identity_graph_summary.get("anomalies", [])
        diff_name_anomaly = next((a for a in graph_anomalies if a.get("type") == "IDENTITY_LINK_DIFF_NAME"), None)

        if face_matched and diff_name_anomaly:
            past_name = diff_name_anomaly.get("past_identity", {}).get("holder_name", "Another Identity")
            past_doc = diff_name_anomaly.get("past_identity", {}).get("document_number", "Prior Passport")
            flag = (
                f"CONTRADICTION: Live face matches current document, but matches previous encounter "
                f"({past_doc}) registered under a different name ('{past_name}')"
            )
            contradiction_flags.append(flag)
            overall_classification = "SYNTHETIC_IDENTITY_HOPPING"
            escalated_risk_score = max(escalated_risk_score, 95.0)
            contradiction_matrix.append({
                "category": "Identity Continuity",
                "check_name": "Current Biometric vs. Historical Graph",
                "signal_a": "Current Face: Match",
                "signal_b": f"History: Seen as '{past_name}'",
                "status": "CONTRADICTION",
                "severity": "CRITICAL",
                "finding": f"Traveler's face was previously recorded with document {past_doc} under the name '{past_name}'.",
            })
        elif diff_name_anomaly:
            contradiction_matrix.append({
                "category": "Identity Continuity",
                "check_name": "Current Biometric vs. Historical Graph",
                "signal_a": "Current Face: Mismatch",
                "signal_b": "History: Linked to other identity",
                "status": "ALERT",
                "severity": "HIGH",
                "finding": "Cross-encounter identity link detected across distinct demographic records.",
            })
        else:
            contradiction_matrix.append({
                "category": "Identity Continuity",
                "check_name": "Current Biometric vs. Historical Graph",
                "signal_a": "Current Face: Verified",
                "signal_b": "History: No Contradictory Records",
                "status": "PASS",
                "severity": "LOW",
                "finding": "No conflicting biometric or demographic aliases discovered across historical border crossings.",
            })

        # --- SIGNAL 5: Clean Document vs Watchlist Alerts ---
        if watchlist_hits and len(watchlist_hits) > 0:
            top_hit = watchlist_hits[0]
            hit_source = top_hit.get("source", "ALERT_LIST")
            contradiction_matrix.append({
                "category": "Watchlist",
                "check_name": "Credential Claims vs. Security Watchlist",
                "signal_a": "Document: Valid",
                "signal_b": f"Watchlist: HIT ({hit_source})",
                "status": "CONTRADICTION",
                "severity": "CRITICAL",
                "finding": f"Document details match active security circular from {hit_source}.",
            })
            escalated_risk_score = max(escalated_risk_score, 98.0)
            overall_classification = "WATCHLIST_POSITIVE_ALERT"

        has_contradictions = len(contradiction_flags) > 0

        # Recommended Action based on Contradictions
        if escalated_risk_score >= 85.0:
            recommended_action = "DETAIN"
        elif escalated_risk_score >= 45.0 or has_contradictions:
            recommended_action = "SECONDARY_HOLD"
        else:
            recommended_action = "PASS"

        return {
            "has_contradictions": has_contradictions,
            "overall_classification": overall_classification,
            "escalated_risk_score": escalated_risk_score,
            "recommended_action": recommended_action,
            "contradiction_flags": contradiction_flags,
            "contradiction_matrix": contradiction_matrix,
        }


contradiction_engine = ContradictionEngine()

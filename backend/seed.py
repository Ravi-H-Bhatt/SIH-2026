"""
Seed script — creates the database tables, seeds default users, and loads the 3 SIH demo cases.
Run: python seed.py
"""

import uuid
from datetime import datetime, timezone, timedelta
from app.core.database import engine, SessionLocal, Base
from app.core.security import hash_password
from app.models import (
    User,
    ScanRecord,
    ExtractedData,
    ForgeryResult,
    FaceResult,
    RiskScore,
    AuditLog,
)


def seed():
    print("[INIT] Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] Tables created successfully.")

    db = SessionLocal()
    try:
        default_users = [
            {
                "email": "admin@border.gov",
                "full_name": "System Administrator",
                "password": "admin123",
                "role": "admin",
                "is_approved": True,  # Admin always approved
            },
            {
                "email": "officer@border.gov",
                "full_name": "Demo Officer (DEL-T3)",
                "password": "officer123",
                "role": "officer",
                "is_approved": True,  # Pre-approved for demo
            },
            {
                "email": "supervisor@border.gov",
                "full_name": "Demo Supervisor (BOI-HQ)",
                "password": "supervisor123",
                "role": "supervisor",
                "is_approved": True,  # Pre-approved for demo
            },
        ]

        officer_user = None
        for user_data in default_users:
            user = db.query(User).filter(User.email == user_data["email"]).first()
            if not user:
                user = User(
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=hash_password(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                    is_approved=user_data.get("is_approved", True),
                    approved_at=datetime.now(timezone.utc) if user_data.get("is_approved") else None,
                )
                db.add(user)
                print(f"[SUCCESS] Created user: {user_data['email']} (Approved: {user_data.get('is_approved', True)})")
            else:
                user.hashed_password = hash_password(user_data["password"])
                user.role = user_data["role"]
                user.is_active = True
                user.is_approved = user_data.get("is_approved", True)
                if user.is_approved and not user.approved_at:
                    user.approved_at = datetime.now(timezone.utc)
                print(f"[SUCCESS] Updated credentials for user: {user_data['email']} (Approved: {user.is_approved})")
            if user_data["role"] == "officer":
                officer_user = user
        
        db.commit()
        if officer_user:
            db.refresh(officer_user)

        # ---------------------------------------------------------------------
        # SEED THE 3 SHOWCASE DEMO SCENARIOS
        # ---------------------------------------------------------------------
        existing_scans_count = db.query(ScanRecord).count()
        if existing_scans_count == 0:
            print("[SEED DEMO] Seeding the 3 canonical SIH showcase scenarios...")

            # CASE 1: Obvious Physical/Digital Forgery
            case1_id = uuid.uuid4()
            case1_scan = ScanRecord(
                id=case1_id,
                document_type="passport",
                status="completed",
                checkpoint_id="DEL-T3-EGATE-01",
                officer_id=officer_user.id if officer_user else None,
                document_image_path="uploads/test/test_passport_rahul.jpg",
                face_image_path="uploads/test/test_face_live.jpg",
                chip_pki_status="SIGNATURE_MISMATCH",
                final_decision="DETAIN",
                canonical_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                notes="CASE 1 [DEMO]: Obvious Forgery — Expired passport with tampered expiry year and replaced photo.",
            )
            case1_extracted = ExtractedData(
                scan_id=case1_id,
                fields={
                    "document_number": "J8391024",
                    "full_name": "MALHOTRA / VIKRAM",
                    "dob": "1985-05-12",
                    "nationality": "IND",
                    "expiry_date": "2028-11-20",
                    "issuing_country": "IND",
                },
                mrz_data={
                    "line1": "P<INDMALHOTRA<<VIKRAM<<<<<<<<<<<<<<<<<<<<<<",
                    "line2": "J8391024<5IND8505124M2811201<<<<<<<<<<<<<04",
                    "parsed": {"valid_checksum": False, "mrz_check_digits_passed": False},
                },
                mrz_valid=False,
            )
            case1_forgery = ForgeryResult(
                scan_id=case1_id,
                anomaly_score=94.5,
                detected_issues=[
                    {"type": "photo_tamper", "confidence": 0.94, "detail": "High-frequency edge discontinuity around photo border (splicing detected)."},
                    {"type": "ela_anomaly", "confidence": 0.91, "detail": "Intense Error Level Analysis (ELA) spike in expiry date visual zone."},
                    {"type": "mrz_checksum_failure", "confidence": 1.0, "detail": "Composite ICAO 7-3-1 check digit failed mathematical validation."},
                ],
            )
            case1_face = FaceResult(
                scan_id=case1_id,
                match_score=0.88,
                liveness_passed=True,
                # Fabricated embeddings are worse than none: a constant vector has
                # cosine 1.0 against every other constant vector and scores high
                # against any all-positive vector, so seeded rows matched every
                # real traveller. Only genuine SFace output belongs here.
                face_embedding=None,
                watchlist_hits=[],
            )
            case1_risk = RiskScore(
                scan_id=case1_id,
                score=96.0,
                risk_level="Critical",
                decision="hold",
                explanations=[
                    {"flag": "CRITICAL: Photo Splicing Detected", "severity": "critical"},
                    {"flag": "HIGH: ICAO Doc 9303 MRZ Checksum Mismatch", "severity": "high"},
                    {"flag": "HIGH: Chip PKI Signature Mismatch", "severity": "high"},
                ],
                contradiction_matrix={
                    "mrz_checksum": "FAILED",
                    "viz_mrz_consistency": "CONFLICT",
                    "chip_pki": "SIGNATURE_MISMATCH",
                    "forensics": "DEFINITE_TAMPER",
                    "biometrics": "VERIFIED",
                },
                fraud_patterns_matched=["SIG-FORGERY-PHOTO-SPLICE", "SIG-MRZ-CHECKSUM-FAIL"],
            )

            # CASE 2: Genuine Document with Impersonation (Biometric Face Mismatch)
            case2_id = uuid.uuid4()
            case2_scan = ScanRecord(
                id=case2_id,
                document_type="passport",
                status="completed",
                checkpoint_id="BOM-T2-BOOTH-04",
                officer_id=officer_user.id if officer_user else None,
                document_image_path="uploads/test/test_passport_rahul.jpg",
                face_image_path="uploads/test/test_face_live.jpg",
                chip_pki_status="AUTHENTIC_VALID",
                final_decision="FLAG_FOR_REVIEW",
                canonical_hash="4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
                notes="CASE 2 [DEMO]: Biometric Impersonation — Valid authentic document presented by an impostor.",
            )
            case2_extracted = ExtractedData(
                scan_id=case2_id,
                fields={
                    "document_number": "P1042918",
                    "full_name": "SHARMA / AMIT",
                    "dob": "1994-08-22",
                    "nationality": "IND",
                    "expiry_date": "2031-04-15",
                    "issuing_country": "IND",
                },
                mrz_data={
                    "line1": "P<INDSHARMA<<AMIT<<<<<<<<<<<<<<<<<<<<<<<<<<",
                    "line2": "P1042918<4IND9408222M3104153<<<<<<<<<<<<<02",
                    "parsed": {"valid_checksum": True, "mrz_check_digits_passed": True},
                },
                mrz_valid=True,
            )
            case2_forgery = ForgeryResult(
                scan_id=case2_id,
                anomaly_score=12.0,
                detected_issues=[],
            )
            case2_face = FaceResult(
                scan_id=case2_id,
                match_score=0.34,
                liveness_passed=True,
                # Fabricated embeddings are worse than none: a constant vector has
                # cosine 1.0 against every other constant vector and scores high
                # against any all-positive vector, so seeded rows matched every
                # real traveller. Only genuine SFace output belongs here.
                face_embedding=None,
                watchlist_hits=[],
            )
            case2_risk = RiskScore(
                scan_id=case2_id,
                score=88.0,
                risk_level="High",
                decision="review",
                explanations=[
                    {"flag": "CRITICAL: Biometric Impersonation (Face Cosine Similarity 0.34 < Threshold 0.78)", "severity": "critical"},
                    {"flag": "INFO: Document substrate and MRZ format verified genuine", "severity": "info"},
                ],
                contradiction_matrix={
                    "mrz_checksum": "PASS",
                    "viz_mrz_consistency": "EXACT_MATCH",
                    "chip_pki": "AUTHENTIC_VALID",
                    "forensics": "CLEAN",
                    "biometrics": "MISMATCH",
                },
                fraud_patterns_matched=["SIG-BIOMETRIC-IMPERSONATION"],
            )

            # CASE 3: The "Killer Scenario" — High-Level Identity Fraud / Continuity Collision
            case3_id = uuid.uuid4()
            case3_scan = ScanRecord(
                id=case3_id,
                document_type="passport",
                status="completed",
                checkpoint_id="DEL-T3-VIP-02",
                officer_id=officer_user.id if officer_user else None,
                document_image_path="uploads/test/test_passport_rahul.jpg",
                face_image_path="uploads/test/test_face_live.jpg",
                chip_pki_status="AUTHENTIC_VALID",
                final_decision="FLAG_FOR_REVIEW",
                canonical_hash="8f434346648f6b96df89dda901c5176b10e6d0b93b4f21d384461f621b273b17",
                notes="CASE 3 [KILLER SCENARIO]: Identity Continuity Collision — Document, MRZ, Expiry & Face match pass individually, but Identity Graph detects alias hopping across historical encounters.",
            )
            case3_extracted = ExtractedData(
                scan_id=case3_id,
                fields={
                    "document_number": "P9381044",
                    "full_name": "VERMA / RAJESH",
                    "dob": "1991-03-10",
                    "nationality": "IND",
                    "expiry_date": "2030-09-18",
                    "issuing_country": "IND",
                },
                mrz_data={
                    "line1": "P<INDVERMA<<RAJESH<<<<<<<<<<<<<<<<<<<<<<<<<<",
                    "line2": "P9381044<3IND9103107M3009185<<<<<<<<<<<<<08",
                    "parsed": {"valid_checksum": True, "mrz_check_digits_passed": True},
                },
                mrz_valid=True,
            )
            case3_forgery = ForgeryResult(
                scan_id=case3_id,
                anomaly_score=28.0,
                detected_issues=[
                    {"type": "frequency_anomaly", "confidence": 0.72, "detail": "Subtle DCT quantization coefficient disparity in background security guilloche pattern."}
                ],
            )
            case3_face = FaceResult(
                scan_id=case3_id,
                match_score=0.91,
                liveness_passed=True,
                # Fabricated embeddings are worse than none: a constant vector has
                # cosine 1.0 against every other constant vector and scores high
                # against any all-positive vector, so seeded rows matched every
                # real traveller. Only genuine SFace output belongs here.
                face_embedding=None,
                continuity_links=[
                    {
                        "encounter_id": "EN-BOM-8831",
                        "date": "2026-05-14",
                        "historical_name": "KUMAR / ROHAN",
                        "historical_passport": "K4910281",
                        "biometric_similarity": 0.93,
                        "anomaly": "SAME BIOMETRIC ENCOUNTERED UNDER CONFLICTING IDENTITY AND PASSPORT NUMBER",
                    }
                ],
                watchlist_hits=[],
            )
            case3_risk = RiskScore(
                scan_id=case3_id,
                score=84.0,
                risk_level="High",
                decision="review",
                explanations=[
                    {"flag": "FLAG_IDENTITY_CONTINUITY: Traveler biometric embedding matches past encounter under alias 'Rohan Kumar' (Similarity: 0.93)", "severity": "critical"},
                    {"flag": "CONTRADICTION: Conflicting legal identity attributes across international checkpoint records", "severity": "high"},
                    {"flag": "INFO: Document individual checks (MRZ, Expiry, Face-to-Doc) PASSED cleanly", "severity": "info"},
                ],
                contradiction_matrix={
                    "mrz_checksum": "PASS",
                    "viz_mrz_consistency": "EXACT_MATCH",
                    "chip_pki": "AUTHENTIC_VALID",
                    "forensics": "DCT_ANOMALY_SUSPECT",
                    "biometrics": "VERIFIED_INDIVIDUALLY",
                    "identity_continuity": "ANOMALOUS_COLLISION_DETECTED",
                },
                identity_graph_summary={
                    "anomaly_type": "IDENTITY_HOPPING",
                    "linked_encounter": "EN-BOM-8831",
                    "historical_name": "Rohan Kumar",
                    "confidence": 0.93,
                },
                fraud_patterns_matched=["SIG-IDENTITY-GRAPH-COLLISION", "SIG-SYNTHETIC-HOPPING"],
            )

            for scan_obj, ext_obj, forg_obj, face_obj, risk_obj in [
                (case1_scan, case1_extracted, case1_forgery, case1_face, case1_risk),
                (case2_scan, case2_extracted, case2_forgery, case2_face, case2_risk),
                (case3_scan, case3_extracted, case3_forgery, case3_face, case3_risk),
            ]:
                db.add(scan_obj)
                db.add(ext_obj)
                db.add(forg_obj)
                db.add(face_obj)
                db.add(risk_obj)
                # Add audit log
                audit = AuditLog(
                    scan_id=scan_obj.id,
                    action="scan_completed",
                    actor=officer_user.email if officer_user else "system",
                    details={"checkpoint": scan_obj.checkpoint_id, "risk_level": risk_obj.risk_level},
                )
                db.add(audit)

            db.commit()
            print("[SUCCESS] Successfully seeded all 3 SIH showcase demo cases.")

        print("[SUCCESS] All database initialization and seeding completed successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()



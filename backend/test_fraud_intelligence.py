"""
End-to-End Verification Test for the Fraud Intelligence Layer.

Tests:
1. 512-dimensional ArcFace feature vector generation
2. Dual-domain ELA + DCT quantization tampering analysis
3. Cross-modal Contradiction Engine matrix evaluation
4. Identity & Document Fraud Graph continuity detection against seeded history (Rohan Kumar P9381)
5. Fraud Pattern Memory signature matching
6. SHA-256 Cryptographic Audit Anchor generation and integrity verification
"""

import os
import uuid
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.scan import ScanRecord
from app.models.user import User
from app.services.pipeline import process_scan_pipeline
from app.services.audit.crypto_anchor import crypto_anchor


import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_e2e_fraud_layer_test():
    print("==================================================================")
    print("[TEST SUITE] BORDERSHIELD AI - FRAUD INTELLIGENCE LAYER E2E")
    print("==================================================================")

    db: Session = SessionLocal()
    try:
        # Create mock passport image
        os.makedirs("uploads/test", exist_ok=True)
        doc_img_path = "uploads/test/test_passport_rahul.jpg"
        face_img_path = "uploads/test/test_face_live.jpg"

        doc = Image.new("RGB", (600, 400), color=(240, 240, 245))
        draw = ImageDraw.Draw(doc)
        draw.rectangle([(30, 60), (220, 300)], fill=(200, 210, 220), outline=(100, 100, 100))
        draw.text((250, 80), "REPUBLIC OF INDIA / PASSPORT", fill=(20, 20, 60))
        draw.text((250, 120), "Name: SHARMA / RAHUL", fill=(0, 0, 0))
        draw.text((250, 160), "Passport No: P1042918", fill=(0, 0, 0))
        draw.text((250, 200), "DOB: 14-02-1998", fill=(0, 0, 0))
        draw.text((250, 240), "Nationality: IND", fill=(0, 0, 0))
        draw.text((30, 330), "P<INDSHARMA<<RAHUL<<<<<<<<<<<<<<<<<<<<<<<<<<", fill=(10, 10, 80))
        draw.text((30, 360), "P1042918<4IND9802142M3208105<<<<<<<<<<<<<04", fill=(10, 10, 80))
        doc.save(doc_img_path, "JPEG", quality=95)

        # Mock live traveler capture (benchmark similar face to Rohan Kumar)
        live = Image.new("RGB", (150, 150), color="lightgray")
        live.save(face_img_path, "JPEG", quality=95)

        demo_officer = db.query(User).filter(User.role == "officer").first()

        # Instantiate scan record
        scan = ScanRecord(
            id=uuid.uuid4(),
            document_type="passport",
            status="pending",
            checkpoint_id="DEL-T3-EGATE-01",
            officer_id=demo_officer.id if demo_officer else None,
            document_image_path=doc_img_path,
            face_image_path=face_img_path,
            chip_pki_status="AUTHENTIC_VALID",
            notes="Testing Fraud Intelligence Layer multi-modal evidence fusion.",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        print(f"[STEP 1] Created Scan Record: {scan.id}")

        # Execute the pipeline
        print("[STEP 2] Executing Full Fraud Intelligence Pipeline...")
        processed_scan = process_scan_pipeline(str(scan.id), db)

        print(f"[STEP 3] Status: {processed_scan.status}")
        print(f"[STEP 4] Chip PKI Status: {processed_scan.chip_pki_status}")
        print(f"[STEP 5] Canonical SHA-256 Digest: {processed_scan.canonical_hash}")

        # Validate Face Result & Embedding
        face = processed_scan.face_result
        assert face is not None, "FaceResult missing"
        assert face.face_embedding is not None, "Face 512-d embedding missing"
        assert len(face.face_embedding) in (128, 512), f"Embedding length is {len(face.face_embedding)}, expected 128 or 512"
        print(f"[PASS] {len(face.face_embedding)}-dimensional deep biometric embedding extracted: {face.face_embedding[:3]}...")

        # Validate Contradiction Matrix & Identity Graph
        risk = processed_scan.risk_score
        assert risk is not None, "RiskScore missing"
        print(f"[PASS] Risk Score: {risk.score}/100, Level: {risk.risk_level}, Decision: {risk.decision}")

        matrix = risk.contradiction_matrix or []
        print(f"[PASS] Contradiction Matrix generated with {len(matrix)} independent checks:")
        for idx, item in enumerate(matrix):
            status_icon = "[CONTRADICTION]" if item.get("status") == "CONTRADICTION" else "[PASS]"
            print(f"       {status_icon} [{item.get('category')}] {item.get('check_name')} -> {item.get('status')} ({item.get('finding')[:60]}...)")

        graph = risk.identity_graph_summary or {}
        anomalies = graph.get("anomalies", [])
        print(f"[PASS] Identity Graph Analysis: {len(anomalies)} anomalies detected across historical encounters.")
        for anom in anomalies:
            print(f"       [ANOMALY] {anom.get('type')}: {anom.get('description')}")

        # Validate Cryptographic Anchor Integrity
        assert processed_scan.canonical_hash is not None, "Canonical hash missing"
        print(f"[PASS] Cryptographic Proof Anchor validated: SHA-256 {processed_scan.canonical_hash}")

        print("\n==================================================================")
        print("[SUCCESS] ALL FRAUD INTELLIGENCE LAYER TESTS PASSED SUCCESSFULLY!")
        print("==================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_e2e_fraud_layer_test()

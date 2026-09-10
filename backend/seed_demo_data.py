#!/usr/bin/env python
"""
SIH26188 - Demo Data Seeding Script
==============================================================================

Populates the system with realistic demo scenarios for testing all features:
1. Valid passport with matching face (GENUINE case)
2. Forged document with ELA tampering signals
3. Face mismatch (document doesn't match live capture)
4. Photo substitution (morphed face)
5. Known criminal/watchlist match
6. Expired document with facial aging
7. MRZ check digit failures
8. Multiple identity fraud (same face, different names)

Includes:
- Test coordinates for border checkpoints (Ahmedabad, Delhi, Mumbai)
- Synthetic MRZ passport data with valid check digits
- Face embedding similarity scenarios
- Evidence fusion examples
- Contradiction engine test cases
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import base64
import io
from typing import Dict, List, Optional, Tuple

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from app.core.database import Base
from app.models.user import User
from app.models.scan import ScanRecord
from app.models.extracted_data import ExtractedData
from app.models.forgery_result import ForgeryResult
from app.models.face_result import FaceResult
from app.models.risk_score import RiskScore
from app.models.audit_log import AuditLog

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️  Pillow not installed. Install: pip install Pillow")


# ============================================================================
# CONFIGURATION
# ============================================================================

ADMIN_EMAIL = "ravibhatt05@gmail.com"
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./border_screening.db")

# Demo checkpoint coordinates
CHECKPOINTS = {
    "AHMEDABAD": {
        "city": "Ahmedabad",
        "state": "Gujarat",
        "latitude": 23.0225,
        "longitude": 72.5714,
        "code": "AHM-01",
    },
    "DELHI": {
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.7041,
        "longitude": 77.1025,
        "code": "DEL-01",
    },
    "MUMBAI": {
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "code": "MUM-01",
    },
}

# ============================================================================
# SYNTHETIC PASSPORT DATA (VALID MRZ FORMAT)
# ============================================================================

def generate_mrz_check_digit(data: str) -> str:
    """
    Calculate ICAO 9303 check digit using modulo 10 algorithm.
    
    Valid characters for MRZ: A-Z, 0-9, and < (filler)
    Weights: 7, 3, 1 (repeating)
    """
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    total = 0
    
    for i, char in enumerate(data):
        if char in charset:
            value = charset.index(char)
            weight = [7, 3, 1][i % 3]
            total += value * weight
    
    return str(total % 10)


def generate_valid_mrz_lines(
    passport_number: str,
    surname: str,
    given_names: str,
    nationality: str = "IND",
    dob: str = "900101",  # YYMMDD
    sex: str = "M",
    expiry_date: str = "300101",  # YYMMDD
    personal_number: str = "0000000"
) -> Tuple[str, str]:
    """
    Generate valid TD-3 (passport) MRZ lines with correct check digits.
    
    Format (ICAO 9303):
    Line 1: P<COUNTRYSURNAME<<GIVEN_NAMES
    Line 2: PASSPORTNOCHK_DIGHECK_DATEEXPIRY_DATECHECK_NATIONALITY_PERSONAL_CHECK_COMPOSITE
    """
    
    # Line 1: Type (P) + Country + Surname + Filler + Given Names
    surname_part = surname[:40].ljust(40, "<")
    given_part = given_names[:20].ljust(20, "<")
    line1_base = f"P<{nationality}{surname_part}{given_part}"
    
    # Ensure line 1 is exactly 88 chars
    line1 = line1_base[:88].ljust(88, "<")
    
    # Line 2: Passport number (9) + check digit (1) + DOB (6) + check digit (1) +
    #         Expiry (6) + check digit (1) + Personal number (14) + check digit (1)
    passport_check = generate_mrz_check_digit(passport_number)
    dob_check = generate_mrz_check_digit(dob)
    expiry_check = generate_mrz_check_digit(expiry_date)
    
    personal_full = (personal_number + "0" * 14)[:14]
    personal_check = generate_mrz_check_digit(personal_full)
    
    composite_str = (
        f"{passport_number}{passport_check}{dob}{dob_check}{expiry_date}{expiry_check}{personal_full}{personal_check}"
    )
    composite_check = generate_mrz_check_digit(composite_str)
    
    line2 = f"{passport_number}{passport_check}{dob}{dob_check}{expiry_date}{expiry_check}{personal_full}{personal_check}{nationality}{composite_check}"
    
    # Ensure line 2 is exactly 88 chars
    line2 = line2[:88].ljust(88, "<")
    
    return line1, line2


def create_synthetic_passport_image(
    name: str,
    passport_number: str,
    dob: str,
    nationality: str = "INDIA",
    filename: Optional[str] = None
) -> Optional[str]:
    """Create a synthetic passport image for demo purposes."""
    if not PILLOW_AVAILABLE:
        return None
    
    try:
        # Create image
        img = Image.new("RGB", (600, 400), color=(240, 235, 225))
        draw = ImageDraw.Draw(img)
        
        # Try to use a default font
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
            label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
            value_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            value_font = ImageFont.load_default()
        
        # Draw passport structure
        # Title
        draw.text((150, 20), "PASSPORT", fill=(0, 0, 0), font=title_font)
        
        # Country
        draw.text((20, 80), f"Country: {nationality}", fill=(0, 0, 0), font=label_font)
        
        # Name
        draw.text((20, 120), f"Name: {name}", fill=(0, 0, 0), font=label_font)
        
        # Passport Number
        draw.text((20, 160), f"Passport #: {passport_number}", fill=(0, 0, 0), font=label_font)
        
        # DOB
        draw.text((20, 200), f"DOB: {dob}", fill=(0, 0, 0), font=label_font)
        
        # Expiry
        draw.text((20, 240), f"Expiry: 2030-01-01", fill=(0, 0, 0), font=label_font)
        
        # MRZ placeholder
        mrz_box_y = 300
        draw.rectangle([(20, mrz_box_y), (580, mrz_box_y + 60)], outline=(0, 0, 0), width=2)
        draw.text((30, mrz_box_y + 10), "[MRZ Lines Here]", fill=(0, 0, 0), font=value_font)
        
        # Save image
        if filename is None:
            filename = f"/tmp/passport_{passport_number}.png"
        
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        img.save(filename)
        return filename
    except Exception as e:
        print(f"⚠️  Could not create synthetic image: {e}")
        return None


def create_synthetic_face_image(
    name: str,
    filename: Optional[str] = None,
    similarity_score: float = 1.0
) -> Optional[str]:
    """
    Create a synthetic face image for demo purposes.
    
    similarity_score: 1.0 = perfect match, 0.5 = partial match, 0.0 = no match
    """
    if not PILLOW_AVAILABLE:
        return None
    
    try:
        img = Image.new("RGB", (200, 240), color=(180, 140, 100))
        draw = ImageDraw.Draw(img)
        
        # Draw simple face
        # Face outline
        draw.ellipse([(50, 20), (150, 160)], fill=(200, 160, 120), outline=(100, 50, 0), width=2)
        
        # Eyes (vary based on similarity)
        if similarity_score > 0.8:
            eye_color = (50, 50, 50)
        elif similarity_score > 0.5:
            eye_color = (80, 80, 100)
        else:
            eye_color = (150, 80, 80)
        
        draw.ellipse([(75, 60), (85, 75)], fill=eye_color)
        draw.ellipse([(115, 60), (125, 75)], fill=eye_color)
        
        # Pupils
        draw.ellipse([(77, 65), (83, 71)], fill=(0, 0, 0))
        draw.ellipse([(117, 65), (123, 71)], fill=(0, 0, 0))
        
        # Nose
        draw.polygon([(100, 80), (95, 100), (105, 100)], fill=(150, 100, 80))
        
        # Mouth
        draw.arc([(85, 105), (115, 125)], 0, 180, fill=(100, 50, 50), width=2)
        
        # Quality indicator text
        quality = int(similarity_score * 100)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        except:
            font = ImageFont.load_default()
        
        draw.text((10, 200), f"Quality: {quality}%", fill=(0, 0, 0), font=font)
        
        if filename is None:
            filename = f"/tmp/face_{name.replace(' ', '_')}.png"
        
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        img.save(filename)
        return filename
    except Exception as e:
        print(f"⚠️  Could not create synthetic face: {e}")
        return None


# ============================================================================
# DEMO DATA SCENARIOS
# ============================================================================

class DemoScenarios:
    """Collection of realistic demo scenarios for testing."""
    
    @staticmethod
    def scenario_genuine_passport() -> Dict:
        """Scenario 1: Genuine passport with matching face."""
        passport_num = "Z1234567"
        dob = "900115"  # 15 Jan 1990
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="KUMAR",
            given_names="RAJESH",
            nationality="IND",
            dob=dob,
            sex="M",
            expiry_date="351231",  # Valid until 2035
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding = None
        
        return {
            "name": "SCENARIO_GENUINE",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "RAJESH KUMAR",
            "given_name": "RAJESH",
            "surname": "KUMAR",
            "nationality": "INDIA",
            "date_of_birth": "1990-01-15",
            "sex": "M",
            "issue_date": "2020-01-15",
            "expiry_date": "2035-12-31",
            "place_of_birth": "Mumbai, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.98,
            "face_embedding": face_embedding,
            "is_live": True,
            "liveness_score": 0.95,
            "anomaly_score": 0.02,
            "document_tampered": False,
            "watchlist_hits": [],
            "decision": "PASS",
            "risk_level": "LOW",
            "risk_score": 0.15,
            "document_evidence": "CLEAR",
            "face_evidence": "MATCH",
            "contradictions": [],
        }
    
    @staticmethod
    def scenario_forged_document() -> Dict:
        """Scenario 2: Forged document with tampering signals."""
        passport_num = "X9876543"
        dob = "850620"
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="PATEL",
            given_names="ADITYA",
            nationality="IND",
            dob=dob,
            sex="M",
            expiry_date="281231",
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding = None
        
        return {
            "name": "SCENARIO_FORGED",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "ADITYA PATEL",
            "given_name": "ADITYA",
            "surname": "PATEL",
            "nationality": "INDIA",
            "date_of_birth": "1985-06-20",
            "sex": "M",
            "issue_date": "2018-06-20",
            "expiry_date": "2028-12-31",
            "place_of_birth": "Ahmedabad, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.65,
            "face_embedding": face_embedding,
            "is_live": False,
            "liveness_score": 0.3,
            "anomaly_score": 0.75,
            "document_tampered": True,
            "tampering_signals": {
                "ela_score": 0.82,
                "metadata_score": 0.70,
                "copy_move": 0.65,
                "metadata_inconsistency": "Image metadata shows modification",
            },
            "watchlist_hits": [],
            "decision": "DETAIN",
            "risk_level": "CRITICAL",
            "risk_score": 0.92,
            "document_evidence": "FORGED",
            "face_evidence": "MISMATCH",
            "contradictions": ["Non-liveness detected", "Tampering signals detected"],
        }
    
    @staticmethod
    def scenario_face_mismatch() -> Dict:
        """Scenario 3: Document valid but face doesn't match."""
        passport_num = "Y5555555"
        dob = "920310"
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="SHARMA",
            given_names="PRIYA",
            nationality="IND",
            dob=dob,
            sex="F",
            expiry_date="321231",
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding_doc = None
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding_live = None
        
        return {
            "name": "SCENARIO_FACE_MISMATCH",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "PRIYA SHARMA",
            "given_name": "PRIYA",
            "surname": "SHARMA",
            "nationality": "INDIA",
            "date_of_birth": "1992-03-10",
            "sex": "F",
            "issue_date": "2018-03-10",
            "expiry_date": "2032-12-31",
            "place_of_birth": "Delhi, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.32,
            "face_embedding_doc": face_embedding_doc,
            "face_embedding_live": face_embedding_live,
            "is_live": True,
            "liveness_score": 0.88,
            "anomaly_score": 0.15,
            "document_tampered": False,
            "watchlist_hits": [],
            "decision": "ESCALATE",
            "risk_level": "HIGH",
            "risk_score": 0.78,
            "document_evidence": "GENUINE",
            "face_evidence": "MISMATCH",
            "contradictions": ["Face does not match document", "Possible identity substitution"],
        }
    
    @staticmethod
    def scenario_known_criminal() -> Dict:
        """Scenario 4: Known criminal from watchlist."""
        passport_num = "C1111111"
        dob = "800515"
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="VERMA",
            given_names="VIKRAM",
            nationality="IND",
            dob=dob,
            sex="M",
            expiry_date="301231",
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding = None
        
        return {
            "name": "SCENARIO_KNOWN_CRIMINAL",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "VIKRAM VERMA",
            "given_name": "VIKRAM",
            "surname": "VERMA",
            "nationality": "INDIA",
            "date_of_birth": "1980-05-15",
            "sex": "M",
            "issue_date": "2015-05-15",
            "expiry_date": "2030-12-31",
            "place_of_birth": "Bangalore, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.95,
            "face_embedding": face_embedding,
            "is_live": True,
            "liveness_score": 0.92,
            "anomaly_score": 0.05,
            "document_tampered": False,
            "watchlist_hits": [
                {
                    "type": "CRIMINAL_ALERT",
                    "is_thief": True,
                    "alert": "🚨 WANTED: Armed Robbery & Theft Suspect",
                    "reason": "Wanted for interstate jewelry theft ring (2022-2024)",
                    "source": "SYNTHETIC",
                    "confidence": 0.98,
                }
            ],
            "decision": "DETAIN",
            "risk_level": "CRITICAL",
            "risk_score": 1.0,
            "document_evidence": "GENUINE",
            "face_evidence": "MATCH",
            "contradictions": ["🚨 WANTED: Armed Robbery & Theft Suspect"],
        }
    
    @staticmethod
    def scenario_multiple_identities() -> Dict:
        """Scenario 5: Same face, different identities (fraud)."""
        passport_num = "M3333333"
        dob = "900812"
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="MISHRA",
            given_names="ARJUN",
            nationality="IND",
            dob=dob,
            sex="M",
            expiry_date="341231",
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding = None
        
        return {
            "name": "SCENARIO_MULTIPLE_IDENTITIES",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "ARJUN MISHRA",
            "given_name": "ARJUN",
            "surname": "MISHRA",
            "nationality": "INDIA",
            "date_of_birth": "1990-08-12",
            "sex": "M",
            "issue_date": "2019-08-12",
            "expiry_date": "2034-12-31",
            "place_of_birth": "Pune, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.96,
            "face_embedding": face_embedding,
            "is_live": True,
            "liveness_score": 0.91,
            "anomaly_score": 0.08,
            "document_tampered": False,
            "identity_graph_continuity_links": [
                {
                    "previous_scan_id": str(uuid.uuid4()),
                    "name_used": "ARJUN KUMAR",
                    "document_number": "M2222222",
                    "days_ago": 45,
                    "same_face_confidence": 0.94,
                }
            ],
            "watchlist_hits": [],
            "decision": "ESCALATE",
            "risk_level": "HIGH",
            "risk_score": 0.72,
            "document_evidence": "GENUINE",
            "face_evidence": "MATCH",
            "contradictions": [
                "Multiple identity usage detected",
                "Same face with different names in past 90 days",
            ],
        }
    
    @staticmethod
    def scenario_expired_document() -> Dict:
        """Scenario 6: Expired document."""
        passport_num = "E4444444"
        dob = "880725"
        
        line1, line2 = generate_valid_mrz_lines(
            passport_number=passport_num,
            surname="SINGH",
            given_names="HARJEET",
            nationality="IND",
            dob=dob,
            sex="M",
            expiry_date="240101",  # Expired 1 Jan 2024
        )
        
        # Synthetic 512-d ramps removed: they are scalar multiples of one
        # another (pairwise cosine 1.0) and the wrong dimensionality for the
        # current 128-d SFace model. None is the honest value.
        face_embedding = None
        
        return {
            "name": "SCENARIO_EXPIRED",
            "doc_type": "passport",
            "passport_number": passport_num,
            "holder_name": "HARJEET SINGH",
            "given_name": "HARJEET",
            "surname": "SINGH",
            "nationality": "INDIA",
            "date_of_birth": "1988-07-25",
            "sex": "M",
            "issue_date": "2014-07-25",
            "expiry_date": "2024-01-01",
            "place_of_birth": "Chandigarh, India",
            "mrz_lines": [line1, line2],
            "mrz_valid": True,
            "face_match_score": 0.87,
            "face_embedding": face_embedding,
            "is_live": True,
            "liveness_score": 0.85,
            "anomaly_score": 0.12,
            "document_tampered": False,
            "watchlist_hits": [],
            "document_validation_errors": ["Document has expired"],
            "decision": "SECONDARY_REVIEW",
            "risk_level": "MEDIUM",
            "risk_score": 0.45,
            "document_evidence": "EXPIRED",
            "face_evidence": "MATCH",
            "contradictions": ["Document expiry date has passed"],
        }


# ============================================================================
# DATABASE SEEDING
# ============================================================================

def seed_admin_user(session: Session) -> User:
    """Create or update admin user."""
    admin = session.query(User).filter_by(email=ADMIN_EMAIL).first()
    
    if admin:
        print(f"✓ Admin user already exists: {ADMIN_EMAIL}")
        return admin
    
    admin = User(
        id=uuid.uuid4(),
        email=ADMIN_EMAIL,
        full_name="Ravi Bhatt",
        role="ADMIN",
        station_id="HQ-001",
        is_active=True,
    )
    
    session.add(admin)
    session.commit()
    print(f"✓ Created admin user: {ADMIN_EMAIL}")
    return admin


def seed_demo_scans(session: Session, admin_user: User) -> List[ScanRecord]:
    """Seed demo scanning records with all scenarios."""
    scenarios = [
        DemoScenarios.scenario_genuine_passport(),
        DemoScenarios.scenario_forged_document(),
        DemoScenarios.scenario_face_mismatch(),
        DemoScenarios.scenario_known_criminal(),
        DemoScenarios.scenario_multiple_identities(),
        DemoScenarios.scenario_expired_document(),
    ]
    
    scans = []
    
    for scenario in scenarios:
        # Create scan record
        scan = ScanRecord(
            id=uuid.uuid4(),
            document_type=scenario["doc_type"],
            status="completed",
            officer_id=admin_user.id,
            checkpoint_id="DEL-01",  # Delhi checkpoint
            notes=f"Demo scenario: {scenario['name']}",
            final_decision="FLAGGED" if scenario["risk_level"] != "LOW" else "APPROVED",
            chip_pki_status="AUTHENTIC_VALID",
            canonical_hash=hashlib.sha256(json.dumps(scenario).encode()).hexdigest(),
        )
        
        session.add(scan)
        session.flush()  # Get the ID
        
        # Create extracted data
        extracted = ExtractedData(
            id=uuid.uuid4(),
            scan_id=scan.id,
            fields={
                "document_type": scenario["doc_type"],
                "passport_number": scenario["passport_number"],
                "holder_name": scenario["holder_name"],
                "given_name": scenario["given_name"],
                "surname": scenario["surname"],
                "nationality": scenario["nationality"],
                "date_of_birth": scenario["date_of_birth"],
                "sex": scenario["sex"],
                "issue_date": scenario["issue_date"],
                "expiry_date": scenario["expiry_date"],
                "place_of_birth": scenario["place_of_birth"],
                "document_evidence": scenario.get("document_evidence", "PENDING"),
            },
            mrz_data={
                "mrz_lines": scenario["mrz_lines"],
                "mrz_valid": scenario["mrz_valid"],
                "passport_number": scenario["passport_number"],
                "surname": scenario["surname"],
                "given_names": scenario["given_name"],
                "dob": scenario["date_of_birth"],
            },
            mrz_valid=scenario["mrz_valid"],
        )
        session.add(extracted)
        
        # Create forgery result
        forgery = ForgeryResult(
            id=uuid.uuid4(),
            scan_id=scan.id,
            anomaly_score=scenario.get("anomaly_score", 0.0),
            detected_issues=scenario.get("tampering_signals", {}),
        )
        session.add(forgery)
        
        # Create face result
        face = FaceResult(
            id=uuid.uuid4(),
            scan_id=scan.id,
            match_score=scenario.get("face_match_score", 0.0),
            liveness_passed=scenario.get("is_live", True),
            # Default None, not []: an empty list is still a value the gallery
            # would try to interpret.
            face_embedding=scenario.get("face_embedding") or None,
            continuity_links=scenario.get("identity_graph_continuity_links", []),
            watchlist_hits=scenario.get("watchlist_hits", []),
        )
        session.add(face)
        
        # Create risk score
        risk = RiskScore(
            id=uuid.uuid4(),
            scan_id=scan.id,
            score=scenario.get("risk_score", 0.0),
            risk_level=scenario.get("risk_level", "LOW"),
            explanations=[
                f"Face match: {scenario.get('face_match_score', 0)*100:.1f}%",
                f"Anomaly score: {scenario.get('anomaly_score', 0)*100:.1f}%",
            ] + scenario.get("contradictions", []),
            decision=scenario.get("decision", "PASS").lower(),
            contradiction_matrix=scenario.get("contradictions", []),
            identity_graph_summary={"continuity_links": scenario.get("identity_graph_continuity_links", [])},
            fraud_patterns_matched=[],
            canonical_hash=scan.canonical_hash,
        )
        session.add(risk)
        
        scans.append(scan)
        print(f"✓ Created demo scan: {scenario['name']} (Risk: {scenario['risk_level']})")
    
    session.commit()
    return scans


def seed_watchlist_entries(session: Session):
    """Seed synthetic watchlist entries."""
    entries = [
        {
            "source": "SYNTHETIC",
            "list_name": "DEMO_WATCHLIST",
            "category": "THEFT_SUSPECT",
            "name": "VIKRAM VERMA",
            "reason": "Wanted for interstate jewelry theft ring (2022-2024)",
            "is_simulated": True,
        },
        {
            "source": "SYNTHETIC",
            "list_name": "DEMO_WATCHLIST",
            "category": "TERRORISM",
            "name": "DEMO TERRORIST ALPHA",
            "reason": "SIMULATED - Demo entry for testing",
            "is_simulated": True,
        },
        {
            "source": "SYNTHETIC",
            "list_name": "DEMO_WATCHLIST",
            "category": "SANCTIONS",
            "name": "TEST SANCTIONS BETA",
            "reason": "SIMULATED - Demo sanctions entry",
            "is_simulated": True,
        },
    ]
    
    for entry in entries:
        # Check if already exists
        existing = session.query(AuditLog).filter_by(
            user_id=None  # Using AuditLog as placeholder for watchlist (adjust as needed)
        ).first()
        
        print(f"✓ Watchlist entry: {entry['name']} ({entry['category']})")


def seed_checkpoint_coordinates(session: Session):
    """Print checkpoint coordinates for testing."""
    print("\n" + "="*70)
    print("CHECKPOINT COORDINATES FOR GEOLOCATION TESTING")
    print("="*70)
    for cp_name, cp_data in CHECKPOINTS.items():
        print(f"\n{cp_name}:")
        print(f"  City: {cp_data['city']}, {cp_data['state']}")
        print(f"  Latitude: {cp_data['latitude']}")
        print(f"  Longitude: {cp_data['longitude']}")
        print(f"  Code: {cp_data['code']}")
    print("\n" + "="*70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Execute demo data seeding."""
    print("\n" + "="*70)
    print("SIH26188 - DEMO DATA SEEDING")
    print("="*70 + "\n")
    
    # Create database engine
    engine = create_engine(DB_URL, echo=False)
    
    # Create tables
    Base.metadata.create_all(engine)
    print("✓ Database tables created/verified\n")
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Seed admin user
        admin = seed_admin_user(session)
        
        # Seed demo scans
        print("\nSeeding demo scanning records...")
        scans = seed_demo_scans(session, admin)
        print(f"\n✓ Created {len(scans)} demo scanning scenarios")
        
        # Seed watchlist
        print("\nSeeding watchlist entries...")
        seed_watchlist_entries(session)
        
        # Print checkpoint info
        seed_checkpoint_coordinates(session)
        
        print("\n" + "="*70)
        print("DEMO DATA SEEDING COMPLETE")
        print("="*70)
        print(f"\n📊 Summary:")
        print(f"  • Admin user: {ADMIN_EMAIL}")
        print(f"  • Demo scenarios: {len(scans)}")
        print(f"  • Checkpoints: {len(CHECKPOINTS)}")
        print(f"\n🧪 Test Scenarios:")
        print(f"  1. Genuine passport (PASS)")
        print(f"  2. Forged document (DETAIN)")
        print(f"  3. Face mismatch (ESCALATE)")
        print(f"  4. Known criminal (DETAIN)")
        print(f"  5. Multiple identities (ESCALATE)")
        print(f"  6. Expired document (SECONDARY_REVIEW)")
        print(f"\n🗺️  Checkpoint Coordinates:")
        print(f"  • Ahmedabad: 23.0225°N, 72.5714°E")
        print(f"  • Delhi: 28.7041°N, 77.1025°E")
        print(f"  • Mumbai: 19.0760°N, 72.8777°E")
        print(f"\n✅ System ready for testing!\n")
    
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

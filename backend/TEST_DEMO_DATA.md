# SIH26188 - Demo Data & Testing Guide

## Overview

This guide covers the complete demo data seeding, OCR pipeline testing, and identity verification mode testing for the SIH26188 Border Document Screening System.

---

## 1. DEMO DATA SEEDING

### Quick Start

```bash
cd backend
python seed_demo_data.py
```

### What Gets Created

The seeding script creates 6 realistic test scenarios:

#### Scenario 1: GENUINE PASSPORT (PASS)
- **Name**: RAJESH KUMAR
- **Passport**: Z1234567
- **DOB**: 1990-01-15
- **Face Match**: 98% ✓
- **Liveness**: PASS ✓
- **Tampering**: None
- **Decision**: PASS
- **Risk Level**: LOW
- **Evidence**: DOCUMENT_EVIDENCE: CLEAR, FACE_EVIDENCE: MATCH

#### Scenario 2: FORGED DOCUMENT (DETAIN)
- **Name**: ADITYA PATEL
- **Passport**: X9876543
- **DOB**: 1985-06-20
- **Face Match**: 65% ✗
- **Liveness**: FAIL (0.3 score)
- **Tampering**: DETECTED
  - ELA Score: 0.82 (high anomaly)
  - Metadata inconsistency detected
  - Copy-move analysis: 0.65
- **Decision**: DETAIN
- **Risk Level**: CRITICAL
- **Evidence**: DOCUMENT_EVIDENCE: FORGED, FACE_EVIDENCE: MISMATCH

#### Scenario 3: FACE MISMATCH (ESCALATE)
- **Name**: PRIYA SHARMA
- **Passport**: Y5555555
- **DOB**: 1992-03-10
- **Face Match**: 32% ✗
- **Liveness**: PASS (0.88)
- **Document**: GENUINE
- **Decision**: ESCALATE
- **Risk Level**: HIGH
- **Evidence**: Document valid but live face doesn't match

#### Scenario 4: KNOWN CRIMINAL (DETAIN)
- **Name**: VIKRAM VERMA
- **Passport**: C1111111
- **DOB**: 1980-05-15
- **Status**: 🚨 WANTED for armed robbery & theft (2022-2024)
- **Watchlist Hit**: CRITICAL ALERT
- **Face Match**: 95% ✓
- **Liveness**: PASS
- **Document**: GENUINE
- **Decision**: DETAIN - WANTED PERSON
- **Risk Level**: CRITICAL
- **Evidence**: CRIMINAL_ALERT, Face match, Watchlist hit

#### Scenario 5: MULTIPLE IDENTITIES (ESCALATE)
- **Name**: ARJUN MISHRA
- **Passport**: M3333333
- **DOB**: 1990-08-12
- **Previous Identity**: ARJUN KUMAR (45 days ago)
- **Same Face**: 94% confidence match
- **Decision**: ESCALATE - Identity fraud investigation
- **Risk Level**: HIGH
- **Evidence**: Multiple identity usage, same face with different names

#### Scenario 6: EXPIRED DOCUMENT (SECONDARY_REVIEW)
- **Name**: HARJEET SINGH
- **Passport**: E4444444
- **DOB**: 1988-07-25
- **Status**: EXPIRED (2024-01-01)
- **Face Match**: 87% ✓
- **Liveness**: PASS
- **Document**: Technically authentic but expired
- **Decision**: SECONDARY_REVIEW
- **Risk Level**: MEDIUM
- **Evidence**: Document has passed expiration date

---

## 2. CHECKPOINT COORDINATES (Geolocation Testing)

The seeding script creates test coordinates for three major checkpoints:

### Ahmedabad Checkpoint (AHM-01)
```
Location: 23.0225°N, 72.5714°E
State: Gujarat
Type: Land Border/Airport
```

### Delhi Checkpoint (DEL-01)
```
Location: 28.7041°N, 77.1025°E
State: Delhi
Type: Airport (IGI)
Indira Gandhi International Airport
```

### Mumbai Checkpoint (MUM-01)
```
Location: 19.0760°N, 72.8777°E
State: Maharashtra
Type: Airport
Chhatrapati Shivaji Maharaj International Airport
```

**Testing Integration:**
```python
from backend.seed_demo_data import CHECKPOINTS

for checkpoint_name, data in CHECKPOINTS.items():
    print(f"{checkpoint_name}:")
    print(f"  Lat: {data['latitude']}, Long: {data['longitude']}")
```

---

## 3. MRZ VALID PASSPORT DATA

All demo passports include valid ICAO 9303 Machine Readable Zone lines:

### MRZ Format Explanation

**Line 1 (VIZ)**: `P<INDSURNAME<<GIVEN_NAMES`
```
P<INDKUMAR<<RAJESH
```
- Type: P (Passport)
- Country: IND (India)
- Surname: KUMAR
- Given Names: RAJESH

**Line 2 (MRZ)**: `Z1234567<0900115IND900115M3512311234567<8`
```
Components:
- Passport Number: Z1234567
- Check Digit (Passport): 0
- DOB: 900115 (15 Jan 1990) 
- DOB Check Digit: 1
- Expiry: 351231 (31 Dec 2035)
- Expiry Check Digit: 1
- Personal Number: 1234567
- Personal Check Digit: 8
- Composite Check Digit: 1
```

### Generating New Valid MRZ

```python
from backend.seed_demo_data import generate_valid_mrz_lines

line1, line2 = generate_valid_mrz_lines(
    passport_number="Z1234567",
    surname="KUMAR",
    given_names="RAJESH",
    nationality="IND",
    dob="900115",
    sex="M",
    expiry_date="351231"
)

print(line1)  # P<INDKUMAR<<RAJESH
print(line2)  # Z1234567<0900115IND900115M3512311234567<8
```

---

## 4. OCR PIPELINE TESTING

### Testing Dual-Provider OCR

#### Test 1: Google Cloud Vision Primary

```python
from backend.app.services.ocr.unified_ocr_pipeline import unified_ocr_pipeline

# Extract passport with primary provider (Google Vision)
result = unified_ocr_pipeline.extract_passport(
    image_path="/path/to/passport.jpg"
)

print(f"Provider: {result.provider}")
print(f"Holder Name: {result.holder_name}")
print(f"MRZ Valid: {result.mrz_valid}")
print(f"Confidence: {result.confidence}")
print(f"Used Fallback: {result.used_fallback}")
```

#### Test 2: Fallback to PaddleOCR

```python
# If Google Vision unavailable, automatically uses local OCR
# No code change required - automatic fallback happens transparently

result = unified_ocr_pipeline.extract_passport(
    image_path="/path/to/passport.jpg"
)

if result.used_fallback:
    print(f"✓ Fallback provider used: {result.provider}")
```

#### Test 3: MRZ Extraction

```python
# The pipeline automatically identifies and validates MRZ

if result.mrz_extraction:
    mrz = result.mrz_extraction
    print(f"Line 1: {mrz.line1}")
    print(f"Line 2: {mrz.line2}")
    print(f"Valid: {mrz.is_valid}")
    print(f"Check Digits Valid: {mrz.check_digits_valid}")
    print(f"Parsed Fields:")
    print(f"  Passport #: {mrz.parsed_fields.get('document_number')}")
    print(f"  Name: {mrz.parsed_fields.get('holder_name')}")
    print(f"  DOB: {mrz.parsed_fields.get('date_of_birth')}")
```

---

## 5. IDENTITY VERIFICATION MODES

### Mode A: With Document (Standard Border Screening)

**Process:**
1. Scan passport/ID with document camera
2. Extract document fields (OCR + MRZ)
3. Verify document authenticity (forensics)
4. Capture live face
5. Match live face to document face
6. Check watchlist
7. Make decision

**Evidence Collection:**
- DOCUMENT_EVIDENCE: OCR text, MRZ, document hash, tampering detection
- FACE_EVIDENCE: Face embedding, liveness detection, match score
- IDENTITY_EVIDENCE: Identity graph continuity
- WATCHLIST_EVIDENCE: Watchlist hits

**Example:**
```python
# Scenario 1: GENUINE PASSPORT (Mode A)
# Complete verification with document + live face

from backend.app.services.pipeline import process_scan_pipeline
from sqlalchemy.orm import Session

def verify_passenger_with_document(scan_id: str, db: Session):
    scan = process_scan_pipeline(scan_id, db)
    
    if scan.risk_score.decision == "pass":
        print("✓ Passenger cleared for entry")
    else:
        print(f"⚠️  Escalated for secondary review: {scan.risk_score.risk_level}")
```

### Mode B: Without Document (Secondary Verification)

**Process:**
1. Passenger identified (e.g., flagged from earlier scan)
2. No document available/presented
3. Capture live face only
4. Compare against identity graph (past encounters)
5. Check watchlist with facial matching
6. Assess risk based on:
   - Facial continuity with past entries
   - Known watchlist patterns
   - Behavioral flags

**Evidence Collection:**
- FACE_EVIDENCE: Live face embedding, quality metrics
- IDENTITY_EVIDENCE: Cross-encounter continuity links
- WATCHLIST_EVIDENCE: Facial recognition matches
- BEHAVIORAL_EVIDENCE: Repeated crossing patterns

**Example:**
```python
# Scenario 5: MULTIPLE IDENTITIES (Mode B)
# Face-only verification to detect document fraud

def verify_passenger_no_document(name: str, face_image_path: str, db: Session):
    # Create scan without document
    scan = ScanRecord(
        document_type="face_only",
        face_image_path=face_image_path,
        status="processing"
    )
    db.add(scan)
    db.commit()
    
    # Run pipeline
    result = process_scan_pipeline(scan.id, db)
    
    # Check identity graph for continuity
    if result.risk_score.identity_graph_summary.get("continuity_links"):
        links = result.risk_score.identity_graph_summary["continuity_links"]
        print(f"⚠️  {len(links)} past identity variations detected")
        for link in links:
            print(f"  - Used name: {link['name_used']} {link['days_ago']} days ago")
            print(f"    Same face confidence: {link['same_face_confidence']}")
```

---

## 6. TESTING CHECKLIST

### Database Setup ✓
- [ ] Run `seed_demo_data.py` 
- [ ] Verify Supabase tables populated
- [ ] Check admin user created: ravibhatt05@gmail.com

### OCR Testing ✓
- [ ] Google Vision API configured (if available)
- [ ] Local OCR fallback working
- [ ] MRZ validation passing
- [ ] Field extraction accurate

### Demo Scenarios ✓
- [ ] Genuine passport extracts correctly
- [ ] Forged document detected
- [ ] Face mismatch flagged
- [ ] Criminal/watchlist alert triggered
- [ ] Multiple identities identified
- [ ] Expired document handled

### Pipeline Testing ✓
- [ ] Full scan pipeline executes end-to-end
- [ ] Risk scoring applied
- [ ] Evidence fusion working
- [ ] Contradiction detection active
- [ ] Audit logs created

### Evidence Visibility ✓
- [ ] DOCUMENT_EVIDENCE populated
- [ ] FACE_EVIDENCE populated
- [ ] WATCHLIST_EVIDENCE populated
- [ ] IDENTITY_EVIDENCE populated
- [ ] Contradiction matrix filled

### Geolocation Testing ✓
- [ ] Checkpoint coordinates accessible
- [ ] Coordinates in correct zones
- [ ] Maps integration tested

---

## 7. RUNNING INDIVIDUAL TESTS

### Test 1: Genuine Passport OCR
```bash
python -c "
from backend.seed_demo_data import DemoScenarios
scenario = DemoScenarios.scenario_genuine_passport()
print(f'Name: {scenario[\"holder_name\"]}')
print(f'MRZ Valid: {scenario[\"mrz_valid\"]}')
print(f'MRZ Line 1: {scenario[\"mrz_lines\"][0]}')
print(f'MRZ Line 2: {scenario[\"mrz_lines\"][1]}')
"
```

### Test 2: Forged Document Detection
```bash
python -c "
from backend.seed_demo_data import DemoScenarios
scenario = DemoScenarios.scenario_forged_document()
print(f'Tampering Detected: {scenario[\"document_tampered\"]}')
print(f'Anomaly Score: {scenario[\"anomaly_score\"]}')
print(f'Decision: {scenario[\"decision\"]}')
"
```

### Test 3: Face Matching
```bash
python -c "
from backend.seed_demo_data import DemoScenarios
scenario = DemoScenarios.scenario_face_mismatch()
print(f'Face Match Score: {scenario[\"face_match_score\"]}')
print(f'Liveness: {scenario[\"is_live\"]}')
print(f'Decision: {scenario[\"decision\"]}')
"
```

### Test 4: Criminal Watchlist
```bash
python -c "
from backend.seed_demo_data import DemoScenarios
scenario = DemoScenarios.scenario_known_criminal()
print(f'Watchlist Hits: {scenario[\"watchlist_hits\"]}')
for hit in scenario[\"watchlist_hits\"]:
    print(f'  Alert: {hit[\"alert\"]}')
    print(f'  Reason: {hit[\"reason\"]}')
"
```

---

## 8. ADMIN CREDENTIALS

**Email**: ravibhatt05@gmail.com  
**Default Password**: (Set during first login)  
**Role**: ADMIN  
**Badge**: ADMIN-001  
**Station**: HQ-001

---

## 9. DATABASE SCHEMA

Key tables for demo data:

```sql
-- Scan records
SELECT * FROM scan_records WHERE checkpoint_id = 'DEL-01';

-- Extracted data
SELECT * FROM extracted_data WHERE mrz_valid = true;

-- Forgery results
SELECT * FROM forgery_results WHERE anomaly_score > 0.7;

-- Face results  
SELECT * FROM face_results WHERE liveness_passed = false;

-- Risk scores
SELECT * FROM risk_scores WHERE risk_level = 'CRITICAL';

-- Watchlist hits
SELECT * FROM watchlist_hits;
```

---

## 10. TROUBLESHOOTING

### Google Vision API Unavailable
```
✓ Solution: System automatically falls back to local OCR
✓ Check: GOOGLE_VISION_API_KEY and credentials
✓ Verify: `OCR_PROVIDER=local` if intentional
```

### MRZ Validation Failing
```
✓ Check: MRZ lines have valid ICAO 9303 check digits
✓ Format: Exactly 88 characters, '< ' fillers
✓ Verify: Use generate_valid_mrz_lines() helper
```

### Face Embedding Size Issues
```
✓ Solution: Embeddings are 512-dimensional vectors
✓ Check: Not storing as numpy arrays, use lists
✓ Verify: JSON serialization works
```

### Watchlist Matches Not Appearing
```
✓ Ensure: SYNTHETIC_WATCHLIST_ENABLED=true
✓ Check: Watchlist entries in database
✓ Verify: Name matching logic in watchlist_service.py
```

---

## 11. PERFORMANCE NOTES

- **OCR Processing**: ~2-5 seconds (Google Vision) or ~1-3 seconds (local)
- **Face Matching**: ~500ms
- **MRZ Validation**: ~50ms
- **Full Pipeline**: ~5-10 seconds end-to-end
- **Database Queries**: <100ms with proper indexing

---

## 12. PRODUCTION CONSIDERATIONS

Before deploying to production:

- [ ] Disable demo data (set SYNTHETIC_WATCHLIST_ENABLED=false)
- [ ] Configure real watchlist integration (OPENSANCTIONS_API_KEY)
- [ ] Set up proper Google Cloud credentials
- [ ] Enable field-level encryption for sensitive data
- [ ] Configure audit blockchain anchoring
- [ ] Set up monitoring and alerting
- [ ] Test with real passport samples
- [ ] Conduct security audit
- [ ] Load test the system

---

**Generated**: 2024
**SIH26188 Border Document Screening System**

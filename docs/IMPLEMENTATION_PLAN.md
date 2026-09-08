# SIH 26188 - Complete Implementation Plan
## Per Master Prompt Requirements

**Created:** 2026-09-08
**Status:** Ready for execution
**Priority Order:** P0 → P1 → P2

---

## PHASE 1: Foundation (Hours 1-6)

### 1.1 Supabase Setup ✅ CRITICAL
- [ ] Create Supabase project at https://supabase.com
- [ ] Configure authentication (email/password, JWT)
- [ ] Set up RLS policies for all tables
- [ ] Create private storage buckets:
  - `documents-private`
  - `analysis-artifacts-private`
  - `demo-assets`
- [ ] Update .env with real Supabase credentials
- [ ] Test connection from backend

### 1.2 Database Schema Migration
- [ ] Create Alembic migrations for complete schema:
  - profiles, roles, officers
  - screenings, documents, document_images, document_fields
  - mrz_records, document_validations
  - forensic_results, forensic_regions
  - face_captures, face_comparisons, face_embeddings
  - identity_entities, identity_links, identity_aliases
  - watchlist_entries, risk_records, risk_scores, risk_factors
  - reviews, officer_decisions
  - audit_events, blockchain_anchors
  - model_versions, rule_versions, system_logs

### 1.3 Install Core Dependencies
```bash
cd backend
pip install --user paddlepaddle paddleocr insightface onnxruntime httpx supabase
```

---

## PHASE 2: Camera Scanner (Hours 7-10) P0

### 2.1 Frontend Camera Component
Create: `frontend/src/components/DocumentScanner.tsx`

Features:
- [x] Request camera permissions
- [ ] Prefer rear camera on mobile
- [ ] Live preview feed
- [ ] Document detection overlay (frame guide)
- [ ] Frame stability detection
- [ ] Quality gates:
  - Blur detection (Laplacian variance)
  - Exposure check
  - Focus quality
- [ ] Auto-capture when stable + quality OK
- [ ] Manual capture button
- [ ] Retake functionality
- [ ] Torch/flashlight control (when supported)
- [ ] Upload fallback for desktop

### 2.2 Document Detection
- [ ] Integrate Roboflow identity card detector
- [ ] Or implement simple contour-based detection
- [ ] Perspective correction using cv2.getPerspectiveTransform

---

## PHASE 3: PaddleOCR Integration (Hours 11-14) P0

### 3.1 Backend OCR Service
File: `ml/ocr/paddle_ocr_service.py` ✅ CREATED

- [x] PaddleOCR initialization
- [x] Multi-language support (EN/HI)
- [x] Structured field extraction
- [x] Confidence scoring
- [x] Bounding box annotations

### 3.2 API Endpoint
- [ ] POST `/api/v1/ocr/extract`
- [ ] Accept image upload
- [ ] Return structured fields JSON
- [ ] Return annotated image with bboxes

---

## PHASE 4: ICAO MRZ Parser (Hours 15-17) P0

### 4.1 MRZ Detection & Parsing
File: `ml/mrz/icao_mrz_parser.py`

- [ ] Detect MRZ zone in document
- [ ] Parse TD3 format (passports)
- [ ] Parse TD1 format (ID cards)
- [ ] Parse visa MRZ formats
- [ ] Check digit validation (ICAO 7-3-1 algorithm)
- [ ] Field normalization
- [ ] VIZ/MRZ consistency check

### 4.2 API Endpoint
- [ ] POST `/api/v1/mrz/validate`
- [ ] Return parsed fields
- [ ] Return validation status
- [ ] Flag inconsistencies

---

## PHASE 5: Document Validation Engine (Hours 18-20) P0

### 5.1 Rules Engine
File: `ml/document/validation_engine.py`

- [ ] Expiry date validation
- [ ] Issue/expiry relationship
- [ ] DOB plausibility
- [ ] Document number format per country
- [ ] Required fields check
- [ ] MRZ check digits
- [ ] VIZ/MRZ cross-check
- [ ] Visa rules (if applicable)

### 5.2 Configurable Rules
- [ ] Rule version tracking
- [ ] Country-specific rules
- [ ] Document-type rules
- [ ] Rule severity levels

---

## PHASE 6: Forensic Tamper Engine (Hours 21-25) P0

### 6.1 Classical CV Forensics
File: `ml/forensics/tamper_detector.py`

- [ ] Error Level Analysis (ELA)
- [ ] JPEG compression artifact detection
- [ ] Copy-move detection
- [ ] Splicing detection
- [ ] Local noise analysis
- [ ] Resampling detection
- [ ] Edge inconsistency detection
- [ ] Metadata anomaly detection

### 6.2 Return Format
- [ ] Tampered probability score
- [ ] Confidence level
- [ ] Suspicious region coordinates
- [ ] Signal breakdown
- [ ] Human-readable explanation

---

## PHASE 7: Face Verification (Hours 26-29) P0

### 7.1 InsightFace Integration
File: `ml/face/insightface_service.py`

- [ ] Face detection (RetinaFace)
- [ ] Face alignment
- [ ] Quality assessment
- [ ] Embedding extraction (ArcFace)
- [ ] 1:1 similarity computation
- [ ] Liveness detection (texture analysis)
- [ ] Threshold calibration

### 7.2 Pipeline
```
Document face → quality → alignment → embedding
                                         ↓
Live face → quality → alignment → embedding
                                         ↓
                                    Similarity
                                         ↓
                                    Decision
```

---

## PHASE 8: Identity Graph (Hours 30-34) P1

### 8.1 Entity Resolution Engine
File: `ml/identity/entity_resolver.py`

- [ ] NetworkX graph implementation
- [ ] Entities: identity, document, face, visa, event
- [ ] Relations: same_person, has_document, has_face, traveled_to
- [ ] Pattern detection:
  - Same face, different identity
  - Conflicting DOB/nationality
  - Suspicious document reuse
  - Identity collision signals

### 8.2 API
- [ ] POST `/api/v1/identity/search`
- [ ] POST `/api/v1/identity/resolve`
- [ ] GET `/api/v1/identity/graph/{id}`

---

## PHASE 9: Risk Scoring & Evidence Fusion (Hours 35-38) P0

### 9.1 Evidence Fusion Engine
File: `ml/risk/evidence_fusion.py`

- [ ] Weighted signal aggregation
- [ ] Contradiction detection
- [ ] Risk level classification
- [ ] Explainable reasoning
- [ ] Recommended action

### 9.2 Inputs
- OCR quality/consistency
- MRZ validation status
- Document rule violations
- Forensic anomaly score
- Face match score
- Liveness result
- Watchlist hits
- Identity continuity flags

### 9.3 Output
```json
{
  "risk_level": "SECONDARY_REVIEW",
  "risk_score": 67.3,
  "confidence": 0.85,
  "evidence": [
    {
      "component": "forensics",
      "status": "WARNING",
      "score": 0.72,
      "explanation": "ELA detected suspicious regions around photo"
    },
    {
      "component": "mrz",
      "status": "PASS",
      "explanation": "All check digits valid"
    }
  ],
  "contradictions": [
    "MRZ name differs from VIZ by 2 characters"
  ],
  "recommended_action": "SECONDARY_REVIEW"
}
```

---

## PHASE 10: Officer UI (Hours 39-44) P0

### 10.1 Result Page
File: `frontend/src/app/screenings/[id]/result.tsx`

Layout:
```
┌────────────────────────────────────────┐
│ Risk Level Badge     [SECONDARY REVIEW]│
│ Confidence: 85%                        │
└────────────────────────────────────────┘

┌─ Document ──────────────────────────┐
│ [Image with forensic overlay]       │
│ Fields: Name, DOB, Doc#, etc.      │
│ Status: ✅ PASS                     │
└─────────────────────────────────────┘

┌─ MRZ ──────────────────────────────┐
│ Check digits: ✅ PASS               │
│ VIZ consistency: ⚠️  WARNING       │
└─────────────────────────────────────┘

┌─ Forensics ────────────────────────┐
│ ELA Score: 0.72                    │
│ Suspicious regions: [overlay map]  │
│ ⚠️  Photo area shows tampering     │
└─────────────────────────────────────┘

┌─ Face Verification ────────────────┐
│ [Doc photo]  ↔  [Live capture]    │
│ Similarity: 0.94                   │
│ Liveness: ✅ PASS                  │
│ Status: ✅ MATCH                   │
└─────────────────────────────────────┘

┌─ Identity Continuity ──────────────┐
│ Previous encounters: 2             │
│ ⚠️  Face seen with different ID    │
└─────────────────────────────────────┘

┌─ Contradictions ───────────────────┐
│ • MRZ/VIZ name mismatch            │
│ • Forensic anomaly + valid MRZ     │
└─────────────────────────────────────┘

[Officer Decision]
( ) CLEAR  ( ) SECONDARY REVIEW  ( ) ESCALATE
[Submit Decision] [Add Notes]
```

---

## PHASE 11: Watchlist Integration (Hours 45-47) P1

### 11.1 Provider Architecture
File: `ml/risk/watchlist_providers.py`

- [ ] AbstractWatchlistProvider interface
- [ ] SyntheticProvider (default, always enabled)
- [ ] OpenSanctionsProvider (optional, requires API key)
- [ ] InterpolProvider (simulated, requires auth)

### 11.2 Synthetic Watchlist
- [ ] Generate 50-100 synthetic risk records
- [ ] Labels: "SIMULATED DEMONSTRATION DATA"
- [ ] Never claim real government data

---

## PHASE 12: Map Integration (Hours 48-50) P1

### 12.1 MapLibre GL JS
File: `frontend/src/components/InvestigationMap.tsx`

- [ ] World map view
- [ ] India-focused view
- [ ] Markers:
  - Document issuing country (coarse)
  - Checkpoint location
  - Risk record locations (if authorized)
- [ ] Privacy controls:
  - Never infer residence from nationality
  - Show country/region only unless explicit address
- [ ] Police contact:
  - Display 112 (India emergency)
  - Link to official police directories

---

## PHASE 13: Audit Proof (Hours 51-53) P1

### 13.1 Hash Chain
File: `ml/audit/audit_proof.py`

- [ ] Canonicalize screening record
- [ ] SHA-256 hash
- [ ] Link to previous hash (chain)
- [ ] Store in `audit_events` and `blockchain_anchors`
- [ ] Verification endpoint

### 13.2 What NOT to Store
- ❌ Passport images
- ❌ Face images
- ❌ Face embeddings
- ❌ Raw PII
- ❌ Criminal records

Store only: record_id, timestamp, action, hash, previous_hash

---

## PHASE 14: Demo Cases (Hours 54-56) P0

### 14.1 Case 1: Obvious Tampering
- [ ] Synthetic passport
- [ ] Photo replacement
- [ ] Name modification
- [ ] Expected: HIGH RISK, forensic flags

### 14.2 Case 2: Face Mismatch
- [ ] Valid document (all checks pass)
- [ ] Live face doesn't match
- [ ] Expected: SECONDARY REVIEW

### 14.3 Case 3: Evidence Correlation (Killer)
- [ ] Document: PASS
- [ ] MRZ: PASS
- [ ] Expiry: PASS
- [ ] Face: PASS
- [ ] BUT: Identity graph + subtle forensics + contradiction
- [ ] Expected: SECONDARY REVIEW

---

## PHASE 15: Admin & Roles (Hours 57-59)

### 15.1 Role Implementation
- [ ] SUPER_ADMIN
- [ ] ADMIN
- [ ] OFFICER
- [ ] REVIEWER
- [ ] AUDITOR

### 15.2 Admin Pages
- [ ] `/admin`
- [ ] `/admin/users`
- [ ] `/admin/roles`
- [ ] `/admin/rules`
- [ ] `/admin/models`
- [ ] `/admin/watchlists`
- [ ] `/admin/system-health`
- [ ] `/admin/audit`

---

## PHASE 16: Testing & Validation (Hours 60-64)

### 16.1 Unit Tests
- [ ] MRZ check digit validation
- [ ] Date validation logic
- [ ] Field normalization
- [ ] Risk score calculation
- [ ] Contradiction detection

### 16.2 Integration Tests
- [ ] End-to-end screening flow
- [ ] RLS policies
- [ ] Private storage access
- [ ] API auth/permissions

### 16.3 Manual Testing
- [ ] Upload documents
- [ ] Camera capture
- [ ] All three demo cases
- [ ] Officer decision flow
- [ ] Admin functions

---

## PHASE 17: Deployment (Hours 65-68)

### 17.1 Frontend (Vercel)
- [ ] Environment variables
- [ ] Build optimization
- [ ] CORS configuration
- [ ] Production deploy

### 17.2 Backend (Python hosting)
- [ ] Environment setup
- [ ] GPU access (if needed)
- [ ] Scaling configuration
- [ ] Health checks

### 17.3 Verification
- [ ] HTTPS camera access
- [ ] Supabase connection
- [ ] All APIs functional
- [ ] Performance check (<5s per screening)

---

## PHASE 18: Documentation (Hours 69-72)

### 18.1 Create Missing Docs
- [ ] docs/DATASETS.md
- [ ] docs/API.md
- [ ] docs/SECURITY.md
- [ ] docs/PRIVACY.md
- [ ] docs/DEMO.md
- [ ] docs/JURY.md
- [ ] docs/DECISIONS.md

### 18.2 Jury Defense Prep
Prepare answers for:
- What is unique?
- Why evidence fusion?
- How prevent false positives?
- What's real vs simulated?
- Integration with existing systems?

---

## Priority Matrix

| Feature | Priority | Hours | Dependencies |
|---------|----------|-------|--------------|
| Supabase setup | P0 | 2 | None |
| Database schema | P0 | 2 | Supabase |
| Camera scanner | P0 | 4 | None |
| PaddleOCR | P0 | 3 | Dependencies |
| MRZ parser | P0 | 3 | PaddleOCR |
| Document validation | P0 | 3 | MRZ |
| Forensics | P0 | 5 | None |
| Face verification | P0 | 4 | Dependencies |
| Evidence fusion | P0 | 4 | All P0 |
| Officer UI | P0 | 6 | Evidence fusion |
| Identity graph | P1 | 5 | Database |
| Watchlist | P1 | 3 | None |
| Map | P1 | 3 | None |
| Audit proof | P1 | 3 | Database |
| Demo cases | P0 | 3 | All P0 |
| Admin/roles | P1 | 3 | Database |
| Testing | P0 | 5 | All |
| Deployment | P1 | 4 | All |
| Documentation | P1 | 4 | All |

**Total Estimated: 68-72 hours**
**MVP (P0 only): 36-40 hours**

---

## Current Status: READY TO EXECUTE

Next immediate action:
1. Set up Supabase project
2. Install PaddleOCR dependencies
3. Build camera scanner component
4. Integrate PaddleOCR API


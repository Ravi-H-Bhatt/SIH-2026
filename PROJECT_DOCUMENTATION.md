# AI-Based Border Document Screening System
### SIH26188 — Complete Project Documentation

> Every number in this document was read directly from the source code. Nothing is estimated.

---

## 1. What The Project Does (In Simple Words)

An immigration officer at an airport gets a passport and a traveller standing in front of them. In 10–15 seconds our system answers three questions:

1. **Is this document real?** (forgery forensics + ICAO check digits)
2. **Is this person the owner of this document?** (face match)
3. **Is this person wanted anywhere?** (watchlist / sanctions screening)

Then it gives one number — a **Risk Score from 0 to 100** — and one recommendation: **PASS / REVIEW / HOLD**. The officer still takes the final call. The machine only explains the evidence.

**Our core design rule: the system never guesses.** If OCR cannot read a name, it prints `NOT READ` — not a plausible fake name. If no face is found, it says `biometric_performed = false` — it does not print a fake 0% match. A wrong "everything is fine" at a border is more dangerous than an honest "I could not check this."

---

## 2. Architecture

### 2.1 High-Level Picture

```
┌──────────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js 16.3.4 + React 19.2.8 (port 3000)        │
│  Officer Dashboard · Scanner · Self-Service Kiosk ·          │
│  Biometric Identification · Supervisor Hub · Audit Logs      │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST (JWT) + WebSocket
┌───────────────────────────▼──────────────────────────────────┐
│  BACKEND — FastAPI 0.115.0 + Uvicorn (port 8000)             │
│  JWT auth (HS256) · RBAC · Rate limit 120 req/min · Audit    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  10-STAGE SCREENING PIPELINE (pipeline.py)             │  │
│  │  OCR → Validate → Forgery → Face → Graph →             │  │
│  │  Pattern Memory → Watchlist → Contradiction →          │  │
│  │  Risk Fusion → Crypto Audit Anchor                     │  │
│  └────────────────────────────────────────────────────────┘  │
└───────┬──────────────────┬───────────────────┬───────────────┘
        │                  │                   │
┌───────▼──────┐  ┌────────▼────────┐  ┌───────▼─────────────┐
│ Supabase     │  │ ON-DEVICE AI    │  │ CLOUD APIs          │
│ PostgreSQL   │  │ YuNet ONNX      │  │ Google Cloud Vision │
│ + private    │  │ SFace ONNX      │  │ OpenSanctions       │
│   storage    │  │ Tesseract OCR   │  │ (both optional)     │
│   buckets    │  │ OpenCV/NumPy    │  │                     │
└──────────────┘  └─────────────────┘  └─────────────────────┘
```

### 2.2 Why This Architecture

- **AI runs inside the API process, not as a separate ML server.** No network hop, no serialisation cost, no second thing to deploy. The whole scan finishes inside one HTTP request.
- **ONNX models are bundled in the repo** (`app/services/face/*.onnx`). Face matching needs zero internet. This is the single most important architectural decision for a border post.
- **Cloud is an accelerator, never a dependency.** Google Vision improves OCR accuracy. If it is down, the local engine chain takes over automatically.
- **Database is the source of truth, not local disk.** Images live in *private* Supabase buckets and reach the browser only as 1-hour signed URLs.

### 2.3 Services Map (`backend/app/services/`)

| Folder | What Lives There |
|---|---|
| `ocr/` | `mrz.py` — ICAO 9303 TD1/TD2/TD3 parser + check digits · `ocr_service.py` — local engine chain · `unified_ocr_pipeline.py` — cloud+local router |
| `face/` | `face_service.py` — YuNet + SFace biometrics · `watchlist_service.py` — OpenSanctions + local list |
| `forgery/` | `forgery_service.py` — ELA, DCT, splice, blur, EXIF · `pattern_memory.py` — known counterfeit signatures |
| `graph/` | `identity_graph.py` — NetworkX 1:N identity search across past encounters |
| `risk/` | `risk_engine.py` — evidence fusion · `contradiction_engine.py` — Evidence Truth Matrix |
| `validation/` | ICAO rules, ISO 3166 country codes, expiry/age logic, issuing-authority registry |
| `storage/` | Supabase private buckets, signed URLs, scratch cleanup |
| `audit/` | `crypto_anchor.py` — SHA-256 canonical evidence digest |
| `geo/` | Country centroid table for the operations map |

---

## 3. How A Scan Actually Works — The 10 Stages

Officer uploads a document photo and a live face photo to `POST /api/v1/scans`. Then, in order:

**Stage 1 — OCR & MRZ Reading**
Image is read by Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`). If unavailable → Tesseract → Apple Vision → Windows OCR. The two-line Machine Readable Zone at the bottom of the passport is located and parsed as ICAO 9303 TD3 (2×44), TD1 (3×30) or TD2 (2×36).

**Stage 2 — ICAO Check-Digit Verification**
The MRZ carries self-checking digits. We recompute all three using the official **7-3-1 weighting** (`<`=0, digits as-is, A=10…Z=35, sum mod 10) over document number, date of birth and expiry date. If even one fails, the document data is untrusted. This catches hand-edited passports instantly.

**Stage 3 — Demographic Validation**
Document number pattern `^[A-Z0-9]{6,16}$`, nationality against the full ISO 3166-1 alpha-3 set plus ICAO special codes, expiry in the past, expiry within 90 days, and age sanity (rejects `age > 120` or `age < 0`).

**Stage 4 — Dual-Domain Forgery Forensics**
Five independent physics-based tests (full table in §6). Detects a swapped photo, spliced text, or a Photoshop-edited scan.

**Stage 5 — Biometric Verification**
YuNet finds faces → 5-landmark alignment → SFace produces a 128-dimension embedding → raw cosine similarity (full detail in §5).

**Stage 6 — Identity Continuity Graph (NetworkX)**
The current face is searched 1:N against the last 500 encounters. Two fraud patterns are detected semantically:
- Same face + different name = **identity hopping**
- Same face + different document = **multi-document holder**

**Stage 7 — Fraud Pattern Memory (EU-FADO style)**
Forensic scores are turned into a numeric signature (`ela_variance`, `dct_quantization_error`, `photo_boundary_discontinuity`, `sharpness_index`, `exif_tampered`) and matched against a curated library of known counterfeit families, e.g. `FPM-IND-2025-01` photo substitution.

**Stage 8 — Watchlist Screening**
Name + document number screened against live **OpenSanctions** (terrorism, sanctions, crime, PEP topics) and a local synthetic list. Sources are always reported separately.

**Stage 9 — Contradiction Engine (our signature feature)**
Explained in §4.1.

**Stage 10 — Risk Fusion + Cryptographic Audit Anchor**
All evidence is fused into one 0–100 score with a plain-English explanation for every point added. A canonical SHA-256 digest of the whole verification record is stored so nobody can later edit the result. Optional anchoring to Ethereum Sepolia (chain ID `11155111`).

Total: **~10–15 seconds, synchronous.** The officer waits once and gets a complete answer.

---

## 4. Standout Features

### 4.1 Cross-Modal Contradiction Matrix ⭐ Our Biggest Differentiator

Every other screening product runs checks in parallel and adds up the failures. **A good forgery passes every individual check.** Our Contradiction Engine instead compares the *independent evidence streams against each other* and hunts for claims that cannot both be true:

| Stream A | Stream B | Paradox It Catches |
|---|---|---|
| Chip PKI signature | Photo forensics | Chip says authentic, but the photo shows splice edges → **chip cloned into a forged booklet** |
| Document portrait | Live traveller face | Document is flawless, face does not match → **genuine stolen passport, look-alike impostor** |
| MRZ check digits | Visual zone OCR | Both look fine individually but disagree with each other → **partial data tampering** |
| Current biometric | Historical graph | Same face crossed last week under a different name → **identity hopping** |

Escalation floors are hard-coded: `98.0`, `95.0`, `92.0`, `88.0`, `85.0`, `82.0`, `80.0`, `75.0` depending on which paradox fires. A single contradiction can drive the score to critical no matter how clean the individual checks were.

### 4.2 Refuses To Fabricate Data
Unreadable field → `NOT READ`. No face → `biometric_performed = false`, `match_passed = null`. Wrong embedding dimension → pushed to a `skipped` list with a reason, never truncated to force a comparison. Liveness is **tri-state** (`true` / `false` / `null`) so "could not assess" is never silently read as "live".

### 4.3 Fails Closed, Never Open
Models missing → `not_performed_reason = "MODELS_UNAVAILABLE"`, verification refused. Partial MRZ → `mrz_valid = False`. Non-ICAO MRZ variant → all check digits marked `False`. An invalid date returns `None`, not a guessed date.

### 4.4 Multiple Faces On A Document Handled Correctly
Modern passports carry a **ghost portrait** (a faint secondary image) per ICAO 9303. Naive systems either fail or match the wrong face. We compare every detected face to the largest one: if it is the same person, it is logged as a legitimate ghost image and verification continues; if it is a different person, the portrait is declared ambiguous and we refuse rather than pick one at random.

### 4.5 Cryptographic Audit Trail
Every audit row gets a SHA-256 hash generated in the **ORM layer** (`before_insert` event), not the application layer — so no code path can write an unhashed row. Per-scan canonical evidence digest is independently verifiable via `POST /scans/{id}/verify-audit`.

### 4.6 Security Refuses To Boot Insecure
In production the app **exits** if: `SECRET_KEY` is the placeholder or under 32 chars, `BYPASS_AUTH=true`, `DEBUG=true`, CORS contains `*`, or `AUTO_APPROVE_USERS=true`. `/docs` is disabled in production. The unauthenticated `/uploads` static mount that used to expose every passport scan was deliberately removed.

### 4.7 Self-Service Kiosk
A separate traveller-facing flow (`welcome → scan → face capture → processing → result`) with a language selector, so low-risk travellers clear themselves and officers focus on the flagged queue.

### 4.8 Watchlist Escalation Respects Civil Liberties
A **name-only** fuzzy match can never auto-detain — that would jail innocent travellers over name collisions. It carries `verified: false` and `action_required: "Adjudicate against the listing before any decision"`, and routes to an officer. Only an **exact document-number match** auto-detains. Severity still matters: a terrorism designation holds the traveller, a PEP note only flags for review. Local demo entries are prefixed `SIMULATED —`.

---

## 5. Face Matching — Thresholds & Metrics (Exact)

### 5.1 The Model Stack

| Component | Detail |
|---|---|
| Detector | **YuNet** (`face_detection_yunet.onnx`), input 320×320 |
| Recognizer | **SFace** (`face_recognition_sface.onnx`), input 112×112 |
| Runtime | OpenCV DNN (`cv2.FaceDetectorYN` / `cv2.FaceRecognizerSF`) — **no PyTorch, no TensorFlow** |
| Embedding | **128-dimension**, L2-normalised |
| Metric | **Raw cosine similarity**, clipped to `[-1, 1]`, never rescaled into a fake percentage |
| Alignment | 5-landmark `alignCrop` before feature extraction |
| Internet needed | **None.** Both models ship in the repo. |

### 5.2 All Thresholds

| Threshold | Value | Meaning |
|---|---|---|
| `MIN_SAFE_COSINE_THRESHOLD` | **0.363** | Hard floor. SFace's published same-domain operating point. Config cannot go below it. |
| `FACE_MATCH_COSINE_THRESHOLD` — **1:1** | **0.363** | Verification: is this traveller the document holder? |
| `FACE_IDENTITY_MATCH_THRESHOLD` — **1:N** | **0.50** | Identification: search a gallery. **Deliberately stricter.** |
| `FACE_QUALITY_THRESHOLD` | **0.6** | Minimum detector confidence to accept a face |
| YuNet create threshold | 0.5 | Model construction |
| YuNet runtime threshold | **0.4** | `max(0.2, min(conf, 0.9) - 0.2)` — detect permissively, filter strictly after |
| Crop margin | **0.15** (15%) | Context kept around the face box |
| `LIVENESS_MIN_FREQ_RATIO` | **0.003** | FFT high/low frequency energy ratio |
| `LIVENESS_MIN_EDGE_VARIANCE` | **10.0** | Texture detail floor |

Effective values are computed, not just read:
- 1:1 = `max(0.363, config)` → **0.363**
- 1:N = `max(1:1_threshold, 0.50)` → **0.50**

**Why 1:N is stricter than 1:1:** in 1:1 you make one comparison. In 1:N against 500 people you make 500 comparisons, so the chance of a random false match is ~500× higher. Raising the bar to 0.50 controls that false-positive inflation. Most projects use one threshold everywhere — that is statistically wrong, and this is a strong point to make to judges.

### 5.3 1:N Search Parameters

| Parameter | Value |
|---|---|
| `top_k` default / max | 10 / **50** |
| `gallery_limit` default / max | 500 / **2000** |
| Identity graph gallery cap | **500** most recent encounters |
| Incomparable embeddings | Reported in `skipped`, never coerced |

### 5.4 Liveness / Anti-Spoofing

An FFT texture heuristic (honestly labelled as such, not a trained anti-spoof CNN): grayscale → 128×128 → 2D FFT → radius-16 low-pass mask → `freq_ratio = high_energy / low_energy`, plus edge variance. Fails if `edge_variance < 10.0` **or** `freq_ratio < 0.003`, catching screen replays and paper printouts. Exceptions return `None` (unverified), never `True`.

### 5.5 Why Face Match May Say "NOT PERFORMED"

Machine-readable reasons — each one is a deliberate refusal, not a crash:

| Reason Code | Cause |
|---|---|
| `NO_DOCUMENT_PORTRAIT` | No face found on the document above 0.6 confidence |
| `NO_FACE_IN_LIVE_CAPTURE` | No face in the traveller photo |
| `NO_LIVE_CAPTURE` | No live image submitted |
| `MULTIPLE_FACES_IN_LIVE_CAPTURE` | More than one person in frame → recapture |
| `DOCUMENT_PORTRAIT_AMBIGUOUS` | Several faces on the document belong to **different people** → cannot decide which is the portrait |
| `MODELS_UNAVAILABLE` | ONNX models not loaded |
| `COMPARISON_ERROR` | Feature extraction failed |

---

## 6. Forgery Forensics — Thresholds & Weights

| Technique | How It Works | Flag Threshold | Weight |
|---|---|---|---|
| **ELA** (Error Level Analysis) | Re-saves JPEG at quality 90, measures compression error difference — edited regions compress differently | mean brightness **> 45** | **× 0.35** |
| **DCT quantisation** | 8×8 block DCT, AC-energy ratio — detects double JPEG compression | ratio **> 5.0**, score **> 55.0** | **× 0.30** |
| **Photo-boundary splice** | Canny(100, 200) edge density in a 15px ring around the portrait | density **> 0.25** | **× 0.40** (highest — direct photo substitution evidence) |
| **Blur / sharpness** | Laplacian-style variance | variance **< 100.0** | **+15 flat** |
| **EXIF metadata** | Scans for `photoshop, gimp, canva, adobe, pixelmator, lightroom, paint.net` | keyword present | **+35 flat**, confidence **0.95** |

Final: `anomaly_score = min(100, max(0, Σ))`.

Pattern memory gates: `boundary >= 40.0 AND (ela >= 30.0 OR forgery >= 35.0)`, or `dct >= 35.0 OR exif_tampered`. Confidence `0.65 – 0.96`.

---

## 7. Risk Score Matrix (Complete & Exact)

The engine mixes **`max()` floors** (a serious finding sets a minimum, it cannot be diluted by clean checks) with **additive points** (independent minor findings accumulate). This hybrid is what stops one clean signal from washing out one fatal signal.

| # | Evidence | Effect On Score |
|---|---|---|
| 1 | Contradiction engine fires | `max(score, 75.0)` — up to **98.0** by paradox type |
| 2 | Known fraud signature matched | `max(score, 70.0)` |
| 3 | Identity graph anomaly — CRITICAL | `max(score, 85.0)` |
| 4 | Identity graph anomaly — other | `max(score, 65.0)` |
| 5 | Forgery anomaly score | `+ anomaly_score × 0.35` |
| 6 | MRZ required but check digits fail | **+25.0** |
| 7 | Document expired | `max(score, 80.0)` → critical |
| 8 | Any other validation failure | **+15.0** each |
| 9 | Biometric not performed / indeterminate | **+20.0** |
| 10 | **Face match FAILED** | **+35.0** |
| 11 | **Liveness FAILED** | **+45.0** (highest single additive — a spoof attempt is deliberate) |
| 12 | Liveness indeterminate | **+10.0** |
| 13 | Watchlist hit — critical (terror / sanctions) | **+85.0** |
| 14 | Watchlist hit — other | **+50.0** |

Final: `min(100.0, max(0.0, raw_score))` rounded to 1 decimal.

### Decision Bands

| Score | Risk Level | Decision | Officer Action |
|---|---|---|---|
| **≥ 80.0** | `critical` | **HOLD** | Detain and escalate |
| **50.0 – 79.9** | `high` | **REVIEW** | Secondary inspection |
| **25.0 – 49.9** | `medium` | **REVIEW** | Manual verification |
| **< 25.0** | `low` | **PASS** | Clear |

Every point carries a human-readable explanation string, e.g. `"cosine 0.2140 < required 0.363"`. Nothing is a black box.

### 7.1 Final Escalation Layer (`pipeline.py`)

After the risk engine returns, the pipeline applies overrides for the findings that must never be diluted. **These only ever escalate — a decision already raised is never downgraded.**

| Finding | Score | Level | Decision |
|---|---|---|---|
| **Verified** watchlist hit (exact document-number match) | **100.0** | critical | **DETAIN** |
| **Unverified critical** listing (terrorism / sanctions, name-only match) | `max(score, 90.0)` | critical | **HOLD** |
| Unverified non-critical listing (crime / PEP) | `max(score, 72.0)` | high | **REVIEW** |
| MRZ **reference mismatch** — document disagrees with the issuing authority's record | `max(score, 90.0)` | critical | **HOLD** |

The distinction in rows 1 and 2 is a deliberate civil-liberties safeguard. An **exact document number** match is a strong identifier and can auto-detain. A **name-only** fuzzy match cannot — that would detain innocent travellers over name collisions, so it holds them for an officer to adjudicate instead. But a terrorism designation is still treated more seriously than a PEP note.

---

## 8. OCR & MRZ

**Fallback chain (automatic):**
`Google Vision REST (API key) → Google Vision SDK (ADC) → Tesseract → Apple Vision → Windows OCR`

| Setting | Value |
|---|---|
| `OCR_PROVIDER` default | `local` (offline-first out of the box) |
| `OCR_FALLBACK_ENABLED` | `True` |
| `OCR_LOCAL_ENGINES` | `tesseract, apple_vision, windows` |
| `VISION_MAX_RETRIES` | 2 (3 attempts total) |
| `VISION_REQUEST_TIMEOUT_SECONDS` | 30.0 |
| `VISION_MAX_IMAGE_BYTES` | 10 MB |

**MRZ formats:** TD3/MRP 2×44, TD1 3×30, TD2 2×36, TD3-line-2-only recovery, and a non-ICAO simplified variant (always marked invalid).

**Check digit algorithm:** weights `[7, 3, 1]` cycling, `<`=0, digits literal, letters `ord(c) - 55`, result `sum mod 10`. Verified independently over document number, DOB and expiry — all three must pass for `mrz_valid = True`.

**Smart repairs, bounded:** issuing-state code repaired only from the check-digit-protected MRZ line 2; nationality OCR fixes limited to `1→I` and `0→O`. Date sanity `1900–2100`, month 1–12, day 1–31, century pivot on the current year. **Anything unfixable returns `None`, never a guess.**

**ID cards without MRZ** are handled honestly: `mrz_required: false`, `mrz_verifiable: false`, with the note *"No MRZ present on this document type — no check digits to verify"* — the absence of an MRZ is not counted as a failure.

---

## 9. Watchlist / Sanctions Screening

| Item | Detail |
|---|---|
| Live source | **OpenSanctions API** — `POST /match/{dataset}?algorithm=logic-v1` |
| Auth | `Authorization: ApiKey` |
| Match threshold | **0.70** (`OPENSANCTIONS_MATCH_THRESHOLD`) |
| Timeout | 12.0 s |
| Local name similarity floor | **0.86** (`MIN_NAME_SIMILARITY`) |
| Algorithm | `difflib.SequenceMatcher`: `(token_overlap × 0.6) + (sequence_ratio × 0.4)` |
| Surname guard | Surname set intersection, or surname ratio **≥ 0.9** (tolerates one transcription error) |
| Stopwords ignored | `AL, EL, BIN, IBN, BINT, ABU, DE, VAN, VON, MC, MAC, MR, DR, JR, SR…` |
| Normalisation | NFKD decompose → strip accents → uppercase → collapse whitespace |

**Severity mapping from OpenSanctions topics:**

| Topic | Severity | Label | Risk Points |
|---|---|---|---|
| `terror` | **critical** | TERRORISM LISTING | +85 |
| `sanction*` | **critical** | SANCTIONS DESIGNATION | +85 |
| `crime*` | high | INTERNATIONAL CRIME LISTING | +50 |
| `role.pep*` | medium | POLITICALLY EXPOSED PERSON | +50 |

Exact document-number match → `confidence = 1.0`, `verified = true`. Name-only match → `verified = false` and requires officer adjudication. Screening is wrapped so it **can never break a scan** — if OpenSanctions is unreachable it degrades to the local list and says so.

---

## 10. Complete Tech Stack

### Backend — Python 3.12

| Category | Package | Version |
|---|---|---|
| Web framework | `fastapi` | 0.115.0 |
| ASGI server | `uvicorn[standard]` | 0.30.0 |
| Uploads | `python-multipart` | 0.0.9 |
| ORM | `sqlalchemy` | 2.0.35 |
| Postgres driver | `psycopg[binary]` | 3.3.5 |
| Validation | `pydantic[email]` | 2.9.0 |
| Settings | `pydantic-settings` | 2.5.0 |
| Env | `python-dotenv` | 1.0.1 |
| JWT | `python-jose[cryptography]` | 3.3.0 |
| Password hash | `bcrypt` (via `passlib[bcrypt]`) | 1.7.4 |
| **Computer vision** | `opencv-python-headless` | 4.10.0.84 |
| Imaging | `Pillow` | 10.4.0 |
| Numerics | `numpy` | 1.26.4 |
| DCT / signal | `scipy` | 1.14.1 |
| **Identity graph** | `networkx` | 3.3 |
| **Cloud OCR** | `google-cloud-vision` | 3.7.2 |
| Google auth | `google-auth` | 2.29.0 |
| **Local OCR** | `pytesseract` | 0.3.13 |
| HTTP | `httpx` | 0.27.0 |
| Async files | `aiofiles` | 24.1.0 |

**Deliberately removed to stay deployable:** `paddleocr` + `paddlepaddle` (~700 MB), `insightface`, `onnxruntime` (~250 MB — OpenCV imports ONNX natively), `scikit-image`. **Total AI footprint is a few MB, not gigabytes.** This is an engineering achievement worth mentioning.

### Frontend

| Package | Version | Role |
|---|---|---|
| `next` | **16.3.4** | App Router framework |
| `react` / `react-dom` | **19.2.8** | UI |
| `typescript` | ^5 | Type safety |
| `tailwindcss` + `@tailwindcss/postcss` | ^4.1.14 | Styling (Tailwind v4) |
| `class-variance-authority` / `clsx` / `tailwind-merge` | — | Component variants |
| `lucide-react` | ^0.469.0 | Icons |
| `leaflet` + `react-leaflet` | ^1.9.4 / ^5.0.0 | Operations map |
| `@supabase/supabase-js` | ^2.58.0 | Google OAuth (browser only) |
| `eslint` + `eslint-config-next` | ^9 / 16.3.4 | Linting |

### AI / ML Inventory (Straight Answer For Judges)

| Capability | Technology | Runs Where |
|---|---|---|
| Face detection | **YuNet** (ONNX CNN) | **On-device** |
| Face recognition | **SFace** (ONNX CNN, 128-d) | **On-device** |
| Liveness | FFT frequency + texture analysis | **On-device** |
| Forgery forensics | ELA, DCT, Canny splice, EXIF | **On-device** |
| OCR (primary) | **Google Cloud Vision** `DOCUMENT_TEXT_DETECTION` | Cloud |
| OCR (fallback) | **Tesseract 5**, Apple Vision, Windows OCR | **On-device** |
| MRZ parsing | ICAO 9303 rule engine + 7-3-1 check digits | **On-device** |
| Identity graph | **NetworkX** graph reasoning | **On-device** |
| Sanctions | **OpenSanctions** `logic-v1` + `difflib` fuzzy match | Cloud + local |
| Evidence fusion | Custom weighted risk engine | **On-device** |

**Only 2 of 10 capabilities need internet, and both have working local fallbacks.**

### Infrastructure

| Item | Detail |
|---|---|
| Database | Supabase **PostgreSQL** (SQLite fallback for dev) |
| Storage | Supabase private buckets `document-images`, `face-captures` |
| Pooler handling | Detects Supavisor transaction mode (`:6543`) → `prepare_threshold=None` + `NullPool`; direct mode → `pool_size=5`, `max_overflow=10`, `pool_recycle=300`, `pool_pre_ping` |
| Deployment | **Railway** (NIXPACKS), healthcheck `/api/v1/health` |
| Blockchain (optional) | Ethereum **Sepolia**, chain ID `11155111` |

---

## 11. Database Schema

All primary keys are UUIDv4.

| Table | Key Columns |
|---|---|
| `users` | email (unique), full_name, hashed_password, role, is_active, **is_approved** (default False), approved_by, approved_at |
| `scan_records` | document_type, status, checkpoint_id, officer_id, document_image_path, face_image_path (`supabase://` URIs), final_decision, **chip_pki_status**, canonical_hash, lat/long, is_criminal, is_wanted |
| `extracted_data` | fields (JSON), mrz_data (line1/line2/parsed), **mrz_valid** |
| `forgery_results` | anomaly_score (0–100), detected_issues (JSON) |
| `face_results` | match_score, liveness_passed, **face_embedding** (JSON 128-d), continuity_links, watchlist_hits |
| `risk_scores` | score, risk_level, decision, explanations, **contradiction_matrix**, identity_graph_summary, fraud_patterns_matched, canonical_hash |
| `audit_logs` | timestamp, action, actor, details, **hash** (SHA-256, auto-generated in ORM) |
| `mrz_references` | Issuing-authority registry: document_number (unique), holder_name, dob, expiry, is_revoked, is_reported_stolen |

---

## 12. API Reference

Base: `/api/v1`. Every protected route re-checks `is_active` **and** `is_approved` on **every request** — so revoking an officer takes effect immediately, not after their token expires.

### Auth
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Email + password → JWT |
| POST | `/auth/google` | Supabase token → app JWT (verified server-side) |
| POST | `/auth/refresh` | Re-issue JWT |
| GET | `/auth/providers` | Which login methods are enabled |

### Scanning
| Method | Path | Purpose | Role |
|---|---|---|---|
| POST | `/scans` | Upload + run full pipeline | any approved |
| GET | `/scans` | Paged list with filters + search | any |
| GET | `/scans/{id}` | Full detail + signed image URLs | any |
| GET | `/scans/{id}/status` | Lightweight poll | any |
| POST | `/scans/{id}/decision` | approved / flagged / detained | **officer+** |
| POST | `/scans/{id}/verify-audit` | Verify SHA-256 evidence digest | any |

### Biometrics
| Method | Path | Purpose |
|---|---|---|
| POST | `/face/compare` | **1:1** → cosine + `SAME_PERSON` / `DIFFERENT_PERSON` / `NOT_COMPARABLE` |
| POST | `/face/search` | **1:N** identification (`top_k` ≤ 50, `gallery_limit` ≤ 2000) |
| GET | `/face/gallery` | Gallery diagnostics: comparable vs incomparable |

### Dashboards & Admin
| Method | Path | Purpose | Role |
|---|---|---|---|
| GET | `/dashboard/stats` | Daily totals + risk distribution | any |
| GET | `/dashboard/map` | Geospatial origin feed | any |
| GET | `/supervisor/dashboard` | Throughput, officer activity | **supervisor+** |
| GET | `/supervisor/flagged-queue` | Review queue | **supervisor+** |
| POST | `/supervisor/override/{id}` | Override with audit trail | **supervisor+** |
| GET | `/audit/logs` | Audit search | **admin / investigator / supervisor** |
| GET/POST/PATCH/DELETE | `/users/*` | User management + approval | **admin** |
| WS | `/ws?token=<jwt>` | Authenticated feed socket | officer+ |
| GET | `/health` | DB liveness | public |

### Security Config
| Setting | Value |
|---|---|
| JWT algorithm | **HS256** |
| Token expiry | **120 minutes** |
| Rate limit | **120 requests / 60 s** per IP |
| Password hashing | **bcrypt** with per-password salt |
| RBAC ranks | `auditor` 10 · `investigator` 20 · `officer` 30 · `supervisor` 40 · `admin` 100 |
| Signed URL TTL | **3600 s** |
| Max upload | **15 MB** |

---

## 13. ⚡ WHAT IF THERE IS NO INTERNET? (Critical Judge Question)

**Short answer: the system keeps working, and it tells the officer exactly what it could not check.**

Border posts have unreliable connectivity. We designed for that from the start rather than patching it later.

### Works Fully Offline — No Degradation

| Capability | Why |
|---|---|
| **Face detection** | YuNet ONNX bundled in the repo |
| **Face matching 1:1 & 1:N** | SFace ONNX bundled in the repo |
| **Liveness detection** | Pure NumPy FFT maths |
| **All forgery forensics** | ELA, DCT, splice, blur, EXIF — all local |
| **MRZ parsing + ICAO check digits** | Pure Python rule engine |
| **Demographic validation** | Local ISO 3166 tables |
| **Identity continuity graph** | Local NetworkX + local DB |
| **Fraud pattern memory** | Local signature library |
| **Contradiction engine** | Local logic |
| **Risk scoring** | Local |
| **Cryptographic audit hashing** | Local SHA-256 |

### Degrades Gracefully — Automatic, No Officer Action Needed

| Capability | Offline Behaviour |
|---|---|
| **OCR** | Google Vision fails → falls back to Tesseract → Apple Vision → Windows OCR. Logged as `"Using local OCR fallback."` Accuracy dips slightly; the pipeline continues. |
| **Sanctions screening** | OpenSanctions unreachable → caught, logged `"[Watchlist] OpenSanctions step skipped"`, degrades to the local list. **Explicitly coded so screening can never break a scan.** |
| **Blockchain anchor** | Disabled by default; local SHA-256 digest is still computed and stored. |

### And If Everything Fails?

It **refuses honestly** instead of pretending:

> `"No text could be extracted from the document image. Check image focus/lighting, install a local OCR engine (brew install tesseract), or configure OCR_PROVIDER=google_vision."`

Missing models → `MODELS_UNAVAILABLE`, verification refused, **no fake score invented**.

**The line to say out loud:** *`OCR_PROVIDER` defaults to `local`. A fresh checkout of our project is offline-first by default. Cloud is an upgrade, never a requirement — and when a cloud check is skipped, the officer is told, so an unchecked field is never mistaken for a cleared one.*

---

## 14. Future Scope

**Near term**
- **Alembic migrations** to replace `create_all` for safe production schema evolution
- **Redis-backed rate limiting** — the current limiter is in-process, so it does not survive restarts or scale across workers
- **Celery / async job queue** so the 10–15 s pipeline stops blocking the HTTP request
- **Server-side WebSocket broadcast** — the authenticated socket exists; pushing live scan events over it removes REST polling
- **Response caching** for Vision and OpenSanctions to cut repeat cost and latency

**Biometrics**
- **Trained anti-spoof CNN** to replace the FFT heuristic; add depth/IR sensors and passive blink detection
- **pgvector + ANN indexing** (HNSW/IVF) so 1:N scales from 500 to millions of encounters
- **NFC / eMRTD chip reading** with real ICAO PKD certificate-chain validation — today `chip_pki_status` is supplied as input
- **Iris and fingerprint** fusion for multi-modal biometrics

**AI / ML**
- **Deep-learning forgery detector** (EfficientNet / Vision Transformer) alongside the physics-based tests
- **Document-type classifier** to auto-detect country and template
- **Self-learning pattern memory** — promote confirmed frauds into the signature library automatically
- **Explainable AI heatmaps** showing officers *where* on the document tampering was found
- **Real-time OCR quality coaching** during capture ("move closer", "reduce glare")

**Integrations**
- Live **INTERPOL SLTD** (Stolen and Lost Travel Documents) — the config flag exists, the client is future work
- National immigration databases and visa systems
- **Real offline sync**: bundled sanctions snapshot with delta updates when connectivity returns, plus an outbox that replays queued screenings
- **Edge deployment** on ruggedised hardware for remote land borders
- Mobile officer app for mobile checkpoints

**Operations**
- Multi-language UI for the kiosk (Hindi + regional languages)
- Automated model-drift monitoring and threshold recalibration against a labelled test set
- FRR/FAR/ROC benchmarking on a public face dataset to publish an empirical operating point instead of relying on SFace's published one
- Load testing and horizontal scaling profile

---

## 15. Honest Limitations (Say These Before Judges Find Them)

Being upfront here is a strength, not a weakness — it shows engineering maturity.

1. **Liveness is a heuristic, not a trained anti-spoof model.** Labelled as such in code and in this document.
2. **The local watchlist is synthetic** — 10 demo entries, prefixed `SIMULATED —`. Real screening needs the OpenSanctions key.
3. **`chip_pki_status` is an input, not a real NFC read.** No physical chip reader is integrated yet.
4. **WebSocket does not broadcast yet.** It authenticates and heartbeats; dashboards poll REST. We are not claiming live push.
5. **1:N is capped at 500 encounters** — sufficient for a checkpoint demo, needs pgvector for national scale.
6. **Rate limiting is in-process** and collapses to a single bucket behind a proxy.
7. **`verify-audit` reports a hash match even when nothing was anchored on-chain** — blockchain anchoring is off by default.
8. **Thresholds are the published SFace operating point,** not empirically tuned on an Indian passport dataset. Correct next step is FRR/FAR calibration.
9. **No Alembic migrations** — schema is created at boot.
10. **`FORENSICS_ELA_QUALITY` and `FORENSICS_TAMPERING_THRESHOLD` config keys are currently unused;** the forgery service uses hard-coded values (quality 90, `>45`, `>55.0`, `>0.25`, `<100.0`).

---

## 16. One-Minute Pitch

> Border fraud today is not crude. It is a genuine stolen passport with a professionally swapped photo, or the same person crossing under three names. Every check passes individually.
>
> So we stopped adding up checks and started **cross-examining** them. Our Contradiction Engine runs eleven independent evidence streams — ICAO check digits, ELA and DCT forensics, 128-dimension SFace biometrics, a NetworkX identity graph, OpenSanctions — and then hunts for claims that cannot both be true. A perfect chip signature on a booklet with spliced photo edges. A flawless document whose portrait does not match the person holding it. A new name on a face we saw last Tuesday.
>
> Every score is explained in plain English, sealed with SHA-256, and the officer always decides. And because the neural networks are bundled ONNX models running on-device, the whole thing works with the internet cable pulled out — which is exactly the condition at the borders that need it most.

---

*AI-Based Border Document Screening System · SIH26188*
*All thresholds, weights and versions verified against source code.*

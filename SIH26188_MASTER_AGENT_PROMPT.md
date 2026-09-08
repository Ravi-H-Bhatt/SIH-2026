# SIH 26188 — Master Agent IDE Build Prompt

## Mission

Build the complete Smart India Hackathon 2026 solution for **PS 26188 — AI-Based Fake Identity & Document Screening System** as a working, end-to-end, deployable prototype.

The application must not be a generic OCR + face-recognition demo. It must be an **AI Identity-Fraud Intelligence & Evidence Platform** that combines document intelligence, MRZ/structural validation, forensic tamper analysis, face verification, controlled face-variation robustness testing, identity continuity/entity resolution, risk-data screening, evidence fusion, explainable risk, human officer review, mapping, and tamper-evident audit.

## Mandatory operating rule: this Markdown is the source of truth

1. At the beginning of EVERY task, inspect this file.
2. Treat this file as the authoritative project requirements/architecture document.
3. Before adding, removing, changing, or replacing a technology, dataset, API, route, table, model, UI flow, or security decision, compare the proposed change against this file.
4. If requirements conflict, do not silently choose. Document the conflict in `docs/DECISIONS.md`, verify the external source, then update this file only after the decision is confirmed.
5. Keep `docs/IMPLEMENTATION_STATUS.md` updated after meaningful work.
6. Never implement a feature only because it sounds impressive; it must have a documented PS/product purpose.
7. Never claim an integration works unless it has actually been tested.

## Source verification rules

### Primary PS source
Use the official SIH portal when accessible:
https://sih.gov.in/sih2026PS

The page supplied by the user, https://sihone.pages.dev/ps/26188, is an aggregator and is not authoritative. It may be used as a secondary reference only.

### ICAO
Official Doc 9303 page:
https://www.icao.int/publications/doc-series/doc-9303

Use current official ICAO material. Doc 9303 is a **standard/publication, not an ML dataset**.

Do not confuse:
- MRZ OCR
- MRZ parsing
- MRZ check-digit validation
with:
- ePassport chip reading
- Logical Data Structure (LDS)
- Passive Authentication
- Active/Chip Authentication
- PKI/certificate validation

MRZ check digits are deterministic consistency/error-detection mechanisms; they are not cryptographic authentication of the ePassport chip.

### INTERPOL
Official SLTD page:
https://www.interpol.int/en/How-we-work/Border-management/SLTD-database-travel-and-identity-documents

INTERPOL databases are accessed by authorized users through I-24/7. Do **not** fabricate or assume a public INTERPOL developer API key. Implement a provider adapter with `INTERPOL_ENABLED=false` by default and use simulated data for the public SIH demo unless authorized credentials/access are genuinely provided.

### OpenSanctions
Official docs:
https://www.opensanctions.org/docs/api/matching/
https://www.opensanctions.org/docs/api/request/

Use as an optional external entity/risk source. It is not an MHA database and must never be described as one.

## PS-aligned capabilities

The product must cover the PS core functions:

1. OCR extraction
2. Document validation
3. Tampering/forgery detection
4. Face detection/verification

The system should support configurable document classes such as passport, visa, national identity document, driving licence, permit, and other authorized document types.

## Product concept

Build:

**AI Identity-Fraud Intelligence & Evidence Platform**

Core workflow:

Camera / file upload
→ document detection
→ image quality assessment
→ document rectification/cropping
→ OCR
→ MRZ detection and validation
→ structured field extraction
→ document-rule validation
→ forensic tamper analysis
→ document-face extraction
→ live face capture
→ 1:1 face verification
→ controlled face-variation robustness/morphing analysis
→ authorized identity search
→ identity continuity/entity resolution
→ risk/watchlist screening
→ contradiction analysis
→ evidence fusion
→ explainable risk
→ officer review
→ decision
→ immutable/tamper-evident audit proof

## Main differentiator

Do not build only:
`OCR → face matching → fake/not-fake`

The main innovation is **evidence correlation**.

A document may individually pass OCR, MRZ, expiry, structural checks, and face verification while the combined evidence still produces an anomaly requiring secondary review.

Example:

- Document structure: PASS
- MRZ check digits: PASS
- Expiry: PASS
- Face verification: PASS
- Forensic signal: WARNING
- Identity continuity: WARNING
- Cross-document contradiction: WARNING

Result:
**SECONDARY REVIEW**

The system must explain the evidence. It must not silently convert evidence into an unsupported accusation.

## Identity continuity / entity-resolution engine

Create an identity graph using authorized/synthetic records.

Entities:
- identity
- passport/document
- visa
- face embedding
- name variants/aliases
- DOB
- nationality
- verification event
- travel/event record
- risk record

Relations:
- identity ↔ document
- identity ↔ face
- identity ↔ historical event
- document ↔ visa
- identity ↔ alias
- identity ↔ risk record

Detect suspicious patterns such as:
- same/similar biometric representation associated with different synthetic/authorized identity records
- conflicting DOB/name/nationality values
- suspicious reuse of document attributes
- conflicting documents
- anomalous identity relationships

Do not automatically say “same person”. Use:
**Potential identity collision / candidate relationship — officer review required.**

## Face permutation / robustness feature

Implement the user's requested face-variation idea as a controlled robustness/identity-consistency module.

For synthetic or explicitly authorized enrolled identities only, generate bounded variants such as:
- beard ↔ no beard
- moustache ↔ no moustache
- hairstyle variation
- modest hairline variation
- glasses ↔ no glasses
- lighting changes
- pose changes
- other controlled appearance perturbations

Purpose:
Test whether an identity matcher remains stable under realistic appearance changes and whether controlled variants create a candidate relationship in the authorized/synthetic identity database.

Also evaluate genuine morphing attacks using a proper morph dataset.

Do not provide an unrestricted public “identify this random person” service. Candidate retrieval must be access-controlled and the UI must use cautious wording.

## Live passport/document scanner

Implement a browser camera experience using supported browser camera APIs.

The scanner must have:
- camera permission handling
- rear-camera preference on mobile where available
- live preview
- document framing overlay
- stable-frame quality gate
- automatic or assisted capture
- manual capture
- retake
- torch control when supported
- blur/quality/exposure checks
- document quadrilateral detection where possible
- crop and perspective correction
- upload fallback

The web scanner is **camera/image scanning**, not an ePassport NFC chip reader.

Provide a clean `DocumentReaderProvider` / adapter boundary for future physical readers or mobile NFC integrations.

Do not claim NFC/PKI works unless real hardware and tests confirm it.

## Document detection

Use an appropriate document-localization model/dataset where useful.

Reference Roboflow resource:
https://universe.roboflow.com/2bs/identity-card-xrh4n

Important: this resource is for identity-card localization/object detection, not a complete forgery detector.

## Dataset policy

Do not download massive datasets unnecessarily.

The team explicitly wants to use a **small, representative, license-checked subset** for development/demo.

Create a dataset manifest documenting:
- exact source URL
- direct data/download URL if available
- license
- access requirements
- size
- task
- subset used
- reason for use
- limitations

Never silently use a third-party mirror when the original source has different licensing/access terms.

### Recommended public datasets/resources to investigate and verify

**MIDV-500** — document detection/recognition/OCR/capture robustness.
Source family: Smart Engines / MIDV-500 paper and release.
Do not use it as the primary tamper-localization benchmark.

**MIDV-2020** — document analysis/OCR/recognition/capture conditions.

**FantasyID** — digital identity-document manipulation research.
Official/project:
https://www.idiap.ch/en/scientific-research/data/fantasyid
Zenodo:
https://zenodo.org/records/17063366
Paper:
https://arxiv.org/abs/2507.20808

**DocTamper** — tampered-text/document forensics.
Official repository:
https://github.com/qcf-568/DocTamper
The official repository currently states non-commercial use and an application/password process. Verify terms before use.

**FRLL-Morphs** — face morphing vulnerability research.
https://www.idiap.ch/en/scientific-research/data/frll-morphs

**IDNet** — identity-document analysis.
https://www.kaggle.com/datasets/chitreshkr/idnet-identity-document-analysis
Verify underlying license/source before production use.

**Synthetic passport dataset**:
https://www.kaggle.com/datasets/simongraves/passport-dataset
The Kaggle page currently shows CC BY-NC-ND 4.0. Treat as demo/research only and do not redistribute or use beyond its terms.

**Generated MRZ dataset**:
https://www.kaggle.com/datasets/trainingdatapro/ocr-machine-readable-zone-mrz-detection
Verify licensing/access terms before use.

## Small-subset strategy

Do NOT consume 100k+ images.

Implement configurable sampling, e.g.:
- 100–500 document images per relevant document task for initial development
- 200–1000 tampered samples depending on dataset size and compute
- 100–500 face/morph examples for evaluation
- 50–200 carefully curated demo cases

The exact counts must be chosen after checking available licenses, labels, class balance, and compute.

Keep:
`data/raw` outside Git.

Use scripts to download/prepare only selected subsets.

## Synthetic fraud generation

Create controlled synthetic fraud samples from synthetic/authorized source documents.

Examples:
- name replacement
- DOB modification
- passport/document number modification
- expiry modification
- nationality modification
- photo replacement
- copy/paste text
- splicing
- local blur
- inconsistent compression
- resampling
- stamp insertion/removal
- MRZ manipulation
- screenshot/reprint artifacts
- perspective distortion
- lighting/glare/blur

Metadata:
- sample_id
- source_id
- tampered
- tamper_type
- tampered_region
- field_changed
- severity
- generation_method

Avoid source leakage between train and test.

## OCR

**Primary OCR provider: Google Cloud Vision API** (when configured with valid credentials).

**Fallback OCR provider: Local OCR** (PaddleOCR or existing OCR service).

Architecture:
- Camera/Upload → Supabase private storage → FastAPI → Google Cloud Vision OCR
- → normalized text/coordinates → MRZ parser → document validation → forensics
- → face analysis → identity engine → risk engine

Authentication:
- Preferred: Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json)
- Optional: GOOGLE_VISION_API_KEY for testing only (service account strongly preferred)

Configuration via backend .env:
- `OCR_PROVIDER=google_vision` — enables Google Vision as primary
- `OCR_FALLBACK_ENABLED=true` — uses local OCR when Vision fails/unavailable
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`
- `VISION_MAX_IMAGE_BYTES=10485760` — 10 MB limit
- `VISION_REQUEST_TIMEOUT_SECONDS=30`
- `VISION_MAX_RETRIES=2`

**CRITICAL SECURITY RULES:**
- NEVER expose GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_VISION_API_KEY to the browser
- NEVER prefix these with NEXT_PUBLIC_
- NEVER commit service-account JSON files to Git (protected by .gitignore)
- NEVER send continuous camera frames to Vision (only captured/uploaded images)

Output structured fields with confidence and bounding boxes.

Fields may include:
- full name
- given name
- surname
- document number
- nationality
- date of birth
- sex
- issue date
- expiry date
- visa number/type/entries/stay duration where applicable

If a field cannot be reliably extracted, return unknown/low confidence rather than inventing a value.

**Google Vision is ONLY the OCR/text-extraction layer.** It does NOT replace:
- MRZ check-digit validation
- Document forensics / tamper detection
- Face verification / identity matching
- Identity continuity / entity resolution
- Risk engine / evidence fusion

## MRZ

Implement:
- MRZ localization
- OCR
- parsing
- field normalization
- check-digit validation
- VIZ/MRZ consistency
- date validation

Support TD3 first; add TD1/TD2 and visa formats where feasible.

Use ICAO Doc 9303 as the standards reference.

## Document validation

Create configurable rules for:
- expiry
- issue/expiry relationship
- DOB plausibility
- document-number format
- required fields
- MRZ check digits
- VIZ/MRZ consistency
- visa rules where configured

Record the rule version used for each result.

## Forensic tamper engine

Combine classical computer vision + practical ML signals.

Possible signals:
- copy-move
- splicing
- edge inconsistencies
- local noise inconsistencies
- compression differences
- resampling
- local blur
- suspicious text regions
- photo replacement
- metadata anomalies

Do not present ELA or any single signal as definitive proof.

Return:
- tampered_probability or evidence score
- confidence
- suspicious regions
- signal list
- human-readable explanation
- model version

## Face verification

Pipeline:
Document face
→ quality
→ alignment
→ embedding
+
Live face
→ quality
→ embedding
→ 1:1 similarity
→ calibrated decision

Clearly distinguish:
- face detection
- 1:1 verification
- 1:N identification
- liveness
- morphing attack detection

For demo use only synthetic/authorized subjects.

## Risk/watchlist data

Create provider abstraction:
- SyntheticRiskProvider
- OpenSanctionsProvider
- InterpolProvider
- GovernmentProvider

Default guaranteed demo provider:
`SyntheticRiskProvider`

Synthetic records must be clearly labelled:
**SIMULATED DEMONSTRATION DATA — NOT GOVERNMENT DATA**

Do not scrape or fabricate criminal records.

## Map feature

Add a map to the officer investigation console.

Provide two geographic views:
1. world map
2. India-focused map

Use a mature web mapping solution such as MapLibre GL JS or Leaflet with an appropriate basemap/provider, subject to provider terms and rate limits.

The map should visualize:
- document issuing country/region
- detected country/region
- explicit city/state/address fields only when they are actually present and authorized
- screening/checkpoint location where provided by the application
- relevant authorized/synthetic risk-record locations
- verified public police-station/service locations when available

CRITICAL PRIVACY RULE:
A passport normally does not establish a person's exact residence. Never infer a home address from nationality or issuing country. Do not show an invented residence pin.

Use coarse geography unless an explicit authorized address exists.

When address/city/region is available, show source attribution in the UI:
- `Source: extracted document field`
- `Source: checkpoint metadata`
- `Source: synthetic record`

For police contacts:
- Prefer official government police sources/directories when available.
- In India, provide the national emergency number **112** where appropriate and clearly distinguish emergency contact from a local station number.
- If an exact local number cannot be verified, do not invent it; show the official police website/search link instead.

The map must not become a people-tracking feature.

## Evidence fusion / risk engine

Output:
- risk_level
- risk_score
- confidence
- evidence[]
- recommended_action
- model_versions
- rule_versions

Prefer an explainable weighted evidence/rule engine first; optionally add a trained model only when validation data is sufficient.

Recommended actions:
- CLEAR
- SECONDARY REVIEW
- ESCALATE

The system assists an authorized officer. It does not make autonomous immigration decisions.

## Contradiction engine

Examples:
- passport name vs visa name mismatch
- DOB mismatch
- MRZ vs visible-zone mismatch
- document-rule conflict
- weak face verification
- forensic anomaly
- identity-collision signal
- risk-record match

Return detailed reasons.

## Supabase architecture

Use Supabase for:
- Auth
- PostgreSQL
- private Storage
- application data
- configuration
- audit events

Use private buckets and signed access.

Suggested buckets:
- documents-private
- analysis-artifacts-private
- demo-assets

Enable/test RLS on every sensitive table.

## Core database

Create migrations for at least:
- profiles
- roles
- officers
- screenings
- documents
- document_images
- document_fields
- mrz_records
- document_validations
- forensic_results
- forensic_regions
- face_captures
- face_comparisons
- face_embeddings
- identity_entities
- identity_links
- identity_aliases
- watchlist_entries
- risk_records
- risk_scores
- risk_factors
- reviews
- officer_decisions
- audit_events
- blockchain_anchors
- model_versions
- rule_versions
- system_logs

Use UUIDs, foreign keys, indexes, created_at/updated_at where appropriate, and vector indexing if pgvector is genuinely available.

## Role-based admin system

Roles:
- SUPER_ADMIN
- ADMIN
- OFFICER
- REVIEWER
- AUDITOR

Admin pages:
- `/admin`
- `/admin/users`
- `/admin/roles`
- `/admin/rules`
- `/admin/models`
- `/admin/watchlists`
- `/admin/system-health`
- `/admin/audit`

Do not trust client-provided roles for authorization.

## API

FastAPI backend.

Create a documented API under `/api/v1`.

Suggested endpoints:
- POST `/screenings`
- POST `/documents/upload`
- POST `/documents/{id}/analyze`
- POST `/ocr`
- POST `/mrz/validate`
- POST `/forensics/analyze`
- POST `/face/verify`
- POST `/identity/search`
- POST `/identity/resolve`
- POST `/risk/evaluate`
- POST `/watchlist/screen`
- POST `/officer/decision`
- GET `/screenings/{id}`
- GET `/screenings/{id}/evidence`
- GET `/screenings/{id}/timeline`
- POST `/audit/anchor`
- POST `/audit/verify`
- GET `/health`

Use Pydantic validation, structured errors, timeouts, and authentication/authorization.

Long-running CV jobs must use asynchronous/background processing.

## Frontend

Use:
- Next.js
- TypeScript
- Tailwind CSS
- a consistent component library where appropriate

Pages:
- Login
- Officer Dashboard
- New Screening
- Live Scanner
- Analysis Processing
- Screening Result
- Forensic Evidence
- Face Verification
- Identity Graph
- Watchlist/Risk
- Map
- Review Queue
- Officer Decision
- Audit Trail
- Blockchain/Audit Proof
- Admin
- System Health

The entire iconography, spacing, colors, typography, loading states, empty states, error states, and responsive behavior must be consistent. Replace vague/unrelated icons with clear semantic icons from one icon library. Do not use random emoji as primary UI icons.

## Officer result UI

Top:
- risk level
- recommended action
- confidence

Then evidence cards:
- OCR
- MRZ
- document validity
- tampering
- face verification
- identity continuity
- external/synthetic risk screening
- contradictions

Every warning has a `Why?` explanation.

## Evidence graph

Visual graph:
Document
↕
Identity
↕
Face
↕
Visa
↕
Events
↕
Risk record

Use it for investigation context, not decorative animation.

## Audit / blockchain

Use blockchain only for tamper-evident audit.

Canonicalize verification record → SHA-256 → anchor/reference.

Never store:
- passport images
- face images
- face embeddings
- Aadhaar data
- raw PII
- criminal records
on-chain.

For the 36-hour MVP, prioritize a deterministic local tamper-evident hash chain/Merkle-style proof or another lightweight auditable mechanism. Add a real permissioned chain only if it can be demonstrated without destabilizing the product.

## Offline/degraded mode

At minimum provide graceful degraded states.

Where feasible, support local:
- document capture
- OCR
- MRZ
- basic validation
- face verification
- basic rules

Then sync when connectivity returns.

Never fake successful external verification when offline.

## Architecture

Preferred:

Officer Browser
→ Next.js/Vercel
→ FastAPI
→ CV/ML modules
→ Supabase Postgres/Storage/Auth
→ optional OpenSanctions provider
→ optional government/INTERPOL adapters
→ audit proof

Do not run heavy ML inside Vercel serverless functions just because the web frontend is hosted there.

## Environment variables

Frontend:
- NEXT_PUBLIC_SUPABASE_URL
- NEXT_PUBLIC_SUPABASE_ANON_KEY
- NEXT_PUBLIC_API_BASE_URL

Backend:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- OPENSANCTIONS_API_KEY
- INTERPOL_ENABLED
- INTERPOL_BASE_URL
- INTERPOL_API_KEY
- BLOCKCHAIN_RPC_URL
- BLOCKCHAIN_PRIVATE_KEY

Never expose secrets using `NEXT_PUBLIC_`.

Create `.env.example` only with placeholders.

## Deployment

Frontend:
**Vercel**

Backend AI:
Deploy FastAPI to a Python-capable service appropriate for the selected models/compute.

Database/storage/auth:
**Supabase**

Production browser camera requires HTTPS/secure context and proper permissions.

Verify CORS and the exact production API URL.

## Repository structure

Use/adapt:

```
apps/web
services/api
ml/ocr
ml/document
ml/mrz
ml/forensics
ml/face
ml/identity
ml/risk
database/migrations
database/seed
data/raw
data/processed
data/synthetic
data/demo
scripts
blockchain
docs
  ARCHITECTURE.md
  DATASETS.md
  API.md
  SECURITY.md
  PRIVACY.md
  DEMO.md
  JURY.md
  DECISIONS.md
  IMPLEMENTATION_STATUS.md
tests
```

## Dataset scripts

Create scripts such as:
- `scripts/verify_datasets.py`
- `scripts/download_selected_datasets.py`
- `scripts/prepare_midv.py`
- `scripts/prepare_fantasyid.py`
- `scripts/prepare_doctamper.py`
- `scripts/prepare_morph_data.py`
- `scripts/generate_synthetic_frauds.py`
- `scripts/build_demo_cases.py`

Do not download full 100k+ datasets unless explicitly needed.

## Six-person build ownership

Default allocation:
1. Frontend/scanner/UI
2. FastAPI/backend/integration
3. OCR/MRZ/document validation
4. forensics/face/morphing
5. identity graph/database/risk engine
6. Supabase/security/deployment/audit/blockchain/integration

The agent should optimize responsibilities after inspecting the actual repository.

## 36-hour MVP priority

P0:
- camera/upload scanner
- document detection/rectification
- OCR
- MRZ
- validation
- basic tamper analysis
- face extraction + 1:1 verification
- Supabase persistence
- explainable risk
- officer result UI

P1:
- identity continuity
- contradiction engine
- map
- synthetic watchlist/risk provider
- audit proof

P2:
- OpenSanctions live integration
- advanced morphing detector
- offline sync enhancements
- physical-reader/NFC adapter
- real permissioned blockchain
- advanced multi-spectral adapter

If a P2 feature threatens P0/P1 stability, cut P2.

## Three mandatory demo cases

### Case 1 — obvious document tampering
Show source, altered sample, suspicious region, evidence, and escalation.

### Case 2 — valid document + face mismatch
Document fields/MRZ may pass, but live-face verification produces a review signal.

### Case 3 — killer differentiator
Document PASS
MRZ PASS
Expiry PASS
Face PASS
but identity continuity/forensic/contradiction evidence triggers secondary review.

Use synthetic identities.

## Testing

At minimum test:
- MRZ check digits
- field normalization
- date validation
- OCR schema
- document rules
- face thresholds
- identity search
- risk scoring
- contradiction rules
- RLS
- permissions
- private storage
- API timeouts/failures
- audit hash verification
- end-to-end screening

## Build discipline

At the beginning of every implementation task:
1. Read this file.
2. Inspect repository state.
3. Make a small implementation plan.
4. Implement the minimum coherent slice.
5. Run tests/lint/typecheck/build relevant to the change.
6. Update documentation/status.
7. Verify the user-visible flow.

Never leave the repository in a state where UI claims a backend feature exists when it does not.

## Completion gate

Do not say “complete” until the following have been tested as far as the environment permits:

- Supabase authentication works
- RLS works
- private storage works
- document upload works
- browser camera page works
- OCR works
- MRZ validation works
- document validation works
- forensic result works
- face verification works
- identity search works against synthetic/authorized data
- risk engine works
- map renders
- police-contact sourcing behaves safely
- admin roles work
- audit proof verifies
- Vercel production build succeeds
- FastAPI production build/startup succeeds

For any feature unavailable because of missing external authorization, hardware, dataset, or credentials, show an honest `NOT CONFIGURED` or `MANUAL REVIEW REQUIRED` state and document the exact dependency.

## Jury defense

Prepare concise answers for:
- What is unique?
- Why isn't OCR enough?
- Why isn't face verification enough?
- What is identity continuity?
- Why evidence fusion?
- Why synthetic data?
- How do you prevent false positives?
- Why blockchain?
- Why not store documents on blockchain?
- How do you protect biometrics?
- What happens offline?
- What exactly is real in the prototype?
- What requires government authorization?
- How would this integrate with existing border readers?

## Final principle

The final product must be presented as:

**An explainable AI identity-fraud intelligence layer that augments existing document and biometric verification by correlating document, forensic, identity, and risk evidence for authorized officer review.**

It must be technically honest, privacy-conscious, testable, and feasible.

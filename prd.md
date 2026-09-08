# Product Requirements Document (PRD)
## AI-Based Border Document Screening System

---

## 1. What Is This Product?

A software platform that uses Artificial Intelligence to automatically check passports, visas, ID cards, driving licenses, and permits at border checkpoints. Instead of officers manually reading every document and comparing faces, the system does it in seconds — catching fakes, flagging suspicious travelers, and logging everything for future reference.

---

## 2. The Problem We're Solving

| Problem | Impact |
|---------|--------|
| Manual passport checking is **slow** | Long queues, frustrated travelers, delays |
| Human officers **miss things** | Forged stamps, altered photos, tampered text slip through |
| Fraud is getting **smarter** | AI-generated fakes, deepfakes, cloned documents are hard to spot by eye |
| No **standard process** | Different officers check different things — inconsistent decisions |
| Poor **record keeping** | Hard to trace back who was checked, what was found, and why a decision was made |

---

## 3. Who Uses This System?

| User | How They Use It |
|------|-----------------|
| **Border Officers** | View the dashboard, see alerts, make final pass/flag decisions |
| **Checkpoint Supervisors** | Monitor throughput, review flagged cases, manage officer workload |
| **Intelligence / Investigation Teams** | Search audit logs, track patterns, investigate flagged identities |
| **System Admins** | Manage users, update watchlists, monitor system health |
| **Travelers** (indirect) | Place document on scanner, look at camera — that's it |

---

## 4. What Documents Does It Handle?

- **Passports** (including e-Passports with NFC chips)
- **Visas** (sticker visas, stamp visas, e-Visas)
- **National ID Cards**
- **Driving Licenses**
- **Travel Permits and Work Permits**

---

## 5. Core Features (Functional Modules)

### 5.1 — OCR & Data Extraction

**What it does:** Reads the document image and pulls out all text fields automatically.

- Reads the **MRZ** (Machine Readable Zone — the coded lines at the bottom of passports) using ICAO 9303 standards
- Extracts **visual zone** fields: full name, date of birth, nationality, document number, expiry date, gender, issuing country, visa type/dates
- Validates MRZ **check digits** (built-in error-checking math in passport codes)
- Handles real-world image issues: blurry scans, glare, tilted documents, low light
- Pre-processes images: deskewing (straightening), deblurring, lighting correction

### 5.2 — Document Validation

**What it does:** Checks if the extracted data makes sense and follows the rules.

- Cross-checks MRZ data against the visual zone (e.g., does the printed name match the MRZ name?)
- Validates country codes against ISO standard lists
- Checks field lengths, formats, and expected patterns for each document type
- Verifies issuing authority information
- Flags **anomalies**: mismatched nationality, invalid checksum, unexpected field values, expired documents
- If the document has an **NFC chip** (e-Passport), reads and verifies the chip's digital signature

### 5.3 — Tampering & Forgery Detection

**What it does:** Uses AI to detect if a document has been physically or digitally altered.

**Photo Tampering:**
- Checks if the photo has been replaced (detects printed vs real skin textures)
- Looks for inconsistencies around photo edges — splicing or pasting artifacts

**Text Tampering:**
- Compares fonts across the document — different fonts = possible edit
- Checks for colour/background inconsistencies around text (signs of digital erasing and retyping)

**Stamp Forgery:**
- Reads entry/exit stamps using OCR
- Checks stamp sequence for logic (e.g., can't exit a country you never entered)
- Compares stamp styles against known authentic templates

**Security Feature Checks:**
- If UV/IR scanner hardware is available, verifies fluorescent fibers, inks, holograms, and security threads
- Checks watermark presence and placement against known templates

**Digital Forensics:**
- Runs Error Level Analysis (ELA) — spots areas of an image that have been edited
- Checks image metadata for suspicious info (e.g., wrong camera type, editing software traces)
- Detects copy-move regions (duplicate areas pasted into the document)

### 5.4 — Face Verification & Liveness

**What it does:** Confirms the person holding the document is the person *on* the document.

**1:1 Matching (Person vs Document):**
- Crops the face from the document photo
- Captures a live photo/video of the traveler via camera
- Compares the two faces using deep learning models (ArcFace / InsightFace)
- Returns a confidence score

**Liveness Detection:**
- Prevents spoofing (holding up a printed photo or a phone screen)
- Uses challenges: blink detection, head turn, or passive liveness (texture analysis)

**1:N Matching (Person vs Watchlist):**
- Compares the live face against a database of wanted/flagged individuals
- Connects to INTERPOL, PNR (Passenger Name Record) lists, and national watchlists
- Matching thresholds set to minimize false positives (wrongly flagging innocent people)

### 5.5 — Risk Scoring & Decision Support

**What it does:** Combines all signals into one easy-to-understand risk score.

**Inputs to the score:**
- OCR quality and consistency
- Document validation pass/fail results
- Forgery detection flags
- Face match confidence
- Watchlist hit results
- Document age and expiry status
- Travel history anomalies (from stamps)

**Output:**
- A **risk score** (e.g., Low / Medium / High / Critical)
- **Explainable reasons** in plain language — e.g., *"MRZ checksum failed"*, *"Face match score below threshold"*, *"Entry stamp without matching exit stamp"*
- **Recommended action**: Pass, Secondary Review, or Hold

### 5.6 — Audit Trail & Logging

**What it does:** Records every single check for accountability and future investigation.

- Logs: original document image, extracted data, every analysis result, final decision, officer ID, timestamp
- Stored in an **append-only** (cannot be deleted or modified) database
- Optionally backed by **blockchain** hashing for tamper-proof verification
- Searchable by investigators later
- Compliant with data retention regulations

### 5.7 — External System Integration

**What it does:** Talks to other government and international databases.

| System | Purpose |
|--------|---------|
| **INTERPOL SLTD** | Check if the document is reported stolen or lost |
| **National Visa Database** | Verify visa validity and conditions |
| **Immigration Control System** | Push/pull passenger data and decisions |
| **PNR / Airline Manifests** | Cross-check travel plans against document claims |
| **National Watchlists** | Flag persons of interest |
| **Sanction Lists** | OSINT and sanctions screening |

- All integrations via **REST APIs** with **mutual TLS** (encrypted and authenticated connections)
- Data exchange format: **JSON**

### 5.8 — User Interface

**For Border Officers (Web Dashboard):**
- Shows the scanned document image with highlighted problem areas
- Displays extracted data side-by-side with the document
- Shows risk score with colour coding (green/yellow/red)
- Lists each alert with explanation
- One-click actions: Approve, Flag for Review, Detain
- Search and filter past checks

**For Self-Service Kiosks (Optional):**
- Guides traveler: "Place your passport on the scanner" → "Look at the camera"
- Runs automated check
- If clean → traveler proceeds
- If flagged → alerts an officer silently

---

## 6. Performance Targets

| Metric | Target |
|--------|--------|
| **Processing time per document** | Under **5 seconds** end-to-end |
| **Throughput** | 500–1000+ checks per hour per checkpoint |
| **OCR Accuracy** | 95–99% on standard quality scans |
| **False Negative Rate** (missed forgery) | Below **2%** |
| **False Positive Rate** (wrongly flagged legit doc) | Below **0.1%** |
| **Face Match Accuracy** | 99%+ (on good-quality captures) |
| **System Uptime** | 99.9% |

---

## 7. Security & Privacy Requirements

| Requirement | Details |
|-------------|---------|
| **Encryption in transit** | All data transmitted over TLS 1.3 |
| **Encryption at rest** | All stored data (images, PII, logs) encrypted using AES-256 |
| **Access control** | Role-based access — officers see what they need, admins manage the system |
| **PII handling** | Minimal data storage; comply with GDPR and applicable local privacy laws (e.g., India's DPDP Act) |
| **Biometric data** | Stored only as encrypted embeddings, never raw images long-term |
| **Audit logs** | Immutable, tamper-evident (hashed and signed) |
| **Model security** | ML models encrypted and access-controlled to prevent theft or tampering |
| **Key management** | Centralized key management system (e.g., HashiCorp Vault) |

---

## 8. Datasets for Training & Testing

| Dataset | What It Contains | Use |
|---------|-----------------|-----|
| **MIDV-500 / MIDV-2019 / MIDV-2020** | Clean document images (50 doc types, multiple captures) | OCR training, baseline validation |
| **IDNet** | 837K synthetic document images with diverse fraud types | Forgery detection model training |
| **DocTamper** | 170K tampered document images | Tamper detection training |
| **LFW (Labeled Faces in the Wild)** | Face images in real-world conditions | Face recognition benchmarking |
| **Custom Synthetic Data** | GAN-generated forged documents (morphed photos, fake stamps) | Augmenting rare fraud cases |
| **NIST FRVT Benchmarks** | Standard face recognition test sets | Face matching accuracy evaluation |

---

## 9. Unique Innovations / Differentiators

1. **Multi-Zone Analysis** — Don't just check the whole document. Segment it into zones (photo, text blocks, stamps, watermarks, holograms) and run specialized AI on each zone separately. Catches alterations that whole-document checks miss.

2. **Behavioral & Contextual Signals** — Cross-reference the traveler's story with their documents. Does their visa type match their stated travel plan? Does the itinerary make sense? Flag contradictions.

3. **Adaptive Learning Loop** — When officers flag a missed forgery, it feeds back into the AI model. The system learns new fraud patterns continuously. Synthetic fraud generation (using GANs) fills gaps for rare forgery types.

4. **Edge Computing Option** — Run lightweight AI models on local hardware (e.g., NVIDIA Jetson) at remote or offline checkpoints. No internet needed for basic checks.

5. **OSINT Enrichment** — Optionally check names against open-source intelligence: news, social media, and public sanction databases for hidden risk signals.

---

## 10. Constraints & Assumptions

- The system assumes standard camera/scanner hardware is available at checkpoints (minimum 5MP camera, flatbed or passport scanner)
- UV/IR scanning features only work if specialized scanner hardware is present
- NFC chip reading requires compatible passport reader hardware
- External database access (INTERPOL, watchlists) requires network connectivity and API credentials
- Face matching accuracy depends on camera quality and lighting at the checkpoint
- System must work in both **online** (cloud-connected) and **offline** (edge-only) modes with graceful degradation

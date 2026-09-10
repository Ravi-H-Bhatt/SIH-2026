# Technical Q&A — AI Border Document Screening (SIH26188)

Answers verified against the actual code, not the docs. Each item states
**IMPLEMENTED** or **NOT IMPLEMENTED**, and how it would be built either way.

---

## 1. Blockchain — how is it implemented, what makes it uncrackable?

**NOT IMPLEMENTED.** There is no blockchain. Be careful claiming otherwise in a demo.

What actually exists (`app/services/audit/crypto_anchor.py`):
- A **SHA-256 canonical hash** of each scan's evidence, stored in `scan_records.canonical_hash`.
- Canonical = deterministic JSON (`sort_keys=True`, compact separators) so the same evidence always hashes identically.
- `verify_integrity()` recomputes the hash and compares. Endpoint: `POST /api/v1/scans/{id}/verify-audit`.

What is only config, wired to nothing:
```
BLOCKCHAIN_ANCHOR_ENABLED=false      # read by nothing except a config validator
GOOGLE_BLOCKCHAIN_RPC_URL=...YOUR_PROJECT...   # placeholder, never called
BLOCKCHAIN_ANCHOR_PRIVATE_KEY=       # empty
```
No `web3`, no transaction signing, no RPC call anywhere in the codebase.

**What the hash does and does not give you**
- ✅ Detects **silent tampering**: change a stored field, the recomputed hash differs.
- ❌ Not tamper-*proof*: whoever can edit the DB row can also recompute and overwrite the hash. There is no external witness.
- ❌ SHA-256 is not "uncrackable" because of the algorithm alone; the weakness here is that the hash lives in the same database as the data it protects.

**How to actually implement it**
1. **HMAC-SHA256** with a key held in a KMS/HSM (not in the DB) — stops an attacker with DB write access from forging hashes. Cheapest real win.
2. **Hash chaining**: each record stores `hash(current_evidence + previous_hash)`, forming an append-only chain. Altering record *n* breaks every record after it.
3. **Merkle tree + on-chain anchor**: batch a day's hashes into a Merkle root, publish the single root to a chain (Polygon/Sepolia via `web3.py`), store the tx hash. One transaction per day. This is what makes it externally verifiable — the root is witnessed by a network nobody controls.
4. Optionally RFC 3161 trusted timestamping as a cheaper alternative to a chain.

ℹ️ **Security check performed:** `backend/.env` holds live `GOOGLE_BLOCKCHAIN_API_KEY`, `GOOGLE_VISION_API_KEY` and `OPENSANCTIONS_API_KEY`. Verified **not git-tracked** (`.gitignore` lines 6–7 cover `.env` and `.env.*`), so the keys are not in history. Keep it that way — never commit it.

---

## 2. How is AI implemented here?

**IMPLEMENTED** — three pretrained deep models, no training of our own.

| Task | Model | How it runs |
|---|---|---|
| Face detection | **YuNet** (`face_detection_yunet.onnx`, 232 KB) | `cv2.FaceDetectorYN` — OpenCV DNN, on-device |
| Face recognition | **SFace** (`face_recognition_sface.onnx`, 38 MB) | `cv2.FaceRecognizerSF` — outputs 128-d embedding, on-device |
| OCR | **Google Cloud Vision** (`DOCUMENT_TEXT_DETECTION`) | REST API call, cloud CNN |
| Fallback OCR | Tesseract LSTM / Apple Vision | on-device |

Everything else is **deterministic algorithms, not learned models**: ICAO check digits, ELA, DCT, Canny, FFT, cosine similarity, graph traversal, rule-based risk scoring.

We do not train anything. No `torch`, `tensorflow`, or `scikit-learn` in `requirements.txt` — confirmed by grep.

---

## 3. What do officers do where there is no internet / no device?

**NOT IMPLEMENTED.** The system currently **requires internet**:

| Dependency | Needs internet? |
|---|---|
| Google Vision OCR | **Yes** |
| Supabase Postgres + Storage | **Yes** |
| OpenSanctions screening | **Yes** |
| YuNet + SFace face matching | No — fully local |
| Tesseract / Apple Vision OCR | No — fully local |
| MRZ check digits, ELA/DCT forensics | No — pure computation |

A `REQUIRE_SUPABASE=false` SQLite fallback exists but is a **developer** convenience, not an offline field mode.

**How to implement offline mode**
1. Set `OCR_PROVIDER=local` — Tesseract + Apple Vision already work with zero network.
2. Ship the OpenSanctions dataset as a **local SQLite/FTS5 snapshot**, refreshed when connectivity returns. Removes the last hard network dependency for screening.
3. **Outbox pattern**: write scans to local SQLite with a `synced=false` flag; a background worker pushes to Supabase when online. Officer never blocks on the network.
4. Cache the face gallery locally so 1:N still works (128-d × N floats is tiny — 10k travellers ≈ 5 MB).
5. Keep the SHA-256 anchor local; chain-anchor on reconnect.

Result: full OCR + MRZ + forgery + face matching offline; only live sanctions freshness is degraded.

---

## 4. Someone built a complete fake identity years ago (fake Aadhaar/PAN, or a Pakistani national holding another nation's identity). How do we catch it?

**NOT DETECTABLE by this system today.** Honest answer: if every document is genuinely issued and internally consistent, nothing in our pipeline flags it. This is the hardest problem in the whole domain and we should say so rather than overclaim.

Why our current checks all pass for such a person:
- MRZ check digits → valid (the document is real)
- Forgery forensics → clean (no tampering)
- Face match → passes (it is genuinely their face)
- Watchlist → no hit (unknown identity)
- Identity graph → no prior encounter, or consistent ones

**What we DO catch, and it matters:** the moment they use a **second** identity, the identity graph links the encounters biometrically and raises `IDENTITY_LINK_DIFF_NAME` — same face, different name. That is the one lever we have, and it works (verified: 4 records, one face, 4 names, all linked).

**How to implement real detection**
1. **Issuance-time verification, not border-time** — query the issuing authority's API (UIDAI/Passport Seva) for whether the document was issued and to whom. Our `MRZReference` table is the placeholder for this and is currently empty.
2. **Biometric de-duplication at enrolment** — 1:N against the national gallery when the document is *issued*. A person already enrolled under another name is caught there, not at the border.
3. **Document-history depth signals**: an identity with no school records, no travel history, no financial footprint before year *X* is statistically anomalous. Requires cross-agency data we do not have.
4. **Linguistic / dialect analysis** of the interview, and **document-issuance geography** consistency (born in district A, all documents issued in district B).
5. **Family-graph cross-checks** — a synthetic identity usually has no verifiable relatives.

Bluntly: this is solved by inter-agency data sharing at enrolment, not by a scanner at the gate. Our contribution is catching the *second* use of a face.

---

## 5. How does the MRZ checksum work?

**IMPLEMENTED** — real ICAO 9303 arithmetic, `app/services/ocr/mrz.py:90-107`.

**Algorithm: weights 7-3-1 repeating**
```python
weights = [7, 3, 1]
for i, char in enumerate(data):
    if char == '<':      val = 0
    elif char.isdigit(): val = int(char)
    else:                val = ord(char.upper()) - 55   # A=10 ... Z=35
    total += val * weights[i % 3]
check_digit = total % 10
```

Worked example — document number `Z43R34255`:
```
Z=35 4  3  R=27 3  4  2  5  5
×7  ×3 ×1 ×7   ×3 ×1 ×7 ×3 ×1
245 12 3  189  9  4  14 15 5   → 496 → 496 % 10 = 6
```
So the check digit must be `6`. Any single-character edit changes the sum and fails.

**Which digits we verify (3 of 5)**
| Field | Position (TD3 line 2) | Verified |
|---|---|---|
| Document number | 0–8, CD at 9 | ✅ |
| Date of birth | 13–18, CD at 19 | ✅ |
| Expiry date | 21–26, CD at 27 | ✅ |
| Optional data | CD at 42 | ❌ read, never checked |
| Composite | CD at 43 | ❌ read, never checked |

`mrz_valid = doc_num_valid AND dob_valid AND expiry_valid`.

**Formats supported:** TD3 (passport, 2×44), TD1 (ID card, 3×30), TD2 (travel doc, 2×36).
**Not supported:** MRV-A/MRV-B (visa MRZ).

**To complete it:** verify the composite digit over the concatenated fields — it is the one that catches an attacker who edits two fields so their individual digits still compute.

---

## 6. What CV model do we use? What is the latest? Why not that?

**Using:** YuNet (detection, 2021) + **SFace** (recognition, 2021), both ONNX via OpenCV.

| Model | Year | Dim | Notes |
|---|---|---|---|
| **SFace (ours)** | 2021 | 128 | 38 MB, CPU-fast, bundled with OpenCV Zoo |
| ArcFace R100 | 2019 | 512 | ~99.8% LFW, 250 MB, needs `onnxruntime` |
| AdaFace | 2022 | 512 | Best-in-class on low-quality/surveillance images |
| TransFace / ViT-based | 2023+ | 512 | Highest accuracy, GPU-dependent |

**Why SFace:**
- Runs on a plain CPU at a checkpoint — no GPU at a land border.
- Zero extra dependencies: `cv2.FaceRecognizerSF` is built into `opencv-python-headless`. ArcFace would add `onnxruntime` + `insightface` (~250 MB).
- Published operating threshold (0.363 cosine) we can defend, and our measurements match it: same person 0.60–0.83, different people −0.10 to 0.28.

**Why AdaFace would be better:** printed/laminated passport photo vs live webcam is a **cross-domain, low-quality** comparison, which is exactly what AdaFace was designed for. Upgrade path: drop in the ONNX file, keep the same 1:1 and 1:N code, re-calibrate the threshold on a labelled set. Only the model file and threshold change.

---

## 7. What do our forces use today, and what is novel here?

**Currently in the field:** ICAO-compliant passport readers (MRZ OCR + optional chip read), the ICP/Immigration database lookup, watchlist checks, and an officer's eyes. Verification is essentially *read the document, look up the name, look at the face*.

**What is genuinely novel in this project:**
1. **Cross-Modal Contradiction Matrix** — the real contribution. It does not ask "did each check pass?" but "do the checks **contradict each other**?" A valid chip + a spliced photo = photo substitution on a genuine passport. A valid chip + a face mismatch = impostor with a real passport. These survive every individual check and are invisible to a per-check pass/fail system.
2. **Identity Continuity Graph** — 1:N biometric search across *past* encounters, so the same face under a different name is flagged as synthetic identity hopping. Most checkpoint systems compare only against the document in hand.
3. **Explainable risk fusion** — weighted, per-signal explanations rather than an opaque score, so an officer can justify a detention.
4. **Face-only screening** — identifies a traveller presenting no document at all, by face alone.

**Honest positioning:** the underlying models (SFace, Vision OCR) are off-the-shelf. The novelty is the **correlation and reasoning layer** on top, plus refusing to fabricate confidence when a check did not run.

---

## 8. What are the main ML algorithms applied?

**Learned (deep) models — 3:**
1. **YuNet** — CNN face detector, returns box + 5 landmarks + confidence.
2. **SFace** — CNN embedding network, 112×112 → 128-d vector, trained with a margin-based softmax.
3. **Google Vision OCR** — cloud CNN + sequence model for text detection/recognition.

**Classical algorithms — the rest:**
| Algorithm | Where | Purpose |
|---|---|---|
| **Cosine similarity** | face 1:1 and 1:N | identity comparison |
| **ELA** (Error Level Analysis) | forgery | JPEG recompression residual → splice detection |
| **DCT** (`scipy.fftpack.dctn`) | forgery | frequency-domain compression anomalies |
| **Canny edge detection** | forgery | rigid rectangular boundary around a pasted photo |
| **FFT** (`np.fft.fft2`) | liveness | high/low frequency ratio → screen-replay / print detection |
| **CLAHE** | preprocessing | contrast normalisation before OCR |
| **Levenshtein-style name similarity** | watchlist | fuzzy name matching, threshold 0.86 |
| **Graph construction/traversal** (`networkx`) | identity graph | entity resolution across encounters |
| **ICAO 7-3-1 modulo-10** | MRZ | check digit verification |
| **Weighted linear fusion** | risk engine | explainable score aggregation |

**No trained classifier of our own.** No supervised learning, no dataset, no `.fit()` call anywhere.

---

## 9. What "permutation of facial things" is applied?

**IMPLEMENTED** — this is the multi-face comparison strategy.

**1:1 verification — live face × every document face**
A document may hold several faces (main portrait + ICAO ghost image, or a multi-person page). We compute the cosine against **all** of them and keep the best:
```
doc faces   : 4
per-face    : face 1: 0.269 · face 3: 0.067 · face 2: -0.005 · face 4: -0.017
best        : face 1 @ 0.2688   (threshold 0.363)  → NO MATCH
```
So it is *n* comparisons for *n* document faces, not one.

**Ghost-image disambiguation** — each secondary face is compared to the main portrait:
- matches (≥0.363) → ICAO secondary portrait of the same holder → benign, verification proceeds
- differs → another person is on the page → flagged as not a single-holder credential

Measured: real ghost images score 0.72–0.79 at 17–19% of the main portrait's size; collage faces score −0.08 to 0.22.

**1:N gallery search** — probe face × every stored encounter (N comparisons), ranked by cosine, threshold 0.50 (stricter than 1:1 because false-match probability grows with N).

**New fraud case this catches:** if the traveller matches a *secondary* face rather than the main portrait, that is flagged as possible photo substitution — on a genuine credential the holder is always the main portrait.

---

## 10. Where is ANN applied?

Two readings, both answered:

**(a) Artificial Neural Network — IMPLEMENTED, indirectly.**
The three deep models above (YuNet, SFace, Vision OCR) are CNNs, executed through **OpenCV's DNN module** reading ONNX graphs. We run inference only; we never train or backprop. There is no hand-built ANN, no `MLPClassifier`, no `torch.nn`.

**(b) Approximate Nearest Neighbour — NOT IMPLEMENTED.**
1:N search is a **brute-force linear scan**: every gallery embedding is compared, capped at 500 records (`MAX_GALLERY`). At 128 dimensions this is a single matrix multiply and is genuinely fast to ~100k records.

**How to implement ANN search** when the gallery grows past ~1M:
- **FAISS** (`IndexIVFFlat` or `IndexHNSWFlat`) — sub-linear search, the standard choice.
- **pgvector** on the existing Supabase Postgres — add a `vector(128)` column with an HNSW index and search in SQL. Least new infrastructure, so the natural next step here.
- Note the trade-off: ANN is *approximate*, so it can miss a true match. For a border watchlist, tune `nprobe`/`ef_search` for high recall and accept the latency.

---

## 11. Would RGB / UV / IR scanning improve the system?

**NOT IMPLEMENTED** — we process a single visible-light image. UV appears only as *advice text* in `pattern_memory.py` ("recommend UV lamp inspection"), never as a captured channel.

**Yes, it would improve it substantially** — this is the biggest accuracy gain available, because most physical security features are deliberately invisible in RGB:

| Channel | Reveals | Catches |
|---|---|---|
| **UV (365 nm)** | Fluorescent fibres, UV-reactive inks, security print | Counterfeit substrate, reprinted laminate — invisible in RGB |
| **IR (850 nm)** | B900 ink, laser-engraved data, IR-opaque inks | Photo substitution, altered text (the original shows through) |
| **Coaxial / oblique light** | Holograms, OVI, embossing, intaglio relief | Flat reprints of a 3D security feature |
| **RGB (current)** | Visible print, portrait | Only crude digital edits |

**How to implement:**
1. Use a multi-spectral document scanner (Regula 70x9, Access-IS ATOM, 3M AT9000) — these already output RGB/UV/IR image sets over USB.
2. Per-channel detectors: UV fluorescence pattern match against a per-country template library; IR channel checked for text that should vanish or persist.
3. **Cross-channel contradiction** — feeds our existing Contradiction Matrix naturally: "visible print clean, but UV substrate does not fluoresce" is exactly the class of finding this architecture is built to reason about.
4. Would raise physical-forgery detection far above what ELA/DCT can achieve, since those only detect *digital* manipulation.

---

## 12. Full pipeline, architecture, and every library used

### Stack
| Layer | Technology |
|---|---|
| Frontend | Next.js 16.3.4 (Turbopack), React 19, TypeScript |
| Backend | FastAPI 0.115, Uvicorn, Python 3.12 |
| Database | Supabase PostgreSQL (Supavisor pooler), SQLAlchemy 2.0 |
| Storage | Supabase Storage, private buckets + short-lived signed URLs |
| Auth | JWT (python-jose), bcrypt (passlib), Google OAuth via Supabase |

### The 10 pipeline stages (`app/services/pipeline.py`)

| # | Stage | Library / algorithm | Output |
|---|---|---|---|
| 1 | **OCR extraction** | Google Cloud Vision REST → fallback `pytesseract` / Apple Vision; `Pillow` + `cv2` CLAHE preprocessing | raw text + lines |
| 2 | **MRZ parse + check digits** | own `mrz.py`, ICAO 9303 7-3-1 mod-10, anchored regex TD1/TD2/TD3 | fields + `mrz_valid` |
| 3 | **Field validation** | own `validation_service.py`, `datetime`, 269-code ISO 3166-1 set | expiry / DOB / format / country flags |
| 4 | **Forgery forensics** | `Pillow ImageChops` (ELA), `scipy.fftpack.dctn` (DCT), `cv2.Canny` (splice), PIL `_getexif()` | anomaly score + issues |
| 5 | **Face detect + 1:1** | `cv2.FaceDetectorYN` (YuNet) → `alignCrop` → `cv2.FaceRecognizerSF` (SFace) → cosine | raw cosine vs 0.363 |
| 6 | **Liveness** | `numpy.fft.fft2` frequency ratio + edge variance | live / not / unassessed |
| 7 | **Identity graph 1:N** | `numpy` cosine + `networkx` graph, threshold 0.50 | links + hopping anomalies |
| 8 | **Watchlist / sanctions** | **OpenSanctions** `/match` REST (`algorithm=logic-v1`, threshold 0.70) via `urllib`; 9 local synthetic rows | hits + severity |
| 9 | **Contradiction matrix** | own `contradiction_engine.py` rule correlation | 5 verification streams |
| 10 | **Risk fusion + anchor** | own `risk_engine.py` weighted sum; `hashlib` SHA-256 canonical digest | score, decision, hash |

### Key API endpoints
```
POST /api/v1/scans                  upload document and/or face → full pipeline
GET  /api/v1/scans?include_images   list travellers (+ signed photo URLs)
POST /api/v1/scans/{id}/decision    officer decision (officer+ role)
POST /api/v1/scans/{id}/verify-audit  recompute and compare SHA-256
POST /api/v1/face/compare           1:1 — two images → cosine + verdict
POST /api/v1/face/search            1:N — one face → ranked DB matches
GET  /api/v1/face/gallery           gallery health / comparable embeddings
GET  /api/v1/dashboard/stats|map    aggregates and operations map
```

### External APIs
| Service | Use | Auth |
|---|---|---|
| Google Cloud Vision | primary OCR | API key |
| OpenSanctions | sanctions/PEP/terror screening | ApiKey header |
| Supabase | Postgres + object storage | service-role key |
| INTERPOL SLTD | **NOT IMPLEMENTED** — flag exists, no client | — |

### Risk weights (`risk_engine.py`)
```
contradiction found      → floor at escalated score (75–98)
identity graph anomaly   → floor 85 (critical) / 65
forgery anomaly          → score × 0.35
MRZ invalid (when req'd) → +25
expired document         → floor 80  (critical, hold)
biometric mismatch       → +35
biometric not performed  → +20
liveness failed          → +45
watchlist critical       → +85
```
Bands: ≥80 critical/hold · ≥50 high/review · ≥25 medium/review · else low/pass

### Biometric thresholds (raw SFace cosine, no rescaling)
```
FACE_MATCH_COSINE_THRESHOLD    = 0.363   # 1:1, hard floor in code
FACE_IDENTITY_MATCH_THRESHOLD  = 0.50    # 1:N, stricter than 1:1
FACE_QUALITY_THRESHOLD         = 0.6     # min YuNet detector confidence
```

---

## Extra questions you did not ask but will be asked

**Is the ePassport chip / PKI verified?**
**NOT IMPLEMENTED.** `chip_pki_status` is an HTTP form field the client sends. No BAC/PACE, no DG1/DG2/SOD read, no CSCA/Document-Signer certificate chain, no passive authentication. To implement: NFC reader (PC/SC), read SOD, verify the DS certificate against the CSCA masterlist, then hash-compare DG1/DG2.

**Which document types actually work?**
Passport/MRZ is solid. **No document-type classifier.** Visa: 0 of 4 required fields extracted, no MRV parser. Driving licence and permit: no parsing path. The only non-passport branch is Aadhaar-shaped.

**Why does Overall Anomaly Index show 0/100 with flags listed?**
Each forgery weight is added only *inside* its own `if flag` branch, and the sub-detectors return hardcoded constants (5.0/10.0/12.0) in the common case, so the index floors at 0. The flags shown below it come from `risk_score.explanations`, a different field. Known, unfixed.

**Is stamp forgery or text manipulation detected?**
**NOT IMPLEMENTED.** No stamp/seal detector, no font/kerning/baseline analysis, no copy-move detection. Metadata analysis is a substring match against 7 editor names.

**What is the accuracy?**
We have no labelled test set, so there is no honest accuracy figure. What is measured: same-person pairs 0.60–0.83 cosine, different-person −0.10 to 0.28, clean separation at 0.363. SFace's published LFW accuracy is ~99.6%, but that is same-domain and does not transfer to printed-vs-webcam.

**What is deliberately NOT faked?**
A design rule worth stating: the system never invents a value it did not measure. Missing fields render `NOT READ`, an unread MRZ says so, a biometric that did not run reports `not performed` with a machine-readable reason, and an unverifiable comparison is `NOT_COMPARABLE` rather than a similarity of zero. Earlier versions fabricated a full passport (`JOHN DOE`, `P<INDDOE...`, a valid future expiry) whenever OCR failed, and remapped any cosine above 0.30 into a passing 0.70+ score. Both are removed.

---

# Part 2 — Follow-up answers

## 13. I put a Google Blockchain API key in `.env`. If I turn the flag on, does it become blockchain?

**No.** Turning `BLOCKCHAIN_ANCHOR_ENABLED=true` changes nothing, for two reasons.

**Reason 1 — there is no code to switch on.** Verified by grep, the flag is read in exactly two places, neither of which writes to a chain:
```
app/core/config.py:383       inside a property called blockchain_can_write
scripts/verify_supabase.py:176   a diagnostic that just prints the status
```
No file in `app/services/` ever calls the RPC URL. The pipeline computes SHA-256 and stops. Flipping the flag makes `blockchain_can_write` return `True` and nothing else happens.

**Reason 2 — an API key cannot write to a chain.** This is the important part:

| What you need | What you have |
|---|---|
| **RPC access** (permission to talk to a node) | ✅ the API key gives you this |
| **A funded wallet** (private key + ETH for gas) | ❌ `BLOCKCHAIN_ANCHOR_PRIVATE_KEY=` is empty |
| **A real RPC URL** | ❌ yours still says `.../projects/YOUR_PROJECT/...` — a placeholder |

The API key only authenticates you to Google's node. Writing data costs **gas**, which is paid from a wallet you control. No wallet, no write. Reading is free; writing never is.

So today it is **SHA-256 hashing only** — which is genuinely useful, just not a blockchain.

---

## 14. How do we implement blockchain, easily?

Three options, cheapest first. **Option A is enough for a hackathon and is honest.**

### Option A — Hash chain (no blockchain, no cost, ~1 hour)
Each record stores the hash of the previous one. Altering record *n* breaks every record after it, so tampering is detectable without any external network.

```python
# in pipeline.py, replacing the plain hash call
prev = db.query(ScanRecord).order_by(ScanRecord.created_at.desc()).first()
prev_hash = prev.canonical_hash if prev else "0" * 64

payload["previous_hash"] = prev_hash          # chain the records together
canonical_sha256, _ = crypto_anchor.generate_canonical_hash(payload)
```
Add one column: `previous_hash = Column(String(64))`. Verification walks the chain and recomputes.
**Call it what it is:** "an append-only cryptographic audit chain". Not blockchain — but the tamper-evidence property is real, and a judge who knows the field will respect the accuracy.

### Option B — Merkle root on a public testnet (~half a day)
One transaction per day covers unlimited scans, so gas is negligible on a testnet.

```bash
pip install web3 eth-account
```
```python
from web3 import Web3
import hashlib

def merkle_root(hashes: list[str]) -> str:
    layer = [bytes.fromhex(h) for h in sorted(hashes)]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])                      # duplicate the odd tail
        layer = [hashlib.sha256(layer[i] + layer[i + 1]).digest()
                 for i in range(0, len(layer), 2)]
    return layer[0].hex()

def anchor_daily_root(root_hex: str) -> str:
    w3 = Web3(Web3.HTTPProvider(settings.blockchain_rpc_endpoint))
    acct = w3.eth.account.from_key(settings.BLOCKCHAIN_ANCHOR_PRIVATE_KEY)
    tx = {
        "from": acct.address,
        "to": acct.address,                # self-send; the payload is the point
        "value": 0,
        "data": "0x" + root_hex,           # the Merkle root, immutable once mined
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 30000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        "chainId": settings.BLOCKCHAIN_CHAIN_ID,
    }
    signed = acct.sign_transaction(tx)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()
```

**Setup steps**
1. Fix the RPC URL — replace `YOUR_PROJECT` with your real GCP project id.
2. Create a wallet: `w3.eth.account.create()`. Put the private key in `.env`, the address in `BLOCKCHAIN_ANCHOR_FROM_ADDRESS`.
3. Fund it from a **Sepolia faucet** (free test ETH — sepoliafaucet.com).
4. Store `tx_hash` + `merkle_root` in a new `audit_anchors` table.
5. Verify: fetch the tx from any block explorer, recompute the root from your stored hashes, compare.

**Why this is the right design:** you never put personal data on-chain (irreversible and a privacy violation) — only a 32-byte root that proves *"these records existed in this exact state at this time"*.

### Option C — Hyperledger Fabric / private chain
Realistic for a government deployment, wrong for a hackathon. Needs multiple orgs running peers and an ordering service. Weeks of work.

### What makes it strong
- **SHA-256**: changing one bit changes ~half the output bits; no known preimage or collision attack.
- **Merkle tree**: altering any single record changes the root, so one 32-byte value protects the whole batch.
- **On-chain root**: the record sits in a ledger nobody controls. This is the only step that makes it tamper-*proof* rather than tamper-*evident* — an insider with DB access still cannot rewrite history.
- **Missing today**: the hash lives beside the data it protects, so an admin can recompute it. Option A fixes most of this; Option B fixes it properly.

---

## 15. What are the maps used for?

**IMPLEMENTED** — `GET /api/v1/dashboard/map`, rendered by `OperationsMapPanel` (dashboard + supervisor) and `LocationMap` (single scan).

**Two kinds of marker**
| Marker | Where it comes from |
|---|---|
| **Checkpoint** | `CHECKPOINT_LATITUDE/LONGITUDE` from config — your gate's fixed position, with total scans and flagged count |
| **Origin** | The document's **issuing country**, mapped to a country centroid via `geo_reference.COUNTRY_CENTROIDS` |

**What it is genuinely useful for**
1. **Origin-flow intelligence** — which nationalities are arriving at this gate, and which are being flagged. Spot a sudden spike from one country.
2. **Multi-checkpoint view** — a supervisor sees load and flag rate across gates at once.
3. **Risk colouring** — critical/high scans are visibly distinct, so a cluster stands out.

**One honest limitation, stated in the code and the UI:** an origin marker is a **country centroid, not an address**. A UAE passport plots at the geographic middle of the UAE, not where the holder lives. `geo_reference.py` says so, and the API returns a `geocode_note` to that effect. Anyone claiming these are real residence geocodes is misreading the data.

**Future improvements**
- Route/trajectory lines from origin → checkpoint to visualise transit corridors.
- Heatmap of flagged scans per corridor to reveal smuggling routes.
- Real geocoding of the document address field (a paid geocoder), only where the address was actually read.
- Time-slider replay of crossings — useful for investigating a coordinated group.

---

## 16. Fake IDENTITY vs fake DOCUMENT — how is each detected?

These are two different problems and the system handles them very differently. This distinction is the clearest way to explain the project.

| | **Fake document** | **Fake identity** |
|---|---|---|
| What it means | The paper/chip is forged or altered | The paper is genuine, the *person* behind it is not |
| Example | Photo swapped, DOB edited, counterfeit booklet | Real Aadhaar obtained years ago with false particulars |
| Attacks | the credential | the enrolment process |
| **Our detection** | ✅ **Good** | ⚠️ **Only on the second use** |

### A. Fake DOCUMENT — detected, 4 independent ways

1. **MRZ check digits** (`mrz.py`) — ICAO 7-3-1 mod-10 over document number, DOB, expiry. Catches a forger who edits a field and forgets to recompute its digit. **Important limitation: check digits do NOT protect the name — see §18.**
2. **Photo-substitution forensics** (`forgery_service.py`) — ELA finds JPEG recompression mismatch where a photo was pasted; Canny edge density finds the rigid rectangular boundary of a glued portrait.
3. **MRZ vs visual-zone cross-check** — the printed text and the machine-readable strip must agree. Forgers routinely alter one and forget the other; the Contradiction Matrix catches the disagreement.
4. **Face vs portrait** — if the portrait was replaced, the live traveller matches the document but not the *original* holder; combined with a valid chip this yields the `PHOTO_SUBSTITUTION_ON_GENUINE_DOCUMENT` classification.

**Gaps:** no stamp/seal forgery detector, no font/kerning analysis for text edits, EXIF check is a 7-word keyword scan, composite check digit unverified, and chip PKI is simulated.

### B. Fake IDENTITY — mostly NOT detected today

If the document is genuinely issued and the face genuinely belongs to the holder, **every one of our checks correctly passes.** MRZ valid, no tampering, face matches, no watchlist hit. There is nothing to find in the document, because the lie was told years earlier at the enrolment counter.

**The one thing we DO catch, and it is real:** the moment that person uses a **second** identity, the Identity Continuity Graph links the two encounters biometrically and raises `IDENTITY_LINK_DIFF_NAME` — *same face, different name*. Verified working: 4 records, one face, four different names, all linked at cosine 0.56–0.75.

So our honest claim is: **we cannot validate an identity's origin, but we can prove one face is using multiple identities.**

### C. The Pakistan / Aadhaar scenario, specifically

*"Someone from another country built a full Indian identity, or an Indian built a foreign one. How do we know?"*

**Today: we do not**, if they present only that one identity and it was genuinely issued. Saying otherwise would be dishonest.

**What would actually catch it**
1. **Verify against the issuer, not the paper** — call UIDAI / Passport Seva to confirm the document was issued *and to this biometric*. Our `MRZReference` table is the hook for this and is currently empty. This is the single highest-value addition.
2. **Biometric de-duplication at enrolment** — 1:N against the national gallery *when the document is issued*. A face already enrolled under a different name is caught there. Border-time is too late.
3. **Footprint-depth analysis** — a genuine identity has school, tax, medical, and travel history. A synthetic one begins abruptly. Needs cross-agency data.
4. **Issuance-geography consistency** — born in district A but every document issued in district B, far from any family link, is a known pattern.
5. **Family-graph verification** — synthetic identities rarely have verifiable relatives.
6. **Linguistic/dialect screening** during the interview — human-led, informed by our risk flags.

**The point to make:** a scanner at the gate cannot solve enrolment fraud. It is solved by inter-agency verification at issuance. Our contribution is making the *reuse* of a face impossible to hide.

---

## 17. Future roadmap, short

Ordered by value per unit of effort.

| Priority | Item | Effort | Why |
|---|---|---|---|
| 1 | **Fix the forgery anomaly index** (stuck at 0/100) | hours | An existing feature is silently dead |
| 2 | **Real chip PKI** — SOD read + CSCA chain | days | Replaces a simulated field with real cryptography |
| 3 | **UV/IR multi-spectral capture** | days + hardware | Biggest accuracy jump; most security features are invisible in RGB |
| 4 | **Issuer API verification** (UIDAI / Passport Seva) | days | The only real answer to fake identity |
| 5 | **Offline mode** — local OCR + sanctions snapshot + outbox sync | days | Border posts genuinely lack connectivity |
| 6 | **Hash chain → Merkle → on-chain anchor** | hours → days | Makes the audit trail tamper-proof, not just tamper-evident |
| 7 | **Visa / DL / permit parsing + doc-type classifier** | days | Required by the problem statement, currently absent |
| 8 | **Stamp forgery + text-manipulation detectors** | days | 2 of 4 required tampering use cases |
| 9 | **pgvector for 1:N search** | hours | Brute-force scan won't scale past ~100k |
| 10 | **AdaFace upgrade** | hours | Better on printed-vs-webcam cross-domain matching |
| 11 | **Labelled test set + accuracy metrics** | days | We currently have no defensible accuracy number |

**One-line summary for a judge:** we detect *forged documents* well and *reused faces* reliably; verifying that an identity was legitimately issued in the first place requires issuer-side integration, which is the next milestone.

---

## 18. If someone changes the NAME, must they change the MRZ too?

**No. And this is the most important limitation to understand about check digits.**

Reproduce it yourself: `./venv/bin/python mrz_tamper_demo.py`

### Why the name is unprotected

TD3 has 5 check digits. **Every one of them is on line 2.** The name lives on **line 1**, which has **no check digit at all**.

```
LINE 1  P<INDDOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<   <-- name here, ZERO check digits
LINE 2  P1234567<1IND9001011M3110153<<<<<<<<<<<<<<06
                 ^        ^        ^             ^^
                 CD       CD       CD            CD composite
              docnum     dob     expiry        optional
```

Even the **composite** digit (position 43) only covers line-2 fields — positions 0–9, 13–19 and 21–42. It never touches line 1.

So a forger changing the name recomputes **nothing**.

### Measured results

| Attack | Check digits | Our verdict |
|---|---|---|
| Genuine document | all valid | ✅ ACCEPTED — correct |
| **Change name only** (`DOE JOHN` → `KHAN IMRAN`) | still all valid | ❌ **ACCEPTED — we miss it** |
| Change DOB, fix its own digit, leave composite stale | field digits valid, composite wrong | ❌ **ACCEPTED — we miss it** |
| Change DOB, forget the digit | DOB digit fails | ✅ REJECTED — caught |

So the honest rule:

> Check digits catch **careless** forgery of the document number, DOB and expiry. They catch **nothing** about the name, and nothing at all if the forger recomputes the digit properly.

### What SHOULD catch a name change

1. **MRZ vs visual-zone comparison** — the printed name on the data page vs the MRZ name. A forger must edit both consistently. **NOT IMPLEMENTED here:** `parse_mrz_lines(visual_fallback=...)` only uses the visual zone to *fill missing* fields, never to *cross-check* them. There is no name-comparison code anywhere.
2. **The ePassport chip** — the name sits in DG1, and DG1's hash is inside the SOD, which is signed by the issuing country's Document Signer certificate. Editing the printed name cannot forge that signature. This is the real defence. **NOT IMPLEMENTED** (chip status is a form field, §"Is the ePassport chip verified").
3. **Issuer lookup** — ask the issuing authority what name that document number was issued under. **NOT IMPLEMENTED** (`MRZReference` table is empty).
4. **Face + identity graph** — does not verify the name, but catches the same face appearing under a *different* name across encounters. ✅ **This part works.**

### Easiest fix (worth doing before the demo)

Add a VIZ-vs-MRZ consistency check. The visual name is already extracted into `visual_fields["holder_name"]` and the MRZ name into `parsed["holder_name"]` — they are simply never compared:

```python
# in ocr_service.process_document, after parsing the MRZ
mrz_name = (parsed.get("holder_name") or "").strip().upper()
viz_name = (visual_fields.get("holder_name") or "").strip().upper()

if mrz_name and viz_name:
    # Compare on a normalised token set: OCR reorders and drops middle names,
    # so exact equality would false-positive constantly.
    if set(mrz_name.split()) != set(viz_name.split()):
        flags.append(
            f"NAME MISMATCH: MRZ reads {mrz_name!r} but the printed visual zone "
            f"reads {viz_name!r} — possible data-page alteration"
        )
```

The Contradiction Engine already looks for flags containing `"mismatch"` and raises `VISUAL_ZONE_MANIPULATION`, so this one flag would light up the existing matrix row with no other changes.

**Say this in the demo:** "check digits protect the numeric fields, not the name — the name is protected by the chip signature and by MRZ-to-print consistency, which is our next milestone." That answer is more credible than claiming the checksum covers everything.

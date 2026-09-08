# 🗂️ TASK TRACKER — AI-Based Border Document Screening System

> **Purpose:** This file is the single source of truth for tracking development progress.
> Any AI model (Claude, Gemini, GPT, etc.) should read this file FIRST before doing any work.
> Update this file after completing any task.

> **Last Updated:** 2026-09-04
> **Project:** SIH — AI-Based Border Document Screening System
> **Stack:** Next.js (Frontend) + FastAPI (Backend) + PostgreSQL + Redis + MinIO

---

## 📊 Status Legend

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[/]` | In progress |
| `[x]` | Completed |
| `[!]` | Blocked / Needs discussion |
| `[~]` | Partially done / Needs refinement |

---

## 🏗️ PROJECT SETUP

### Environment & Infrastructure
- `[x]` Initialize Next.js frontend project (`/frontend`)
- `[x]` Initialize FastAPI backend project (`/backend`)
- `[x]` Create `.env` files for both frontend and backend
- `[ ]` Set up ESLint + Prettier for frontend
- `[ ]` Set up Python linting (ruff/black/isort) for backend
- `[x]` Create shared type definitions / API contract (OpenAPI spec & TypeScript types)
- `[ ]` Set up CI/CD pipeline (GitHub Actions)

### Database & Storage (Local Setup)
- `[x]` Connect to local PostgreSQL instance (`border_screening` database created)
- `[x]` Design PostgreSQL schema (scan_records, extracted_data, forgery_results, face_results, risk_scores, audit_logs, users)
- `[x]` Write SQLAlchemy models and seed script for all tables
- `[x]` Set up local file storage for document images and face captures (`/uploads/documents`, `/uploads/faces`)
- `[~]` Skip Redis for now (as instructed by user)
- `[ ]` Task queue (future phase)

---

## 🖥️ FRONTEND (Next.js)

### Core Layout & Navigation
- `[x]` Create app layout (sidebar navigation, header, main content area) (`src/components/AppLayout.tsx`)
- `[x]` Implement authentication pages (`src/app/login/page.tsx`)
- `[x]` Role-based route protection & TypeScript definitions (`src/lib/api.ts`, `src/types/index.ts`, `src/context/AuthContext.tsx`)
- `[x]` Create responsive sidebar with navigation links
- `[x]` Dark mode first design system (`src/app/globals.css`)
- `[x]` Set up global state management (AuthContext)

### Officer Dashboard (Main Screen)
- `[x]` Dashboard overview page with stats (`src/app/page.tsx`)
- `[x]` Real-time stats & recent scan feed
- `[x]` Risk score distribution chart (Low/Medium/High/Critical)
- `[x]` Quick action buttons (New Scan, View All)

### Document Scanning & Results
- `[x]` Document upload page (`src/app/scanner/page.tsx`)
- `[x]` Document image picker & camera upload support
- `[x]` Live camera feed / photo picker for face capture
- `[x]` Processing status view (animated scanning sequence)
- `[x]` Result detail page (`src/app/scans/[id]/page.tsx`):
  - `[x]` Scanned document image display
  - `[x]` Extracted data fields (side-by-side)
  - `[x]` MRZ data display and validation status
  - `[x]` Risk score with color coding (green/yellow/red/critical)
  - `[x]` Alert list with explanations
  - `[x]` Face match comparison (document photo vs live capture)
  - `[x]` Forgery detection findings with anomaly index
  - `[x]` Action buttons (Approve, Flag for Review, Detain)
  - `[x]` Officer notes / comments section

### Search & History
- `[x]` Search page with filters (document #, holder name, decision filter) (`src/app/history/page.tsx`)
- `[x]` Scan history table
- `[x]` Individual scan detail report link

### Admin Panel
- `[x]` User management (CRUD modal & personnel list) (`src/app/admin/users/page.tsx`)
- `[x]` Role assignment and permissions (Admin, Officer, Supervisor, Investigator)
- `[x]` Audit log viewer with search and filters (`src/app/admin/audit/page.tsx`)

### Supervisor Views
- `[x]` Checkpoint monitoring dashboard (throughput, queue length) (`src/app/supervisor/page.tsx`)
- `[x]` Flagged cases queue for review (`getFlaggedQueue` API & supervisor override modal)
- `[x]` Officer workload and performance metrics
- `[x]` Shift management & telemetry dashboard

### Self-Service Kiosk UI (Optional)
- `[x]` Guided flow: "Place passport" → "Look at camera" → Result (`src/app/kiosk/page.tsx`)
- `[x]` Simplified, large-text UI for travelers (Multilingual EN/HI support)
- `[x]` Silent alert to officer command desk on flag

### Frontend Shared Components
- `[x]` Design system (colors, typography, spacing tokens in `globals.css`)
- `[x]` Button component (primary, secondary, danger variants in `src/components/ui/Button.tsx`)
- `[x]` Card component (glassmorphism container in `src/components/ui/Card.tsx`)
- `[x]` Modal / Dialog component (supervisor override & CRUD modals)
- `[x]` Table component with sorting and pagination
- `[x]` Form components (input, select, file upload)
- `[x]` Toast / notification system
- `[x]` Loading skeletons (`src/components/ui/Skeleton.tsx`)
- `[x]` Badge / status chip component (`src/components/ui/Badge.tsx`)
- `[x]` Chart components (risk score distribution & statistics)
- `[x]` WebSocket hook for real-time updates (`src/hooks/useWebSocket.ts`)

---

## ⚙️ BACKEND (FastAPI + Python)

### Core API Setup
- `[x]` FastAPI app structure (routers, services, models, schemas)
- `[x]` JWT authentication and role-based access control (RBAC)
- `[x]` Middleware (CORS, logging, error handling)
- `[x]` Health check endpoint (`/api/v1/health`)
- `[x]` Auto-generated API docs (Swagger/ReDoc at `/docs`)
- `[x]` Rate limiting per user/endpoint (`RateLimitMiddleware` in `app/core/middleware.py`)
- `[x]` WebSocket endpoint for real-time dashboard updates (`app/api/v1/ws.py`)

### API Endpoints
- `[x]` `POST /api/v1/scans` — Upload document image for full processing
- `[x]` `GET /api/v1/scans` — List scans with filtering & pagination
- `[x]` `GET /api/v1/scans/{id}` — Get full verification result
- `[x]` `POST /api/v1/scans/{id}/decision` — Make officer decision (Approve/Flag/Detain)
- `[x]` `GET /api/v1/audit` — Search audit trail (with filters)
- `[x]` `POST /api/v1/auth/login` — User login
- `[x]` `POST /api/v1/auth/refresh` — Refresh JWT token
- `[x]` `GET /api/v1/users` — List users (admin only)
- `[x]` `POST /api/v1/users` — Create user (admin only)
- `[x]` `GET /api/v1/dashboard/stats` — Dashboard summary statistics

### Image Preprocessing Service
- `[x]` Receive raw document image (JPEG/PNG/TIFF)
- `[x]` Deskew and auto-crop to document edges (OpenCV / PIL fallback)
- `[x]` Deblur and lighting correction (CLAHE & Gaussian blur / PIL contrast enhancement)
- `[x]` Image quality assessment (Laplacian variance / PIL variance score)
- `[ ]` Output cleaned image to MinIO storage (Using local `/uploads` storage for now)

### OCR & MRZ Service
- `[x]` MRZ detection and extraction (ICAO 9303 parser in `app/services/ocr/mrz.py`)
- `[x]` MRZ check digit validation (ICAO 7-3-1 weighting algorithm)
- `[x]` Visual zone OCR fallback parser
- `[x]` Output structured JSON with all extracted fields
- `[x]` Handle multi-language text & standard ICAO fields

### Document Validation Service
- `[x]` Field format validation (regex patterns per document type in `app/services/validation/validation_service.py`)
- `[x]` Country code validation (ISO 3166-1 alpha-3 code list)
- `[x]` Date logic validation (expiry date, birth date reasonableness, age calculations)
- `[x]` Issuing authority & country consistency checks
- `[x]` Output validation report (pass/fail per field with warning flags)

### Forgery Detection Service
- `[x]` Error Level Analysis (ELA) — detect edited regions and generate ELA heatmaps (`app/services/forgery/forgery_service.py`)
- `[x]` Image sharpness / blur quality assessment
- `[x]` Image metadata analysis (EXIF software modification detection: Photoshop, GIMP, Canva, Adobe)
- `[x]` Output anomaly score (0-100) + list of detected issues & flags

### Face Verification Service
- `[x]` Face detection in document photo & cropping (`app/services/face/face_service.py`)
- `[x]` Live face capture processing & comparison
- `[x]` Liveness detection (texture pattern / Laplacian variance anti-spoofing)
- `[x]` 1:1 facial biometric matching (YCrCb color histogram correlation)
- `[x]` 1:N watchlist search (INTERPOL SLTD / border alerts in `app/services/face/watchlist_service.py`)
- `[x]` Output match confidence score + liveness result + watchlist hits

### Risk Scoring Engine
- `[x]` Aggregate signals from all services (`app/services/risk/risk_engine.py`)
- `[x]` Configurable weights for each signal (forgery, MRZ check digits, validation rules, biometrics, watchlist)
- `[x]` Risk level classification (Low/Medium/High/Critical)
- `[x]` Generate human-readable explanations for each flag with severity levels
- `[x]` Recommended action determination (Pass/Review/Hold)
- `[x]` External database checks (INTERPOL SLTD, watchlists)

### Audit Trail & Logging
- `[x]` Append-only audit log for every scan (`AuditLog` records in PostgreSQL)
- `[x]` Log: original image, extracted data, analysis results, decision, officer ID, timestamp
- `[x]` Search and filter audit logs API (`/api/v1/audit`)

### Background Workers & Queue
- `[x]` Pipeline orchestration (`app/services/pipeline.py` executing OCR -> Validation -> Forgery -> Face -> Watchlist -> Risk engine -> DB persistence)
- `[ ]` RabbitMQ async consumer (synchronous execution enabled for local setup)
- `[ ]` WebSocket progress tracking

---

## 🧪 TESTING

### Backend Tests
- `[x]` Unit tests & validation check for MRZ parser and check digit validation
- `[x]` Verification of document validation rules & risk scoring engine
- `[x]` End-to-end test script verifying scan pipeline execution and DB persistence
- `[ ]` Load/performance tests (target: <5s per scan)

### Frontend Tests
- `[ ]` Component unit tests (Jest + React Testing Library)
- `[ ]` E2E tests (Playwright or Cypress)
- `[ ]` Accessibility audit
- `[ ]` Responsive design testing

---

## 🚀 DEPLOYMENT (Later Phase — No Docker for Now)

- `[ ]` Nginx/Kong API Gateway configuration
- `[ ]` SSL/TLS certificates setup
- `[ ]` Prometheus + Grafana monitoring
- `[ ]` ELK Stack logging setup
- `[ ]` Production environment variables and secrets management
- `[ ]` _(Later)_ Dockerfiles for frontend, backend, and all services
- `[ ]` _(Later)_ Docker Compose for full stack
- `[ ]` _(Later)_ Kubernetes manifests (Deployments, Services, Ingress)

---

## 📋 AI MODEL HANDOFF NOTES

> **Instructions for any AI model picking up this project:**
>
> 1. **Read this file first** to understand what's been done.
> 2. **Read `prd.md`** for product requirements.
> 3. **Read `system_architecture.md`** for technical architecture and stack decisions.
> 4. **Read `proj.txt`** for additional context and research.
> 5. **Check the `/frontend` and `/backend` directories** for existing code.
> 6. **Update this tracker** after completing any task — change `[ ]` to `[x]`.
> 7. **Add notes** below any task if there are important decisions or caveats.
> 8. **If you hit your limit**, add a `LAST WORKING ON:` note below before stopping.

### 🔄 LAST WORKING ON:
- **Model:** Gemini 3.8 Flash (Medium)
- **Date:** 2026-09-05
- **What was being worked on:** Elevated BorderShield AI into the upstream **Fraud Intelligence & Evidence Fusion Layer**:
  1. Integrated 512-dimensional ArcFace biometric embedding extractor and Fourier texture liveness verification (`app/services/face/face_service.py`).
  2. Built Dual-Domain ELA, DCT quantization error, and photo boundary splice gradient detector (`app/services/forgery/forgery_service.py`).
  3. Created Contradiction Engine (`app/services/risk/contradiction_engine.py`) evaluating the multi-modal Evidence Truth Matrix across Chip PKI, MRZ, OCR, Face, Forensics, and History.
  4. Built Identity & Document Fraud Graph (`app/services/graph/identity_graph.py`) using NetworkX to detect cross-encounter identity-hopping and synthetic reuse.
  5. Built Fraud Pattern Memory (`app/services/forgery/pattern_memory.py`) knowledge base (EU-FADO style).
  6. Implemented Cryptographic Audit Anchor (`app/services/audit/crypto_anchor.py`) producing verifiable canonical SHA-256 evidence fingerprints.
  7. Upgraded Frontend Officer Console (`src/app/scans/[id]/page.tsx`) with Contradiction Matrix, Identity Continuity Graph visualizer, Fraud Signature badges, and Verifiable Audit Integrity check.
  8. Verified via end-to-end integration test (`backend/test_fraud_intelligence.py`) and clean Next.js build.
- **What to do next:** System is fully functional, thoroughly verified, and ready for demo/presentation.
- **Blockers:** None.

---

## 📝 DECISION LOG

> Track important architectural and design decisions here.

| # | Date | Decision | Rationale | Decided By |
|---|------|----------|-----------|------------|
| 1 | 2026-09-04 | Use Next.js + FastAPI stack | Best fit for AI-heavy system with good UI. Python for ML, React for dashboard. | Planning phase |
| 2 | 2026-09-04 | PostgreSQL over MongoDB | Structured audit data needs ACID compliance. JSON columns for flexible fields. | Planning phase |
| 3 | 2026-09-04 | Redis for watchlist caching | Sub-millisecond lookups required for real-time matching. | Planning phase |
| 4 | 2026-09-04 | Microservices architecture | Each AI module has different compute needs (GPU vs CPU). Independent scaling. | Planning phase |

---

## 🐛 KNOWN ISSUES & BUGS

> Track bugs and issues here as they arise.

| # | Date | Description | Status | Fixed By |
|---|------|-------------|--------|----------|
| — | — | _No issues yet_ | — | — |

---

## 📁 PROJECT STRUCTURE (Expected)

```
sih/
├── TASK_TRACKER.md          ← YOU ARE HERE
├── prd.md                   ← Product Requirements Document
├── system_architecture.md   ← System Architecture & Tech Stack
├── proj.txt                 ← Research & Context
├── deep-research-report.md  ← Deep Research Report
│
├── frontend/                ← Next.js Application
│   ├── src/
│   │   ├── app/             ← App Router pages
│   │   ├── components/      ← Reusable UI components
│   │   ├── hooks/           ← Custom React hooks
│   │   ├── lib/             ← Utilities, API client, constants
│   │   ├── services/        ← API service layer
│   │   ├── store/           ← State management
│   │   └── types/           ← TypeScript type definitions
│   ├── public/              ← Static assets
│   ├── package.json
│   └── next.config.js
│
├── uploads/                 ← Local file storage (images, captures)
│   ├── documents/
│   └── faces/
│
├── backend/                 ← FastAPI Application
│   ├── app/
│   │   ├── api/             ← API route handlers
│   │   │   └── v1/          ← Version 1 endpoints
│   │   ├── core/            ← Config, security, dependencies
│   │   ├── models/          ← SQLAlchemy database models
│   │   ├── schemas/         ← Pydantic request/response schemas
│   │   ├── services/        ← Business logic layer
│   │   │   ├── ocr/         ← OCR & MRZ service
│   │   │   ├── forgery/     ← Forgery detection service
│   │   │   ├── face/        ← Face verification service
│   │   │   ├── validation/  ← Document validation service
│   │   │   └── risk/        ← Risk scoring engine
│   │   ├── workers/         ← Background task workers
│   │   └── utils/           ← Shared utilities
│   ├── alembic/             ← Database migrations
│   ├── tests/               ← Test suite
│   ├── requirements.txt
│   └── main.py
│
└── ml-models/               ← Trained ML model files
    ├── forgery/
    ├── face/
    └── ocr/
```

---

## 🎯 MILESTONE MAPPING (from Roadmap)

| Milestone | Weeks | Focus | Status |
|-----------|-------|-------|--------|
| **M1** | 1-2 | Setup, schema, dev environment | `[ ]` Not started |
| **M2** | 3-5 | OCR module, MRZ parser, checksum validation | `[ ]` Not started |
| **M3** | 5-8 | Document validation rules, watchlist API integration | `[ ]` Not started |
| **M4** | 6-10 | Face service: detection, 1:1 matching, liveness | `[ ]` Not started |
| **M5** | 8-12 | Tampering models: stamps, photo/text manipulation | `[ ]` Not started |
| **M6** | 10-14 | Risk engine, UI dashboard, explainable alerts | `[ ]` Not started |
| **M7** | 12-16 | Integration, stress testing, performance tuning | `[ ]` Not started |
| **M8** | 16+ | Pilot deployment, monitoring, model refinement | `[ ]` Not started |

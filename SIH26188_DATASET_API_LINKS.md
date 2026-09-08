# SIH 26188 — Verified Dataset / API / Standards Links

Use this file as the source list when setting up data and integrations. Verify license/access again before production use.

## 1. SIH / PS

Official SIH portal:
https://sih.gov.in/sih2026PS

Secondary reference only:
https://sihone.pages.dev/ps/26188

## 2. ICAO Doc 9303

Official collection:
https://www.icao.int/publications/doc-series/doc-9303

Parts currently listed by ICAO include Parts 1–13. Use the current official page and amendments when implementing standards.

Part 1 direct PDF:
https://www.icao.int/publications/documents/9303_p1_cons_en.pdf

Part 3 direct PDF:
https://www.icao.int/publications/Documents/9303_p3_cons_en.pdf

Part 4: use the current Part 4 link from the ICAO Doc 9303 page.

Part 11 / security mechanisms:
https://store.icao.int/en/machine-readable-travel-documents-part-11-security-mechanisms-for-mrtds-doc-9303-11-amendment-no-2-dated-23-2-26

Part 12 / PKI:
https://store.icao.int/en/machine-readable-travel-documents-part-12-public-key-infrastructure-for-mrtds-doc-9303-12

## 3. Document datasets

### MIDV-500

Smart Engines dataset/paper information:
https://smartengines.com/wp-content/uploads/2020/04/datasets-of-id-documents-midv-500.pdf

Use primarily for document detection/recognition/OCR/capture robustness. Do not use it as the main modern tamper-localization dataset.

### MIDV-2020

Use the Smart Engines MIDV family/source and verify the current distribution method before downloading.

### FantasyID

Idiap project:
https://www.idiap.ch/en/scientific-research/data/fantasyid

Zenodo direct dataset record:
https://zenodo.org/records/17063366

Paper:
https://arxiv.org/abs/2507.20808

### DocTamper

Official repository:
https://github.com/qcf-568/DocTamper

Important: official repository currently states non-commercial use and an application/password process. Verify rights before using beyond research/SIH prototype purposes.

### IDNet

Kaggle:
https://www.kaggle.com/datasets/chitreshkr/idnet-identity-document-analysis

The page describes a large synthetic identity-document dataset. Verify underlying license/terms before use.

### Synthetic passports

Kaggle:
https://www.kaggle.com/datasets/simongraves/passport-dataset

The page describes 100,000+ synthetic passport images from 100+ countries and currently lists CC BY-NC-ND 4.0. Use a small subset only and do not redistribute beyond the license.

### Generated MRZ

Kaggle:
https://www.kaggle.com/datasets/trainingdatapro/ocr-machine-readable-zone-mrz-detection

The page describes generated MRZ images and OCR results. Verify terms/access before use.

### FRLL-Morphs

Idiap:
https://www.idiap.ch/en/scientific-research/data/frll-morphs

Use for controlled face-morphing vulnerability evaluation.

## 4. Roboflow document detector

Identity Card resource:
https://universe.roboflow.com/2bs/identity-card-xrh4n

Use only as a document localization/detection component. It is not a complete forgery detector.

## 5. Risk / watchlist APIs

### OpenSanctions

Matching API:
https://www.opensanctions.org/docs/api/matching/

Request/API docs:
https://www.opensanctions.org/docs/api/request/

API base:
https://api.opensanctions.org

Use as optional external entity/risk screening. Never call it an MHA or INTERPOL source.

### INTERPOL SLTD

Official:
https://www.interpol.int/en/How-we-work/Border-management/SLTD-database-travel-and-identity-documents

INTERPOL database access is via authorized law-enforcement infrastructure/I-24/7. Do not invent a public developer API key. Implement an adapter with simulated/demo mode.

## 6. Mapping

Recommended frontend options:
- MapLibre GL JS: https://maplibre.org/
- Leaflet: https://leafletjs.com/

For geocoding/search providers, verify current API terms and rate limits before selecting one.

Privacy rule: a passport does not normally prove a person's exact residence. Do not infer a residence location from nationality or issuing country. Prefer country/region/city only when explicitly present and authorized.

For India emergency contact, display **112** as the national emergency number where appropriate. Do not invent local police-station numbers; obtain exact numbers only from verified official sources or authoritative directories.

## 7. Supabase

Docs:
https://supabase.com/docs/guides/auth
https://supabase.com/docs/guides/database/postgres/row-level-security
https://supabase.com/docs/guides/storage/buckets/fundamentals

Use private buckets and RLS.

## 8. Deployment

Next.js/Vercel:
https://vercel.com/docs
https://nextjs.org/docs

FastAPI:
https://fastapi.tiangolo.com/

Keep heavy CV/ML inference outside Vercel serverless functions unless the selected runtime/model is explicitly shown to fit.

## 9. Recommended small-subset starting point

Do not download all 100k+ examples.

Start with a curated subset and increase only when tests show a need:
- MIDV-family: small representative subset for OCR/geometry/capture conditions
- FantasyID: small train/dev/test subset for manipulation experiments
- DocTamper: small authorized research subset, respecting its access terms
- FRLL-Morphs: small evaluation subset
- Synthetic passport dataset: small demo/training subset only
- Synthetic fraud generator: enough examples to cover every intended attack type

Keep a manifest of exact filenames/IDs used so the project is reproducible.

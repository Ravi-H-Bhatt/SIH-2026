#!/usr/bin/env python3
"""
Seed realistic demo data into Supabase.

Creates staff accounts and a spread of completed screenings so the dashboards,
supervisor queue, operations map, and criminal-alert panels all have something
real to render. Every scan gets its full evidence chain: extracted MRZ fields,
forgery analysis, face match, risk fusion, canonical hash, and audit trail.

Idempotent — reruns update the demo rows rather than duplicating them. Only
touches records tagged with the DEMO_TAG checkpoint prefix or demo emails, so
your own scans are never modified.

Usage:
    cd backend && python3 scripts/seed_demo_data.py
    cd backend && python3 scripts/seed_demo_data.py --purge   # remove demo data
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.extracted_data import ExtractedData  # noqa: E402
from app.models.face_result import FaceResult  # noqa: E402
from app.models.forgery_result import ForgeryResult  # noqa: E402
from app.models.risk_score import RiskScore  # noqa: E402
from app.models.scan import ScanRecord  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.audit.crypto_anchor import crypto_anchor  # noqa: E402
from app.services.geo.geo_reference import geo_reference  # noqa: E402

OK = "\033[92m✓\033[0m"
INFO = "\033[90m·\033[0m"

DEMO_PASSWORD = "Demo@12345"
DEMO_EMAIL_DOMAIN = "demo.borderguard.gov.in"

# ── staff ───────────────────────────────────────────────────────────────────
# is_approved=False rows exercise the admin-approval queue.
DEMO_USERS = [
    ("priya.sharma",   "Priya Sharma",    "supervisor",    True),
    ("arjun.mehta",    "Arjun Mehta",     "supervisor",    True),
    ("rahul.verma",    "Rahul Verma",     "officer",       True),
    ("sneha.iyer",     "Sneha Iyer",      "officer",       True),
    ("vikram.singh",   "Vikram Singh",    "officer",       True),
    ("neha.gupta",     "Neha Gupta",      "investigator",  True),
    ("kabir.rao",      "Kabir Rao",       "officer",       False),   # awaiting approval
    ("ananya.das",     "Ananya Das",      "officer",       False),   # awaiting approval
]

CHECKPOINTS = [
    ("IGI T3 — Counter 04", 28.5562, 77.1000),
    ("IGI T3 — Counter 07", 28.5565, 77.1015),
    ("Kiosk-01 Self-Service", 28.5558, 77.0994),
    ("Attari Land Border", 31.6040, 74.5720),
    ("Mumbai CSMIA T2", 19.0896, 72.8656),
]

# ── travellers ──────────────────────────────────────────────────────────────
# (name, doc_no, country, sex, dob, profile)
# profile drives every downstream score so the evidence stays self-consistent.
TRAVELLERS = [
    ("AARAV SHARMA",       "Z3821456", "IND", "M", "1991-04-12", "clean"),
    ("MEERA KRISHNAN",     "Z4192837", "IND", "F", "1988-11-03", "clean"),
    ("DANIEL O CONNOR",    "GB9382741", "GBR", "M", "1979-02-21", "clean"),
    ("YUKI TANAKA",        "TK7261882", "JPN", "F", "1995-07-30", "clean"),
    ("HANS MUELLER",       "DE4471920", "DEU", "M", "1983-09-14", "clean"),
    ("SARAH WILLIAMS",     "US8812440", "USA", "F", "1990-01-25", "low_face"),
    ("MOHAMMED AL FARSI",  "AE5561238", "ARE", "M", "1986-06-08", "expired"),
    ("LIN WEI",            "CN9928374", "CHN", "F", "1993-03-17", "mrz_fail"),
    ("RAVI PATEL",         "Z7719283", "IND", "M", "1975-12-01", "tampered"),
    ("ELENA PETROVA",      "RU3345671", "RUS", "F", "1992-08-19", "tampered"),
    # ── watchlist hits (document numbers match watchlist_service.py exactly) ──
    ("JOHN THIEF",         "A11111111", "USA", "M", "1984-05-05", "criminal_thief"),
    ("JANE ROBBER",        "B22222222", "GBR", "F", "1989-10-22", "criminal_thief"),
    ("FRAUDSTER SMITH",    "C33333333", "USA", "M", "1981-07-11", "criminal_fraud"),
    ("BAD ACTOR",          "P99999999", "PAK", "M", "1977-03-09", "interpol"),
    ("WANTED PERSON",      "P88888888", "AFG", "M", "1980-01-30", "wanted"),
]

# profile -> (forgery, face_match, liveness, risk, level, decision, final, flags)
PROFILES = {
    "clean": (
        4.0, 0.91, True, 8.0, "low", "pass", "approved",
        [{"flag": "MRZ check digits valid", "severity": "info"},
         {"flag": "Face match above threshold", "severity": "info"}],
    ),
    "low_face": (
        9.0, 0.52, True, 41.0, "medium", "review", None,
        [{"flag": "Face similarity 0.52 below 0.70 threshold", "severity": "medium"},
         {"flag": "Manual biometric confirmation required", "severity": "medium"}],
    ),
    "expired": (
        6.0, 0.88, True, 46.0, "medium", "review", None,
        [{"flag": "Document expired 2024-08-31", "severity": "high"},
         {"flag": "MRZ check digits valid", "severity": "info"}],
    ),
    "mrz_fail": (
        22.0, 0.79, True, 58.0, "high", "review", "flagged",
        [{"flag": "MRZ document-number check digit failed", "severity": "high"},
         {"flag": "VIZ/MRZ surname mismatch", "severity": "high"}],
    ),
    "tampered": (
        78.0, 0.44, False, 82.0, "high", "hold", "flagged",
        [{"flag": "ELA indicates photo-region resave at q=95", "severity": "critical"},
         {"flag": "DCT quantization discontinuity along photo boundary", "severity": "high"},
         {"flag": "Liveness check failed — possible presentation attack", "severity": "high"}],
    ),
    "criminal_thief": (
        34.0, 0.86, True, 100.0, "critical", "detain", "detained",
        [{"flag": "🚨 CRIMINAL WATCHLIST HIT — wanted for theft", "severity": "critical"},
         {"flag": "Detain and notify authorities immediately", "severity": "critical"}],
    ),
    "criminal_fraud": (
        41.0, 0.83, True, 100.0, "critical", "detain", "detained",
        [{"flag": "🚨 CRIMINAL WATCHLIST HIT — fraud / identity theft", "severity": "critical"},
         {"flag": "Cross-encounter identity reuse detected", "severity": "high"}],
    ),
    "interpol": (
        66.0, 0.71, True, 96.0, "critical", "detain", "detained",
        [{"flag": "INTERPOL SLTD — document reported stolen", "severity": "critical"},
         {"flag": "Chip PKI signature mismatch", "severity": "critical"}],
    ),
    "wanted": (
        28.0, 0.89, True, 88.0, "critical", "hold", "detained",
        [{"flag": "Immigration alert — active entry restriction", "severity": "critical"}],
    ),
}

CRIMINAL_PROFILES = {"criminal_thief", "criminal_fraud", "interpol", "wanted"}

CRIME_DETAIL = {
    "criminal_thief": ("Yes", "Multiple theft and burglary cases registered (SIMULATED DEMO DATA)", "Yes",
                       "Wanted for theft — detain and notify authorities"),
    "criminal_fraud": ("Yes", "Financial fraud and identity theft (SIMULATED DEMO DATA)", "Yes",
                       "Wanted for fraud — secondary inspection required"),
    "interpol":       ("Yes", "INTERPOL Red Notice — document fraud (SIMULATED DEMO DATA)", "Yes",
                       "INTERPOL SLTD stolen document alert"),
    "wanted":         ("No", None, "Yes",
                       "Immigration alert — entry restriction active (SIMULATED DEMO DATA)"),
}


def mrz_lines(name: str, doc_no: str, country: str, sex: str, dob: str) -> list[str]:
    """Builds plausible TD3 MRZ lines for display purposes."""
    parts = name.split()
    surname = parts[-1]
    given = " ".join(parts[:-1]) or parts[0]
    name_field = f"{surname}<<{given.replace(' ', '<')}"
    line1 = f"P<{country}{name_field}".ljust(44, "<")[:44]
    yy = dob[2:4] + dob[5:7] + dob[8:10]
    line2 = f"{doc_no}<{country}{yy}{sex}3009152<<<<<<<<<<<<<<<<".ljust(44, "<")[:44]
    return [line1, line2]


def purge(db) -> None:
    emails = [f"{u}@{DEMO_EMAIL_DOMAIN}" for u, *_ in DEMO_USERS]
    docs = [t[1] for t in TRAVELLERS]

    scans = (
        db.query(ScanRecord)
        .join(ExtractedData, ExtractedData.scan_id == ScanRecord.id)
        .filter(ExtractedData.fields["document_number"].as_string().in_(docs))
        .all()
    )
    for scan in scans:
        db.delete(scan)          # cascades to result tables
    removed_users = db.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)
    db.commit()
    print(f"{OK} Removed {len(scans)} demo scan(s) and {removed_users} demo user(s).")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true", help="delete demo data and exit")
    args = ap.parse_args()

    if not settings.resolved_database_url().startswith("postgresql"):
        print("✗ Not connected to Supabase. Run scripts/verify_supabase.py first.")
        return 1

    Base.metadata.create_all(engine)
    db = SessionLocal()
    rng = random.Random(26188)  # deterministic output across runs

    try:
        if args.purge:
            purge(db)
            return 0

        print("\n\033[1mSEEDING DEMO DATA -> SUPABASE\033[0m")
        print("─" * 66)

        # ── users ───────────────────────────────────────────────────────────
        officers: list[User] = []
        created = updated = 0
        for username, full_name, role, approved in DEMO_USERS:
            email = f"{username}@{DEMO_EMAIL_DOMAIN}"
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=role,
                    is_active=True,
                    is_approved=approved,
                    approved_at=datetime.now(timezone.utc) if approved else None,
                )
                db.add(user)
                created += 1
            else:
                user.full_name, user.role, user.is_approved = full_name, role, approved
                updated += 1
            if role in ("officer", "supervisor"):
                officers.append(user)
        db.commit()
        for user in officers:
            db.refresh(user)
        pending = sum(1 for *_, a in DEMO_USERS if not a)
        print(f"{OK} Users: {created} created, {updated} updated "
              f"({pending} awaiting admin approval)")

        # ── scans ───────────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        made = skipped = 0

        for idx, (name, doc_no, country, sex, dob, profile) in enumerate(TRAVELLERS):
            existing = (
                db.query(ScanRecord)
                .join(ExtractedData, ExtractedData.scan_id == ScanRecord.id)
                .filter(ExtractedData.fields["document_number"].as_string() == doc_no)
                .first()
            )
            if existing:
                skipped += 1
                continue

            forgery, face_match, live, risk, level, decision, final, flags = PROFILES[profile]
            chk_name, chk_lat, chk_lng = CHECKPOINTS[idx % len(CHECKPOINTS)]
            officer = officers[idx % len(officers)]
            created_at = now - timedelta(hours=rng.uniform(0.5, 70), minutes=rng.randint(0, 59))
            is_passport = True
            scan_id = uuid.uuid4()

            fields = {
                "success": True,
                "document_type": "passport",
                "document_number": doc_no,
                "holder_name": name,
                "surname": name.split()[-1],
                "given_names": " ".join(name.split()[:-1]),
                "issuing_country": country,
                "nationality": country,
                "date_of_birth": dob,
                "sex": sex,
                "expiry_date": "2024-08-31" if profile == "expired" else "2030-09-15",
                "mrz_valid": profile != "mrz_fail",
                "mrz_required": True,
                "mrz_lines": mrz_lines(name, doc_no, country, sex, dob),
                "ocr_engine": "google_vision",
                "raw_ocr_text": f"REPUBLIC OF {country}\nPASSPORT\n{name}\n{doc_no}",
            }

            origin = geo_reference.coordinates_for_country(country)
            is_crim, crim_rec, is_wanted, wanted_det = CRIME_DETAIL.get(
                profile, ("No", None, "No", None)
            )

            scan = ScanRecord(
                id=scan_id,
                document_type="passport" if is_passport else "id_card",
                status="completed",
                checkpoint_id=chk_name,
                officer_id=officer.id,
                # Demo rows carry no real image. Using a supabase:// URI here
                # would 404 on signed-URL generation, so leave it null and let
                # the UI show its "no image" state honestly.
                document_image_path=None,
                face_image_path=None,
                chip_pki_status="SIGNATURE_MISMATCH" if profile == "interpol" else "AUTHENTIC_VALID",
                notes="SIMULATED DEMO RECORD — not a real traveller.",
                final_decision=final,
                country=country,
                city=None,
                latitude=str(origin[0]) if origin else None,
                longitude=str(origin[1]) if origin else None,
                checkpoint_latitude=str(chk_lat),
                checkpoint_longitude=str(chk_lng),
                is_criminal=is_crim,
                criminal_record=crim_rec,
                is_wanted=is_wanted,
                wanted_details=wanted_det,
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(scan)
            db.flush()

            db.add(ExtractedData(
                scan_id=scan_id,
                fields=fields,
                mrz_data={"mrz_lines": fields["mrz_lines"], "flags": []},
                mrz_valid=fields["mrz_valid"],
                created_at=created_at,
            ))

            issues = []
            if profile == "tampered":
                issues = [
                    {"type": "photo_tamper", "confidence": 0.93,
                     "detail": "ELA residual concentrated in portrait region"},
                    {"type": "dct_discontinuity", "confidence": 0.81,
                     "detail": "8x8 block quantization mismatch at photo edge"},
                ]
            elif profile == "interpol":
                issues = [{"type": "chip_signature", "confidence": 0.88,
                           "detail": "ePassport SOD signature does not verify"}]
            db.add(ForgeryResult(
                scan_id=scan_id, anomaly_score=forgery,
                detected_issues=issues, created_at=created_at,
            ))

            hits = []
            if profile in CRIMINAL_PROFILES:
                from app.services.face.watchlist_service import watchlist_service
                hits = watchlist_service.check_watchlist(doc_no, name)
            db.add(FaceResult(
                scan_id=scan_id,
                match_score=face_match,
                liveness_passed=live,
                # 512-d embeddings are large and meaningless as fake data;
                # store null rather than noise that could pollute the identity graph.
                face_embedding=None,
                continuity_links=[],
                watchlist_hits=hits,
                created_at=created_at,
            ))

            digest = {
                "scan_id": str(scan_id),
                "document_number": doc_no,
                "holder_name": name,
                "chip_pki_status": scan.chip_pki_status,
                "mrz_valid": fields["mrz_valid"],
                "forgery_anomaly_score": forgery,
                "face_match_score": face_match,
                "contradiction_flags": [f["flag"] for f in flags],
                "overall_classification": (
                    "FRAUDULENT_INCONSISTENT" if level in ("high", "critical")
                    else "GENUINE_CONSISTENT"
                ),
                "officer_decision": (final or decision).upper(),
                "timestamp": created_at.isoformat(),
            }
            canonical_hash, _ = crypto_anchor.generate_canonical_hash(digest)
            scan.canonical_hash = canonical_hash

            db.add(RiskScore(
                scan_id=scan_id, score=risk, risk_level=level,
                explanations=flags, decision=decision,
                contradiction_matrix=[
                    {"check": "MRZ check digits", "result": fields["mrz_valid"]},
                    {"check": "Chip PKI", "result": scan.chip_pki_status == "AUTHENTIC_VALID"},
                    {"check": "Face match", "result": face_match >= 0.70},
                    {"check": "Liveness", "result": live},
                    {"check": "Watchlist clear", "result": not hits},
                ],
                identity_graph_summary={"continuity_links": [], "reused_document": False},
                fraud_patterns_matched=(
                    [{"pattern": "EU-FADO photo-substitution signature", "confidence": 0.79}]
                    if profile == "tampered" else []
                ),
                canonical_hash=canonical_hash,
                created_at=created_at,
            ))

            db.add(AuditLog(
                scan_id=scan_id, action="scan_created", actor=officer.email,
                details={"document_type": "passport", "checkpoint_id": chk_name,
                         "source": "demo_seed"},
                timestamp=created_at,
            ))
            db.add(AuditLog(
                scan_id=scan_id, action="scan_completed", actor="system",
                details={"risk_score": risk, "risk_level": level,
                         "decision": decision, "canonical_hash": canonical_hash},
                timestamp=created_at + timedelta(seconds=4),
            ))
            if final:
                db.add(AuditLog(
                    scan_id=scan_id, action="decision_made", actor=officer.email,
                    details={"decision": final, "source": "demo_seed"},
                    timestamp=created_at + timedelta(seconds=20),
                ))

            made += 1

        db.commit()
        print(f"{OK} Scans: {made} created, {skipped} already present")

        # ── summary ─────────────────────────────────────────────────────────
        total = db.query(ScanRecord).count()
        crim = db.query(ScanRecord).filter(ScanRecord.is_criminal == "Yes").count()
        want = db.query(ScanRecord).filter(ScanRecord.is_wanted == "Yes").count()
        mapped = db.query(ScanRecord).filter(ScanRecord.latitude.isnot(None)).count()
        awaiting = db.query(User).filter(User.is_approved.is_(False)).count()

        print("\n\033[1mIN SUPABASE NOW\033[0m")
        print("─" * 66)
        print(f"  scan_records        {total}")
        print(f"  criminal flagged    {crim}")
        print(f"  wanted flagged      {want}")
        print(f"  map-plottable       {mapped}")
        print(f"  users               {db.query(User).count()}  ({awaiting} awaiting approval)")
        print(f"\n{INFO} Demo staff login password: {DEMO_PASSWORD}")
        print(f"{INFO} All demo records are labelled SIMULATED. Purge with --purge.\n")
        return 0

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"\n✗ {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

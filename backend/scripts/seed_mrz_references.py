#!/usr/bin/env python3
"""
Populate the MRZ reference registry from the extracted UAE passport fixture.

Gives the pipeline known-good records to compare scans against. Two of the 15
are deliberately marked revoked / reported stolen so the "genuine blank, bad
status" and "altered data" paths can both be demonstrated.

Usage:
    cd backend && python3 scripts/seed_mrz_references.py
    cd backend && python3 scripts/seed_mrz_references.py --purge
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.mrz_reference import MRZReference  # noqa: E402
from app.services.face.watchlist_service import normalize_doc_number  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "uae_reference_passports.json")

# Documents the issuing authority has flagged, keyed by document number.
ISSUER_STATUS = {
    "Z43R34255": {
        "is_reported_stolen": True,
        "revocation_reason": "Reported stolen in Dubai, 2019 (SIMULATED)",
    },
    "Z54R76423": {
        "is_revoked": True,
        "revocation_reason": "Revoked — holder subject to sanctions designation (SIMULATED)",
    },
}

OK = "\033[92m✓\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true")
    args = ap.parse_args()

    if not settings.resolved_database_url().startswith("postgresql"):
        print("✗ Not connected to Supabase. Run scripts/verify_supabase.py first.")
        return 1

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        if args.purge:
            n = db.query(MRZReference).delete()
            db.commit()
            print(f"{OK} Removed {n} reference record(s).")
            return 0

        if not os.path.exists(FIXTURE):
            print(f"✗ Fixture not found: {FIXTURE}")
            return 1

        payload = json.load(open(FIXTURE))
        records = payload.get("records", [])

        created = updated = 0
        for rec in records:
            doc = normalize_doc_number(rec.get("document_number"))
            if not doc:
                continue

            status = ISSUER_STATUS.get(doc, {})
            row = db.query(MRZReference).filter(MRZReference.document_number == doc).first()

            fields = dict(
                document_type="passport",
                issuing_country=rec.get("issuing_country"),
                nationality=rec.get("issuing_country"),
                surname=rec.get("surname"),
                given_names=rec.get("given_names"),
                holder_name=rec.get("holder_name"),
                date_of_birth=rec.get("date_of_birth"),
                expiry_date=rec.get("expiry_date"),
                sex=rec.get("sex"),
                is_revoked=status.get("is_revoked", False),
                is_reported_stolen=status.get("is_reported_stolen", False),
                revocation_reason=status.get("revocation_reason"),
                source="uae_reference_fixture",
                notes="SYNTHETIC reference record — not a real traveller.",
            )

            if row is None:
                db.add(MRZReference(document_number=doc, **fields))
                created += 1
            else:
                for k, v in fields.items():
                    setattr(row, k, v)
                updated += 1

        db.commit()

        total = db.query(MRZReference).count()
        flagged = db.query(MRZReference).filter(
            (MRZReference.is_revoked.is_(True)) | (MRZReference.is_reported_stolen.is_(True))
        ).count()

        print(f"{OK} MRZ reference registry: {created} created, {updated} updated")
        print(f"  total records   : {total}")
        print(f"  revoked/stolen  : {flagged}")
        print("\nSample:")
        for r in db.query(MRZReference).limit(5).all():
            flag = " [REVOKED]" if r.is_revoked else (" [STOLEN]" if r.is_reported_stolen else "")
            print(f"  {r.document_number:<11} {r.holder_name:<22} dob={r.date_of_birth} "
                  f"exp={r.expiry_date}{flag}")
        return 0

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"✗ {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

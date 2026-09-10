"""
Purge unusable face embeddings from the gallery.

An embedding is unusable when it cannot support a meaningful cosine comparison:

  - wrong dimensionality      not the current model's 128-d SFace output
                              (512-d rows are leftovers from the removed ArcFace
                              backend and from `[0.0] * 512` error fallbacks)
  - zero magnitude            the old "extraction failed" sentinel
  - constant vector           e.g. [0.05] * 128 from seed.py; cosine between any
                              two constant vectors is exactly 1.0, so these
                              matched each other and every all-positive vector
  - non-finite values         NaN / inf

These rows are set to NULL rather than deleted: the scan, its risk score and its
audit trail remain intact, only the unusable biometric is removed. A NULL
embedding is correctly skipped by the identity graph, whereas a garbage one
produces confident false links.

Usage:
    ./venv/bin/python scripts/purge_invalid_embeddings.py           # dry run
    ./venv/bin/python scripts/purge_invalid_embeddings.py --apply   # commit
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal          # noqa: E402
from app.models.face_result import FaceResult       # noqa: E402
from app.services.face.face_service import SFACE_DIM  # noqa: E402


def classify(embedding):
    """Returns a reason string when the embedding is unusable, else None."""
    if not embedding:
        return None  # already NULL/empty — nothing to do

    if len(embedding) != SFACE_DIM:
        return f"wrong dimensionality ({len(embedding)}, expected {SFACE_DIM})"

    arr = np.asarray(embedding, dtype=np.float64)

    if not np.all(np.isfinite(arr)):
        return "contains NaN or infinity"

    if float(np.linalg.norm(arr)) < 1e-8:
        return "zero magnitude"

    if float(np.std(arr)) < 1e-9:
        return f"constant vector (all values {embedding[0]})"

    return None


def main() -> int:
    apply_changes = "--apply" in sys.argv

    db = SessionLocal()
    try:
        rows = db.query(FaceResult).all()
        print(f"Inspecting {len(rows)} face_results rows\n")

        doomed = []
        kept = 0
        already_null = 0

        for row in rows:
            if not row.face_embedding:
                already_null += 1
                continue
            reason = classify(row.face_embedding)
            if reason:
                doomed.append((row, reason))
            else:
                kept += 1

        for row, reason in doomed:
            print(f"  PURGE scan={row.scan_id}  {reason}")

        print()
        print(f"  usable, kept          : {kept}")
        print(f"  already NULL          : {already_null}")
        print(f"  unusable, to purge    : {len(doomed)}")

        if not doomed:
            print("\nNothing to purge — the gallery is clean.")
            return 0

        if not apply_changes:
            print("\nDRY RUN — no changes written. Re-run with --apply to commit.")
            return 0

        for row, _ in doomed:
            row.face_embedding = None
        db.commit()
        print(f"\nPurged {len(doomed)} unusable embedding(s). Scans and audit "
              f"records were left untouched.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""
Verification harness for the biometric scoring fix.

Computes the full pairwise raw-cosine matrix over every image containing exactly
one detectable face, and checks the two properties that were broken:

  1. Self-comparison must score ~1.0  (the metric actually measures identity)
  2. Different people must score below the 1:1 threshold  (it discriminates)

Run:  ./venv/bin/python verify_face_matching.py [extra_image ...]
"""

import glob
import os
import sys

from app.services.face.face_service import (
    MIN_SAFE_COSINE_THRESHOLD,
    _effective_1to1_threshold,
    _effective_1toN_threshold,
    cosine_similarity,
    face_service,
)

SEARCH_GLOBS = [
    "uploads/**/*.jpg",
    "uploads/**/*.jpeg",
    "uploads/**/*.png",
    "verify_images/*.jpg",
    "verify_images/*.jpeg",
    "verify_images/*.png",
]


def collect_candidates(extra):
    paths = []
    for pattern in SEARCH_GLOBS:
        paths.extend(glob.glob(pattern, recursive=True))
    paths.extend(extra)
    # Skip derived artefacts so a face is not compared against its own crop.
    return sorted({
        p for p in paths
        if "_ela" not in os.path.basename(p) and os.path.isfile(p)
    })


def main():
    extra = sys.argv[1:]
    t_1to1 = _effective_1to1_threshold()
    t_1ton = _effective_1toN_threshold()

    print("=" * 78)
    print("BIOMETRIC SCORING VERIFICATION")
    print("=" * 78)
    print(f"models available      : {face_service.models_available}")
    print(f"embedding dimension   : {face_service.dim}")
    print(f"1:1 threshold (cosine): {t_1to1}")
    print(f"1:N threshold (cosine): {t_1ton}")
    print(f"hard floor            : {MIN_SAFE_COSINE_THRESHOLD}")
    print()

    if not face_service.models_available:
        print("FAIL: models not loaded, cannot verify")
        return 1

    usable = []
    for path in collect_candidates(extra):
        res = face_service.analyse_image(path)
        if res["ok"] and res["face_count"] == 1:
            usable.append((path, res))
        elif res["face_count"] > 1:
            print(f"  multi-face (refused, correct): {path}  faces={res['face_count']}")

    print(f"\nsingle-face images usable as probes: {len(usable)}")
    for path, res in usable:
        print(f"  {os.path.basename(path):<44} conf={res['confidence']:.3f} "
              f"dim={len(res['embedding'])}")

    if not usable:
        print("\nNo single-face images found. Pass image paths as arguments.")
        return 1

    # Property 1 — self-similarity must be ~1.0
    print("\n" + "-" * 78)
    print("PROPERTY 1: self-comparison must be ~1.0")
    print("-" * 78)
    ok1 = True
    for path, res in usable:
        cos = cosine_similarity(res["embedding"], res["embedding"])
        verdict = "OK" if cos is not None and cos > 0.999 else "FAIL"
        ok1 &= verdict == "OK"
        print(f"  [{verdict}] {os.path.basename(path):<44} cosine={cos}")

    # Property 2 — pairwise matrix
    print("\n" + "-" * 78)
    print("PROPERTY 2: pairwise raw cosine (no rescaling)")
    print("-" * 78)
    print(f"{'image A':<32} {'image B':<32} {'cosine':>8}  verdict")
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            pa, ra = usable[i]
            pb, rb = usable[j]
            cos = cosine_similarity(ra["embedding"], rb["embedding"])
            verdict = "SAME_PERSON" if cos >= t_1to1 else "DIFFERENT"
            print(f"{os.path.basename(pa):<32.32} {os.path.basename(pb):<32.32} "
                  f"{cos:>8.4f}  {verdict}")

    # Property 3 — degenerate vectors must be refused, not scored
    print("\n" + "-" * 78)
    print("PROPERTY 3: degenerate / incompatible vectors must be refused")
    print("-" * 78)
    probe = usable[0][1]["embedding"]
    cases = {
        "zero vector (128-d)":      [0.0] * 128,
        "constant [0.05]*128 (old seed.py)": [0.05] * 128,
        "512-d ramp (old seed_demo_data.py)": [0.1 * i + 0.05 * (i % 2) for i in range(512)],
        "empty":                    [],
    }
    ok3 = True
    for label, vec in cases.items():
        cos = cosine_similarity(probe, vec)
        if label.startswith("constant"):
            # Same length, non-zero: comparable, but must NOT score as a match.
            passed = cos is not None and cos < t_1to1
            detail = f"cosine={cos:.4f} (must be < {t_1to1})"
        else:
            passed = cos is None
            detail = f"cosine={cos} (must be None)"
        ok3 &= passed
        print(f"  [{'OK' if passed else 'FAIL'}] {label:<38} {detail}")

    print("\n" + "=" * 78)
    print(f"self-similarity property : {'PASS' if ok1 else 'FAIL'}")
    print(f"degenerate-vector property: {'PASS' if ok3 else 'FAIL'}")
    print("=" * 78)
    return 0 if (ok1 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(main())

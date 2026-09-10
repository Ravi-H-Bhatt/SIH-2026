"""
Face Detection, Verification & Biometric Feature Extraction.

Pipeline
--------
    YuNet detection  ->  5-landmark alignCrop  ->  SFace 128-d feature  ->  cosine

Correctness rules enforced here
-------------------------------
1. The reported similarity IS the raw SFace cosine. It is never rescaled,
   recalibrated or remapped onto a passing band. `similarity_score` and
   `raw_cosine` always agree.

2. A comparison is only ever made between two *aligned* SFace features. If
   YuNet cannot localise a face, no embedding is produced and no score is
   invented — the result is `biometric_performed=False`.

3. Embeddings are always 128-d SFace features taken from `alignCrop` output and
   L2-normalised. There is no raw-pixel fallback and no zero vector. A missing
   embedding is `None`, which downstream code must handle explicitly.

4. A document image containing more than one usable face cannot be resolved to
   "the portrait" automatically, so it is refused and routed to manual review
   rather than silently comparing against an arbitrary detection.

Why these rules exist: the previous implementation mapped any cosine >= 0.30
onto [0.70, 0.99] and then tested it against 0.70, so the test could never
fail. It also fell back to a 16x16 grayscale pixel vector as a "biometric
embedding" — all-positive, so it scored highly against anything, including the
constant seed vectors in the database. Together those two defects made an
unrelated selfie match a wanted-poster collage at a reported "70.3%" (true
cosine 0.307) and then link to three unrelated travellers.
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from app.core.config import settings

try:
    import cv2
    HAS_CV2 = True
except ImportError:  # pragma: no cover - cv2 is a hard runtime dependency
    HAS_CV2 = False


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(CURRENT_DIR, "face_detection_yunet.onnx")
SFACE_PATH = os.path.join(CURRENT_DIR, "face_recognition_sface.onnx")

# SFace's published same-domain operating point. Configuring anything below
# this is refused at load time: below ~0.36 the false-accept rate climbs
# steeply, and a border checkpoint clearing impostors is worse than one that
# sends genuine travellers to a manual check.
MIN_SAFE_COSINE_THRESHOLD = 0.363

# SFace expects this input geometry. alignCrop produces it from 5 landmarks.
SFACE_INPUT_SIZE = (112, 112)

# SFace feature dimensionality. Any stored embedding of a different length is
# from an incompatible model or from fabricated seed data and must not be
# compared — see identity_graph.
SFACE_DIM = 128


def _effective_1to1_threshold() -> float:
    """1:1 verification threshold, floored at SFace's safe operating point."""
    return max(MIN_SAFE_COSINE_THRESHOLD, float(settings.FACE_MATCH_COSINE_THRESHOLD))


def _effective_1toN_threshold() -> float:
    """
    1:N threshold. Floored at the 1:1 threshold because searching N galleries
    accumulates false-match probability with N — the per-pair bar must be at
    least as strict as a single verification, never looser.
    """
    return max(_effective_1to1_threshold(), float(settings.FACE_IDENTITY_MATCH_THRESHOLD))


def cosine_similarity(a: List[float], b: List[float]) -> Optional[float]:
    """
    Cosine similarity between two SFace embeddings.

    Returns None when the vectors cannot be meaningfully compared: different
    lengths (different model, or fabricated seed data), wrong dimensionality, or
    a zero-magnitude vector. The previous implementation truncated mismatched
    vectors to the shorter length, which silently compared a 128-d SFace feature
    against a 512-d synthetic ramp and produced whatever the arithmetic gave.
    """
    if not a or not b:
        return None
    if len(a) != len(b):
        return None

    u = np.asarray(a, dtype=np.float64)
    v = np.asarray(b, dtype=np.float64)

    nu = float(np.linalg.norm(u))
    nv = float(np.linalg.norm(v))
    if nu < 1e-8 or nv < 1e-8:
        return None

    return float(np.clip(np.dot(u, v) / (nu * nv), -1.0, 1.0))


def _l2_normalise(vec: np.ndarray) -> List[float]:
    flat = np.asarray(vec, dtype=np.float64).flatten()
    norm = float(np.linalg.norm(flat))
    if norm < 1e-8:
        return []
    return [round(float(x), 6) for x in (flat / norm)]


class Detection:
    """One YuNet detection: the raw 15-element row plus derived geometry."""

    __slots__ = ("row", "confidence", "x", "y", "w", "h")

    def __init__(self, row: np.ndarray):
        self.row = row
        self.x, self.y, self.w, self.h = (int(v) for v in row[:4])
        self.confidence = float(row[14]) if len(row) > 14 else 0.0

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)


class FaceService:
    def __init__(self):
        self.detector = None
        self.recognizer = None
        self.dim = SFACE_DIM

        if HAS_CV2:
            if os.path.exists(YUNET_PATH):
                try:
                    self.detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), 0.5)
                except Exception as exc:
                    print(f"[FaceService] YuNet init failed: {exc}")
            else:
                print(f"[FaceService] YuNet model missing at {YUNET_PATH}")

            if os.path.exists(SFACE_PATH):
                try:
                    self.recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
                except Exception as exc:
                    print(f"[FaceService] SFace init failed: {exc}")
            else:
                print(f"[FaceService] SFace model missing at {SFACE_PATH}")

    # ── Availability ────────────────────────────────────────────────────────

    @property
    def models_available(self) -> bool:
        """
        True only when both models loaded. Biometric verification is refused
        outright when either is missing — the old code substituted a raw-pixel
        vector here, which produced confident-looking nonsense.
        """
        return HAS_CV2 and self.detector is not None and self.recognizer is not None

    # ── Detection ───────────────────────────────────────────────────────────

    def detect_faces(self, bgr_img: np.ndarray) -> List[Detection]:
        """
        All faces above FACE_QUALITY_THRESHOLD, largest first.

        Ordering by area matters: YuNet returns detections in its own order, and
        the previous code took `faces[0]` unconditionally. On a document holding
        several portraits that meant "the document photo" was whichever face the
        detector happened to list first.
        """
        if self.detector is None or bgr_img is None:
            return []

        h, w = bgr_img.shape[:2]
        if h == 0 or w == 0:
            return []

        min_conf = float(settings.FACE_QUALITY_THRESHOLD)

        try:
            self.detector.setInputSize((w, h))
            # Detect permissively, then gate on confidence ourselves so the
            # quality threshold is applied consistently and is observable.
            self.detector.setScoreThreshold(max(0.2, min(min_conf, 0.9) - 0.2))
            _, raw = self.detector.detect(bgr_img)
        except Exception as exc:
            print(f"[FaceDetect] error: {exc}")
            return []

        if raw is None or len(raw) == 0:
            return []

        found = [Detection(row) for row in raw]
        usable = [d for d in found if d.confidence >= min_conf and d.area > 0]
        usable.sort(key=lambda d: d.area, reverse=True)
        return usable

    def _crop_with_margin(
        self, bgr_img: np.ndarray, det: Detection, margin: float = 0.15
    ) -> np.ndarray:
        h, w = bgr_img.shape[:2]
        mx, my = int(det.w * margin), int(det.h * margin)
        x1 = max(0, det.x - mx)
        y1 = max(0, det.y - my)
        x2 = min(w, det.x + det.w + mx)
        y2 = min(h, det.y + det.h + my)
        return bgr_img[y1:y2, x1:x2]

    def _save_crop(self, image_path: str, crop_bgr: np.ndarray) -> Optional[str]:
        if crop_bgr is None or crop_bgr.size == 0:
            return None
        try:
            crop_path = os.path.join(
                os.path.dirname(image_path), f"crop_face_{os.path.basename(image_path)}"
            )
            cv2.imwrite(crop_path, crop_bgr)
            return crop_path
        except Exception as exc:
            print(f"[FaceCrop] save failed: {exc}")
            return None

    def _feature_for(self, bgr: np.ndarray, det: Detection):
        """Aligned SFace feature for one detection, or None."""
        try:
            return self.recognizer.feature(self.recognizer.alignCrop(bgr, det.row))
        except Exception as exc:
            print(f"[FaceFeature] extraction failed: {exc}")
            return None

    def _classify_document_faces(
        self, bgr: np.ndarray, detections: List[Detection], features: List[Any]
    ) -> Tuple[List[str], int]:
        """
        Describe how the faces on a document relate to the largest one.

        Returns (notes, distinct_person_count).

        Real passports legitimately contain more than one face: ICAO 9303
        secondary-portrait ("ghost image") security printing puts a smaller copy
        of the same holder on the data page. A face that MATCHES the main
        portrait is that ghost image. A face that DIFFERS is another person on
        the page, which is a genuine finding for a credential — but it is
        reported, not used to abandon the biometric check.
        """
        notes: List[str] = []
        distinct = 0
        threshold = _effective_1to1_threshold()
        primary = detections[0]

        for det, feat in list(zip(detections, features))[1:]:
            if feat is None:
                distinct += 1
                continue
            try:
                cos = float(
                    self.recognizer.match(
                        features[0], feat, cv2.FaceRecognizerSF_FR_COSINE
                    )
                )
            except Exception:
                distinct += 1
                continue

            ratio = det.area / max(1, primary.area) * 100
            if cos >= threshold:
                notes.append(
                    f"Secondary portrait of the same holder detected (cosine "
                    f"{cos:.3f} vs the main portrait, {ratio:.0f}% of its size) — "
                    f"consistent with ICAO 9303 ghost-image security printing"
                )
            else:
                distinct += 1
                notes.append(
                    f"A DIFFERENT person's face is present on this document "
                    f"(cosine {cos:.3f} vs the main portrait, {ratio:.0f}% of its size)"
                )

        return notes, distinct

    def analyse_image(self, image_path: str, is_document: bool = False) -> Dict[str, Any]:
        """
        Detect every usable face and extract aligned SFace features.

        `feature` / `embedding` refer to the largest face (the credential
        portrait on a document). `all_features` holds one feature per detection
        so a 1:1 comparison can be attempted against EVERY face present.

        Design note: an earlier version refused outright when a document held
        faces of more than one person. That was wrong for a border system — it
        turned the single most important check into "not performed" and gave the
        officer no biometric information at all. The comparison now always runs
        against every face, the best match is reported, and a multi-person
        document is raised as its own separate finding.
        """
        result: Dict[str, Any] = {
            "ok": False,
            "face_count": 0,
            "confidence": None,
            "feature": None,
            "embedding": None,
            "all_features": [],
            "all_detections": [],
            "distinct_people": 0,
            "crop_path": None,
            "reason": None,
            "notes": [],
        }

        if not self.models_available:
            result["reason"] = (
                "Biometric models unavailable (YuNet/SFace not loaded) — "
                "verification cannot be performed"
            )
            return result

        if not image_path or not os.path.exists(image_path):
            result["reason"] = "Image file not readable"
            return result

        bgr = cv2.imread(image_path)
        if bgr is None:
            result["reason"] = "Image could not be decoded"
            return result

        detections = self.detect_faces(bgr)
        result["face_count"] = len(detections)

        if not detections:
            result["reason"] = "No face detected above the quality threshold"
            return result

        features = [self._feature_for(bgr, d) for d in detections]
        if features[0] is None:
            result["reason"] = "Feature extraction failed on the primary face"
            return result

        primary = detections[0]
        result["all_detections"] = detections
        result["all_features"] = features
        result["confidence"] = round(primary.confidence, 4)

        if is_document and len(detections) > 1:
            notes, distinct = self._classify_document_faces(bgr, detections, features)
            result["notes"] = notes
            result["distinct_people"] = distinct
        elif not is_document and len(detections) > 1:
            # Several people at the counter is an acquisition problem worth
            # flagging, but the largest (nearest) face is still the traveller
            # being processed, so the check proceeds.
            result["notes"] = [
                f"{len(detections)} faces in the live capture — matched against "
                f"the largest (nearest) face. Recapture with only the traveller "
                f"in frame for a clean record."
            ]

        embedding = _l2_normalise(features[0])
        if not embedding or len(embedding) != SFACE_DIM:
            result["reason"] = "Degenerate feature vector — discarded"
            return result

        result["ok"] = True
        result["feature"] = features[0]
        result["embedding"] = embedding
        result["crop_path"] = self._save_crop(image_path, self._crop_with_margin(bgr, primary))
        return result

    # ── Backwards-compatible helpers ────────────────────────────────────────

    def detect_and_crop_face(
        self, image_path: str, is_document: bool = False
    ) -> Tuple[Optional[str], Optional[np.ndarray], Optional[Any]]:
        """
        Legacy 3-tuple helper: (crop_path, crop_bgr, detection_row).

        Unlike the old implementation this returns None rather than falling back
        to a fixed "the photo is usually here" rectangle. A guessed region is
        not a face, and treating it as one produced unverifiable comparisons
        that were nonetheless scored and reported.
        """
        if not image_path or not os.path.exists(image_path) or not HAS_CV2:
            return None, None, None

        bgr = cv2.imread(image_path)
        if bgr is None:
            return None, None, None

        detections = self.detect_faces(bgr)
        if not detections:
            return None, None, None

        primary = detections[0]
        crop = self._crop_with_margin(bgr, primary)
        return self._save_crop(image_path, crop), crop, primary.row

    def crop_face_from_document(
        self, doc_image_path: str
    ) -> Tuple[Optional[str], Optional[Image.Image]]:
        crop_path, crop_bgr, _ = self.detect_and_crop_face(doc_image_path, is_document=True)
        if crop_path and crop_bgr is not None:
            return crop_path, Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
        return None, None

    def get_embedding(self, image_path: str) -> Optional[List[float]]:
        """
        Aligned, L2-normalised SFace embedding, or None.

        None means "no usable face". It never means "here is a vector anyway".
        """
        return self.analyse_image(image_path).get("embedding")

    # ── 1:1 verification ────────────────────────────────────────────────────

    def match_faces_1to1(
        self, doc_image_path: str, live_face_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        Verify a live capture against a document portrait.

        Contract:
          similarity_score   raw cosine clamped to [0, 1] for display
          raw_cosine         raw cosine in [-1, 1], or None if not computed
          match_threshold    the cosine actually required to pass
          match_passed       True / False, or None when no comparison happened
          biometric_performed  False when there was nothing to compare
          embedding          128-d live-capture embedding, or None
        """
        threshold = _effective_1to1_threshold()

        base: Dict[str, Any] = {
            "similarity_score": None,
            "raw_cosine": None,
            "match_threshold": round(threshold, 4),
            "match_passed": None,
            "biometric_performed": False,
            "is_live": None,
            "liveness_checked": False,
            "crop_path": None,
            "embedding": None,
            "document_face_count": 0,
            "live_face_count": 0,
            "document_distinct_people": 0,
            # Cosine against each face found on the document, best first.
            "per_face_scores": [],
            "matched_face_index": None,
            # Machine-readable reason the comparison did not happen, so callers
            # can render an accurate message instead of assuming "no selfie".
            "not_performed_reason": None,
            "flags": [],
        }

        if not self.models_available:
            base["not_performed_reason"] = "MODELS_UNAVAILABLE"
            base["flags"] = [
                "Biometric models unavailable — face verification not performed. "
                "MANUAL VERIFICATION REQUIRED"
            ]
            return base

        # is_document=True lets a legitimate ICAO ghost portrait through: extra
        # faces are cleared when they are the SAME holder, and only refused when
        # they are a different person.
        doc = self.analyse_image(doc_image_path, is_document=True)
        base["document_face_count"] = doc["face_count"]
        base["crop_path"] = doc.get("crop_path")

        # Multi-face findings are recorded but never block verification.
        doc_notes = list(doc.get("notes") or [])
        base["document_distinct_people"] = doc.get("distinct_people", 0)

        if not doc["ok"]:
            base["not_performed_reason"] = "NO_DOCUMENT_PORTRAIT"
            base["flags"] = doc_notes + [
                f"No usable credential portrait in the document image "
                f"({doc['reason']}) — biometric comparison not performed. "
                f"MANUAL VERIFICATION REQUIRED"
            ]
            return base

        # Store the document embedding so a document-only scan still contributes
        # a genuine biometric to the gallery.
        base["embedding"] = doc["embedding"]

        if not live_face_path or not os.path.exists(live_face_path):
            base["not_performed_reason"] = "NO_LIVE_CAPTURE"
            base["flags"] = doc_notes + [
                "No live face capture supplied — 1:1 biometric match not performed"
            ]
            return base

        live = self.analyse_image(live_face_path, is_document=False)
        base["live_face_count"] = live["face_count"]

        if not live["ok"]:
            base["not_performed_reason"] = "NO_FACE_IN_LIVE_CAPTURE"
            base["flags"] = doc_notes + [
                f"No usable face in the live capture ({live['reason']}) — "
                f"biometric comparison not performed. MANUAL VERIFICATION REQUIRED"
            ]
            return base

        base["embedding"] = live["embedding"]

        # Compare the live face against EVERY face on the document and keep the
        # best. On a single-portrait passport this is identical to comparing
        # against the portrait. On a multi-face document it answers the question
        # that actually matters — "is the traveller in front of me anywhere on
        # this document?" — instead of giving up.
        doc_features = doc.get("all_features") or [doc["feature"]]
        per_face: List[Dict[str, Any]] = []

        for idx, feat in enumerate(doc_features):
            if feat is None:
                continue
            try:
                raw = float(
                    self.recognizer.match(feat, live["feature"], cv2.FaceRecognizerSF_FR_COSINE)
                )
            except Exception:
                continue
            per_face.append({
                "face_index": idx,
                "is_primary": idx == 0,
                "cosine": round(float(np.clip(raw, -1.0, 1.0)), 4),
            })

        if not per_face:
            base["not_performed_reason"] = "COMPARISON_ERROR"
            base["flags"] = doc_notes + [
                "Biometric comparison could not be computed against any face on "
                "the document. MANUAL VERIFICATION REQUIRED"
            ]
            return base

        per_face.sort(key=lambda e: e["cosine"], reverse=True)
        best = per_face[0]
        cos = best["cosine"]
        match_passed = cos >= threshold

        base["per_face_scores"] = per_face
        base["matched_face_index"] = best["face_index"]

        # Ghost-portrait / multi-person notes carry forward so the officer sees
        # why the document had several faces even on a successful comparison.
        flags: List[str] = list(doc_notes)
        is_live, liveness_flag = self.verify_liveness_path(live_face_path)
        if liveness_flag:
            flags.append(liveness_flag)

        if len(per_face) > 1:
            detail = ", ".join(
                f"face {e['face_index'] + 1}: {e['cosine']:.3f}" for e in per_face
            )
            flags.append(
                f"Live capture compared against all {len(per_face)} faces on the "
                f"document ({detail}). Best match: face "
                f"{best['face_index'] + 1} at cosine {cos:.4f}"
                + ("" if best["is_primary"] else " — NOT the main portrait")
            )

        if match_passed and not best["is_primary"]:
            flags.append(
                f"The traveller matches a SECONDARY face on the document, not the "
                f"main portrait. On a genuine credential the holder is the main "
                f"portrait — treat this as a possible photo-substitution or a "
                f"non-credential document. MANUAL VERIFICATION REQUIRED"
            )

        if base["document_distinct_people"]:
            flags.append(
                f"This document carries faces of "
                f"{base['document_distinct_people'] + 1} different people — it is "
                f"not a single-holder credential. Verify the document type."
            )

        if not match_passed:
            flags.append(
                f"Biometric mismatch: best cosine similarity {cos:.4f} across "
                f"{len(per_face)} document face(s) is below the required "
                f"{threshold:.3f} — the live traveller does not match this document"
            )

        if doc["confidence"] is not None and live["confidence"] is not None:
            flags.append(
                f"Detector confidence — document {doc['confidence']:.2f}, "
                f"live {live['confidence']:.2f}"
            )

        base.update({
            # Negative cosines are genuine "nothing like each other" results.
            # Clamp only the display value; keep the true figure alongside it.
            "similarity_score": round(max(0.0, cos), 4),
            "raw_cosine": cos,
            "match_passed": bool(match_passed),
            "biometric_performed": True,
            "is_live": is_live,
            "liveness_checked": True,
            "flags": flags,
        })
        return base

    # ── 1:N search ──────────────────────────────────────────────────────────

    def rank_gallery(
        self,
        probe_embedding: List[float],
        gallery: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Rank a gallery against a probe embedding.

        `gallery` items must carry an "embedding" key; every other key is
        preserved on the way out. Entries whose embedding cannot be compared
        (wrong length, zero vector, missing) are reported separately in
        `skipped` instead of being coerced into a comparison.
        """
        threshold = _effective_1toN_threshold()
        scored: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for entry in gallery:
            emb = entry.get("embedding")
            cos = cosine_similarity(probe_embedding, emb)
            if cos is None:
                skipped.append({
                    **{k: v for k, v in entry.items() if k != "embedding"},
                    "reason": (
                        f"incomparable embedding (length {len(emb) if emb else 0}, "
                        f"expected {len(probe_embedding)})"
                    ),
                })
                continue

            scored.append({
                **{k: v for k, v in entry.items() if k != "embedding"},
                "cosine_similarity": round(cos, 4),
                "similarity_percent": round(max(0.0, cos) * 100, 2),
                "is_match": bool(cos >= threshold),
            })

        scored.sort(key=lambda e: e["cosine_similarity"], reverse=True)
        matches = [e for e in scored if e["is_match"]]

        return {
            "threshold": round(threshold, 4),
            "compared": len(scored),
            "skipped": skipped,
            "results": scored[:top_k],
            "matches": matches[:top_k],
            "match_count": len(matches),
            "best": scored[0] if scored else None,
        }

    def compare_two_images(self, path_a: str, path_b: str) -> Dict[str, Any]:
        """
        Direct 1:1 comparison of two arbitrary images.

        Used by the face-comparison endpoint and by verification tooling. Same
        rules as match_faces_1to1: raw cosine, no rescale, explicit refusal when
        a face is missing or ambiguous.
        """
        threshold = _effective_1to1_threshold()
        a = self.analyse_image(path_a)
        b = self.analyse_image(path_b)

        out: Dict[str, Any] = {
            "threshold": round(threshold, 4),
            "image_a": {
                "face_count": a["face_count"],
                "confidence": a["confidence"],
                "usable": a["ok"],
                "reason": a["reason"],
            },
            "image_b": {
                "face_count": b["face_count"],
                "confidence": b["confidence"],
                "usable": b["ok"],
                "reason": b["reason"],
            },
            "cosine_similarity": None,
            "similarity_percent": None,
            "is_match": None,
            "verdict": None,
        }

        if not a["ok"] or not b["ok"]:
            out["verdict"] = "NOT_COMPARABLE"
            return out

        cos = cosine_similarity(a["embedding"], b["embedding"])
        if cos is None:
            out["verdict"] = "NOT_COMPARABLE"
            return out

        out["cosine_similarity"] = round(cos, 4)
        out["similarity_percent"] = round(max(0.0, cos) * 100, 2)
        out["is_match"] = bool(cos >= threshold)
        out["verdict"] = "SAME_PERSON" if cos >= threshold else "DIFFERENT_PERSON"
        return out

    # ── Liveness ────────────────────────────────────────────────────────────

    def verify_liveness_path(self, image_path: str) -> Tuple[Optional[bool], Optional[str]]:
        try:
            with Image.open(image_path) as img:
                return self.verify_liveness(img.convert("RGB"))
        except Exception as exc:
            # Fail closed: an unreadable capture is "unknown", not "live". The
            # old code returned True here, so any exception silently produced a
            # liveness PASS.
            return None, f"Liveness could not be assessed ({exc}) — treat as unverified"

    def verify_liveness(self, face_image: Image.Image) -> Tuple[Optional[bool], Optional[str]]:
        """
        Presentation-attack heuristic: FFT high/low frequency energy ratio plus
        edge variance. Catches obvious screen replays and flat paper prints.

        This is a texture heuristic, not a trained anti-spoofing model. It does
        not detect a high-quality print or a masked presentation, and the flag
        text says so rather than implying certified liveness.
        """
        try:
            gray = ImageOps.grayscale(face_image).resize((128, 128))
            arr = np.array(gray, dtype=np.float32)

            spectrum = np.abs(np.fft.fftshift(np.fft.fft2(arr)))
            rows, cols = arr.shape
            crow, ccol = rows // 2, cols // 2
            radius = 16

            mask = np.ones((rows, cols), np.uint8)
            mask[crow - radius:crow + radius, ccol - radius:ccol + radius] = 0

            high = float(np.mean(spectrum * mask))
            low = float(np.mean(spectrum * (1 - mask))) + 1e-5
            freq_ratio = high / low

            edge_variance = float(
                np.var(np.array(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32))
            )

            if (
                edge_variance < settings.LIVENESS_MIN_EDGE_VARIANCE
                or freq_ratio < settings.LIVENESS_MIN_FREQ_RATIO
            ):
                return False, (
                    f"Liveness alert: low texture detail (edge variance "
                    f"{edge_variance:.1f}, frequency ratio {freq_ratio:.4f}) — "
                    f"possible screen replay or paper print"
                )
            return True, None
        except Exception as exc:
            return None, f"Liveness could not be assessed ({exc}) — treat as unverified"


face_service = FaceService()

"""
Face Verification & Biometric Feature Extraction Service.

Features:
- State-of-the-art YuNet Deep Face Detection for documents and live camera captures
- SFace Deep Biometric Feature Extraction & mathematical Cosine Similarity verification
- Fourier / FFT frequency domain & Laplacian texture anti-spoofing liveness
- Generates normalized feature vectors for cross-encounter Identity Graph continuity search
"""

import os
import math
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageOps, ImageFilter
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def _preprocess_for_matching(bgr_img):
    """
    Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) to normalize
    lighting differences between printed ID photos and live webcam captures.
    This dramatically improves cross-domain face matching accuracy.
    """
    if not HAS_CV2 or bgr_img is None:
        return bgr_img
    try:
        lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        merged = cv2.merge([l_channel, a_channel, b_channel])
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    except Exception:
        return bgr_img


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(CURRENT_DIR, "face_detection_yunet.onnx")
SFACE_PATH = os.path.join(CURRENT_DIR, "face_recognition_sface.onnx")


class BiometricFeatureExtractor:
    """
    SFace deep feature extractor for normalized facial embeddings.
    """
    def __init__(self):
        self.dim = 128
        self.recognizer = None
        if HAS_CV2 and os.path.exists(SFACE_PATH):
            try:
                self.recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
            except Exception as e:
                print(f"[FaceService] Warning initializing SFace: {e}")

    def get_embedding(self, cv2_or_pil_img: Any) -> List[float]:
        """
        Converts face crop into a normalized 128-dimensional biometric embedding.
        """
        try:
            if isinstance(cv2_or_pil_img, Image.Image):
                arr = np.array(cv2_or_pil_img.convert("RGB"))
                cv_img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if HAS_CV2 else None
            else:
                cv_img = cv2_or_pil_img

            if self.recognizer is not None and cv_img is not None:
                # Resize to SFace standard 112x112 input
                aligned = cv2.resize(cv_img, (112, 112))
                feature = self.recognizer.feature(aligned)
                vec = feature.flatten().tolist()
                norm = math.sqrt(sum(x * x for x in vec)) + 1e-7
                return [round(float(x / norm), 5) for x in vec]

            # Fallback normalized representation
            if isinstance(cv2_or_pil_img, Image.Image):
                pil_img = cv2_or_pil_img.convert("L").resize((16, 16))
            else:
                pil_img = Image.fromarray(cv_img).convert("L").resize((16, 16))
            raw = np.array(pil_img, dtype=np.float32).flatten()[:self.dim]
            norm = np.linalg.norm(raw) + 1e-7
            return [round(float(x / norm), 5) for x in raw.tolist()]
        except Exception as e:
            print(f"[FaceEmbedding] Extraction error: {e}")
            return [0.0] * self.dim


class FaceService:
    def __init__(self):
        self.extractor = BiometricFeatureExtractor()
        self.detector = None
        self.recognizer = None

        if HAS_CV2:
            if os.path.exists(YUNET_PATH):
                try:
                    self.detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), 0.5)
                except Exception as e:
                    print(f"[FaceService] Warning initializing YuNet: {e}")

            if os.path.exists(SFACE_PATH):
                try:
                    self.recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
                except Exception as e:
                    print(f"[FaceService] Warning initializing SFace: {e}")

    def detect_and_crop_face(self, image_path: str, is_document: bool = False) -> Tuple[Optional[str], Optional[np.ndarray], Optional[Any]]:
        """
        Uses YuNet face detector to locate, align, and crop the face from an image.
        Works across Indian Aadhaar cards, Passports, National IDs, and live captures.
        """
        if not os.path.exists(image_path) or not HAS_CV2:
            return None, None, None

        try:
            bgr_img = cv2.imread(image_path)
            if bgr_img is None:
                return None, None, None

            h, w, _ = bgr_img.shape
            face_box = None
            detected_face_info = None

            if self.detector is not None:
                self.detector.setInputSize((w, h))
                self.detector.setScoreThreshold(0.5)
                _, faces = self.detector.detect(bgr_img)
                if faces is None or len(faces) == 0:
                    # Retry with lower threshold for noisy or low-contrast passport/ID photos
                    self.detector.setScoreThreshold(0.3)
                    _, faces = self.detector.detect(bgr_img)

                if faces is not None and len(faces) > 0:
                    detected_face_info = faces[0]
                    x, y, fw, fh = faces[0][:4]
                    x, y, fw, fh = int(x), int(y), int(fw), int(fh)
                    # Add margin
                    margin_x = int(fw * 0.15)
                    margin_y = int(fh * 0.15)
                    x1 = max(0, x - margin_x)
                    y1 = max(0, y - margin_y)
                    x2 = min(w, x + fw + margin_x)
                    y2 = min(h, y + fh + margin_y)
                    face_box = (x1, y1, x2, y2)

            # Fallback if no face detected by YuNet
            if face_box is None:
                if is_document:
                    # Aadhaar photo area: left 3-40% width, top 12-72% height
                    # (accounts for side-printed "Aadhaar no. issued" text strip)
                    face_box = (int(w * 0.03), int(h * 0.12), int(w * 0.40), int(h * 0.72))
                else:
                    face_box = (int(w * 0.15), int(h * 0.10), int(w * 0.85), int(h * 0.90))

            x1, y1, x2, y2 = face_box
            cropped_bgr = bgr_img[y1:y2, x1:x2]

            crop_dir = os.path.dirname(image_path)
            crop_filename = f"crop_face_{os.path.basename(image_path)}"
            crop_path = os.path.join(crop_dir, crop_filename)
            cv2.imwrite(crop_path, cropped_bgr)

            return crop_path, cropped_bgr, detected_face_info
        except Exception as e:
            print(f"[FaceCrop] Error: {e}")
            return None, None, None

    def crop_face_from_document(self, doc_image_path: str) -> Tuple[Optional[str], Optional[Image.Image]]:
        """
        Backwards-compatible helper returning crop path and PIL Image.
        """
        crop_path, cropped_bgr, _ = self.detect_and_crop_face(doc_image_path, is_document=True)
        if crop_path and cropped_bgr is not None:
            rgb = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB)
            return crop_path, Image.fromarray(rgb)
        return None, None

    def match_faces_1to1(
        self, doc_image_path: str, live_face_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        Performs 1:1 facial biometric matching using YuNet + SFace.
        """
        doc_crop_path, doc_bgr, doc_face_info = self.detect_and_crop_face(doc_image_path, is_document=True)

        if not doc_crop_path or doc_bgr is None:
            # Fallback if document cannot be loaded - FORCE SECONDARY REVIEW
            return {
                "similarity_score": 0.35,  # LOW SCORE - Force review
                "is_live": False,  # Assume not live
                "match_passed": False,  # Do not auto-approve
                "crop_path": doc_crop_path or doc_image_path,
                "embedding": [0.0] * 512,
                "flags": ["❌ Could not extract face from document - SECONDARY REVIEW REQUIRED"],
            }

        # If live camera feed not provided, the comparison simply did not happen.
        # `biometric_performed=False` distinguishes "not tested" from "tested and
        # failed" — without it the risk engine reported a genuine passport as an
        # impostor presentation purely because no selfie was submitted.
        if not live_face_path or not os.path.exists(live_face_path):
            doc_emb = self.extractor.get_embedding(doc_bgr)
            return {
                "similarity_score": 0.0,
                "biometric_performed": False,
                "is_live": None,          # unknown, not "failed"
                "match_passed": None,     # unknown, not "failed"
                "crop_path": doc_crop_path,
                "embedding": doc_emb,
                "flags": ["No live face capture supplied — biometric match not performed"],
            }

        try:
            live_crop_path, live_bgr, live_face_info = self.detect_and_crop_face(live_face_path, is_document=False)
            if live_bgr is None:
                live_bgr = cv2.imread(live_face_path)

            doc_raw_img = cv2.imread(doc_image_path)
            live_raw_img = cv2.imread(live_face_path)

            # Apply CLAHE preprocessing to normalize lighting differences
            # between printed ID photos and webcam captures
            doc_raw_img = _preprocess_for_matching(doc_raw_img)
            live_raw_img = _preprocess_for_matching(live_raw_img)
            doc_bgr = _preprocess_for_matching(doc_bgr)
            live_bgr = _preprocess_for_matching(live_bgr)

            # Deep feature extraction and matching with SFace
            if self.recognizer is not None and doc_face_info is not None and live_face_info is not None:
                face1_align = self.recognizer.alignCrop(doc_raw_img, doc_face_info)
                face2_align = self.recognizer.alignCrop(live_raw_img, live_face_info)

                f1 = self.recognizer.feature(face1_align)
                f2 = self.recognizer.feature(face2_align)

                cos_sim = float(self.recognizer.match(f1, f2, cv2.FaceRecognizerSF_FR_COSINE))

                # Cross-domain threshold lowered to 0.30 for document-to-live matching.
                # Standard SFace 0.363 is calibrated for same-domain comparisons;
                # printed ID photos vs webcam captures (glasses, lighting, age gaps)
                # consistently produce lower cosine scores for genuine matches.
                CROSS_DOMAIN_THRESHOLD = 0.30
                if cos_sim >= CROSS_DOMAIN_THRESHOLD:
                    calibrated = 0.72 + min(0.27, ((cos_sim - CROSS_DOMAIN_THRESHOLD) / (1.0 - CROSS_DOMAIN_THRESHOLD)) * 0.27)
                    match_passed = True
                else:
                    calibrated = max(0.15, (cos_sim + 0.2) / (CROSS_DOMAIN_THRESHOLD + 0.2) * 0.70)
                    match_passed = False

                embedding = f2.flatten().tolist()
                norm = math.sqrt(sum(x * x for x in embedding)) + 1e-7
                norm_emb = [round(float(x / norm), 5) for x in embedding]
            else:
                # Fallback extractor with CLAHE-preprocessed crops
                f1_vec = self.extractor.get_embedding(doc_bgr)
                f2_vec = self.extractor.get_embedding(live_bgr)
                u = np.array(f1_vec, dtype=np.float32)
                v = np.array(f2_vec, dtype=np.float32)
                cos_sim = float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-7))
                calibrated = max(0.50, min(0.98, (cos_sim + 1.0) / 2.0))
                match_passed = calibrated >= 0.68
                norm_emb = f2_vec

            # Anti-spoofing liveness check on live image
            live_pil = Image.open(live_face_path)
            is_live, liveness_flag = self.verify_liveness(live_pil)

            flags = []
            if not is_live and liveness_flag:
                flags.append(liveness_flag)
            if not match_passed:
                flags.append(f"Biometric threshold not met: Match confidence {calibrated * 100:.1f}% below border standard (72%)")

            return {
                "similarity_score": round(calibrated, 4),
                "is_live": is_live,
                "match_passed": match_passed and is_live,
                "crop_path": doc_crop_path,
                "embedding": norm_emb,
                "flags": flags,
            }
        except Exception as e:
            print(f"[FaceMatch] Error: {e}")
            doc_emb = self.extractor.get_embedding(doc_bgr)
            # On error - return LOW score to force manual review, not auto-approval
            return {
                "similarity_score": 0.40,  # LOW SCORE - Error during matching
                "is_live": False,  # Assume not verified
                "match_passed": False,  # Do not auto-approve on error
                "crop_path": doc_crop_path,
                "embedding": doc_emb,
                "flags": [f"⚠️ Facial matching error: {str(e)} - MANUAL VERIFICATION REQUIRED"],
            }

    def verify_liveness(self, face_image: Image.Image) -> Tuple[bool, Optional[str]]:
        """
        Anti-spoofing & liveness detection using Fourier (FFT) texture frequencies
        and edge energy to catch screen replays and paper print attacks.
        """
        try:
            gray = ImageOps.grayscale(face_image).resize((128, 128))
            arr = np.array(gray, dtype=np.float32)

            f = np.fft.fft2(arr)
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = np.abs(fshift)

            rows, cols = arr.shape
            crow, ccol = rows // 2, cols // 2

            radius = 16
            mask = np.ones((rows, cols), np.uint8)
            mask[crow - radius:crow + radius, ccol - radius:ccol + radius] = 0
            high_freq_energy = float(np.mean(magnitude_spectrum * mask))
            low_freq_energy = float(np.mean(magnitude_spectrum * (1 - mask))) + 1e-5
            freq_ratio = high_freq_energy / low_freq_energy

            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_arr = np.array(edges, dtype=np.float32)
            edge_variance = float(np.var(edge_arr))

            # Relaxed thresholds to reduce false positives on dark/uneven
            # webcam captures (edge_variance 15→10, freq_ratio 0.005→0.003)
            if edge_variance < 10.0 or freq_ratio < 0.003:
                return False, "Liveness alert: Low texture variance detected (potential digital screen replay or paper print attack)"

            return True, None
        except Exception as e:
            print(f"[Liveness] Verification error: {e}")
            return True, None


face_service = FaceService()

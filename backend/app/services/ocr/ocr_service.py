"""
OCR & Image Preprocessing Service for Border Document Screening.

Handles image deskewing, contrast enhancement, MRZ region extraction, and
cross-platform text extraction.

Engine chain (configurable via OCR_LOCAL_ENGINES, first available wins):
  1. tesseract     — pytesseract, works on macOS / Linux / Windows
  2. apple_vision  — native macOS Vision framework via pyobjc
  3. windows       — legacy WinRT OCR engine

Google Cloud Vision runs upstream in the pipeline; when it returns text the
pipeline hands it to process_document() directly and no local engine is needed.
"""

import logging
import os
import re
import asyncio
import shutil
import sys
from typing import Dict, Any, Tuple, Optional, List
from PIL import Image, ImageEnhance, ImageFilter

from app.core.config import settings
from app.services.ocr.mrz import parse_mrz_lines

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    import numpy as np


class OCRError(RuntimeError):
    """Raised when no OCR engine could read the document at all."""


class OCRService:
    def __init__(self):
        self._engine_cache: Optional[str] = None

    def preprocess_image(self, image_path: str) -> Any:
        """
        Deskews, resizes, and cleans up document image for OCR processing.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Could not load image at path: {image_path}")

        if HAS_CV2:
            image = cv2.imread(image_path)
            if image is not None:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
                return blurred

        # Fallback PIL implementation
        pil_img = Image.open(image_path).convert("L")
        enhancer = ImageEnhance.Contrast(pil_img)
        enhanced = enhancer.enhance(1.5)
        blurred = enhanced.filter(ImageFilter.GaussianBlur(radius=1))
        return blurred

    # ── engine: cross-platform dispatcher ──────────────────────────────────
    def extract_text(self, image_path: str) -> Tuple[str, List[str], str]:
        """
        Runs the first available local OCR engine.

        Returns (full_text, lines, engine_name). engine_name is "none" when
        every configured engine is unavailable or produced nothing.
        """
        engines = {
            "tesseract": self.extract_text_via_tesseract,
            "apple_vision": self.extract_text_via_apple_vision,
            "windows": self.extract_text_via_windows_ocr,
        }

        attempted: List[str] = []
        for name in settings.local_ocr_engines:
            runner = engines.get(name)
            if runner is None:
                continue
            attempted.append(name)
            try:
                text, lines = runner(image_path)
            except Exception as exc:  # noqa: BLE001 - try the next engine
                logger.debug("[OCR] engine '%s' raised: %s", name, exc)
                continue
            if text and text.strip():
                logger.info("[OCR] engine '%s' extracted %d chars.", name, len(text))
                self._engine_cache = name
                return text, lines, name

        logger.error(
            "[OCR] No local engine produced text (tried: %s). "
            "Install Tesseract (`brew install tesseract`) or set "
            "OCR_PROVIDER=google_vision with credentials.",
            ", ".join(attempted) or "none configured",
        )
        return "", [], "none"

    # ── engine: Tesseract (macOS / Linux / Windows) ────────────────────────
    def extract_text_via_tesseract(self, image_path: str) -> Tuple[str, List[str]]:
        """
        Runs Tesseract on both the raw image and a preprocessed variant,
        keeping whichever produced more text. MRZ glyphs read far better on
        the contrast-enhanced version.
        """
        try:
            import pytesseract
        except ImportError:
            return "", []

        cmd = settings.TESSERACT_CMD or shutil.which("tesseract")
        if not cmd:
            logger.debug("[OCR] tesseract binary not found on PATH.")
            return "", []
        pytesseract.pytesseract.tesseract_cmd = cmd

        candidates: List[Any] = []
        try:
            candidates.append(Image.open(image_path).convert("RGB"))
        except Exception as exc:
            logger.warning("[OCR] could not open %s: %s", image_path, exc)
            return "", []

        try:
            processed = self.preprocess_image(image_path)
            if HAS_CV2 and isinstance(processed, np.ndarray):
                candidates.append(Image.fromarray(processed))
            elif isinstance(processed, Image.Image):
                candidates.append(processed)
        except Exception:
            pass

        best_text = ""
        # psm 3 = full auto page segmentation, psm 6 = uniform block (better for MRZ)
        for img in candidates:
            for psm in (3, 6):
                try:
                    text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm}")
                except Exception as exc:
                    logger.debug("[OCR] tesseract psm=%s failed: %s", psm, exc)
                    continue
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text

        lines = [ln.strip() for ln in best_text.splitlines() if ln.strip()]
        return best_text, lines

    # ── engine: native macOS Vision framework ──────────────────────────────
    def extract_text_via_apple_vision(self, image_path: str) -> Tuple[str, List[str]]:
        """Uses the on-device macOS Vision text recognizer (needs pyobjc)."""
        if sys.platform != "darwin":
            return "", []
        try:
            import Quartz
            import Vision
            from Foundation import NSURL
        except ImportError:
            return "", []

        url = NSURL.fileURLWithPath_(os.path.abspath(image_path))
        source = Quartz.CGImageSourceCreateWithURL(url, None)
        if source is None:
            return "", []
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
        if cg_image is None:
            return "", []

        collected: List[str] = []

        def _handler(request, error):
            if error is not None:
                return
            for observation in request.results() or []:
                candidate = observation.topCandidates_(1)
                if candidate and candidate.count() > 0:
                    collected.append(str(candidate.objectAtIndex_(0).string()))

        request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(_handler)
        request.setRecognitionLevel_(1)  # 1 == accurate
        request.setUsesLanguageCorrection_(False)  # MRZ is not natural language

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
        ok, err = handler.performRequests_error_([request], None)
        if not ok:
            logger.debug("[OCR] Apple Vision request failed: %s", err)
            return "", []

        lines = [ln.strip() for ln in collected if ln.strip()]
        return "\n".join(lines), lines

    # ── engine: legacy WinRT ───────────────────────────────────────────────
    def extract_text_via_windows_ocr(self, image_path: str) -> Tuple[str, List[str]]:
        """
        Executes native offline Windows OCR (WinSDK) on the image.
        Returns empty on non-Windows platforms.
        """
        if sys.platform != "win32":
            return "", []
        try:
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage import StorageFile

            async def _ocr():
                engine = OcrEngine.try_create_from_user_profile_languages()
                abs_path = os.path.abspath(image_path)
                file = await StorageFile.get_file_from_path_async(abs_path)
                stream = await file.open_async(0)
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                result = await engine.recognize_async(bitmap)
                lines = [line.text.strip() for line in result.lines if line.text.strip()]
                return "\n".join(lines), lines

            # Handle existing event loop if called within async context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(asyncio.run, _ocr()).result()
                else:
                    return loop.run_until_complete(_ocr())
            except RuntimeError:
                return asyncio.run(_ocr())

        except Exception as e:
            logger.debug("[OCR] Windows OCR engine error: %s", e)
            return "", []

    def _extract_passport_visual_fields(self, ocr_lines: List[str], full_text: str) -> Dict[str, Any]:
        """
        Extracts structured fields from the visual inspection zone of a passport.
        Filters out header labels, sample watermarks, and boilerplate text.
        """
        data = {
            "surname": "",
            "given_names": "",
            "holder_name": "",
            "document_number": None,
            "date_of_birth": None,
            "expiry_date": None,
            "sex": None,
            "nationality": "IND",
            "issuing_country": "IND",
        }

        # Ignored words / watermarks / headers that should never be names or numbers
        blacklist = {
            "SAMPLE", "IMMIHELP", "SPECIMEN", "WATERMARK", "REPUBLIC", "INDIA",
            "GOVERNMENT", "PASSPORT", "PLACE OF BIRTH", "DATE OF BIRTH", "DATE OF EXPIRY",
            "COUNTRY CODE", "SURNAME", "GIVEN NAMES", "AUTHORITY", "SIGNATURE",
            "TYPE", "CODE", "NATIONALITY", "SEX", "INDIAN"
        }

        num_lines = len(ocr_lines)
        for i, line in enumerate(ocr_lines):
            clean_l = line.strip()
            upper_l = clean_l.upper()

            # Surname extraction
            if re.search(r"\b(?:Surname|Nom)\b", clean_l, re.IGNORECASE) and not data["surname"]:
                # Check same line after separator
                parts = re.split(r"[:/]", clean_l, maxsplit=1)
                if len(parts) > 1 and parts[1].strip() and not any(b in parts[1].upper() for b in blacklist):
                    val = re.sub(r"[^A-Za-z\s-]", "", parts[1]).strip()
                    if len(val) >= 2:
                        data["surname"] = val
                elif i + 1 < num_lines:
                    candidate = ocr_lines[i + 1].strip()
                    if not any(b in candidate.upper() for b in blacklist):
                        val = re.sub(r"[^A-Za-z\s-]", "", candidate).strip()
                        if len(val) >= 2 and not any(char.isdigit() for char in val):
                            data["surname"] = val

            # Given Names extraction
            if re.search(r"\b(?:Given\s*Name|Given\s*Names|N\.m|Name\(s\)|Names|Prénoms)\b", clean_l, re.IGNORECASE) and not data["given_names"]:
                parts = re.split(r"[:/)]", clean_l, maxsplit=1)
                if len(parts) > 1 and parts[1].strip() and not any(b in parts[1].upper() for b in blacklist):
                    val = re.sub(r"[^A-Za-z\s-]", "", parts[1]).strip()
                    if len(val) >= 2:
                        data["given_names"] = val
                elif i + 1 < num_lines:
                    candidate = ocr_lines[i + 1].strip()
                    if not any(b in candidate.upper() for b in blacklist):
                        val = re.sub(r"[^A-Za-z\s-]", "", candidate).strip()
                        if len(val) >= 2 and not any(char.isdigit() for char in val):
                            data["given_names"] = val

            # Passport No extraction
            if re.search(r"\b(?:Passport\s*No|Passport\s*Number|P\.No)\b", clean_l, re.IGNORECASE) and not data["document_number"]:
                parts = re.split(r"[:/.]", clean_l, maxsplit=1)
                for part_candidate in [parts[-1] if len(parts) > 1 else "", ocr_lines[i + 1] if i + 1 < num_lines else ""]:
                    match = re.search(r"\b([A-Z0-9]{7,9})\b", part_candidate.strip())
                    if match:
                        cand = match.group(1).upper()
                        if cand not in blacklist and any(c.isdigit() for c in cand):
                            data["document_number"] = cand
                            break

            # Date of Birth
            if re.search(r"\b(?:Date\s*of\s*Birth|DOB)\b", clean_l, re.IGNORECASE) and not data["date_of_birth"]:
                # Check current or next line for DD/MM/YYYY
                for text_to_check in [clean_l, ocr_lines[i + 1] if i + 1 < num_lines else ""]:
                    d_match = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", text_to_check)
                    if d_match:
                        d, m, y = d_match.groups()
                        data["date_of_birth"] = f"{y}-{m}-{d}"
                        break

            # Expiry Date
            if re.search(r"\b(?:Expiry|Date\s*of\s*Expiry)\b", clean_l, re.IGNORECASE) and not data["expiry_date"]:
                # Check current line, next line, or lines after
                found_dates = []
                for offset in range(0, 4):
                    if i + offset < num_lines:
                        d_matches = re.findall(r"(\d{2})[/-](\d{2})[/-](\d{4})", ocr_lines[i + offset])
                        for d, m, y in d_matches:
                            found_dates.append(f"{y}-{m}-{d}")
                if found_dates:
                    # Sort dates so later date (expiry) is picked over issue date
                    found_dates.sort()
                    data["expiry_date"] = found_dates[-1]

            # Sex / Gender
            if ("SEX" in upper_l or "GENDER" in upper_l) and not data["sex"]:
                if "FEMALE" in upper_l or "/ F" in upper_l or " F" in upper_l:
                    data["sex"] = "F"
                elif "MALE" in upper_l or "/ M" in upper_l or " M" in upper_l:
                    data["sex"] = "M"

        # Combine Holder Name
        if data["given_names"] and data["surname"]:
            data["holder_name"] = f"{data['given_names']} {data['surname']}"
        elif data["given_names"]:
            data["holder_name"] = data["given_names"]
        elif data["surname"]:
            data["holder_name"] = data["surname"]

        return data

    def extract_mrz_text(self, image_path: str, ocr_lines: Optional[List[str]] = None) -> str:
        """
        Locates and extracts MRZ text lines if present in the document.
        Supports 2-line standard TD3 and single-line TD3 lines.
        """
        if not ocr_lines:
            return ""

        mrz_candidates = []
        for line in ocr_lines:
            clean = line.replace(" ", "").upper()
            # MRZ lines typically have '<', or match TD3 line format (DocNum + check digit + Nat + DOB + sex)
            has_filler = "<" in clean
            looks_like_mrz = (
                clean.startswith("P<") or clean.startswith("I<") or clean.startswith("V<") or
                clean.startswith("A<") or re.search(r"[A-Z0-9]{8,9}<\d[A-Z]{3}\d{6}", clean) is not None
            )
            if (has_filler or looks_like_mrz) and len(clean) >= 20:
                mrz_candidates.append(clean)

        if mrz_candidates:
            return "\n".join(mrz_candidates[:3])

        return ""

    def process_document(
        self,
        image_path: str,
        document_type: str = "passport",
        prefetched_text: Optional[str] = None,
        prefetched_lines: Optional[List[str]] = None,
        prefetched_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full OCR pipeline execution: Preprocessing -> Text Extraction -> Field Parsing.

        When the caller already has text (e.g. Google Cloud Vision ran upstream)
        pass it via prefetched_text so we parse fields from the better source
        instead of re-OCRing with a weaker local engine.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image not found at path: {image_path}")

        # 1. Obtain text — prefer the upstream provider, fall back to local engines.
        engine = prefetched_provider or "prefetched"
        full_text = (prefetched_text or "").strip()
        ocr_lines = [ln.strip() for ln in (prefetched_lines or []) if ln.strip()]
        if full_text and not ocr_lines:
            ocr_lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]

        if not full_text:
            full_text, ocr_lines, engine = self.extract_text(image_path)

        if not full_text.strip():
            raise OCRError(
                "No text could be extracted from the document image. "
                "Check image focus/lighting, install a local OCR engine "
                "(`brew install tesseract`), or configure OCR_PROVIDER=google_vision."
            )

        full_text_upper = full_text.upper()

        # Determine document type reliably
        is_passport = (
            document_type == "passport" or
            "PASSPORT" in full_text_upper or
            "REPUBLIC OF INDIA" in full_text_upper or
            "P<" in full_text_upper or
            any("PASSPORT" in l.upper() for l in ocr_lines)
        )

        visual_fields = {}
        if is_passport:
            visual_fields = self._extract_passport_visual_fields(ocr_lines, full_text)

        # 2. Check for MRZ (Machine Readable Zone)
        mrz_raw_text = self.extract_mrz_text(image_path, ocr_lines)

        if mrz_raw_text:
            parsed = parse_mrz_lines(mrz_raw_text, visual_fallback=visual_fields)
            
            # Use visual fields to enrich if MRZ had missing fields (e.g. Line 1 was missing)
            holder_name = parsed.get("holder_name")
            if not holder_name or holder_name in ["TRAVELER", "UNREADABLE NAME"]:
                holder_name = visual_fields.get("holder_name") or holder_name or "TRAVELER"

            doc_number = parsed.get("document_number")
            if not doc_number or doc_number in ["UNKNOWN", "NOT_DETECTED"]:
                doc_number = visual_fields.get("document_number")

            dob = parsed.get("date_of_birth") or visual_fields.get("date_of_birth")
            expiry = parsed.get("expiry_date") or visual_fields.get("expiry_date")
            sex = parsed.get("sex") if parsed.get("sex") not in [None, "U"] else (visual_fields.get("sex") or "U")

            return {
                "success": True,
                "document_type": "passport",
                "document_number": doc_number,
                "holder_name": holder_name,
                "surname": parsed.get("surname") or visual_fields.get("surname", ""),
                "given_names": parsed.get("given_names") or visual_fields.get("given_names", ""),
                "issuing_country": parsed.get("issuing_country", "IND"),
                "nationality": parsed.get("nationality", "IND"),
                "date_of_birth": dob,
                "sex": sex,
                "expiry_date": expiry,
                "mrz_valid": parsed.get("mrz_valid", False),
                "mrz_required": True,
                "mrz_lines": parsed.get("mrz_lines", []),
                "check_digits": parsed.get("check_digits", {}),
                "flags": parsed.get("flags", []),
                "raw_ocr_text": full_text,
                "ocr_engine": engine,
            }

        # If it is a passport without readable MRZ, return visual zone data with mrz_valid = False
        if is_passport:
            return {
                "success": True,
                "document_type": "passport",
                "document_number": visual_fields.get("document_number") or "NOT_DETECTED",
                "holder_name": visual_fields.get("holder_name") or "TRAVELER",
                "surname": visual_fields.get("surname", ""),
                "given_names": visual_fields.get("given_names", ""),
                "issuing_country": visual_fields.get("issuing_country", "IND"),
                "nationality": visual_fields.get("nationality", "IND"),
                "date_of_birth": visual_fields.get("date_of_birth"),
                "sex": visual_fields.get("sex") or "U",
                "expiry_date": visual_fields.get("expiry_date"),
                "mrz_valid": False,
                "mrz_required": True,
                "mrz_lines": [],
                "check_digits": {
                    "doc_number_valid": False,
                    "dob_valid": False,
                    "expiry_valid": False
                },
                "flags": ["MRZ lines could not be decoded from passport image"],
                "raw_ocr_text": full_text,
                "ocr_engine": engine,
            }

        # 3. Non-Passport Document Extraction (Aadhaar Card / National ID)
        doc_number = None
        holder_name = None
        dob = None
        sex = None
        issuing_country = "IND"
        nationality = "IND"
        flags = []

        # Look for Aadhaar 12-digit format (XXXX XXXX XXXX or XXXXXXXXXXXX)
        aadhaar_match = re.search(r"\b(\d{4}\s\d{4}\s\d{4})\b", full_text)
        if aadhaar_match:
            doc_number = aadhaar_match.group(1)
            document_type = "id_card"
        else:
            generic_id = re.search(r"\b([A-Z0-9]{8,14})\b", full_text)
            if generic_id and generic_id.group(1).upper() not in ["SAMPLE", "IMMIHELP", "REPUBLIC", "INDIA"]:
                doc_number = generic_id.group(1)

        # DOB Extraction (DD/MM/YYYY or DD-MM-YYYY)
        dob_match = re.search(r"(?:DOB|Date of Birth|Birth)\s*[:/]?\s*(\d{2}[/-]\d{2}[/-]\d{4})", full_text, re.IGNORECASE)
        if dob_match:
            try:
                d, m, y = re.split(r"[/-]", dob_match.group(1))
                dob = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            except Exception:
                dob = dob_match.group(1)

        # Gender Extraction
        if re.search(r"\b(?:Female|Fem)\b", full_text, re.IGNORECASE) or re.search(r"/\s*Female", full_text, re.IGNORECASE):
            sex = "F"
        elif re.search(r"\b(?:Male)\b", full_text, re.IGNORECASE) or re.search(r"/\s*Male", full_text, re.IGNORECASE):
            sex = "M"

        # Name Extraction for Indian Aadhaar / National ID
        noise_keywords = ["dob", "male", "female", "year", "aadhaar", "help", "www", "father", "place", "birth", "republic", "sample", "immihelp"]
        for i, line in enumerate(ocr_lines):
            clean_l = line.lower()
            if any(k in clean_l for k in ["india", "government", "authority", "enrolment", "identity"]):
                if i + 1 < len(ocr_lines):
                    candidate = ocr_lines[i + 1].strip()
                    if not any(k in candidate.lower() for k in noise_keywords):
                        if re.match(r"^[A-Za-z\s.'-]+$", candidate) and len(candidate) > 2:
                            holder_name = candidate
                            break

        return {
            "success": True,
            "document_type": document_type,
            "document_number": doc_number or "NOT_DETECTED",
            "holder_name": holder_name or "TRAVELER",
            "issuing_country": issuing_country,
            "nationality": nationality,
            "date_of_birth": dob,
            "sex": sex or "U",
            "expiry_date": None,
            "mrz_valid": True,
            "mrz_required": False,
            "mrz_lines": [],
            "check_digits": {
                "doc_number_valid": True if doc_number else False,
                "dob_valid": True if dob else False,
                "expiry_valid": True
            },
            "flags": flags,
            "raw_ocr_text": full_text,
            "ocr_engine": engine,
        }


ocr_service = OCRService()


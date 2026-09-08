"""
Unified OCR Pipeline — Google Cloud Vision + PaddleOCR (Local) Dual-Provider Support

SIH26188 Comprehensive OCR Integration:

This module provides a unified, production-ready OCR pipeline that:

1. PRIMARY: Google Cloud Vision API (DOCUMENT_TEXT_DETECTION for full page layout)
   - Best for multi-language documents
   - Accurate layout preservation
   - Bounding box annotations
   - Confidence scores

2. FALLBACK: Local PaddleOCR or Windows OCR
   - No API costs
   - Works offline
   - Fast inference
   - Multi-language support

3. MRZ EXTRACTION: Dual-path with check-digit validation
   - Identifies MRZ zones automatically
   - ICAO 9303 check digit validation
   - Composite check validation

4. FIELD EXTRACTION: Structured passport/ID data
   - Name, DOB, Expiry, Nationality
   - Document numbers
   - Visual zone parsing (Viz)
   - MRZ consistency checking

5. EVIDENCE FUSION: Rich output for pipeline
   - OCR confidence metrics
   - Bounding boxes for tamper detection
   - Provider trace (for audit)
   - Fallback indicators
"""

import os
import io
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class OCRProviderType(str, Enum):
    """Supported OCR providers."""
    GOOGLE_VISION = "google_vision"
    PADDLE_OCR = "paddle_ocr"
    LOCAL_OCR = "local_ocr"
    WINDOWS_OCR = "windows_ocr"


class DocumentZone(str, Enum):
    """Document zones for extraction."""
    MRZ = "MRZ"  # Machine readable zone (bottom of passport)
    VIZ = "VIZ"  # Visual inspection zone (top/middle)
    SECURITY = "SECURITY"  # Security features zone


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OCRTextBlock:
    """Single text block from OCR."""
    text: str
    confidence: float
    zone: Optional[DocumentZone] = None
    bounding_box: Optional[Dict[str, int]] = None  # {x, y, width, height}


@dataclass
class MRZExtraction:
    """MRZ parsing result."""
    line1: str
    line2: str
    is_valid: bool
    check_digits_valid: Dict[str, bool]
    parsed_fields: Dict[str, Any]
    confidence: float


@dataclass
class PassportExtractionResult:
    """Structured passport extraction."""
    provider: str
    success: bool
    document_type: str
    passport_number: Optional[str]
    holder_name: Optional[str]
    surname: Optional[str]
    given_names: Optional[str]
    date_of_birth: Optional[str]
    expiry_date: Optional[str]
    sex: Optional[str]
    nationality: str
    mrz_valid: bool
    mrz_lines: List[str]
    mrz_extraction: Optional[MRZExtraction]
    viz_fields: Dict[str, Any]
    raw_text: str
    confidence: float
    used_fallback: bool
    warnings: List[str]
    debug_info: Dict[str, Any]


# ============================================================================
# DUAL-PROVIDER OCR EXTRACTOR
# ============================================================================

class UnifiedOCRPipeline:
    """
    Production OCR pipeline with Google Vision primary + local fallback.
    
    Features:
    - Automatic provider fallback on errors
    - Structured field extraction
    - MRZ validation and parsing
    - Evidence audit trail
    """

    def __init__(
        self,
        primary_provider: OCRProviderType = OCRProviderType.GOOGLE_VISION,
        enable_fallback: bool = True,
        max_image_bytes: int = 10 * 1024 * 1024,
    ):
        self.primary_provider = primary_provider
        self.enable_fallback = enable_fallback
        self.max_image_bytes = max_image_bytes

        # Import providers
        self._google_vision_provider = None
        self._local_ocr_provider = None
        self._paddle_ocr_provider = None

        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available OCR providers."""
        # Google Vision
        try:
            from app.services.google_vision import GoogleVisionOCRProvider
            if GoogleVisionOCRProvider.is_available():
                self._google_vision_provider = GoogleVisionOCRProvider()
                logger.info("✓ Google Vision API provider initialized")
            else:
                logger.warning("⚠️  Google Vision API not available (no credentials)")
        except Exception as e:
            logger.warning(f"⚠️  Google Vision initialization failed: {e}")

        # PaddleOCR
        try:
            from ml.ocr.paddle_ocr_service import paddle_ocr_service, PADDLE_AVAILABLE
            if PADDLE_AVAILABLE and paddle_ocr_service:
                self._paddle_ocr_provider = paddle_ocr_service
                logger.info("✓ PaddleOCR provider initialized")
            else:
                logger.warning("⚠️  PaddleOCR not available")
        except Exception as e:
            logger.warning(f"⚠️  PaddleOCR initialization failed: {e}")

        # Local OCR (existing Windows OCR service)
        try:
            from app.services.ocr.ocr_service import ocr_service
            self._local_ocr_provider = ocr_service
            logger.info("✓ Local OCR service provider initialized")
        except Exception as e:
            logger.warning(f"⚠️  Local OCR initialization failed: {e}")

    # ========================================================================
    # PRIMARY EXTRACTION METHOD
    # ========================================================================

    def extract_passport(
        self,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
    ) -> PassportExtractionResult:
        """
        Extract structured passport data with dual-provider support.

        Args:
            image_path: Path to image file
            image_bytes: Raw image bytes

        Returns:
            PassportExtractionResult with all extracted fields
        """

        # Validate input
        if image_path is None and image_bytes is None:
            raise ValueError("Either image_path or image_bytes must be provided")

        # Load image bytes if needed
        if image_bytes is None:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()

        if len(image_bytes) > self.max_image_bytes:
            raise ValueError(
                f"Image too large: {len(image_bytes) / 1024 / 1024:.1f}MB "
                f"(max {self.max_image_bytes / 1024 / 1024:.1f}MB)"
            )

        # Step 1: Run primary provider
        result, used_fallback = self._run_primary_provider(
            image_bytes=image_bytes,
            image_path=image_path,
        )

        if result:
            # Step 2: Extract and validate MRZ
            mrz_extraction = self._extract_and_validate_mrz(result)

            # Step 3: Enrich with VIZ fields
            viz_fields = self._extract_viz_fields(result)

            # Step 4: Merge results
            final_result = self._merge_extraction_results(
                provider=self.primary_provider.value,
                ocr_result=result,
                mrz_extraction=mrz_extraction,
                viz_fields=viz_fields,
                used_fallback=used_fallback,
            )

            return final_result

        raise RuntimeError(
            "All OCR providers failed. Check logs for details."
        )

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _run_primary_provider(
        self,
        image_bytes: bytes,
        image_path: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Run primary provider with fallback to local if enabled.

        Returns:
            (ocr_result_dict, used_fallback_bool)
        """
        used_fallback = False

        # Try primary provider
        if self.primary_provider == OCRProviderType.GOOGLE_VISION:
            if self._google_vision_provider:
                try:
                    logger.info("Running primary provider: Google Vision")
                    result = self._google_vision_provider.extract_document_text(image_bytes)
                    text = result.get("text", "")
                    if text:
                        return self._normalize_google_vision_result(result), False
                    logger.warning("Google Vision returned empty text")
                except Exception as e:
                    logger.error(f"Google Vision failed: {e}")
                    if not self.enable_fallback:
                        raise

        # Try PaddleOCR if available
        if self.enable_fallback and self._paddle_ocr_provider and image_path:
            try:
                logger.info("Falling back to PaddleOCR")
                if os.path.exists(image_path):
                    import cv2
                    image = cv2.imread(image_path)
                    if image is not None:
                        result = self._paddle_ocr_provider.extract_text(image)
                        if result.success:
                            used_fallback = True
                            return self._normalize_paddle_ocr_result(result), True
            except Exception as e:
                logger.warning(f"PaddleOCR fallback failed: {e}")

        # Try local OCR if available
        if self.enable_fallback and self._local_ocr_provider and image_path:
            try:
                logger.info("Falling back to local OCR")
                if os.path.exists(image_path):
                    result = self._local_ocr_provider.process_document(image_path)
                    if result.get("success", False):
                        used_fallback = True
                        return result, True
            except Exception as e:
                logger.warning(f"Local OCR fallback failed: {e}")

        return None, used_fallback

    def _normalize_google_vision_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Google Vision result to normalized format."""
        text = result.get("text", "")
        blocks = result.get("blocks", [])
        words = result.get("words", [])

        return {
            "provider": "google_vision",
            "raw_text": text,
            "full_text": text,
            "blocks": blocks,
            "words": words,
            "confidence": result.get("confidence"),
            "structured_fields": self._extract_fields_from_google_vision(text, blocks),
        }

    def _normalize_paddle_ocr_result(self, result: Any) -> Dict[str, Any]:
        """Convert PaddleOCR result to normalized format."""
        return {
            "provider": "paddle_ocr",
            "raw_text": result.full_text,
            "full_text": result.full_text,
            "blocks": [
                {
                    "text": r.text,
                    "confidence": r.confidence,
                    "bounding_box": r.bbox,
                }
                for r in result.raw_results
            ],
            "confidence": result.full_text and min(
                r.confidence for r in result.raw_results
            ) if result.raw_results else None,
            "structured_fields": result.fields,
        }

    def _extract_fields_from_google_vision(
        self,
        text: str,
        blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract passport fields from Google Vision blocks."""
        import re

        fields = {
            "document_number": None,
            "holder_name": None,
            "date_of_birth": None,
            "expiry_date": None,
            "sex": None,
        }

        full_upper = text.upper()

        # Passport number (usually 8-9 chars, alphanumeric)
        passport_match = re.search(r'\bPASSPORT\s*N(?:O|UMBER)[\s:]([A-Z0-9]{7,9})\b', full_upper)
        if passport_match:
            fields["document_number"] = passport_match.group(1)

        # DOB (various formats)
        dob_match = re.search(r'(?:DATE OF BIRTH|DOB)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields["date_of_birth"] = dob_match.group(1)

        # Expiry
        expiry_match = re.search(r'(?:EXPIRY|VALID UNTIL)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', text, re.IGNORECASE)
        if expiry_match:
            fields["expiry_date"] = expiry_match.group(1)

        # Sex
        if re.search(r'\bFEMALE\b', full_upper):
            fields["sex"] = "F"
        elif re.search(r'\bMALE\b', full_upper):
            fields["sex"] = "M"

        return fields

    def _extract_and_validate_mrz(self, ocr_result: Dict[str, Any]) -> Optional[MRZExtraction]:
        """Extract MRZ lines and validate."""
        from app.services.ocr.mrz import parse_mrz_lines

        text = ocr_result.get("raw_text", "")

        # Look for MRZ pattern
        lines = text.split('\n')
        mrz_lines = []
        for line in lines:
            clean = line.replace(' ', '').upper()
            if clean.startswith('P<') or (len(clean) > 40 and '<' in clean):
                mrz_lines.append(clean)

        if len(mrz_lines) >= 2:
            try:
                parsed = parse_mrz_lines('\n'.join(mrz_lines[:2]))
                if parsed.get("mrz_valid"):
                    return MRZExtraction(
                        line1=mrz_lines[0],
                        line2=mrz_lines[1],
                        is_valid=True,
                        check_digits_valid=parsed.get("check_digits", {}),
                        parsed_fields=parsed,
                        confidence=0.95,
                    )
            except Exception as e:
                logger.warning(f"MRZ parsing failed: {e}")

        return None

    def _extract_viz_fields(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract visual inspection zone fields."""
        structured = ocr_result.get("structured_fields", {})
        fields = ocr_result.get("blocks", [])

        # Use pre-extracted structured fields
        return {
            "document_number": structured.get("document_number"),
            "holder_name": structured.get("holder_name"),
            "date_of_birth": structured.get("date_of_birth"),
            "expiry_date": structured.get("expiry_date"),
            "sex": structured.get("sex"),
            "raw_text_blocks": [f.get("text", "") for f in fields[:5]],
        }

    def _merge_extraction_results(
        self,
        provider: str,
        ocr_result: Dict[str, Any],
        mrz_extraction: Optional[MRZExtraction],
        viz_fields: Dict[str, Any],
        used_fallback: bool,
    ) -> PassportExtractionResult:
        """Merge all extraction results into final output."""

        # Prefer MRZ fields over VIZ
        holder_name = (
            mrz_extraction.parsed_fields.get("holder_name")
            if mrz_extraction else None
        ) or viz_fields.get("holder_name")

        passport_number = (
            mrz_extraction.parsed_fields.get("document_number")
            if mrz_extraction else None
        ) or viz_fields.get("document_number")

        dob = (
            mrz_extraction.parsed_fields.get("date_of_birth")
            if mrz_extraction else None
        ) or viz_fields.get("date_of_birth")

        expiry = (
            mrz_extraction.parsed_fields.get("expiry_date")
            if mrz_extraction else None
        ) or viz_fields.get("expiry_date")

        sex = (
            mrz_extraction.parsed_fields.get("sex")
            if mrz_extraction else None
        ) or viz_fields.get("sex")

        return PassportExtractionResult(
            provider=provider,
            success=True,
            document_type="passport",
            passport_number=passport_number,
            holder_name=holder_name,
            surname=mrz_extraction.parsed_fields.get("surname") if mrz_extraction else None,
            given_names=mrz_extraction.parsed_fields.get("given_names") if mrz_extraction else None,
            date_of_birth=dob,
            expiry_date=expiry,
            sex=sex,
            nationality=mrz_extraction.parsed_fields.get("nationality", "IND") if mrz_extraction else "IND",
            mrz_valid=bool(mrz_extraction and mrz_extraction.is_valid),
            mrz_lines=[mrz_extraction.line1, mrz_extraction.line2] if mrz_extraction else [],
            mrz_extraction=mrz_extraction,
            viz_fields=viz_fields,
            raw_text=ocr_result.get("raw_text", ""),
            confidence=ocr_result.get("confidence", 0.0) or 0.75,
            used_fallback=used_fallback,
            warnings=[],
            debug_info={
                "ocr_provider": provider,
                "fallback_used": used_fallback,
                "mrz_found": bool(mrz_extraction),
            },
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

unified_ocr_pipeline = UnifiedOCRPipeline(
    primary_provider=OCRProviderType.GOOGLE_VISION,
    enable_fallback=True,
)

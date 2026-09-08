"""
PaddleOCR Integration Service
Per SIH26188 Master Prompt - Primary OCR Engine

Extracts structured fields from identity documents with:
- High accuracy multi-language text detection
- Bounding box annotations
- Confidence scores
- Field-level extraction
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from PIL import Image
import cv2

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    print("⚠️  PaddleOCR not installed. Install: pip install paddleocr paddlepaddle")


@dataclass
class OCRResult:
    """Structured OCR result"""
    text: str
    confidence: float
    bbox: List[List[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    field_type: Optional[str] = None


@dataclass
class DocumentOCROutput:
    """Complete document OCR output"""
    fields: Dict[str, OCRResult]
    raw_results: List[OCRResult]
    full_text: str
    success: bool
    error: Optional[str] = None


class PaddleOCRService:
    """
    PaddleOCR-based document text extraction
    
    Supports:
    - Multi-language detection (English, Hindi, etc.)
    - Structured field extraction
    - High-quality bounding boxes
    - Confidence thresholding
    """
    
    def __init__(
        self,
        use_angle_cls=True,
        lang='en',
        use_gpu=False,
        show_log=False
    ):
        if not PADDLE_AVAILABLE:
            raise RuntimeError("PaddleOCR not available. Install paddleocr and paddlepaddle.")
        
        self.ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=lang,
            use_gpu=use_gpu,
            show_log=show_log
        )
        
        self.field_patterns = {
            'full_name': ['name', 'full name', 'holder', 'bearer'],
            'given_name': ['given name', 'first name', 'given names'],
            'surname': ['surname', 'last name', 'family name'],
            'document_number': ['passport no', 'document no', 'number', 'passport number'],
            'nationality': ['nationality', 'country', 'issuing country'],
            'date_of_birth': ['date of birth', 'dob', 'birth date'],
            'sex': ['sex', 'gender', 'm/f'],
            'issue_date': ['date of issue', 'issue date', 'issued'],
            'expiry_date': ['date of expiry', 'expiry date', 'valid until'],
            'place_of_birth': ['place of birth', 'birth place'],
            'visa_number': ['visa no', 'visa number'],
            'visa_type': ['visa type', 'type of visa'],
        }
    
    def extract_text(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5
    ) -> DocumentOCROutput:
        """
        Extract all text from document image
        
        Args:
            image: numpy array (BGR or RGB)
            confidence_threshold: minimum confidence to include
            
        Returns:
            DocumentOCROutput with structured fields
        """
        try:
            # Run PaddleOCR
            results = self.ocr.ocr(image, cls=True)
            
            if not results or not results[0]:
                return DocumentOCROutput(
                    fields={},
                    raw_results=[],
                    full_text="",
                    success=False,
                    error="No text detected"
                )
            
            # Parse results
            raw_results = []
            full_text_parts = []
            
            for line in results[0]:
                bbox, (text, confidence) = line
                
                if confidence >= confidence_threshold:
                    ocr_result = OCRResult(
                        text=text,
                        confidence=confidence,
                        bbox=bbox
                    )
                    raw_results.append(ocr_result)
                    full_text_parts.append(text)
            
            # Extract structured fields
            fields = self._extract_fields(raw_results)
            
            return DocumentOCROutput(
                fields=fields,
                raw_results=raw_results,
                full_text=' '.join(full_text_parts),
                success=True
            )
            
        except Exception as e:
            return DocumentOCROutput(
                fields={},
                raw_results=[],
                full_text="",
                success=False,
                error=str(e)
            )
    
    def _extract_fields(self, raw_results: List[OCRResult]) -> Dict[str, OCRResult]:
        """
        Match OCR results to known document fields
        
        Uses pattern matching and proximity heuristics
        """
        fields = {}
        text_lower = [r.text.lower() for r in raw_results]
        
        for field_name, patterns in self.field_patterns.items():
            for i, text in enumerate(text_lower):
                for pattern in patterns:
                    if pattern in text:
                        # Field label found, value is likely next
                        if i + 1 < len(raw_results):
                            value_result = raw_results[i + 1]
                            fields[field_name] = value_result
                            break
        
        return fields
    
    def extract_with_visualization(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5
    ) -> Tuple[DocumentOCROutput, np.ndarray]:
        """
        Extract text and return annotated image
        
        Returns:
            (OCR output, annotated image)
        """
        output = self.extract_text(image, confidence_threshold)
        
        # Draw bounding boxes
        vis_image = image.copy()
        for result in output.raw_results:
            bbox = np.array(result.bbox, dtype=np.int32)
            cv2.polylines(vis_image, [bbox], True, (0, 255, 0), 2)
            
            # Draw confidence
            x, y = bbox[0]
            conf_text = f"{result.confidence:.2f}"
            cv2.putText(
                vis_image, conf_text, (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
            )
        
        return output, vis_image


# Global instance
paddle_ocr_service = PaddleOCRService() if PADDLE_AVAILABLE else None

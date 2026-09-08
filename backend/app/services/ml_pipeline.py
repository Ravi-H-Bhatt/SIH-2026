"""
Complete ML Pipeline - Integrates ALL 9 ML Services
Part of SIH26188 AI Border Document Screening System

This orchestrates the entire screening process from document capture to final decision.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
import hashlib
import numpy as np
from PIL import Image
import io

# Add ml directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "ml"))

# Import all ML services
from mrz.icao_mrz_parser import ICAOMRZParser
from ocr.paddle_ocr_service import PaddleOCRService
from forensics.tamper_detector import ForensicTamperDetector
from document.validation_engine import DocumentValidationEngine
from face.insightface_service import InsightFaceService
from risk.evidence_fusion import EvidenceFusionEngine, EvidenceSignal
from identity.entity_resolver import IdentityGraph
from risk.watchlist_providers import WatchlistService
from audit.audit_proof import AuditProofService

from dataclasses import dataclass, asdict
from enum import Enum


class ScreeningStatus(str, Enum):
    """Screening status"""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    ERROR = "ERROR"


@dataclass
class ScreeningResult:
    """Complete screening result"""
    screening_id: str
    status: ScreeningStatus
    
    # Overall assessment
    risk_level: str  # CLEAR, LOW, MEDIUM, HIGH, CRITICAL
    risk_score: float  # 0-1
    confidence: float  # 0-1
    recommended_action: str  # CLEAR, SECONDARY_REVIEW, ESCALATE
    
    # Component results
    mrz_result: Optional[Dict[str, Any]] = None
    ocr_result: Optional[Dict[str, Any]] = None
    forensics_result: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    face_result: Optional[Dict[str, Any]] = None
    identity_graph_result: Optional[Dict[str, Any]] = None
    watchlist_hits: Optional[list] = None
    
    # Evidence fusion
    contradictions: list = None
    key_factors: list = None
    reasoning: str = ""
    
    # Audit
    audit_record_hash: Optional[str] = None
    
    # Timing
    processing_time_ms: int = 0
    timestamp: str = ""
    
    # Errors
    errors: list = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class MLPipeline:
    """
    Complete ML Pipeline - orchestrates all 9 services.
    
    Processing Flow:
    1. Initialize all services
    2. Run services in parallel where possible
    3. Fuse evidence and detect contradictions
    4. Generate audit record
    5. Return comprehensive result
    """
    
    def __init__(self):
        """Initialize all ML services"""
        self.initialized = False
        self.services = {}
        self.errors = []
        
        # Initialize services
        self._init_services()
    
    def _init_services(self):
        """Initialize all 9 ML services"""
        try:
            # 1. MRZ Parser
            self.services['mrz'] = ICAOMRZParser()
            print("✓ MRZ Parser initialized")
        except Exception as e:
            self.errors.append(f"MRZ Parser init failed: {e}")
            self.services['mrz'] = None
        
        try:
            # 2. PaddleOCR
            self.services['ocr'] = PaddleOCRService()
            print("✓ PaddleOCR initialized")
        except Exception as e:
            self.errors.append(f"PaddleOCR init failed: {e}")
            self.services['ocr'] = None
        
        try:
            # 3. Forensic Detector
            self.services['forensics'] = ForensicTamperDetector()
            print("✓ Forensic Detector initialized")
        except Exception as e:
            self.errors.append(f"Forensics init failed: {e}")
            self.services['forensics'] = None
        
        try:
            # 4. Validation Engine
            self.services['validation'] = DocumentValidationEngine()
            print("✓ Validation Engine initialized")
        except Exception as e:
            self.errors.append(f"Validation init failed: {e}")
            self.services['validation'] = None
        
        try:
            # 5. Face Verification
            self.services['face'] = InsightFaceService(match_threshold=0.55)
            print("✓ Face Verification initialized")
        except Exception as e:
            self.errors.append(f"Face Verification init failed: {e}")
            self.services['face'] = None
        
        try:
            # 6. Identity Graph
            self.services['identity'] = IdentityGraph()
            print("✓ Identity Graph initialized")
        except Exception as e:
            self.errors.append(f"Identity Graph init failed: {e}")
            self.services['identity'] = None
        
        try:
            # 7. Watchlist Service
            self.services['watchlist'] = WatchlistService()
            print("✓ Watchlist Service initialized")
        except Exception as e:
            self.errors.append(f"Watchlist init failed: {e}")
            self.services['watchlist'] = None
        
        try:
            # 8. Evidence Fusion
            self.services['fusion'] = EvidenceFusionEngine()
            print("✓ Evidence Fusion initialized")
        except Exception as e:
            self.errors.append(f"Fusion Engine init failed: {e}")
            self.services['fusion'] = None
        
        try:
            # 9. Audit Proof
            self.services['audit'] = AuditProofService()
            print("✓ Audit Proof initialized")
        except Exception as e:
            self.errors.append(f"Audit Service init failed: {e}")
            self.services['audit'] = None
        
        # Check initialization
        active_services = sum(1 for s in self.services.values() if s is not None)
        print(f"\n✓ {active_services}/9 services initialized successfully")
        
        if self.errors:
            print(f"⚠ {len(self.errors)} services failed to initialize:")
            for error in self.errors:
                print(f"  • {error}")
        
        self.initialized = True
    
    async def screen_document(
        self,
        document_image_path: str,
        face_image_path: str,
        officer_id: str,
        station_id: str,
        traveler_info: Optional[Dict[str, Any]] = None
    ) -> ScreeningResult:
        """
        Complete document screening process.
        
        Args:
            document_image_path: Path to document image
            face_image_path: Path to face capture image
            officer_id: Officer conducting screening
            station_id: Border station ID
            traveler_info: Optional additional traveler info
        
        Returns:
            ScreeningResult with complete analysis
        """
        start_time = datetime.now()
        screening_id = self._generate_screening_id()
        
        # Initialize result
        result = ScreeningResult(
            screening_id=screening_id,
            status=ScreeningStatus.IN_PROGRESS,
            risk_level="UNKNOWN",
            risk_score=0.0,
            confidence=0.0,
            recommended_action="UNKNOWN",
            contradictions=[],
            key_factors=[],
            errors=[],
            timestamp=start_time.isoformat()
        )
        
        try:
            # Load images
            doc_img = self._load_image(document_image_path)
            face_img = self._load_image(face_image_path)
            
            # Hash images for audit
            doc_hash = self._hash_image(document_image_path)
            face_hash = self._hash_image(face_image_path)
            
            # ===== STAGE 1: PARALLEL PROCESSING =====
            print(f"\n🔍 Starting screening {screening_id}...")
            
            # Run services in parallel
            tasks = []
            
            # MRZ parsing (needs OCR first for MRZ text)
            ocr_task = self._run_ocr(doc_img)
            tasks.append(('ocr', ocr_task))
            
            # Forensic analysis
            forensics_task = self._run_forensics(document_image_path)
            tasks.append(('forensics', forensics_task))
            
            # Face verification
            face_task = self._run_face_verification(document_image_path, face_image_path)
            tasks.append(('face', face_task))
            
            # Watchlist check (needs traveler info)
            if traveler_info:
                watchlist_task = self._run_watchlist_check(traveler_info)
                tasks.append(('watchlist', watchlist_task))
            
            # Execute parallel tasks
            results_dict = {}
            for name, task in tasks:
                try:
                    results_dict[name] = await task
                except Exception as e:
                    result.errors.append(f"{name} failed: {str(e)}")
                    results_dict[name] = None
            
            # ===== STAGE 2: DEPENDENT PROCESSING =====
            
            # MRZ parsing (needs OCR result)
            mrz_result = None
            if results_dict.get('ocr'):
                mrz_result = await self._run_mrz_parsing(results_dict['ocr'])
                results_dict['mrz'] = mrz_result
            
            # Document validation (needs MRZ + OCR)
            validation_result = None
            if results_dict.get('ocr'):
                validation_result = await self._run_validation(
                    results_dict.get('ocr'),
                    results_dict.get('mrz')
                )
                results_dict['validation'] = validation_result
            
            # Identity graph analysis (needs traveler info + face)
            identity_result = None
            if traveler_info and results_dict.get('face'):
                identity_result = await self._run_identity_analysis(
                    traveler_info,
                    results_dict.get('face')
                )
                results_dict['identity'] = identity_result
            
            # ===== STAGE 3: EVIDENCE FUSION =====
            print("🔗 Fusing evidence...")
            
            fusion_result = await self._run_evidence_fusion(results_dict)
            
            # ===== STAGE 4: AUDIT RECORD =====
            print("📝 Creating audit record...")
            
            audit_hash = await self._create_audit_record(
                screening_id=screening_id,
                officer_id=officer_id,
                station_id=station_id,
                risk_level=fusion_result.risk_level.value,
                recommended_action=fusion_result.recommended_action.value,
                confidence=fusion_result.confidence,
                doc_hash=doc_hash,
                face_hash=face_hash,
                results_dict=results_dict
            )
            
            # ===== STAGE 5: BUILD FINAL RESULT =====
            result.status = ScreeningStatus.COMPLETED
            result.risk_level = fusion_result.risk_level.value
            result.risk_score = fusion_result.risk_score
            result.confidence = fusion_result.confidence
            result.recommended_action = fusion_result.recommended_action.value
            result.contradictions = [asdict(c) for c in fusion_result.contradictions]
            result.key_factors = fusion_result.key_factors
            result.reasoning = fusion_result.reasoning
            
            # Store component results
            result.mrz_result = results_dict.get('mrz')
            result.ocr_result = results_dict.get('ocr')
            result.forensics_result = results_dict.get('forensics')
            result.validation_result = results_dict.get('validation')
            result.face_result = results_dict.get('face')
            result.identity_graph_result = results_dict.get('identity')
            result.watchlist_hits = results_dict.get('watchlist', [])
            
            result.audit_record_hash = audit_hash
            
            # Calculate processing time
            end_time = datetime.now()
            result.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            print(f"✅ Screening completed in {result.processing_time_ms}ms")
            print(f"📊 Risk Level: {result.risk_level} ({result.risk_score:.2%})")
            print(f"🎯 Recommended Action: {result.recommended_action}")
            
            if result.contradictions:
                print(f"⚠️  {len(result.contradictions)} contradictions detected!")
            
            return result
            
        except Exception as e:
            result.status = ScreeningStatus.ERROR
            result.errors.append(f"Pipeline error: {str(e)}")
            print(f"❌ Screening failed: {e}")
            return result
    
    async def _run_ocr(self, doc_img: np.ndarray) -> Optional[Dict[str, Any]]:
        """Run OCR analysis"""
        if not self.services.get('ocr'):
            return None
        
        try:
            result = self.services['ocr'].extract_text(doc_img)
            return {
                'full_text': result.full_text,
                'fields': {f.field_type: f.text for f in result.fields},
                'confidence': result.confidence,
                'raw_results': [{'text': r.text, 'confidence': r.confidence} for r in result.raw_results[:10]]
            }
        except Exception as e:
            print(f"OCR error: {e}")
            return None
    
    async def _run_mrz_parsing(self, ocr_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run MRZ parsing"""
        if not self.services.get('mrz') or not ocr_result:
            return None
        
        try:
            # Extract MRZ from OCR
            full_text = ocr_result.get('full_text', '')
            # Try to find MRZ lines (simple heuristic)
            lines = full_text.split('\n')
            mrz_lines = [l for l in lines if len(l) > 40 and l.replace('<', '').replace('>', '').replace(' ', '').isalnum()]
            
            if len(mrz_lines) >= 2:
                mrz_text = '\n'.join(mrz_lines[:3])  # TD1 = 3 lines, TD3 = 2 lines
                result = self.services['mrz'].parse(mrz_text)
                
                return {
                    'is_valid': result.is_valid,
                    'format_type': result.format_type,
                    'document_number': result.document_number,
                    'surname': result.surname,
                    'given_names': result.given_names,
                    'nationality': result.nationality,
                    'date_of_birth': result.date_of_birth,
                    'sex': result.sex,
                    'date_of_expiry': result.date_of_expiry,
                    'check_digits_valid': result.check_digits_valid
                }
            return None
        except Exception as e:
            print(f"MRZ parsing error: {e}")
            return None
    
    async def _run_forensics(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Run forensic analysis"""
        if not self.services.get('forensics'):
            return None
        
        try:
            result = self.services['forensics'].analyze(image_path)
            return {
                'tampering_probability': result.tampering_probability,
                'confidence': result.confidence,
                'signals': result.signals,
                'suspicious_regions': [asdict(r) for r in result.suspicious_regions],
                'explanation': result.explanation
            }
        except Exception as e:
            print(f"Forensics error: {e}")
            return None
    
    async def _run_validation(
        self,
        ocr_result: Dict[str, Any],
        mrz_result: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Run document validation"""
        if not self.services.get('validation'):
            return None
        
        try:
            fields = ocr_result.get('fields', {})
            result = self.services['validation'].validate_document(
                doc_type='P',  # Assume passport
                fields=fields,
                mrz_result=mrz_result
            )
            return {
                'is_valid': result.is_valid,
                'validation_score': result.validation_score,
                'rules_checked': result.rules_checked,
                'rules_passed': result.rules_passed,
                'rules_failed': result.rules_failed,
                'findings': [asdict(f) for f in result.findings]
            }
        except Exception as e:
            print(f"Validation error: {e}")
            return None
    
    async def _run_face_verification(
        self,
        doc_path: str,
        face_path: str
    ) -> Optional[Dict[str, Any]]:
        """Run face verification"""
        if not self.services.get('face'):
            return None
        
        try:
            result = self.services['face'].verify_faces(doc_path, face_path)
            return {
                'similarity': result.similarity,
                'is_match': result.is_match,
                'confidence': result.confidence,
                'threshold_used': result.threshold_used,
                'doc_face_quality': asdict(result.doc_face_quality),
                'live_face_quality': asdict(result.live_face_quality),
                'liveness_result': result.liveness_result.value,
                'liveness_score': result.liveness_score,
                'explanation': result.explanation
            }
        except Exception as e:
            print(f"Face verification error: {e}")
            return None
    
    async def _run_watchlist_check(
        self,
        traveler_info: Dict[str, Any]
    ) -> list:
        """Run watchlist check"""
        if not self.services.get('watchlist'):
            return []
        
        try:
            hits = self.services['watchlist'].search_all(
                full_name=traveler_info.get('full_name', ''),
                date_of_birth=traveler_info.get('date_of_birth'),
                nationality=traveler_info.get('nationality'),
                document_number=traveler_info.get('document_number')
            )
            return [asdict(h) for h in hits]
        except Exception as e:
            print(f"Watchlist check error: {e}")
            return []
    
    async def _run_identity_analysis(
        self,
        traveler_info: Dict[str, Any],
        face_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Run identity graph analysis"""
        if not self.services.get('identity'):
            return None
        
        try:
            # Extract biometric hash (simplified)
            biometric_hash = face_result.get('doc_face_quality', {}).get('face_size', 0)
            
            result = self.services['identity'].analyze_identity(
                person_attributes=traveler_info,
                document_attributes={'document_number': traveler_info.get('document_number', '')},
                biometric_data={'hash': str(biometric_hash)}
            )
            return asdict(result)
        except Exception as e:
            print(f"Identity analysis error: {e}")
            return None
    
    async def _run_evidence_fusion(
        self,
        results_dict: Dict[str, Any]
    ) -> Any:
        """Run evidence fusion"""
        if not self.services.get('fusion'):
            # Return default result
            from risk.evidence_fusion import FusionResult, RiskLevel, RecommendedAction
            return FusionResult(
                risk_level=RiskLevel.MEDIUM,
                risk_score=0.5,
                confidence=0.5,
                recommended_action=RecommendedAction.SECONDARY_REVIEW,
                signals=[],
                contradictions=[],
                reasoning="Evidence fusion service not available",
                key_factors=[],
                timestamp=datetime.utcnow().isoformat()
            )
        
        try:
            # Build evidence signals
            signals = []
            
            # MRZ signal
            if results_dict.get('mrz'):
                signals.append(EvidenceSignal(
                    source='mrz',
                    risk_score=0.0 if results_dict['mrz'].get('is_valid') else 0.7,
                    confidence=0.95,
                    findings=['MRZ invalid'] if not results_dict['mrz'].get('is_valid') else [],
                    raw_data=results_dict['mrz']
                ))
            
            # OCR signal
            if results_dict.get('ocr'):
                signals.append(EvidenceSignal(
                    source='ocr',
                    risk_score=0.1,
                    confidence=results_dict['ocr'].get('confidence', 0.8),
                    findings=[],
                    raw_data=results_dict['ocr']
                ))
            
            # Forensics signal
            if results_dict.get('forensics'):
                signals.append(EvidenceSignal(
                    source='forensics',
                    risk_score=results_dict['forensics'].get('tampering_probability', 0.0),
                    confidence=results_dict['forensics'].get('confidence', 0.8),
                    findings=[results_dict['forensics'].get('explanation', '')],
                    raw_data=results_dict['forensics']
                ))
            
            # Validation signal
            if results_dict.get('validation'):
                signals.append(EvidenceSignal(
                    source='validation',
                    risk_score=1.0 - results_dict['validation'].get('validation_score', 1.0),
                    confidence=0.9,
                    findings=[f['message'] for f in results_dict['validation'].get('findings', [])[:2]],
                    raw_data=results_dict['validation']
                ))
            
            # Face signal
            if results_dict.get('face'):
                signals.append(EvidenceSignal(
                    source='face',
                    risk_score=0.0 if results_dict['face'].get('is_match') else 0.9,
                    confidence=results_dict['face'].get('confidence', 0.8),
                    findings=['Face mismatch'] if not results_dict['face'].get('is_match') else [],
                    raw_data=results_dict['face']
                ))
            
            # Identity graph signal
            if results_dict.get('identity'):
                signals.append(EvidenceSignal(
                    source='identity_graph',
                    risk_score=results_dict['identity'].get('risk_score', 0.0),
                    confidence=results_dict['identity'].get('confidence', 0.7),
                    findings=results_dict['identity'].get('findings', []),
                    raw_data=results_dict['identity']
                ))
            
            # Watchlist signal
            if results_dict.get('watchlist'):
                hits = results_dict['watchlist']
                if hits:
                    max_confidence = max([h.get('match_confidence', 0) for h in hits])
                    signals.append(EvidenceSignal(
                        source='watchlist',
                        risk_score=0.95,
                        confidence=max_confidence,
                        findings=[f"Watchlist match: {hits[0].get('name', 'Unknown')}"],
                        raw_data={'hits': hits}
                    ))
            
            # Run fusion
            result = self.services['fusion'].fuse_evidence(
                signals=signals,
                historical_data=None,
                watchlist_hits=results_dict.get('watchlist')
            )
            
            return result
            
        except Exception as e:
            print(f"Evidence fusion error: {e}")
            from risk.evidence_fusion import FusionResult, RiskLevel, RecommendedAction
            return FusionResult(
                risk_level=RiskLevel.MEDIUM,
                risk_score=0.5,
                confidence=0.5,
                recommended_action=RecommendedAction.SECONDARY_REVIEW,
                signals=[],
                contradictions=[],
                reasoning=f"Fusion error: {str(e)}",
                key_factors=[],
                timestamp=datetime.utcnow().isoformat()
            )
    
    async def _create_audit_record(
        self,
        screening_id: str,
        officer_id: str,
        station_id: str,
        risk_level: str,
        recommended_action: str,
        confidence: float,
        doc_hash: str,
        face_hash: str,
        results_dict: Dict[str, Any]
    ) -> str:
        """Create audit record"""
        if not self.services.get('audit'):
            return ""
        
        try:
            # Create audit record
            record, record_hash = self.services['audit'].create_audit_record(
                record_id=screening_id,
                officer_id=officer_id,
                station_id=station_id,
                risk_level=risk_level,
                recommended_action=recommended_action,
                confidence=confidence,
                document_image=doc_hash.encode(),
                face_image=face_hash.encode(),
                mrz_data=results_dict.get('mrz', {}),
                decision_data={'recommended_action': recommended_action}
            )
            
            return record_hash
        except Exception as e:
            print(f"Audit record error: {e}")
            return ""
    
    def _generate_screening_id(self) -> str:
        """Generate unique screening ID"""
        from uuid import uuid4
        return f"SCREEN_{uuid4().hex[:12].upper()}"
    
    def _load_image(self, path: str) -> np.ndarray:
        """Load image as numpy array"""
        img = Image.open(path)
        return np.array(img)
    
    def _hash_image(self, path: str) -> str:
        """Hash image file"""
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()


# Singleton instance
_pipeline = None

def get_pipeline() -> MLPipeline:
    """Get or create pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = MLPipeline()
    return _pipeline


# Convenience function
async def screen_traveler(
    document_image_path: str,
    face_image_path: str,
    officer_id: str,
    station_id: str,
    traveler_info: Optional[Dict[str, Any]] = None
) -> ScreeningResult:
    """
    Convenience function to screen a traveler.
    
    Args:
        document_image_path: Path to document image
        face_image_path: Path to face capture
        officer_id: Officer ID
        station_id: Station ID
        traveler_info: Optional traveler details
    
    Returns:
        ScreeningResult
    """
    pipeline = get_pipeline()
    return await pipeline.screen_document(
        document_image_path,
        face_image_path,
        officer_id,
        station_id,
        traveler_info
    )


if __name__ == "__main__":
    # Test the pipeline
    print("=" * 80)
    print("ML PIPELINE TEST")
    print("=" * 80)
    
    async def test():
        # Create dummy images for testing
        import tempfile
        import cv2
        
        # Create dummy document
        doc_img = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.putText(doc_img, "PASSPORT", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        doc_path = tempfile.mktemp(suffix='.jpg')
        cv2.imwrite(doc_path, doc_img)
        
        # Create dummy face
        face_img = np.ones((400, 400, 3), dtype=np.uint8) * 128
        cv2.circle(face_img, (200, 200), 100, (255, 255, 255), -1)
        face_path = tempfile.mktemp(suffix='.jpg')
        cv2.imwrite(face_path, face_img)
        
        # Run screening
        result = await screen_traveler(
            document_image_path=doc_path,
            face_image_path=face_path,
            officer_id="OFFICER_TEST",
            station_id="STATION_TEST",
            traveler_info={
                'full_name': 'TEST USER',
                'date_of_birth': '1990-01-01',
                'nationality': 'IND',
                'document_number': 'TEST123456'
            }
        )
        
        print("\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)
        print(f"Status: {result.status}")
        print(f"Risk Level: {result.risk_level} ({result.risk_score:.2%})")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Recommended Action: {result.recommended_action}")
        print(f"Processing Time: {result.processing_time_ms}ms")
        print(f"Contradictions: {len(result.contradictions)}")
        print(f"Key Factors: {len(result.key_factors)}")
        
        if result.errors:
            print(f"\nErrors: {len(result.errors)}")
            for error in result.errors:
                print(f"  • {error}")
        
        # Cleanup
        os.unlink(doc_path)
        os.unlink(face_path)
    
    asyncio.run(test())

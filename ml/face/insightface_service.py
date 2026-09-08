"""
Face Verification Service - InsightFace with dlib fallback
Part of SIH26188 AI Border Document Screening System

Performs 1:1 face verification between document photo and live capture.
Features face detection, alignment, quality assessment, and liveness detection.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any
from enum import Enum
import numpy as np
import cv2
from pathlib import Path


class FaceQuality(str, Enum):
    """Face image quality levels"""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    UNUSABLE = "UNUSABLE"


class LivenessResult(str, Enum):
    """Liveness detection results"""
    LIKELY_LIVE = "LIKELY_LIVE"
    LIKELY_SPOOF = "LIKELY_SPOOF"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class FaceDetectionResult:
    """Result of face detection"""
    found: bool
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    confidence: float = 0.0
    landmarks: Optional[np.ndarray] = None  # 5-point or 68-point landmarks
    

@dataclass
class FaceQualityAssessment:
    """Face image quality metrics"""
    overall_quality: FaceQuality
    score: float  # 0-1
    sharpness: float
    brightness: float
    contrast: float
    face_size: int  # pixels
    frontal_score: float  # 0-1, 1 = frontal
    issues: List[str]


@dataclass
class FaceVerificationResult:
    """Complete face verification result"""
    similarity: float  # 0-1 similarity score
    is_match: bool
    confidence: float  # How confident in the match decision
    threshold_used: float
    doc_face_quality: FaceQualityAssessment
    live_face_quality: FaceQualityAssessment
    liveness_result: LivenessResult
    liveness_score: float  # 0-1
    explanation: str
    timestamp: str


class InsightFaceService:
    """
    Production-grade face verification service.
    
    Features:
    - Face detection with InsightFace (fallback to dlib if unavailable)
    - Face alignment using 5-point landmarks
    - Quality assessment (blur, brightness, size, pose)
    - Embedding extraction (512-D ArcFace embeddings)
    - 1:1 similarity computation (cosine similarity)
    - Liveness detection (texture analysis)
    - Configurable thresholds
    """
    
    def __init__(
        self,
        model_name: str = "buffalo_l",
        det_thresh: float = 0.5,
        match_threshold: float = 0.55  # Cosine similarity threshold
    ):
        """
        Initialize face verification service.
        
        Args:
            model_name: InsightFace model name
            det_thresh: Face detection confidence threshold
            match_threshold: Similarity threshold for match decision
        """
        self.det_thresh = det_thresh
        self.match_threshold = match_threshold
        self.model_loaded = False
        self.use_fallback = False
        
        # Try to load InsightFace
        try:
            import insightface
            from insightface.app import FaceAnalysis
            
            self.app = FaceAnalysis(
                name=model_name,
                providers=['CPUExecutionProvider']  # Use CPU for portability
            )
            self.app.prepare(ctx_id=0, det_thresh=det_thresh, det_size=(640, 640))
            self.model_loaded = True
            print(f"✓ InsightFace {model_name} loaded successfully")
            
        except ImportError:
            print("⚠ InsightFace not available, will use dlib fallback")
            self.use_fallback = True
            self._init_dlib_fallback()
        except Exception as e:
            print(f"⚠ InsightFace load failed: {e}, using dlib fallback")
            self.use_fallback = True
            self._init_dlib_fallback()
    
    def _init_dlib_fallback(self):
        """Initialize dlib-based fallback face recognition"""
        try:
            import dlib
            import face_recognition
            
            self.face_detector = dlib.get_frontal_face_detector()
            self.landmark_predictor = None  # face_recognition handles this
            self.model_loaded = True
            print("✓ dlib fallback loaded successfully")
            
        except ImportError:
            print("✗ Neither InsightFace nor dlib available!")
            self.model_loaded = False
    
    def verify_faces(
        self,
        doc_image_path: str,
        live_image_path: str
    ) -> FaceVerificationResult:
        """
        Verify if document face matches live capture face.
        
        Args:
            doc_image_path: Path to document photo
            live_image_path: Path to live capture photo
        
        Returns:
            FaceVerificationResult with similarity score and decision
        """
        if not self.model_loaded:
            raise RuntimeError("Face recognition model not loaded")
        
        # Load images
        doc_img = cv2.imread(doc_image_path)
        live_img = cv2.imread(live_image_path)
        
        if doc_img is None or live_img is None:
            raise ValueError("Failed to load one or both images")
        
        # Detect and extract faces
        doc_detection = self.detect_face(doc_img)
        live_detection = self.detect_face(live_img)
        
        if not doc_detection.found:
            raise ValueError("No face detected in document photo")
        if not live_detection.found:
            raise ValueError("No face detected in live capture")
        
        # Assess quality
        doc_quality = self.assess_face_quality(doc_img, doc_detection)
        live_quality = self.assess_face_quality(live_img, live_detection)
        
        # Liveness detection on live capture
        liveness_result, liveness_score = self.detect_liveness(live_img, live_detection)
        
        # Extract embeddings
        doc_embedding = self._extract_embedding(doc_img, doc_detection)
        live_embedding = self._extract_embedding(live_img, live_detection)
        
        # Compute similarity
        similarity = self._compute_similarity(doc_embedding, live_embedding)
        
        # Make match decision
        is_match = similarity >= self.match_threshold
        
        # Compute confidence based on quality and liveness
        confidence = self._compute_confidence(
            similarity, 
            doc_quality, 
            live_quality, 
            liveness_score
        )
        
        # Generate explanation
        explanation = self._generate_explanation(
            similarity,
            is_match,
            doc_quality,
            live_quality,
            liveness_result
        )
        
        from datetime import datetime
        return FaceVerificationResult(
            similarity=similarity,
            is_match=is_match,
            confidence=confidence,
            threshold_used=self.match_threshold,
            doc_face_quality=doc_quality,
            live_face_quality=live_quality,
            liveness_result=liveness_result,
            liveness_score=liveness_score,
            explanation=explanation,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def detect_face(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect face in image"""
        if self.use_fallback:
            return self._detect_face_dlib(image)
        else:
            return self._detect_face_insightface(image)
    
    def _detect_face_insightface(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect face using InsightFace"""
        faces = self.app.get(image)
        
        if len(faces) == 0:
            return FaceDetectionResult(found=False)
        
        # Use largest face if multiple detected
        face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
        
        bbox = face.bbox.astype(int)
        x, y, x2, y2 = bbox
        
        return FaceDetectionResult(
            found=True,
            bbox=(x, y, x2-x, y2-y),
            confidence=face.det_score,
            landmarks=face.kps
        )
    
    def _detect_face_dlib(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect face using dlib fallback"""
        import face_recognition
        
        # Convert BGR to RGB for face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image, model="hog")
        
        if len(face_locations) == 0:
            return FaceDetectionResult(found=False)
        
        # Use first face
        top, right, bottom, left = face_locations[0]
        
        # Get landmarks
        face_landmarks_list = face_recognition.face_landmarks(rgb_image, face_locations)
        landmarks = None
        if face_landmarks_list:
            # Convert to numpy array (use key points only)
            lm = face_landmarks_list[0]
            landmarks = np.array([
                lm['left_eye'][0],
                lm['right_eye'][0],
                lm['nose_tip'][0],
                lm['top_lip'][0],
                lm['bottom_lip'][0]
            ])
        
        return FaceDetectionResult(
            found=True,
            bbox=(left, top, right-left, bottom-top),
            confidence=0.9,  # dlib doesn't provide confidence
            landmarks=landmarks
        )
    
    def assess_face_quality(
        self,
        image: np.ndarray,
        detection: FaceDetectionResult
    ) -> FaceQualityAssessment:
        """
        Assess face image quality.
        
        Checks:
        - Sharpness (Laplacian variance)
        - Brightness (mean luminance)
        - Contrast (std of luminance)
        - Face size (pixel area)
        - Frontal pose (if landmarks available)
        """
        issues = []
        
        # Extract face region
        x, y, w, h = detection.bbox
        face_roi = image[y:y+h, x:x+w]
        
        # Convert to grayscale for analysis
        if len(face_roi.shape) == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_roi
        
        # 1. Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()
        normalized_sharpness = min(sharpness / 500.0, 1.0)  # Normalize to 0-1
        
        if sharpness < 50:
            issues.append("Image is blurry")
        
        # 2. Brightness (mean luminance)
        brightness = gray.mean() / 255.0
        
        if brightness < 0.3:
            issues.append("Image too dark")
        elif brightness > 0.8:
            issues.append("Image too bright")
        
        # 3. Contrast (std of luminance)
        contrast = gray.std() / 128.0  # Normalize to 0-1
        
        if contrast < 0.2:
            issues.append("Low contrast")
        
        # 4. Face size
        face_size = w * h
        min_face_size = 80 * 80
        
        if face_size < min_face_size:
            issues.append(f"Face too small ({w}x{h})")
        
        # 5. Frontal score (simplified - check face symmetry)
        frontal_score = 0.8  # Default assumption
        if detection.landmarks is not None and len(detection.landmarks) >= 2:
            # Check eye alignment (simple frontal test)
            eye_y_diff = abs(detection.landmarks[0][1] - detection.landmarks[1][1])
            eye_x_dist = abs(detection.landmarks[0][0] - detection.landmarks[1][0])
            
            if eye_x_dist > 0:
                frontal_score = 1.0 - min(eye_y_diff / eye_x_dist, 0.5)
            
            if frontal_score < 0.6:
                issues.append("Face not frontal")
        
        # Calculate overall score
        score = (
            normalized_sharpness * 0.3 +
            (1.0 - abs(brightness - 0.5) * 2) * 0.2 +
            contrast * 0.2 +
            min(face_size / (200 * 200), 1.0) * 0.15 +
            frontal_score * 0.15
        )
        
        # Determine quality level
        if score >= 0.8:
            quality = FaceQuality.EXCELLENT
        elif score >= 0.65:
            quality = FaceQuality.GOOD
        elif score >= 0.5:
            quality = FaceQuality.ACCEPTABLE
        elif score >= 0.3:
            quality = FaceQuality.POOR
        else:
            quality = FaceQuality.UNUSABLE
        
        return FaceQualityAssessment(
            overall_quality=quality,
            score=score,
            sharpness=normalized_sharpness,
            brightness=brightness,
            contrast=contrast,
            face_size=face_size,
            frontal_score=frontal_score,
            issues=issues
        )
    
    def detect_liveness(
        self,
        image: np.ndarray,
        detection: FaceDetectionResult
    ) -> Tuple[LivenessResult, float]:
        """
        Simple liveness detection based on texture analysis.
        
        Real faces have more texture variation than printed photos.
        This is a basic implementation - production systems should use
        dedicated liveness models or active liveness (blink detection, etc.)
        
        Returns:
            (LivenessResult, confidence_score)
        """
        x, y, w, h = detection.bbox
        face_roi = image[y:y+h, x:x+w]
        
        # Convert to grayscale
        if len(face_roi.shape) == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_roi
        
        # 1. Local Binary Pattern (LBP) texture analysis
        # Real faces have richer texture than printed photos
        lbp_variance = self._compute_lbp_variance(gray)
        
        # 2. Color diversity (real faces have more color variation)
        if len(face_roi.shape) == 3:
            color_variance = np.mean([face_roi[:,:,i].var() for i in range(3)])
        else:
            color_variance = gray.var()
        
        # 3. Edge density (real faces have more natural edges)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = edges.sum() / edges.size
        
        # Combine signals into liveness score
        lbp_score = min(lbp_variance / 100.0, 1.0)
        color_score = min(color_variance / 1000.0, 1.0)
        edge_score = min(edge_density / 0.1, 1.0)
        
        liveness_score = (
            lbp_score * 0.5 +
            color_score * 0.3 +
            edge_score * 0.2
        )
        
        # Classify
        if liveness_score >= 0.6:
            result = LivenessResult.LIKELY_LIVE
        elif liveness_score <= 0.4:
            result = LivenessResult.LIKELY_SPOOF
        else:
            result = LivenessResult.UNCERTAIN
        
        return result, liveness_score
    
    def _compute_lbp_variance(self, gray: np.ndarray) -> float:
        """Compute Local Binary Pattern variance"""
        # Simple LBP implementation
        rows, cols = gray.shape
        lbp = np.zeros_like(gray)
        
        for i in range(1, rows-1):
            for j in range(1, cols-1):
                center = gray[i, j]
                code = 0
                code |= (gray[i-1, j-1] >= center) << 7
                code |= (gray[i-1, j] >= center) << 6
                code |= (gray[i-1, j+1] >= center) << 5
                code |= (gray[i, j+1] >= center) << 4
                code |= (gray[i+1, j+1] >= center) << 3
                code |= (gray[i+1, j] >= center) << 2
                code |= (gray[i+1, j-1] >= center) << 1
                code |= (gray[i, j-1] >= center) << 0
                lbp[i, j] = code
        
        return lbp.var()
    
    def _extract_embedding(
        self,
        image: np.ndarray,
        detection: FaceDetectionResult
    ) -> np.ndarray:
        """Extract face embedding (512-D vector)"""
        if self.use_fallback:
            return self._extract_embedding_dlib(image, detection)
        else:
            return self._extract_embedding_insightface(image, detection)
    
    def _extract_embedding_insightface(
        self,
        image: np.ndarray,
        detection: FaceDetectionResult
    ) -> np.ndarray:
        """Extract embedding using InsightFace"""
        faces = self.app.get(image)
        if len(faces) == 0:
            raise ValueError("No face detected for embedding extraction")
        
        # Use largest face
        face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
        return face.embedding
    
    def _extract_embedding_dlib(
        self,
        image: np.ndarray,
        detection: FaceDetectionResult
    ) -> np.ndarray:
        """Extract embedding using dlib/face_recognition"""
        import face_recognition
        
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Get face encoding (128-D embedding)
        x, y, w, h = detection.bbox
        face_location = (y, x+w, y+h, x)  # top, right, bottom, left
        
        encodings = face_recognition.face_encodings(rgb_image, [face_location])
        if len(encodings) == 0:
            raise ValueError("Failed to extract face embedding")
        
        return encodings[0]
    
    def _compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between embeddings.
        
        Returns:
            Similarity score (0-1, higher = more similar)
        """
        # Normalize embeddings
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        
        # Convert from [-1, 1] to [0, 1]
        similarity = (similarity + 1.0) / 2.0
        
        return float(similarity)
    
    def _compute_confidence(
        self,
        similarity: float,
        doc_quality: FaceQualityAssessment,
        live_quality: FaceQualityAssessment,
        liveness_score: float
    ) -> float:
        """
        Compute confidence in match decision.
        
        Confidence is high when:
        - Similarity is far from threshold (either way)
        - Both faces have good quality
        - Liveness detection is confident
        """
        # Distance from threshold
        threshold_distance = abs(similarity - self.match_threshold)
        threshold_confidence = min(threshold_distance / 0.2, 1.0)
        
        # Quality confidence
        quality_confidence = (doc_quality.score + live_quality.score) / 2.0
        
        # Liveness confidence (distance from 0.5)
        liveness_confidence = abs(liveness_score - 0.5) * 2.0
        
        # Combine
        confidence = (
            threshold_confidence * 0.5 +
            quality_confidence * 0.3 +
            liveness_confidence * 0.2
        )
        
        return min(confidence, 1.0)
    
    def _generate_explanation(
        self,
        similarity: float,
        is_match: bool,
        doc_quality: FaceQualityAssessment,
        live_quality: FaceQualityAssessment,
        liveness_result: LivenessResult
    ) -> str:
        """Generate human-readable explanation"""
        parts = []
        
        # Match result
        if is_match:
            parts.append(f"Faces MATCH (similarity: {similarity:.2%})")
        else:
            parts.append(f"Faces DO NOT match (similarity: {similarity:.2%}, threshold: {self.match_threshold:.2%})")
        
        # Quality issues
        if doc_quality.overall_quality in [FaceQuality.POOR, FaceQuality.UNUSABLE]:
            parts.append(f"Document photo quality: {doc_quality.overall_quality}")
            if doc_quality.issues:
                parts.append(f"Issues: {', '.join(doc_quality.issues[:2])}")
        
        if live_quality.overall_quality in [FaceQuality.POOR, FaceQuality.UNUSABLE]:
            parts.append(f"Live capture quality: {live_quality.overall_quality}")
            if live_quality.issues:
                parts.append(f"Issues: {', '.join(live_quality.issues[:2])}")
        
        # Liveness
        if liveness_result == LivenessResult.LIKELY_SPOOF:
            parts.append("⚠ Possible presentation attack detected")
        elif liveness_result == LivenessResult.UNCERTAIN:
            parts.append("Liveness detection uncertain")
        
        return ". ".join(parts)


def verify_document_face(
    doc_image_path: str,
    live_image_path: str,
    threshold: float = 0.55
) -> FaceVerificationResult:
    """
    Convenience function for face verification.
    
    Args:
        doc_image_path: Path to document photo
        live_image_path: Path to live capture
        threshold: Similarity threshold for match
    
    Returns:
        FaceVerificationResult
    """
    service = InsightFaceService(match_threshold=threshold)
    return service.verify_faces(doc_image_path, live_image_path)


if __name__ == "__main__":
    # Test with sample images
    print("Face Verification Service - Test Mode")
    print("Note: Requires actual face images to test")

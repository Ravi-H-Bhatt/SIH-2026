"""
Forensic Tamper Detection Engine
Per SIH26188 Master Prompt

Combines classical CV + ML signals to detect document tampering:
- Error Level Analysis (ELA)
- JPEG compression artifacts
- Copy-move detection
- Metadata anomalies
- Local noise analysis
"""

import cv2
import numpy as np
from PIL import Image, ImageChops
from PIL.ExifTags import TAGS
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import io
import hashlib


@dataclass
class ForensicRegion:
    """Suspicious region in document"""
    region_type: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    score: float
    description: str


@dataclass
class ForensicResult:
    """Complete forensic analysis result"""
    tampering_probability: float
    confidence: float
    signals: Dict[str, dict]
    suspicious_regions: List[ForensicRegion]
    explanation: str
    model_version: str = "1.0.0"


class ForensicTamperDetector:
    """
    Document forgery detection using multiple forensic signals
    
    Per master prompt: Returns probability scores, NOT definitive proof
    """
    
    def __init__(self):
        self.model_version = "1.0.0"
        
        # Suspicious software in metadata
        self.editing_software = [
            'photoshop', 'gimp', 'paint.net', 'pixlr', 'canva',
            'photopea', 'fotor', 'befunky', 'editor'
        ]
    
    def analyze(self, image_path: str) -> ForensicResult:
        """
        Run complete forensic analysis
        
        Args:
            image_path: Path to document image
            
        Returns:
            ForensicResult with all signals
        """
        try:
            # Load image
            img_pil = Image.open(image_path)
            img_cv = cv2.imread(image_path)
            
            signals = {}
            suspicious_regions = []
            
            # 1. Error Level Analysis
            ela_score, ela_regions = self._error_level_analysis(img_pil)
            signals['ela'] = {
                'score': ela_score,
                'status': 'WARNING' if ela_score > 0.6 else 'PASS',
                'description': f'ELA score: {ela_score:.2f}'
            }
            suspicious_regions.extend(ela_regions)
            
            # 2. Metadata Analysis
            metadata_score, metadata_info = self._metadata_analysis(img_pil)
            signals['metadata'] = {
                'score': metadata_score,
                'status': 'WARNING' if metadata_score > 0.5 else 'PASS',
                'description': metadata_info,
                'details': self._extract_metadata(img_pil)
            }
            
            # 3. JPEG Compression Analysis
            compression_score = self._compression_analysis(img_cv)
            signals['compression'] = {
                'score': compression_score,
                'status': 'WARNING' if compression_score > 0.6 else 'PASS',
                'description': f'Inconsistent compression detected' if compression_score > 0.6 else 'Uniform compression'
            }
            
            # 4. Local Noise Analysis
            noise_score, noise_regions = self._noise_analysis(img_cv)
            signals['noise'] = {
                'score': noise_score,
                'status': 'WARNING' if noise_score > 0.6 else 'PASS',
                'description': f'Local noise inconsistencies' if noise_score > 0.6 else 'Consistent noise'
            }
            suspicious_regions.extend(noise_regions)
            
            # 5. Edge Consistency
            edge_score = self._edge_consistency(img_cv)
            signals['edges'] = {
                'score': edge_score,
                'status': 'WARNING' if edge_score > 0.6 else 'PASS',
                'description': f'Edge artifacts detected' if edge_score > 0.6 else 'Natural edges'
            }
            
            # 6. Copy-Move Detection
            copymove_score, copymove_regions = self._copy_move_detection(img_cv)
            signals['copy_move'] = {
                'score': copymove_score,
                'status': 'WARNING' if copymove_score > 0.7 else 'PASS',
                'description': f'Potential duplicated regions' if copymove_score > 0.7 else 'No duplication detected'
            }
            suspicious_regions.extend(copymove_regions)
            
            # Calculate overall tampering probability
            weights = {
                'ela': 0.25,
                'metadata': 0.15,
                'compression': 0.15,
                'noise': 0.15,
                'edges': 0.15,
                'copy_move': 0.15
            }
            
            tampering_prob = sum(
                signals[key]['score'] * weights[key]
                for key in weights.keys()
            )
            
            # Calculate confidence
            confidence = min(0.95, 0.5 + (abs(tampering_prob - 0.5) * 0.9))
            
            # Generate explanation
            warning_signals = [k for k, v in signals.items() if v['status'] == 'WARNING']
            if warning_signals:
                explanation = f"Forensic analysis detected suspicious signals: {', '.join(warning_signals)}. "
                explanation += "Manual review recommended."
            else:
                explanation = "No significant tampering indicators detected."
            
            return ForensicResult(
                tampering_probability=tampering_prob,
                confidence=confidence,
                signals=signals,
                suspicious_regions=suspicious_regions,
                explanation=explanation,
                model_version=self.model_version
            )
            
        except Exception as e:
            return ForensicResult(
                tampering_probability=0.5,
                confidence=0.0,
                signals={'error': {'description': str(e)}},
                suspicious_regions=[],
                explanation=f"Analysis failed: {str(e)}",
                model_version=self.model_version
            )
    
    def _error_level_analysis(self, img: Image.Image) -> Tuple[float, List[ForensicRegion]]:
        """
        Error Level Analysis (ELA)
        Detects areas with different compression levels
        """
        try:
            # Save at quality 90 and compare
            temp_buffer = io.BytesIO()
            img.save(temp_buffer, format='JPEG', quality=90)
            temp_buffer.seek(0)
            resaved = Image.open(temp_buffer)
            
            # Calculate difference
            ela_img = ImageChops.difference(img.convert('RGB'), resaved.convert('RGB'))
            extrema = ela_img.getextrema()
            max_diff = max([ex[1] for ex in extrema])
            
            # Normalize
            ela_score = min(1.0, max_diff / 50.0)
            
            # Find high-error regions
            ela_array = np.array(ela_img)
            gray_ela = cv2.cvtColor(ela_array, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray_ela, 20, 255, cv2.THRESH_BINARY)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            regions = []
            for contour in contours:
                if cv2.contourArea(contour) > 1000:  # Filter small noise
                    x, y, w, h = cv2.boundingRect(contour)
                    regions.append(ForensicRegion(
                        region_type='ela_anomaly',
                        bbox=(x, y, w, h),
                        score=ela_score,
                        description='High error level detected'
                    ))
            
            return ela_score, regions
            
        except:
            return 0.0, []
    
    def _metadata_analysis(self, img: Image.Image) -> Tuple[float, str]:
        """
        Analyze EXIF metadata for tampering signs
        """
        try:
            exif = img.getexif()
            if not exif:
                return 0.3, "No EXIF data (may be stripped)"
            
            metadata = self._extract_metadata(img)
            
            # Check for editing software
            software = metadata.get('Software', '').lower()
            for edit_soft in self.editing_software:
                if edit_soft in software:
                    return 0.8, f"Edited with {software}"
            
            # Check for missing expected fields
            expected_fields = ['DateTime', 'Make', 'Model']
            missing = [f for f in expected_fields if f not in metadata]
            
            if len(missing) > 2:
                return 0.5, "Incomplete metadata"
            
            return 0.2, "Metadata appears normal"
            
        except:
            return 0.3, "Metadata analysis failed"
    
    def _extract_metadata(self, img: Image.Image) -> Dict[str, str]:
        """Extract EXIF metadata"""
        try:
            exif = img.getexif()
            if not exif:
                return {}
            
            metadata = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                metadata[tag] = str(value)
            
            return metadata
        except:
            return {}
    
    def _compression_analysis(self, img: np.ndarray) -> float:
        """
        Analyze JPEG compression consistency
        """
        try:
            # Convert to YCrCb
            ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
            y_channel = ycrcb[:, :, 0]
            
            # Split into 8x8 blocks and analyze DCT
            h, w = y_channel.shape
            block_variance = []
            
            for i in range(0, h - 8, 8):
                for j in range(0, w - 8, 8):
                    block = y_channel[i:i+8, j:j+8].astype(np.float32)
                    dct = cv2.dct(block)
                    variance = np.var(dct)
                    block_variance.append(variance)
            
            # Check for inconsistency
            if block_variance:
                variance_std = np.std(block_variance)
                variance_mean = np.mean(block_variance)
                inconsistency = variance_std / (variance_mean + 1e-5)
                score = min(1.0, inconsistency / 2.0)
                return score
            
            return 0.0
            
        except:
            return 0.0
    
    def _noise_analysis(self, img: np.ndarray) -> Tuple[float, List[ForensicRegion]]:
        """
        Analyze local noise patterns
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate local noise variance
            kernel_size = 15
            noise_map = np.zeros_like(gray, dtype=np.float32)
            
            for i in range(0, gray.shape[0] - kernel_size, kernel_size):
                for j in range(0, gray.shape[1] - kernel_size, kernel_size):
                    block = gray[i:i+kernel_size, j:j+kernel_size]
                    noise_map[i:i+kernel_size, j:j+kernel_size] = np.std(block)
            
            # Find high-variance regions
            mean_noise = np.mean(noise_map)
            std_noise = np.std(noise_map)
            
            inconsistency_score = min(1.0, std_noise / (mean_noise + 1e-5))
            
            return inconsistency_score, []
            
        except:
            return 0.0, []
    
    def _edge_consistency(self, img: np.ndarray) -> float:
        """
        Check edge consistency (splicing detection)
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # Analyze edge strength distribution
            edge_pixels = edges > 0
            if not edge_pixels.any():
                return 0.0
            
            # Check for abrupt edge patterns (sign of splicing)
            kernel = np.ones((5, 5), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=1)
            edge_density = np.sum(dilated > 0) / dilated.size
            
            # High density can indicate splicing
            score = min(1.0, edge_density * 5.0)
            return score
            
        except:
            return 0.0
    
    def _copy_move_detection(self, img: np.ndarray) -> Tuple[float, List[ForensicRegion]]:
        """
        Detect copy-move forgery
        Simple block-matching approach
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            # Use ORB for keypoint matching
            orb = cv2.ORB_create(nfeatures=500)
            keypoints, descriptors = orb.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) < 10:
                return 0.0, []
            
            # Match with itself
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(descriptors, descriptors, k=2)
            
            # Find duplicate matches (excluding self-matches)
            duplicate_matches = []
            for m, n in matches:
                if m.distance < 0.7 * n.distance:
                    pt1 = keypoints[m.queryIdx].pt
                    pt2 = keypoints[m.trainIdx].pt
                    distance = np.linalg.norm(np.array(pt1) - np.array(pt2))
                    
                    # If points are far apart but similar, potential copy-move
                    if 50 < distance < min(w, h) * 0.5:
                        duplicate_matches.append((pt1, pt2, m.distance))
            
            if len(duplicate_matches) > 20:
                score = min(1.0, len(duplicate_matches) / 100.0)
                return score, []
            
            return 0.0, []
            
        except:
            return 0.0, []


# Global instance
forensic_detector = ForensicTamperDetector()

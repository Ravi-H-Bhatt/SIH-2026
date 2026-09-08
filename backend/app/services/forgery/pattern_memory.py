"""
Fraud Pattern Memory Service (EU-FADO Inspired Knowledge Base).

Maintains and matches against forensic signatures of known document manipulation
tactics, counterfeit syndicates, and recurring forgery techniques.
"""

from typing import Dict, Any, List, Optional
import math


class FraudPatternMemory:
    def __init__(self):
        # Curated repository of known forensic attack signatures (EU-FADO / BSF Intelligence style)
        self.known_patterns = [
            {
                "pattern_id": "FPM-IND-2025-01",
                "name": "Syndicate Photo-Substitution (Border Cut & Paste)",
                "category": "PHOTO_SUBSTITUTION",
                "description": "Localized border gradient discontinuity with high ELA variance around the portrait frame. Typically observed when an authentic stolen passport has its photo physically swapped.",
                "signature_profile": {
                    "photo_boundary_discontinuity_min": 45.0,
                    "ela_variance_min": 35.0,
                },
                "risk_weight": 40,
                "recommended_action": "UV Lamp inspection & secondary biometric fingerprint cross-check",
            },
            {
                "pattern_id": "FPM-INT-2024-88",
                "name": "Digital Recompression Splicing (Photoshop Patching)",
                "category": "DIGITAL_MANIPULATION",
                "description": "Double JPEG compression artifacts with distinct DCT frequency grid misalignment. Commonly used for DOB and expiry date altering.",
                "signature_profile": {
                    "dct_quantization_error_min": 40.0,
                    "exif_tampered": True,
                },
                "risk_weight": 35,
                "recommended_action": "Cross-verify visual date with MRZ check digit 7-3-1 weighting",
            },
            {
                "pattern_id": "FPM-SYN-2026-03",
                "name": "Screen Replay & Presentation Spoof",
                "category": "BIOMETRIC_SPOOF",
                "description": "Suppressed high-frequency Fourier texture with low Laplacian variance on live camera capture. Indicative of iPad/phone screen replay attack.",
                "signature_profile": {
                    "low_sharpness": True,
                },
                "risk_weight": 50,
                "recommended_action": "Require physical officer presence; request 3D head movement",
            }
        ]

    def match_patterns(
        self,
        forensic_signature: Dict[str, Any],
        forgery_score: float,
        is_live: bool,
        flags: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Compares incoming document forensic signature against known pattern memory.
        """
        matches = []
        
        boundary = forensic_signature.get("photo_boundary_discontinuity", 0.0)
        ela = forensic_signature.get("ela_variance", 0.0)
        dct = forensic_signature.get("dct_quantization_error", 0.0)
        exif = forensic_signature.get("exif_tampered", False)

        # Pattern 1: Photo-Substitution
        if boundary >= 40.0 and (ela >= 30.0 or forgery_score >= 35.0):
            matches.append({
                "pattern_id": "FPM-IND-2025-01",
                "name": "Syndicate Photo-Substitution (Border Cut & Paste)",
                "confidence": round(min(0.96, max(0.65, boundary / 100.0 + ela / 200.0)), 2),
                "severity": "CRITICAL",
                "description": "Abrupt gradient transition detected around passport portrait border matching known physical photo swap techniques.",
                "countermeasure": "Perform manual UV illumination inspection & physical tactile check on laminates."
            })

        # Pattern 2: Digital Recompression / Software Patching
        if dct >= 35.0 or exif:
            conf = 0.90 if exif else round(min(0.85, dct / 100.0 + 0.3), 2)
            matches.append({
                "pattern_id": "FPM-INT-2024-88",
                "name": "Digital Recompression Splicing (Software Tampering)",
                "confidence": conf,
                "severity": "HIGH",
                "description": "DCT frequency grid inconsistency detected matching software-altered document templates.",
                "countermeasure": "Inspect visual zone characters for font kerning deviations against ICAO OCR-B standard."
            })

        # Pattern 3: Screen Replay / Liveness Spoof
        if not is_live:
            matches.append({
                "pattern_id": "FPM-SYN-2026-03",
                "name": "Display Screen / Paper Print Anti-Spoof Violation",
                "confidence": 0.94,
                "severity": "CRITICAL",
                "description": "Live traveler biometric capture exhibited unnatural planar texture consistent with screen reflection replay.",
                "countermeasure": "Halt automated e-Gate; direct traveler to manual officer lane for physical verification."
            })

        return matches


pattern_memory = FraudPatternMemory()

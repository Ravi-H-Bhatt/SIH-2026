"""
Evidence Fusion Engine - Core Innovation of SIH26188 System
Part of SIH26188 AI Border Document Screening System

THIS IS THE KILLER DIFFERENTIATOR:
While individual checks may pass, the fusion engine detects contradictions
and inconsistencies across evidence sources that reveal sophisticated fraud.

Example: Document passes forensics, face matches, MRZ is valid, BUT:
- Person entered 3 times with same face but different names
- DOB in passport doesn't match historical crossing records
- Document number format changed mid-validity period

This is NOT simple scoring - it's evidence correlation and contradiction detection.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import json


class RiskLevel(str, Enum):
    """Risk classification levels"""
    CLEAR = "CLEAR"  # No concerns, clear to proceed
    LOW = "LOW"  # Minor anomalies, likely clerical
    MEDIUM = "MEDIUM"  # Suspicious patterns, warrant attention
    HIGH = "HIGH"  # Strong indicators of fraud, secondary review required
    CRITICAL = "CRITICAL"  # Multiple red flags, escalate immediately


class RecommendedAction(str, Enum):
    """Recommended officer actions"""
    CLEAR = "CLEAR"  # Clear traveler immediately
    SECONDARY_REVIEW = "SECONDARY_REVIEW"  # Send to secondary inspection
    ESCALATE = "ESCALATE"  # Alert supervisor/investigate
    DETAIN = "DETAIN"  # Hold for law enforcement


class ContradictionType(str, Enum):
    """Types of evidence contradictions"""
    TEMPORAL = "TEMPORAL"  # Time-based inconsistencies
    IDENTITY = "IDENTITY"  # Identity mismatches across evidence
    DOCUMENT = "DOCUMENT"  # Document integrity issues
    BEHAVIORAL = "BEHAVIORAL"  # Pattern anomalies
    BIOMETRIC = "BIOMETRIC"  # Face/fingerprint conflicts
    CROSS_SOURCE = "CROSS_SOURCE"  # Conflicts between data sources


@dataclass
class Contradiction:
    """A detected contradiction in evidence"""
    type: ContradictionType
    severity: float  # 0-1, higher = more severe
    description: str
    evidence_sources: List[str]  # Which signals/systems are conflicting
    details: Dict[str, Any]


@dataclass
class EvidenceSignal:
    """Individual evidence signal from a component"""
    source: str  # "mrz", "forensics", "face", "ocr", "validation", etc.
    risk_score: float  # 0-1, 0=clean, 1=high risk
    confidence: float  # 0-1, how confident in this assessment
    findings: List[str]  # Human-readable findings
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class FusionResult:
    """Complete evidence fusion result"""
    risk_level: RiskLevel
    risk_score: float  # 0-1 aggregated risk
    confidence: float  # 0-1 confidence in assessment
    recommended_action: RecommendedAction
    
    # Evidence breakdown
    signals: List[EvidenceSignal]
    contradictions: List[Contradiction]
    
    # Explainability
    reasoning: str  # Why this risk level?
    key_factors: List[str]  # Top 3-5 factors
    
    # Metadata
    timestamp: str
    fusion_version: str = "1.0"


class EvidenceFusionEngine:
    """
    Production-grade evidence fusion and contradiction detection engine.
    
    THE CORE INNOVATION:
    This is not a simple weighted average of component scores.
    It actively looks for contradictions and patterns that indicate
    sophisticated fraud attempts.
    
    Three-stage process:
    1. Signal Aggregation - Collect evidence from all components
    2. Contradiction Detection - Find conflicts across signals
    3. Risk Classification - Determine overall risk + action
    
    Contradiction Examples:
    - Face matches but identity graph shows same face with different name
    - Document forensically clean but validation shows impossible dates
    - MRZ valid but OCR shows different values than MRZ
    - Multiple border crossings with conflicting biographical data
    - Document issued after supposed expiry date
    - Age progression doesn't match photo vs DOB
    """
    
    def __init__(self, version: str = "1.0"):
        self.version = version
        
        # Signal weights (when no contradictions)
        self.signal_weights = {
            "forensics": 0.25,  # Document tampering
            "face": 0.25,       # Biometric verification
            "mrz": 0.15,        # ICAO compliance
            "validation": 0.15, # Business rules
            "ocr": 0.10,        # Field extraction quality
            "watchlist": 0.30,  # Watchlist hits (overrides if present)
            "identity_graph": 0.20  # Historical patterns
        }
        
        # Risk level thresholds
        self.risk_thresholds = {
            RiskLevel.CLEAR: 0.0,
            RiskLevel.LOW: 0.15,
            RiskLevel.MEDIUM: 0.35,
            RiskLevel.HIGH: 0.60,
            RiskLevel.CRITICAL: 0.80
        }
    
    def fuse_evidence(
        self,
        signals: List[EvidenceSignal],
        historical_data: Optional[Dict[str, Any]] = None,
        watchlist_hits: Optional[List[Dict[str, Any]]] = None
    ) -> FusionResult:
        """
        Fuse all evidence signals and detect contradictions.
        
        Args:
            signals: List of evidence signals from components
            historical_data: Optional historical crossing/identity data
            watchlist_hits: Optional watchlist matches
        
        Returns:
            FusionResult with risk assessment and contradictions
        """
        # Stage 1: Signal Aggregation
        base_risk_score = self._aggregate_signals(signals)
        
        # Stage 2: Contradiction Detection (THE INNOVATION)
        contradictions = self._detect_contradictions(
            signals, 
            historical_data, 
            watchlist_hits
        )
        
        # Adjust risk based on contradictions
        contradiction_penalty = self._calculate_contradiction_penalty(contradictions)
        adjusted_risk_score = min(base_risk_score + contradiction_penalty, 1.0)
        
        # Stage 3: Risk Classification
        risk_level = self._classify_risk(adjusted_risk_score, contradictions)
        recommended_action = self._determine_action(risk_level, contradictions)
        
        # Calculate confidence
        confidence = self._calculate_confidence(signals, contradictions)
        
        # Generate explanation
        reasoning = self._generate_reasoning(
            risk_level,
            adjusted_risk_score,
            signals,
            contradictions
        )
        
        key_factors = self._extract_key_factors(signals, contradictions)
        
        return FusionResult(
            risk_level=risk_level,
            risk_score=adjusted_risk_score,
            confidence=confidence,
            recommended_action=recommended_action,
            signals=signals,
            contradictions=contradictions,
            reasoning=reasoning,
            key_factors=key_factors,
            timestamp=datetime.utcnow().isoformat(),
            fusion_version=self.version
        )
    
    def _aggregate_signals(self, signals: List[EvidenceSignal]) -> float:
        """
        Aggregate individual signal scores using weighted average.
        
        Returns:
            Base risk score (0-1)
        """
        if not signals:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for signal in signals:
            weight = self.signal_weights.get(signal.source, 0.1)
            # Weight by confidence
            effective_weight = weight * signal.confidence
            weighted_sum += signal.risk_score * effective_weight
            total_weight += effective_weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def _detect_contradictions(
        self,
        signals: List[EvidenceSignal],
        historical_data: Optional[Dict[str, Any]],
        watchlist_hits: Optional[List[Dict[str, Any]]]
    ) -> List[Contradiction]:
        """
        THE CORE INNOVATION: Detect contradictions across evidence.
        
        This is what separates this system from simple OCR+face matching.
        """
        contradictions = []
        
        # Build evidence map for easier cross-referencing
        evidence_map = {s.source: s for s in signals}
        
        # 1. MRZ vs OCR Contradictions
        if "mrz" in evidence_map and "ocr" in evidence_map:
            mrz_data = evidence_map["mrz"].raw_data or {}
            ocr_data = evidence_map["ocr"].raw_data or {}
            
            mrz_contradictions = self._check_mrz_ocr_consistency(mrz_data, ocr_data)
            contradictions.extend(mrz_contradictions)
        
        # 2. Validation vs Forensics Contradictions
        # Example: Document passes forensics but has impossible dates
        if "validation" in evidence_map and "forensics" in evidence_map:
            val_score = evidence_map["validation"].risk_score
            forensics_score = evidence_map["forensics"].risk_score
            
            # Document looks tampered but validation passes? Suspicious.
            if forensics_score > 0.6 and val_score < 0.2:
                contradictions.append(Contradiction(
                    type=ContradictionType.DOCUMENT,
                    severity=0.7,
                    description="Document shows tampering signs but fields validate correctly - possible sophisticated forgery",
                    evidence_sources=["forensics", "validation"],
                    details={
                        "forensics_risk": forensics_score,
                        "validation_risk": val_score
                    }
                ))
        
        # 3. Face Match vs Identity Graph Contradictions
        # THE KILLER CASE: Face matches but identity graph shows conflicts
        if "face" in evidence_map and "identity_graph" in evidence_map:
            face_data = evidence_map["face"].raw_data or {}
            graph_data = evidence_map["identity_graph"].raw_data or {}
            
            # Face matches (low risk) but identity graph flags issues (high risk)
            if evidence_map["face"].risk_score < 0.3 and evidence_map["identity_graph"].risk_score > 0.6:
                contradictions.append(Contradiction(
                    type=ContradictionType.IDENTITY,
                    severity=0.85,
                    description="Face matches current document BUT identity graph shows same biometric with conflicting identity data in history",
                    evidence_sources=["face", "identity_graph"],
                    details={
                        "face_similarity": face_data.get("similarity", 0),
                        "graph_conflicts": graph_data.get("conflicts", [])
                    }
                ))
        
        # 4. Watchlist Hit vs Face Match Contradiction
        # Example: Face doesn't match document but matches watchlist entry
        if watchlist_hits and "face" in evidence_map:
            for hit in watchlist_hits:
                if hit.get("match_confidence", 0) > 0.7:
                    face_risk = evidence_map["face"].risk_score
                    
                    # Watchlist match but face "matches" document? Something's wrong.
                    if face_risk < 0.3:  # Face matches doc
                        contradictions.append(Contradiction(
                            type=ContradictionType.BIOMETRIC,
                            severity=0.95,
                            description=f"Face matches document but also matches watchlist entry: {hit.get('name', 'Unknown')}",
                            evidence_sources=["face", "watchlist"],
                            details={
                                "watchlist_name": hit.get("name"),
                                "watchlist_reason": hit.get("reason"),
                                "match_confidence": hit.get("match_confidence")
                            }
                        ))
        
        # 5. Historical Data Contradictions
        if historical_data:
            historical_contradictions = self._check_historical_consistency(
                evidence_map,
                historical_data
            )
            contradictions.extend(historical_contradictions)
        
        # 6. Temporal Contradictions
        temporal_contradictions = self._check_temporal_consistency(evidence_map)
        contradictions.extend(temporal_contradictions)
        
        return contradictions
    
    def _check_mrz_ocr_consistency(
        self,
        mrz_data: Dict[str, Any],
        ocr_data: Dict[str, Any]
    ) -> List[Contradiction]:
        """Check MRZ and OCR field consistency"""
        contradictions = []
        
        mrz_fields = mrz_data.get("fields", {})
        ocr_fields = ocr_data.get("fields", {})
        
        # Compare critical fields
        compare_fields = [
            ("document_number", "Document Number"),
            ("surname", "Surname"),
            ("date_of_birth", "Date of Birth"),
            ("date_of_expiry", "Expiry Date")
        ]
        
        mismatches = []
        for field_key, field_name in compare_fields:
            mrz_val = str(mrz_fields.get(field_key, "")).strip().upper()
            ocr_val = str(ocr_fields.get(field_key, "")).strip().upper()
            
            if mrz_val and ocr_val and mrz_val != ocr_val:
                mismatches.append({
                    "field": field_name,
                    "mrz": mrz_val,
                    "ocr": ocr_val
                })
        
        if mismatches:
            contradictions.append(Contradiction(
                type=ContradictionType.DOCUMENT,
                severity=0.75,
                description=f"MRZ and visual inspection zone (VIZ) show different values for {len(mismatches)} field(s)",
                evidence_sources=["mrz", "ocr"],
                details={"mismatches": mismatches}
            ))
        
        return contradictions
    
    def _check_historical_consistency(
        self,
        evidence_map: Dict[str, EvidenceSignal],
        historical_data: Dict[str, Any]
    ) -> List[Contradiction]:
        """Check consistency with historical crossing data"""
        contradictions = []
        
        # Example: Previous crossings show different DOB for same person
        previous_crossings = historical_data.get("previous_crossings", [])
        if previous_crossings:
            current_dob = None
            current_name = None
            
            # Extract current document data
            if "validation" in evidence_map:
                val_data = evidence_map["validation"].raw_data or {}
                current_dob = val_data.get("date_of_birth")
                current_name = val_data.get("full_name")
            
            # Check for conflicts
            for crossing in previous_crossings:
                prev_dob = crossing.get("date_of_birth")
                prev_name = crossing.get("full_name")
                
                if current_dob and prev_dob and current_dob != prev_dob:
                    contradictions.append(Contradiction(
                        type=ContradictionType.TEMPORAL,
                        severity=0.90,
                        description=f"Date of birth changed from previous crossing: {prev_dob} → {current_dob}",
                        evidence_sources=["validation", "historical"],
                        details={
                            "current_dob": current_dob,
                            "previous_dob": prev_dob,
                            "crossing_date": crossing.get("date")
                        }
                    ))
                
                if current_name and prev_name and current_name != prev_name:
                    # Name changes are possible (marriage, etc.) but flag for review
                    contradictions.append(Contradiction(
                        type=ContradictionType.IDENTITY,
                        severity=0.65,
                        description=f"Name differs from previous crossing: {prev_name} → {current_name}",
                        evidence_sources=["validation", "historical"],
                        details={
                            "current_name": current_name,
                            "previous_name": prev_name,
                            "crossing_date": crossing.get("date")
                        }
                    ))
        
        return contradictions
    
    def _check_temporal_consistency(
        self,
        evidence_map: Dict[str, EvidenceSignal]
    ) -> List[Contradiction]:
        """Check for temporal inconsistencies"""
        contradictions = []
        
        if "validation" in evidence_map:
            val_data = evidence_map["validation"].raw_data or {}
            findings = val_data.get("findings", [])
            
            # Look for temporal validation failures
            temporal_errors = [
                f for f in findings 
                if "expired" in str(f).lower() or "issue" in str(f).lower() and "expiry" in str(f).lower()
            ]
            
            if temporal_errors:
                contradictions.append(Contradiction(
                    type=ContradictionType.TEMPORAL,
                    severity=0.80,
                    description="Document has temporal inconsistencies (expiry/issue dates)",
                    evidence_sources=["validation"],
                    details={"errors": temporal_errors}
                ))
        
        return contradictions
    
    def _calculate_contradiction_penalty(
        self,
        contradictions: List[Contradiction]
    ) -> float:
        """
        Calculate risk penalty from contradictions.
        
        Contradictions are MORE serious than individual failures.
        """
        if not contradictions:
            return 0.0
        
        # Contradictions compound - multiple contradictions is VERY suspicious
        total_severity = sum(c.severity for c in contradictions)
        num_contradictions = len(contradictions)
        
        # Non-linear scaling: multiple contradictions are exponentially worse
        if num_contradictions == 1:
            penalty = total_severity * 0.3
        elif num_contradictions == 2:
            penalty = total_severity * 0.5
        else:  # 3+
            penalty = total_severity * 0.7
        
        return min(penalty, 0.8)  # Cap at 0.8 to leave room for base score
    
    def _classify_risk(
        self,
        risk_score: float,
        contradictions: List[Contradiction]
    ) -> RiskLevel:
        """Classify overall risk level"""
        # Critical contradictions auto-escalate
        critical_contradictions = [
            c for c in contradictions 
            if c.severity >= 0.85
        ]
        
        if critical_contradictions:
            return RiskLevel.CRITICAL
        
        # Otherwise use score thresholds
        if risk_score >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif risk_score >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif risk_score >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        elif risk_score >= self.risk_thresholds[RiskLevel.LOW]:
            return RiskLevel.LOW
        else:
            return RiskLevel.CLEAR
    
    def _determine_action(
        self,
        risk_level: RiskLevel,
        contradictions: List[Contradiction]
    ) -> RecommendedAction:
        """Determine recommended officer action"""
        if risk_level == RiskLevel.CRITICAL:
            return RecommendedAction.ESCALATE
        elif risk_level == RiskLevel.HIGH:
            return RecommendedAction.SECONDARY_REVIEW
        elif risk_level == RiskLevel.MEDIUM:
            # Check if watchlist hit
            watchlist_contradictions = [
                c for c in contradictions 
                if "watchlist" in c.evidence_sources
            ]
            if watchlist_contradictions:
                return RecommendedAction.SECONDARY_REVIEW
            return RecommendedAction.SECONDARY_REVIEW
        else:
            return RecommendedAction.CLEAR
    
    def _calculate_confidence(
        self,
        signals: List[EvidenceSignal],
        contradictions: List[Contradiction]
    ) -> float:
        """Calculate confidence in the assessment"""
        # Average signal confidence
        if signals:
            avg_signal_confidence = sum(s.confidence for s in signals) / len(signals)
        else:
            avg_signal_confidence = 0.5
        
        # Contradictions increase confidence (we found something concrete)
        if contradictions:
            contradiction_boost = min(len(contradictions) * 0.1, 0.3)
        else:
            contradiction_boost = 0.0
        
        confidence = min(avg_signal_confidence + contradiction_boost, 1.0)
        return confidence
    
    def _generate_reasoning(
        self,
        risk_level: RiskLevel,
        risk_score: float,
        signals: List[EvidenceSignal],
        contradictions: List[Contradiction]
    ) -> str:
        """Generate human-readable reasoning"""
        parts = []
        
        parts.append(f"Risk Level: {risk_level.value} (score: {risk_score:.2%})")
        
        if contradictions:
            parts.append(f"\n⚠ {len(contradictions)} evidence contradiction(s) detected:")
            for i, contra in enumerate(contradictions[:3], 1):  # Top 3
                parts.append(f"  {i}. {contra.description}")
        
        # High-risk signals
        high_risk_signals = [s for s in signals if s.risk_score > 0.6]
        if high_risk_signals:
            parts.append(f"\nHigh-risk signals ({len(high_risk_signals)}):")
            for sig in high_risk_signals[:3]:
                parts.append(f"  • {sig.source}: {sig.risk_score:.2%} risk")
                if sig.findings:
                    parts.append(f"    - {sig.findings[0]}")
        
        return "\n".join(parts)
    
    def _extract_key_factors(
        self,
        signals: List[EvidenceSignal],
        contradictions: List[Contradiction]
    ) -> List[str]:
        """Extract top 3-5 key factors"""
        factors = []
        
        # Contradictions are always key factors
        for contra in contradictions[:3]:
            factors.append(f"⚠ {contra.description}")
        
        # Add highest risk signals
        sorted_signals = sorted(signals, key=lambda s: s.risk_score, reverse=True)
        for sig in sorted_signals[:2]:
            if sig.risk_score > 0.5 and sig.findings:
                factors.append(f"{sig.source.upper()}: {sig.findings[0]}")
        
        return factors[:5]


def fuse_document_evidence(
    mrz_result: Optional[Dict[str, Any]] = None,
    ocr_result: Optional[Dict[str, Any]] = None,
    forensics_result: Optional[Dict[str, Any]] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    face_result: Optional[Dict[str, Any]] = None,
    watchlist_hits: Optional[List[Dict[str, Any]]] = None,
    identity_graph_result: Optional[Dict[str, Any]] = None,
    historical_data: Optional[Dict[str, Any]] = None
) -> FusionResult:
    """
    Convenience function to fuse all document evidence.
    
    Args:
        mrz_result: MRZ parsing result
        ocr_result: OCR extraction result
        forensics_result: Forensic analysis result
        validation_result: Document validation result
        face_result: Face verification result
        watchlist_hits: Watchlist matches
        identity_graph_result: Identity graph analysis
        historical_data: Historical crossing data
    
    Returns:
        FusionResult with risk assessment
    """
    signals = []
    
    # Convert each component result to EvidenceSignal
    if mrz_result:
        signals.append(EvidenceSignal(
            source="mrz",
            risk_score=0.0 if mrz_result.get("is_valid") else 0.7,
            confidence=0.95,
            findings=["MRZ invalid"] if not mrz_result.get("is_valid") else [],
            raw_data=mrz_result
        ))
    
    if ocr_result:
        signals.append(EvidenceSignal(
            source="ocr",
            risk_score=0.1,  # OCR is mostly for extraction, not risk
            confidence=ocr_result.get("confidence", 0.8),
            findings=[],
            raw_data=ocr_result
        ))
    
    if forensics_result:
        signals.append(EvidenceSignal(
            source="forensics",
            risk_score=forensics_result.get("tampering_probability", 0.0),
            confidence=forensics_result.get("confidence", 0.8),
            findings=[forensics_result.get("explanation", "")],
            raw_data=forensics_result
        ))
    
    if validation_result:
        signals.append(EvidenceSignal(
            source="validation",
            risk_score=1.0 - validation_result.get("validation_score", 1.0),
            confidence=0.9,
            findings=[f.get("message", "") for f in validation_result.get("findings", [])[:2]],
            raw_data=validation_result
        ))
    
    if face_result:
        signals.append(EvidenceSignal(
            source="face",
            risk_score=0.0 if face_result.get("is_match") else 0.9,
            confidence=face_result.get("confidence", 0.8),
            findings=["Face mismatch"] if not face_result.get("is_match") else [],
            raw_data=face_result
        ))
    
    if identity_graph_result:
        signals.append(EvidenceSignal(
            source="identity_graph",
            risk_score=identity_graph_result.get("risk_score", 0.0),
            confidence=identity_graph_result.get("confidence", 0.7),
            findings=identity_graph_result.get("findings", []),
            raw_data=identity_graph_result
        ))
    
    if watchlist_hits:
        # Watchlist hit is high risk
        max_confidence = max([h.get("match_confidence", 0) for h in watchlist_hits])
        signals.append(EvidenceSignal(
            source="watchlist",
            risk_score=0.95,
            confidence=max_confidence,
            findings=[f"Watchlist match: {watchlist_hits[0].get('name', 'Unknown')}"],
            raw_data={"hits": watchlist_hits}
        ))
    
    engine = EvidenceFusionEngine()
    return engine.fuse_evidence(signals, historical_data, watchlist_hits)


if __name__ == "__main__":
    # Demo: The killer case - individual checks pass but contradictions found
    print("Evidence Fusion Engine - Demo")
    print("="*60)
    print("\nScenario: Sophisticated fraud - individual checks pass BUT contradictions exist\n")
    
    # All individual checks look OK
    demo_signals = [
        EvidenceSignal(
            source="forensics",
            risk_score=0.15,  # Clean document
            confidence=0.9,
            findings=["Minor JPEG artifacts (normal)"],
            raw_data={}
        ),
        EvidenceSignal(
            source="face",
            risk_score=0.10,  # Face matches
            confidence=0.85,
            findings=[],
            raw_data={"similarity": 0.92}
        ),
        EvidenceSignal(
            source="mrz",
            risk_score=0.0,  # MRZ valid
            confidence=0.95,
            findings=[],
            raw_data={"is_valid": True, "fields": {"surname": "SHARMA", "date_of_birth": "19900515"}}
        ),
        EvidenceSignal(
            source="validation",
            risk_score=0.05,  # Validation passes
            confidence=0.9,
            findings=[],
            raw_data={"validation_score": 0.95}
        ),
        EvidenceSignal(
            source="identity_graph",
            risk_score=0.75,  # BUT identity graph flags issue
            confidence=0.80,
            findings=["Same biometric found with different DOB in historical records"],
            raw_data={"conflicts": ["DOB mismatch: 1990-05-15 vs 1988-03-20"]}
        )
    ]
    
    engine = EvidenceFusionEngine()
    result = engine.fuse_evidence(demo_signals, historical_data={})
    
    print(f"Risk Level: {result.risk_level}")
    print(f"Risk Score: {result.risk_score:.2%}")
    print(f"Recommended Action: {result.recommended_action}\n")
    print(f"Contradictions Found: {len(result.contradictions)}")
    for c in result.contradictions:
        print(f"  • [{c.type}] {c.description}")
    print(f"\nReasoning:\n{result.reasoning}")

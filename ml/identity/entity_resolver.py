"""
Identity Graph and Entity Resolution
Part of SIH26188 AI Border Document Screening System

Builds and queries an identity knowledge graph to detect:
- Same person using multiple identities
- Same biometric (face) linked to different names/DOBs
- Document reuse patterns
- Travel pattern anomalies
- Identity theft indicators
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from enum import Enum
import json


class EntityType(str, Enum):
    """Types of entities in the graph"""
    PERSON = "PERSON"
    DOCUMENT = "DOCUMENT"
    BIOMETRIC = "BIOMETRIC"
    CROSSING = "CROSSING"


class RelationType(str, Enum):
    """Types of relationships in the graph"""
    OWNS = "OWNS"  # Person owns Document
    HAS_BIOMETRIC = "HAS_BIOMETRIC"  # Person has Biometric
    USED_IN = "USED_IN"  # Document used in Crossing
    SIMILAR_TO = "SIMILAR_TO"  # Biometric similar to Biometric
    ALIAS_OF = "ALIAS_OF"  # Person alias of Person


@dataclass
class Entity:
    """Graph entity node"""
    id: str
    type: EntityType
    attributes: Dict[str, Any]
    created_at: str


@dataclass
class Relationship:
    """Graph relationship edge"""
    from_id: str
    to_id: str
    type: RelationType
    confidence: float  # 0-1
    metadata: Dict[str, Any]
    created_at: str


@dataclass
class IdentityGraphResult:
    """Result of identity graph analysis"""
    risk_score: float  # 0-1
    confidence: float
    findings: List[str]
    conflicts: List[Dict[str, Any]]
    entity_id: str
    related_entities: List[str]
    suspicious_patterns: List[str]


class IdentityGraph:
    """
    Identity knowledge graph using NetworkX.
    
    The graph connects:
    - People (with names, DOB, nationality)
    - Documents (passport numbers, IDs)
    - Biometrics (face embeddings)
    - Border crossings (events)
    
    Pattern detection:
    1. Same face, different identities
    2. Same document, multiple uses after expiry
    3. Conflicting biographical data over time
    4. Impossible travel patterns (same person, different locations, impossible timeframe)
    """
    
    def __init__(self):
        """Initialize identity graph"""
        try:
            import networkx as nx
            self.graph = nx.MultiDiGraph()
            self.nx = nx
            self.enabled = True
        except ImportError:
            print("⚠ NetworkX not available, identity graph disabled")
            self.enabled = False
            self.graph = None
    
    def add_entity(
        self,
        entity_id: str,
        entity_type: EntityType,
        attributes: Dict[str, Any]
    ) -> Entity:
        """Add entity to graph"""
        if not self.enabled:
            return None
        
        entity = Entity(
            id=entity_id,
            type=entity_type,
            attributes=attributes,
            created_at=datetime.utcnow().isoformat()
        )
        
        self.graph.add_node(
            entity_id,
            type=entity_type.value,
            **attributes,
            created_at=entity.created_at
        )
        
        return entity
    
    def add_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: RelationType,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """Add relationship to graph"""
        if not self.enabled:
            return None
        
        relationship = Relationship(
            from_id=from_id,
            to_id=to_id,
            type=rel_type,
            confidence=confidence,
            metadata=metadata or {},
            created_at=datetime.utcnow().isoformat()
        )
        
        self.graph.add_edge(
            from_id,
            to_id,
            type=rel_type.value,
            confidence=confidence,
            metadata=metadata or {},
            created_at=relationship.created_at
        )
        
        return relationship
    
    def analyze_identity(
        self,
        person_attributes: Dict[str, Any],
        document_attributes: Dict[str, Any],
        biometric_data: Optional[Dict[str, Any]] = None
    ) -> IdentityGraphResult:
        """
        Analyze identity against graph to detect fraud patterns.
        
        Args:
            person_attributes: Name, DOB, nationality, etc.
            document_attributes: Document number, expiry, etc.
            biometric_data: Face embedding or hash
        
        Returns:
            IdentityGraphResult with risk assessment
        """
        if not self.enabled:
            return IdentityGraphResult(
                risk_score=0.0,
                confidence=0.0,
                findings=["Identity graph disabled (NetworkX not available)"],
                conflicts=[],
                entity_id="",
                related_entities=[],
                suspicious_patterns=[]
            )
        
        findings = []
        conflicts = []
        suspicious_patterns = []
        
        # Generate IDs
        person_id = self._generate_person_id(person_attributes)
        doc_id = document_attributes.get("document_number", "UNKNOWN")
        
        # Check if person exists
        person_exists = self.graph.has_node(person_id)
        doc_exists = self.graph.has_node(doc_id)
        
        if person_exists:
            # Person seen before - check for conflicts
            stored_attrs = self.graph.nodes[person_id]
            conflicts.extend(self._check_person_conflicts(person_attributes, stored_attrs))
        else:
            # New person
            self.add_entity(person_id, EntityType.PERSON, person_attributes)
        
        if not doc_exists:
            self.add_entity(doc_id, EntityType.DOCUMENT, document_attributes)
        
        # Link person to document
        self.add_relationship(person_id, doc_id, RelationType.OWNS)
        
        # Biometric analysis
        biometric_conflicts = []
        if biometric_data:
            biometric_conflicts = self._analyze_biometric(
                person_id,
                biometric_data,
                person_attributes
            )
            conflicts.extend(biometric_conflicts)
        
        # Pattern detection
        patterns = self._detect_suspicious_patterns(person_id, doc_id)
        suspicious_patterns.extend(patterns)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(conflicts, suspicious_patterns)
        
        # Get related entities
        related = self._get_related_entities(person_id, max_depth=2)
        
        # Generate findings
        if conflicts:
            findings.append(f"Found {len(conflicts)} data conflicts with historical records")
        if suspicious_patterns:
            findings.append(f"Detected {len(suspicious_patterns)} suspicious patterns")
        if not conflicts and not suspicious_patterns:
            findings.append("No conflicts or suspicious patterns detected")
        
        return IdentityGraphResult(
            risk_score=risk_score,
            confidence=0.8 if conflicts or suspicious_patterns else 0.6,
            findings=findings,
            conflicts=conflicts,
            entity_id=person_id,
            related_entities=related,
            suspicious_patterns=suspicious_patterns
        )
    
    def _generate_person_id(self, attributes: Dict[str, Any]) -> str:
        """Generate deterministic person ID"""
        name = attributes.get("full_name", "").upper().strip()
        dob = attributes.get("date_of_birth", "").strip()
        nationality = attributes.get("nationality", "").strip()
        
        return f"PERSON_{name}_{dob}_{nationality}".replace(" ", "_")
    
    def _check_person_conflicts(
        self,
        current_attrs: Dict[str, Any],
        stored_attrs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for conflicts between current and stored person data"""
        conflicts = []
        
        # Check critical fields
        check_fields = ["date_of_birth", "nationality", "sex"]
        
        for field in check_fields:
            current_val = current_attrs.get(field)
            stored_val = stored_attrs.get(field)
            
            if current_val and stored_val and current_val != stored_val:
                conflicts.append({
                    "field": field,
                    "current_value": current_val,
                    "stored_value": stored_val,
                    "severity": "HIGH" if field == "date_of_birth" else "MEDIUM"
                })
        
        return conflicts
    
    def _analyze_biometric(
        self,
        person_id: str,
        biometric_data: Dict[str, Any],
        person_attributes: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze biometric against graph"""
        conflicts = []
        
        # Generate biometric ID (hash of embedding)
        bio_hash = biometric_data.get("hash", biometric_data.get("embedding_hash", "UNKNOWN"))
        bio_id = f"BIO_{bio_hash}"
        
        # Check if biometric exists
        if self.graph.has_node(bio_id):
            # Biometric seen before - who did it belong to?
            # Find all people connected to this biometric
            predecessors = list(self.graph.predecessors(bio_id))
            
            for pred_id in predecessors:
                if pred_id == person_id:
                    continue  # Same person, OK
                
                pred_attrs = self.graph.nodes[pred_id]
                
                # Same biometric, different person - MAJOR RED FLAG
                conflicts.append({
                    "field": "biometric",
                    "current_person": person_attributes.get("full_name"),
                    "previous_person": pred_attrs.get("full_name"),
                    "current_dob": person_attributes.get("date_of_birth"),
                    "previous_dob": pred_attrs.get("date_of_birth"),
                    "severity": "CRITICAL"
                })
        else:
            # New biometric
            self.add_entity(bio_id, EntityType.BIOMETRIC, {"hash": bio_hash})
        
        # Link person to biometric
        self.add_relationship(person_id, bio_id, RelationType.HAS_BIOMETRIC)
        
        return conflicts
    
    def _detect_suspicious_patterns(
        self,
        person_id: str,
        doc_id: str
    ) -> List[str]:
        """Detect suspicious patterns in graph"""
        patterns = []
        
        # Pattern 1: Multiple documents for same person in short time
        if self.graph.has_node(person_id):
            # Get all documents owned by this person
            successors = list(self.graph.successors(person_id))
            documents = [s for s in successors if self.graph.nodes.get(s, {}).get("type") == "DOCUMENT"]
            
            if len(documents) > 3:
                patterns.append(f"Person has {len(documents)} documents on record (unusual)")
        
        # Pattern 2: Document used after expiry
        if self.graph.has_node(doc_id):
            doc_attrs = self.graph.nodes[doc_id]
            expiry = doc_attrs.get("date_of_expiry")
            
            if expiry:
                try:
                    expiry_date = datetime.fromisoformat(expiry) if isinstance(expiry, str) else expiry
                    if expiry_date < datetime.now():
                        patterns.append("Document used after expiry date")
                except:
                    pass
        
        # Pattern 3: Rapid border crossings (would need crossing data)
        # TODO: Implement when crossing entity is added
        
        return patterns
    
    def _calculate_risk_score(
        self,
        conflicts: List[Dict[str, Any]],
        patterns: List[str]
    ) -> float:
        """Calculate risk score from conflicts and patterns"""
        if not conflicts and not patterns:
            return 0.0
        
        risk = 0.0
        
        # Conflicts contribute heavily
        for conflict in conflicts:
            severity = conflict.get("severity", "LOW")
            if severity == "CRITICAL":
                risk += 0.4
            elif severity == "HIGH":
                risk += 0.25
            elif severity == "MEDIUM":
                risk += 0.15
            else:
                risk += 0.05
        
        # Patterns contribute moderately
        risk += len(patterns) * 0.1
        
        return min(risk, 1.0)
    
    def _get_related_entities(
        self,
        entity_id: str,
        max_depth: int = 2
    ) -> List[str]:
        """Get related entities up to max_depth"""
        if not self.graph.has_node(entity_id):
            return []
        
        related = set()
        
        try:
            # BFS to find related entities
            descendants = self.nx.descendants(self.graph, entity_id)
            ancestors = self.nx.ancestors(self.graph, entity_id)
            
            related.update(descendants)
            related.update(ancestors)
            
            return list(related)[:20]  # Limit to 20
        except:
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        if not self.enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": {
                EntityType.PERSON.value: len([n for n, d in self.graph.nodes(data=True) if d.get("type") == EntityType.PERSON.value]),
                EntityType.DOCUMENT.value: len([n for n, d in self.graph.nodes(data=True) if d.get("type") == EntityType.DOCUMENT.value]),
                EntityType.BIOMETRIC.value: len([n for n, d in self.graph.nodes(data=True) if d.get("type") == EntityType.BIOMETRIC.value]),
            }
        }


def analyze_identity_with_graph(
    full_name: str,
    date_of_birth: str,
    nationality: str,
    document_number: str,
    date_of_expiry: str,
    face_embedding_hash: Optional[str] = None
) -> IdentityGraphResult:
    """
    Convenience function to analyze identity.
    
    Args:
        full_name: Person's full name
        date_of_birth: YYYY-MM-DD
        nationality: ISO 3-letter code
        document_number: Document number
        date_of_expiry: YYYY-MM-DD
        face_embedding_hash: Optional hash of face embedding
    
    Returns:
        IdentityGraphResult
    """
    # Note: In production, this would use a persistent graph (Neo4j, etc.)
    # For now, use in-memory graph
    graph = IdentityGraph()
    
    person_attrs = {
        "full_name": full_name,
        "date_of_birth": date_of_birth,
        "nationality": nationality
    }
    
    doc_attrs = {
        "document_number": document_number,
        "date_of_expiry": date_of_expiry
    }
    
    bio_data = {"hash": face_embedding_hash} if face_embedding_hash else None
    
    return graph.analyze_identity(person_attrs, doc_attrs, bio_data)


if __name__ == "__main__":
    # Demo
    print("Identity Graph - Demo")
    print("="*60)
    
    graph = IdentityGraph()
    
    # First crossing - establish identity
    result1 = graph.analyze_identity(
        person_attributes={
            "full_name": "RAJESH SHARMA",
            "date_of_birth": "1990-05-15",
            "nationality": "IND"
        },
        document_attributes={
            "document_number": "A1234567",
            "date_of_expiry": "2025-12-31"
        },
        biometric_data={"hash": "abc123def456"}
    )
    
    print(f"\nFirst crossing:")
    print(f"Risk Score: {result1.risk_score:.2%}")
    print(f"Findings: {result1.findings}")
    
    # Second crossing - SAME biometric but DIFFERENT DOB (FRAUD!)
    result2 = graph.analyze_identity(
        person_attributes={
            "full_name": "RAJESH KUMAR",  # Slightly different name
            "date_of_birth": "1988-03-20",  # DIFFERENT DOB!
            "nationality": "IND"
        },
        document_attributes={
            "document_number": "B7654321",  # Different document
            "date_of_expiry": "2026-06-30"
        },
        biometric_data={"hash": "abc123def456"}  # SAME biometric!
    )
    
    print(f"\nSecond crossing (same biometric, different DOB):")
    print(f"Risk Score: {result2.risk_score:.2%}")
    print(f"Findings: {result2.findings}")
    print(f"Conflicts: {result2.conflicts}")
    
    print(f"\nGraph Statistics:")
    stats = graph.get_statistics()
    print(json.dumps(stats, indent=2))

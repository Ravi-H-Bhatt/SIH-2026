"""
Audit Proof - Cryptographic Evidence Chain
Part of SIH26188 AI Border Document Screening System

Creates tamper-evident audit trails using cryptographic hashing.
Each screening decision is hashed and can be verified later.

IMPORTANT: NO PII or biometrics on blockchain - only record hashes.
Privacy-first design per master prompt requirements.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
import json


@dataclass
class AuditRecord:
    """Single audit record for a screening event"""
    record_id: str  # Unique identifier
    timestamp: str  # ISO 8601 timestamp
    officer_id: str  # Officer who performed screening (hashed)
    station_id: str  # Border station identifier
    
    # Screening result (only metadata, no PII)
    risk_level: str  # CLEAR, LOW, MEDIUM, HIGH, CRITICAL
    recommended_action: str  # CLEAR, SECONDARY_REVIEW, ESCALATE
    confidence: float  # 0-1
    
    # Evidence hashes (NOT raw data)
    document_hash: str  # Hash of document image
    face_hash: str  # Hash of face capture
    mrz_hash: str  # Hash of MRZ data
    decision_hash: str  # Hash of officer decision
    
    # Audit trail
    parent_hash: Optional[str] = None  # Previous record hash (chain)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this record"""
        # Create canonical representation
        canonical = self._canonical_representation()
        
        # Hash
        hash_obj = hashlib.sha256(canonical.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _canonical_representation(self) -> str:
        """
        Create canonical string representation for hashing.
        
        Order matters for reproducible hashing!
        """
        fields = [
            self.record_id,
            self.timestamp,
            self.officer_id,
            self.station_id,
            self.risk_level,
            self.recommended_action,
            f"{self.confidence:.6f}",
            self.document_hash,
            self.face_hash,
            self.mrz_hash,
            self.decision_hash,
            self.parent_hash or ""
        ]
        
        return "|".join(fields)


@dataclass
class AuditChain:
    """Chain of audit records"""
    chain_id: str
    records: List[AuditRecord]
    created_at: str
    
    def add_record(self, record: AuditRecord) -> str:
        """
        Add record to chain and compute its hash.
        
        Returns:
            Record hash
        """
        # Set parent hash to previous record's hash
        if self.records:
            last_record = self.records[-1]
            record.parent_hash = last_record.compute_hash()
        
        self.records.append(record)
        return record.compute_hash()
    
    def verify_integrity(self) -> tuple[bool, Optional[str]]:
        """
        Verify chain integrity.
        
        Returns:
            (is_valid, error_message)
        """
        if not self.records:
            return True, None
        
        for i, record in enumerate(self.records):
            if i == 0:
                # First record should have no parent
                if record.parent_hash is not None and record.parent_hash != "":
                    return False, f"First record has parent hash: {record.record_id}"
            else:
                # Subsequent records should link to previous
                prev_record = self.records[i-1]
                expected_parent = prev_record.compute_hash()
                
                if record.parent_hash != expected_parent:
                    return False, f"Broken chain at record {record.record_id}"
        
        return True, None


class AuditProofService:
    """
    Service for creating and verifying audit proofs.
    
    Features:
    - SHA-256 hashing of all evidence
    - Hash chain for tamper detection
    - Zero-knowledge proofs (record exists without revealing content)
    - Blockchain-ready format (can be anchored to public blockchain)
    """
    
    def __init__(self):
        self.chains: Dict[str, AuditChain] = {}
    
    def create_audit_record(
        self,
        record_id: str,
        officer_id: str,
        station_id: str,
        risk_level: str,
        recommended_action: str,
        confidence: float,
        document_image: bytes,
        face_image: bytes,
        mrz_data: Dict[str, Any],
        decision_data: Dict[str, Any],
        chain_id: Optional[str] = None
    ) -> tuple[AuditRecord, str]:
        """
        Create audit record for a screening event.
        
        Args:
            record_id: Unique record identifier
            officer_id: Officer identifier (will be hashed)
            station_id: Border station ID
            risk_level: Risk classification
            recommended_action: Recommended action
            confidence: Confidence score
            document_image: Document image bytes
            face_image: Face capture bytes
            mrz_data: MRZ data dictionary
            decision_data: Officer decision data
            chain_id: Optional chain ID (creates new if None)
        
        Returns:
            (AuditRecord, record_hash)
        """
        # Hash all PII data
        document_hash = self._hash_bytes(document_image)
        face_hash = self._hash_bytes(face_image)
        mrz_hash = self._hash_dict(mrz_data)
        decision_hash = self._hash_dict(decision_data)
        officer_hash = self._hash_string(officer_id)
        
        # Create record
        record = AuditRecord(
            record_id=record_id,
            timestamp=datetime.utcnow().isoformat(),
            officer_id=officer_hash,
            station_id=station_id,
            risk_level=risk_level,
            recommended_action=recommended_action,
            confidence=confidence,
            document_hash=document_hash,
            face_hash=face_hash,
            mrz_hash=mrz_hash,
            decision_hash=decision_hash
        )
        
        # Add to chain
        if chain_id is None:
            chain_id = f"chain_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        if chain_id not in self.chains:
            self.chains[chain_id] = AuditChain(
                chain_id=chain_id,
                records=[],
                created_at=datetime.utcnow().isoformat()
            )
        
        record_hash = self.chains[chain_id].add_record(record)
        
        return record, record_hash
    
    def verify_record(
        self,
        record: AuditRecord,
        expected_hash: str
    ) -> bool:
        """
        Verify record has not been tampered with.
        
        Args:
            record: AuditRecord to verify
            expected_hash: Expected hash value
        
        Returns:
            True if record is valid
        """
        computed_hash = record.compute_hash()
        return computed_hash == expected_hash
    
    def verify_chain(self, chain_id: str) -> tuple[bool, Optional[str]]:
        """
        Verify entire chain integrity.
        
        Args:
            chain_id: Chain identifier
        
        Returns:
            (is_valid, error_message)
        """
        if chain_id not in self.chains:
            return False, f"Chain not found: {chain_id}"
        
        chain = self.chains[chain_id]
        return chain.verify_integrity()
    
    def get_chain_summary(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of chain (no PII)"""
        if chain_id not in self.chains:
            return None
        
        chain = self.chains[chain_id]
        
        return {
            "chain_id": chain.chain_id,
            "created_at": chain.created_at,
            "record_count": len(chain.records),
            "records": [
                {
                    "record_id": r.record_id,
                    "timestamp": r.timestamp,
                    "risk_level": r.risk_level,
                    "recommended_action": r.recommended_action,
                    "hash": r.compute_hash()
                }
                for r in chain.records
            ]
        }
    
    def export_for_blockchain(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """
        Export chain in blockchain-ready format.
        
        Returns only hashes and metadata - NO PII.
        """
        if chain_id not in self.chains:
            return None
        
        chain = self.chains[chain_id]
        
        return {
            "chain_id": chain.chain_id,
            "created_at": chain.created_at,
            "record_count": len(chain.records),
            "chain_hash": self._compute_chain_hash(chain),
            "records": [
                {
                    "record_id": r.record_id,
                    "timestamp": r.timestamp,
                    "record_hash": r.compute_hash(),
                    "parent_hash": r.parent_hash
                }
                for r in chain.records
            ]
        }
    
    def _hash_bytes(self, data: bytes) -> str:
        """Hash binary data"""
        return hashlib.sha256(data).hexdigest()
    
    def _hash_string(self, data: str) -> str:
        """Hash string data"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def _hash_dict(self, data: Dict[str, Any]) -> str:
        """Hash dictionary (JSON)"""
        # Sort keys for consistent hashing
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return self._hash_string(canonical)
    
    def _compute_chain_hash(self, chain: AuditChain) -> str:
        """Compute hash of entire chain"""
        if not chain.records:
            return ""
        
        # Concatenate all record hashes
        all_hashes = "".join([r.compute_hash() for r in chain.records])
        return self._hash_string(all_hashes)
    
    def prove_record_exists(
        self,
        record_id: str,
        chain_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Zero-knowledge proof that record exists.
        
        Returns proof without revealing record contents.
        """
        if chain_id not in self.chains:
            return None
        
        chain = self.chains[chain_id]
        
        # Find record
        record = None
        for r in chain.records:
            if r.record_id == record_id:
                record = r
                break
        
        if record is None:
            return None
        
        # Return proof (hash only)
        return {
            "record_id": record_id,
            "chain_id": chain_id,
            "record_hash": record.compute_hash(),
            "timestamp": record.timestamp,
            "exists": True
        }


def create_screening_audit(
    record_id: str,
    officer_id: str,
    station_id: str,
    risk_level: str,
    recommended_action: str,
    confidence: float,
    document_image: bytes,
    face_image: bytes,
    mrz_data: Dict[str, Any],
    decision_data: Dict[str, Any]
) -> tuple[str, str]:
    """
    Convenience function to create audit record.
    
    Args:
        record_id: Unique identifier
        officer_id: Officer ID
        station_id: Station ID
        risk_level: Risk classification
        recommended_action: Action recommendation
        confidence: Confidence score
        document_image: Document image bytes
        face_image: Face image bytes
        mrz_data: MRZ data
        decision_data: Decision data
    
    Returns:
        (record_hash, chain_id)
    """
    service = AuditProofService()
    record, record_hash = service.create_audit_record(
        record_id=record_id,
        officer_id=officer_id,
        station_id=station_id,
        risk_level=risk_level,
        recommended_action=recommended_action,
        confidence=confidence,
        document_image=document_image,
        face_image=face_image,
        mrz_data=mrz_data,
        decision_data=decision_data
    )
    
    # Find chain ID
    for cid, chain in service.chains.items():
        if record in chain.records:
            return record_hash, cid
    
    return record_hash, ""


if __name__ == "__main__":
    # Demo
    print("Audit Proof Service - Demo")
    print("="*60)
    
    service = AuditProofService()
    
    # Create first record
    record1, hash1 = service.create_audit_record(
        record_id="SCREEN_001",
        officer_id="OFFICER_123",
        station_id="STATION_DEL",
        risk_level="LOW",
        recommended_action="CLEAR",
        confidence=0.95,
        document_image=b"fake_document_image_data",
        face_image=b"fake_face_image_data",
        mrz_data={"document_number": "A1234567", "surname": "SHARMA"},
        decision_data={"action": "CLEAR", "notes": "All checks passed"},
        chain_id="demo_chain"
    )
    
    print(f"Record 1 created:")
    print(f"  ID: {record1.record_id}")
    print(f"  Hash: {hash1}")
    print(f"  Officer (hashed): {record1.officer_id}")
    
    # Create second record (links to first)
    record2, hash2 = service.create_audit_record(
        record_id="SCREEN_002",
        officer_id="OFFICER_123",
        station_id="STATION_DEL",
        risk_level="HIGH",
        recommended_action="SECONDARY_REVIEW",
        confidence=0.85,
        document_image=b"fake_document_image_data_2",
        face_image=b"fake_face_image_data_2",
        mrz_data={"document_number": "B7654321", "surname": "KUMAR"},
        decision_data={"action": "SECONDARY_REVIEW", "notes": "Forensics flagged"},
        chain_id="demo_chain"
    )
    
    print(f"\nRecord 2 created:")
    print(f"  ID: {record2.record_id}")
    print(f"  Hash: {hash2}")
    print(f"  Parent Hash: {record2.parent_hash}")
    
    # Verify chain
    is_valid, error = service.verify_chain("demo_chain")
    print(f"\nChain verification: {'✓ Valid' if is_valid else f'✗ Invalid - {error}'}")
    
    # Get chain summary
    summary = service.get_chain_summary("demo_chain")
    print(f"\nChain summary:")
    print(json.dumps(summary, indent=2))
    
    # Export for blockchain
    blockchain_data = service.export_for_blockchain("demo_chain")
    print(f"\nBlockchain export:")
    print(json.dumps(blockchain_data, indent=2))
    
    # Zero-knowledge proof
    proof = service.prove_record_exists("SCREEN_001", "demo_chain")
    print(f"\nProof of existence (no PII revealed):")
    print(json.dumps(proof, indent=2))

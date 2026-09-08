"""
Watchlist Providers - Multiple Source Integration
Part of SIH26188 AI Border Document Screening System

Integrates with multiple watchlist sources:
- Synthetic (always enabled, for demos)
- OpenSanctions (open-source sanctions data)
- INTERPOL (simulated, requires real API in production)

Privacy-first: All results clearly labeled as SIMULATED for demo data.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum


class WatchlistCategory(str, Enum):
    """Watchlist entry categories"""
    TERRORISM = "TERRORISM"
    ORGANIZED_CRIME = "ORGANIZED_CRIME"
    SANCTIONS = "SANCTIONS"
    WANTED = "WANTED"
    MISSING_PERSON = "MISSING_PERSON"
    TRAFFICKING = "TRAFFICKING"
    FRAUD = "FRAUD"
    OTHER = "OTHER"


class MatchConfidence(str, Enum):
    """Match confidence levels"""
    EXACT = "EXACT"  # Exact match on multiple fields
    HIGH = "HIGH"  # Strong match
    MEDIUM = "MEDIUM"  # Possible match
    LOW = "LOW"  # Weak match, needs verification


@dataclass
class WatchlistHit:
    """A watchlist match result"""
    source: str  # "synthetic", "opensanctions", "interpol"
    list_name: str  # Specific list name
    category: WatchlistCategory
    match_confidence: float  # 0-1
    confidence_level: MatchConfidence
    
    # Matched entity details
    name: str
    aliases: List[str]
    date_of_birth: Optional[str]
    nationality: Optional[str]
    document_numbers: List[str]
    
    # Watchlist-specific data
    reason: str  # Why on watchlist
    added_date: Optional[str]
    source_url: Optional[str]
    
    # Match details
    matched_fields: List[str]  # Which fields matched
    is_simulated: bool  # TRUE for demo data
    
    timestamp: str


class AbstractWatchlistProvider(ABC):
    """Abstract base class for watchlist providers"""
    
    @abstractmethod
    def search(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
        face_embedding: Optional[Any] = None
    ) -> List[WatchlistHit]:
        """Search watchlist for matches"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass


class SyntheticWatchlistProvider(AbstractWatchlistProvider):
    """
    Synthetic watchlist provider for demonstrations.
    
    ALWAYS ENABLED and clearly labeled as SIMULATED.
    Used for training, demos, and testing without real PII.
    """
    
    def __init__(self):
        # Synthetic watchlist entries (clearly fake names)
        self.entries = [
            {
                "name": "DEMO TERRORIST ALPHA",
                "aliases": ["ALPHA DEMO", "TEST TERRORIST"],
                "date_of_birth": "1980-01-01",
                "nationality": "XXX",
                "document_numbers": ["DEMO123456"],
                "category": WatchlistCategory.TERRORISM,
                "reason": "SIMULATED - Terrorism watch list entry for demonstration purposes",
                "added_date": "2020-01-01"
            },
            {
                "name": "TEST SANCTIONS BETA",
                "aliases": ["BETA TEST", "SANCTIONS DEMO"],
                "date_of_birth": "1975-06-15",
                "nationality": "YYY",
                "document_numbers": ["TEST789012"],
                "category": WatchlistCategory.SANCTIONS,
                "reason": "SIMULATED - Economic sanctions list entry for demonstration",
                "added_date": "2019-05-20"
            },
            {
                "name": "SAMPLE FRAUD GAMMA",
                "aliases": ["GAMMA SAMPLE", "FRAUD TEST"],
                "date_of_birth": "1990-12-25",
                "nationality": "ZZZ",
                "document_numbers": ["SAMPLE345678"],
                "category": WatchlistCategory.FRAUD,
                "reason": "SIMULATED - Known document fraud patterns for testing",
                "added_date": "2021-03-10"
            },
            {
                "name": "DEMO WANTED DELTA",
                "aliases": ["DELTA DEMO"],
                "date_of_birth": "1985-08-08",
                "nationality": "XXX",
                "document_numbers": ["DEMO999888"],
                "category": WatchlistCategory.WANTED,
                "reason": "SIMULATED - Wanted person entry for demonstration purposes",
                "added_date": "2022-11-01"
            }
        ]
    
    def get_provider_name(self) -> str:
        return "synthetic"
    
    def search(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
        face_embedding: Optional[Any] = None
    ) -> List[WatchlistHit]:
        """Search synthetic watchlist"""
        hits = []
        
        name_upper = full_name.upper().strip()
        
        for entry in self.entries:
            matched_fields = []
            match_score = 0.0
            
            # Name matching (fuzzy)
            entry_name = entry["name"].upper()
            if name_upper in entry_name or entry_name in name_upper:
                matched_fields.append("name")
                match_score += 0.5
            
            # Check aliases
            for alias in entry["aliases"]:
                if name_upper in alias.upper() or alias.upper() in name_upper:
                    matched_fields.append("alias")
                    match_score += 0.3
                    break
            
            # DOB matching
            if date_of_birth and entry["date_of_birth"] == date_of_birth:
                matched_fields.append("date_of_birth")
                match_score += 0.3
            
            # Nationality matching
            if nationality and entry["nationality"] == nationality:
                matched_fields.append("nationality")
                match_score += 0.1
            
            # Document number matching
            if document_number and document_number in entry["document_numbers"]:
                matched_fields.append("document_number")
                match_score += 0.4
            
            # If any match found, create hit
            if matched_fields:
                match_confidence = min(match_score, 1.0)
                
                if match_confidence >= 0.8:
                    confidence_level = MatchConfidence.EXACT
                elif match_confidence >= 0.6:
                    confidence_level = MatchConfidence.HIGH
                elif match_confidence >= 0.4:
                    confidence_level = MatchConfidence.MEDIUM
                else:
                    confidence_level = MatchConfidence.LOW
                
                hits.append(WatchlistHit(
                    source=self.get_provider_name(),
                    list_name="SYNTHETIC_DEMO_LIST",
                    category=entry["category"],
                    match_confidence=match_confidence,
                    confidence_level=confidence_level,
                    name=entry["name"],
                    aliases=entry["aliases"],
                    date_of_birth=entry["date_of_birth"],
                    nationality=entry["nationality"],
                    document_numbers=entry["document_numbers"],
                    reason=entry["reason"],
                    added_date=entry["added_date"],
                    source_url="SIMULATED_DATA",
                    matched_fields=matched_fields,
                    is_simulated=True,
                    timestamp=datetime.utcnow().isoformat()
                ))
        
        return hits


class OpenSanctionsProvider(AbstractWatchlistProvider):
    """
    OpenSanctions provider (open-source sanctions database).
    
    OpenSanctions aggregates sanctions data from multiple sources:
    - UN Security Council
    - EU Sanctions
    - OFAC (US)
    - UK Sanctions
    - And many more
    
    API: https://www.opensanctions.org/docs/api/
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.opensanctions.org/search"
        self.enabled = api_key is not None
    
    def get_provider_name(self) -> str:
        return "opensanctions"
    
    def search(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
        face_embedding: Optional[Any] = None
    ) -> List[WatchlistHit]:
        """Search OpenSanctions database"""
        if not self.enabled:
            return []
        
        try:
            import requests
            
            # Build search query
            params = {
                "q": full_name,
                "limit": 10
            }
            
            if date_of_birth:
                params["birthDate"] = date_of_birth
            
            if nationality:
                params["country"] = nationality
            
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"OpenSanctions API error: {response.status_code}")
                return []
            
            data = response.json()
            hits = []
            
            for result in data.get("results", []):
                # Extract relevant fields
                name = result.get("caption", "Unknown")
                aliases = [a.get("name") for a in result.get("properties", {}).get("alias", [])]
                dob = result.get("properties", {}).get("birthDate", [None])[0]
                countries = result.get("properties", {}).get("country", [])
                nat = countries[0] if countries else None
                
                # Determine category
                topics = result.get("topics", [])
                if "crime.terrorism" in topics:
                    category = WatchlistCategory.TERRORISM
                elif "sanction" in topics:
                    category = WatchlistCategory.SANCTIONS
                elif "crime" in topics:
                    category = WatchlistCategory.ORGANIZED_CRIME
                else:
                    category = WatchlistCategory.OTHER
                
                # Calculate match confidence
                matched_fields = ["name"]  # Name always matches (we searched by it)
                match_score = 0.5
                
                if dob and date_of_birth and dob == date_of_birth:
                    matched_fields.append("date_of_birth")
                    match_score += 0.3
                
                if nat and nationality and nat == nationality:
                    matched_fields.append("nationality")
                    match_score += 0.2
                
                match_confidence = min(match_score, 1.0)
                
                if match_confidence >= 0.8:
                    confidence_level = MatchConfidence.EXACT
                elif match_confidence >= 0.6:
                    confidence_level = MatchConfidence.HIGH
                elif match_confidence >= 0.4:
                    confidence_level = MatchConfidence.MEDIUM
                else:
                    confidence_level = MatchConfidence.LOW
                
                hits.append(WatchlistHit(
                    source=self.get_provider_name(),
                    list_name=result.get("dataset", "Unknown"),
                    category=category,
                    match_confidence=match_confidence,
                    confidence_level=confidence_level,
                    name=name,
                    aliases=aliases,
                    date_of_birth=dob,
                    nationality=nat,
                    document_numbers=[],
                    reason=f"Sanctioned: {', '.join(topics)}",
                    added_date=None,
                    source_url=result.get("url"),
                    matched_fields=matched_fields,
                    is_simulated=False,
                    timestamp=datetime.utcnow().isoformat()
                ))
            
            return hits
        
        except Exception as e:
            print(f"OpenSanctions search error: {e}")
            return []


class INTERPOLProvider(AbstractWatchlistProvider):
    """
    INTERPOL watchlist provider (SIMULATED).
    
    In production, this would integrate with INTERPOL's I-24/7 system.
    For this demo, we simulate INTERPOL responses.
    
    Real integration requires:
    - Authorized access to INTERPOL network
    - National Central Bureau (NCB) credentials
    - Secure communication channels
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.enabled = False  # Always simulated in this implementation
    
    def get_provider_name(self) -> str:
        return "interpol"
    
    def search(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
        face_embedding: Optional[Any] = None
    ) -> List[WatchlistHit]:
        """Search INTERPOL database (SIMULATED)"""
        # In a real implementation, this would query INTERPOL's I-24/7
        # For now, return empty (or simulated test data)
        
        # Simulated: If name contains "INTERPOL", create a demo hit
        if "INTERPOL" in full_name.upper():
            return [
                WatchlistHit(
                    source=self.get_provider_name(),
                    list_name="RED_NOTICE_SIMULATED",
                    category=WatchlistCategory.WANTED,
                    match_confidence=0.85,
                    confidence_level=MatchConfidence.HIGH,
                    name=full_name,
                    aliases=[],
                    date_of_birth=date_of_birth,
                    nationality=nationality,
                    document_numbers=[document_number] if document_number else [],
                    reason="SIMULATED - INTERPOL Red Notice (demonstration only)",
                    added_date="2023-01-01",
                    source_url="SIMULATED_INTERPOL",
                    matched_fields=["name"],
                    is_simulated=True,
                    timestamp=datetime.utcnow().isoformat()
                )
            ]
        
        return []


class WatchlistService:
    """
    Unified watchlist service that queries multiple providers.
    """
    
    def __init__(
        self,
        opensanctions_api_key: Optional[str] = None,
        interpol_api_key: Optional[str] = None
    ):
        """
        Initialize watchlist service with multiple providers.
        
        Args:
            opensanctions_api_key: Optional OpenSanctions API key
            interpol_api_key: Optional INTERPOL API key
        """
        self.providers: List[AbstractWatchlistProvider] = []
        
        # Always add synthetic provider (for demos)
        self.providers.append(SyntheticWatchlistProvider())
        
        # Add OpenSanctions if API key provided
        if opensanctions_api_key:
            self.providers.append(OpenSanctionsProvider(opensanctions_api_key))
        
        # Add INTERPOL if API key provided (currently always simulated)
        if interpol_api_key:
            self.providers.append(INTERPOLProvider(interpol_api_key))
    
    def search_all(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
        face_embedding: Optional[Any] = None
    ) -> List[WatchlistHit]:
        """
        Search all configured watchlist providers.
        
        Args:
            full_name: Person's full name
            date_of_birth: YYYY-MM-DD format
            nationality: ISO 3-letter country code
            document_number: Document/passport number
            face_embedding: Optional face embedding for biometric match
        
        Returns:
            List of all watchlist hits across providers
        """
        all_hits = []
        
        for provider in self.providers:
            try:
                hits = provider.search(
                    full_name=full_name,
                    date_of_birth=date_of_birth,
                    nationality=nationality,
                    document_number=document_number,
                    face_embedding=face_embedding
                )
                all_hits.extend(hits)
            except Exception as e:
                print(f"Error querying {provider.get_provider_name()}: {e}")
        
        # Sort by match confidence (highest first)
        all_hits.sort(key=lambda h: h.match_confidence, reverse=True)
        
        return all_hits
    
    def get_active_providers(self) -> List[str]:
        """Get list of active provider names"""
        return [p.get_provider_name() for p in self.providers]


def search_watchlists(
    full_name: str,
    date_of_birth: Optional[str] = None,
    nationality: Optional[str] = None,
    document_number: Optional[str] = None
) -> List[WatchlistHit]:
    """
    Convenience function to search watchlists.
    
    Args:
        full_name: Person's full name
        date_of_birth: YYYY-MM-DD
        nationality: ISO 3-letter code
        document_number: Document number
    
    Returns:
        List of watchlist hits
    """
    service = WatchlistService()
    return service.search_all(full_name, date_of_birth, nationality, document_number)


if __name__ == "__main__":
    # Demo
    print("Watchlist Service - Demo")
    print("="*60)
    
    service = WatchlistService()
    print(f"Active providers: {service.get_active_providers()}\n")
    
    # Test 1: No match
    print("Test 1: Clean traveler (no match expected)")
    hits = service.search_all(
        full_name="RAJESH SHARMA",
        date_of_birth="1990-05-15",
        nationality="IND",
        document_number="A1234567"
    )
    print(f"Hits: {len(hits)}\n")
    
    # Test 2: Synthetic match
    print("Test 2: Synthetic watchlist match")
    hits = service.search_all(
        full_name="DEMO TERRORIST ALPHA",
        date_of_birth="1980-01-01",
        nationality="XXX",
        document_number="DEMO123456"
    )
    print(f"Hits: {len(hits)}")
    for hit in hits:
        print(f"  • [{hit.source}] {hit.name}")
        print(f"    Confidence: {hit.match_confidence:.2%} ({hit.confidence_level})")
        print(f"    Category: {hit.category}")
        print(f"    Reason: {hit.reason}")
        print(f"    Simulated: {hit.is_simulated}")

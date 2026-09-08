"""
Watchlist & Interpol Cross-Check Service.

Checks traveler document numbers and names against border alerts, Interpol SLTD, and watchlist databases.
NOW INCLUDES CRIMINAL/THIEF DETECTION.
"""

from typing import Dict, Any, List, Optional


# Mock Interpol / High Risk Watchlist Database for demonstration & border checks
# EXPANDED WITH CRIMINAL/THIEF CATEGORIES
KNOWN_WATCHLIST_ENTRIES = [
    {
        "document_number": "P99999999",
        "holder_name": "BAD ACTOR",
        "reason": "INTERPOL Red Notice — Document reported stolen / suspected fraud",
        "category": "INTERPOL_SLTD",
        "severity": "critical",
        "is_criminal": True,
        "crime_type": "Document Fraud"
    },
    {
        "document_number": "P88888888",
        "holder_name": "WANTED PERSON",
        "reason": "Immigration Alert — Entry restriction active",
        "category": "IMMIGRATION_ALERT",
        "severity": "high",
        "is_criminal": True,
        "crime_type": "Immigration Violation"
    },
    {
        "document_number": "A11111111",
        "holder_name": "JOHN THIEF",
        "reason": "🚨 WANTED FOR THEFT — Multiple theft cases registered",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "critical",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Theft, Burglary"
    },
    {
        "document_number": "B22222222",
        "holder_name": "JANE ROBBER",
        "reason": "🚨 WANTED FOR ARMED ROBBERY — Dangerous criminal",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "critical",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Armed Robbery"
    },
    {
        "document_number": "C33333333",
        "holder_name": "FRAUDSTER SMITH",
        "reason": "🚨 WANTED FOR FRAUD — Identity theft and financial fraud",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "high",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Fraud, Identity Theft"
    },
    {
        "document_number": "D44444444",
        "holder_name": "STOLEN DOC HOLDER",
        "reason": "⚠️ Using stolen/forged documents",
        "category": "DOCUMENT_FRAUD",
        "severity": "high",
        "is_criminal": True,
        "crime_type": "Document Forgery"
    }
]


class WatchlistService:
    def check_watchlist(
        self,
        document_number: Optional[str],
        holder_name: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks document number and traveler name against watchlist databases.
        Returns hits with criminal/thief flags.
        """
        hits = []

        if not document_number and not holder_name:
            return hits

        clean_doc_num = (document_number or "").upper().strip()
        clean_name = (holder_name or "").upper().strip()

        for entry in KNOWN_WATCHLIST_ENTRIES:
            match = False

            # Exact document number match
            if clean_doc_num and entry["document_number"] == clean_doc_num:
                match = True
            
            # Name match (partial or full)
            elif clean_name and entry["holder_name"] in clean_name:
                match = True
            
            # Reverse name match (handle name variations)
            elif clean_name:
                name_parts = clean_name.split()
                entry_parts = entry["holder_name"].split()
                if any(part in entry_parts for part in name_parts if len(part) > 3):
                    match = True

            if match:
                hit = {
                    "name": entry["holder_name"],
                    "document_number": entry["document_number"],
                    "reason": entry["reason"],
                    "category": entry["category"],
                    "severity": entry["severity"],
                    "confidence": 0.98,
                    "is_criminal": entry.get("is_criminal", False),
                    "is_thief": entry.get("is_thief", False),
                    "crime_type": entry.get("crime_type", "Unknown"),
                    "alert_level": "🚨 CRIMINAL" if entry.get("is_criminal") else "⚠️ ALERT"
                }
                
                # Add special flag for thieves
                if entry.get("is_thief"):
                    hit["display_label"] = "🚨 THIEF/CRIMINAL"
                    hit["action_required"] = "DETAIN AND NOTIFY AUTHORITIES IMMEDIATELY"
                elif entry.get("is_criminal"):
                    hit["display_label"] = "🚨 CRIMINAL"
                    hit["action_required"] = "SECONDARY INSPECTION REQUIRED"
                else:
                    hit["display_label"] = "⚠️ WATCHLIST HIT"
                    hit["action_required"] = "VERIFY AND ESCALATE"
                
                hits.append(hit)

        return hits

    def is_known_criminal(
        self,
        document_number: Optional[str],
        holder_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Quick check if person is a known criminal/thief.
        Returns boolean flag with details.
        """
        hits = self.check_watchlist(document_number, holder_name)
        
        if not hits:
            return {
                "is_criminal": False,
                "is_thief": False,
                "alert": None
            }
        
        # Check if any hit is criminal/thief
        is_criminal = any(h.get("is_criminal", False) for h in hits)
        is_thief = any(h.get("is_thief", False) for h in hits)
        
        most_severe = max(hits, key=lambda h: 
            3 if h.get("severity") == "critical" else 
            2 if h.get("severity") == "high" else 1
        )
        
        return {
            "is_criminal": is_criminal,
            "is_thief": is_thief,
            "alert": most_severe.get("display_label"),
            "reason": most_severe.get("reason"),
            "action_required": most_severe.get("action_required"),
            "crime_type": most_severe.get("crime_type")
        }


watchlist_service = WatchlistService()

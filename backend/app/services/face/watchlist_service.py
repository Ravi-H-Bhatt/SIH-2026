"""
Watchlist & sanctions screening.

Two independent sources, always reported separately so an officer can see where
a hit came from and how much weight it carries:

  1. LOCAL  — a small synthetic list used for demos and offline development.
              Clearly labelled SIMULATED. Never presented as authoritative.
  2. OPENSANCTIONS — live query against api.opensanctions.org, covering
              sanctions designations, PEPs, INTERPOL notices and crime lists.
              Results are marked `verified=False`: an entity match on name and
              date of birth is a *lead* requiring adjudication, not proof of
              identity. Nothing here should auto-detain on its own.

Matching notes
--------------
The previous implementation flagged a traveller if ANY name token longer than
three characters appeared anywhere in a watchlist entry. "JOHN SMITH" therefore
matched "JOHN THIEF" and was reported as wanted for theft. For Gulf names, where
almost every record contains "AL", it would have matched nearly everything.

Matching now requires one of:
  * an exact normalised document-number match (strong identifier), or
  * a full-name similarity above MIN_NAME_SIMILARITY where the *surname* also
    matches, so a shared given name alone can never trigger a hit.
"""

from __future__ import annotations

import json
import logging
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tokens that carry no identifying power in a name comparison.
NAME_STOPWORDS = {
    "AL", "EL", "BIN", "IBN", "BINT", "ABU", "UM", "DE", "DA", "DI", "DU",
    "VAN", "VON", "DER", "DEN", "LA", "LE", "MC", "MAC", "SAN", "SANTA",
    "MR", "MRS", "MS", "DR", "SIR", "JR", "SR",
}

# Full-name similarity required before a name-only hit is reported.
MIN_NAME_SIMILARITY = 0.86

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CONTEXT = ssl.create_default_context()


# ---------------------------------------------------------------------------
# Local synthetic list — demo only
# ---------------------------------------------------------------------------
KNOWN_WATCHLIST_ENTRIES: List[Dict[str, Any]] = [
    {
        "document_number": "P99999999",
        "holder_name": "BAD ACTOR",
        "reason": "INTERPOL Red Notice — document reported stolen / suspected fraud",
        "category": "INTERPOL_SLTD",
        "severity": "critical",
        "is_criminal": True,
        "crime_type": "Document Fraud",
    },
    {
        "document_number": "P88888888",
        "holder_name": "WANTED PERSON",
        "reason": "Immigration alert — entry restriction active",
        "category": "IMMIGRATION_ALERT",
        "severity": "high",
        "is_criminal": True,
        "crime_type": "Immigration Violation",
    },
    {
        "document_number": "A11111111",
        "holder_name": "JOHN THIEF",
        "reason": "Wanted for theft — multiple burglary cases registered",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "critical",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Theft, Burglary",
    },
    {
        "document_number": "B22222222",
        "holder_name": "JANE ROBBER",
        "reason": "Wanted for armed robbery",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "critical",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Armed Robbery",
    },
    {
        "document_number": "C33333333",
        "holder_name": "FRAUDSTER SMITH",
        "reason": "Wanted for fraud — identity theft and financial fraud",
        "category": "CRIMINAL_WATCHLIST",
        "severity": "high",
        "is_criminal": True,
        "is_thief": True,
        "crime_type": "Fraud, Identity Theft",
    },
    {
        "document_number": "D44444444",
        "holder_name": "STOLEN DOC HOLDER",
        "reason": "Presenting stolen or forged travel documents",
        "category": "DOCUMENT_FRAUD",
        "severity": "high",
        "is_criminal": True,
        "crime_type": "Document Forgery",
    },
    # ── International / sanctions-style synthetic entries ────────────────────
    {
        "document_number": "Z43R34255",
        "holder_name": "AHMAD AL FARSI",
        "reason": "Subject of an international narcotics trafficking investigation",
        "category": "INTERNATIONAL_CRIME",
        "severity": "critical",
        "is_criminal": True,
        "crime_type": "Narcotics Trafficking",
    },
    {
        "document_number": "Z54R76423",
        "holder_name": "LAYLA AL MANSOURI",
        "reason": "Financial sanctions designation — terrorism financing",
        "category": "SANCTIONS",
        "severity": "critical",
        "is_criminal": True,
        "crime_type": "Terrorism Financing",
    },
    {
        "document_number": "P90S12345",
        "holder_name": "HUDA AL BINNASSER",
        "reason": "Human trafficking network — INTERPOL Blue Notice (locate/identify)",
        "category": "INTERPOL_NOTICE",
        "severity": "high",
        "is_criminal": True,
        "crime_type": "Human Trafficking",
    },
]


# ---------------------------------------------------------------------------
# Name normalisation & comparison
# ---------------------------------------------------------------------------

def normalize_name(name: Optional[str]) -> str:
    """Upper-case, strip accents and punctuation, collapse whitespace."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in ascii_only)
    return " ".join(cleaned.upper().split())


def name_tokens(name: Optional[str]) -> List[str]:
    """Identifying tokens only — nobility/patronymic particles removed."""
    return [
        t for t in normalize_name(name).split()
        if len(t) > 1 and t not in NAME_STOPWORDS
    ]


def normalize_doc_number(value: Optional[str]) -> str:
    """Document numbers compare without separators or case."""
    if not value:
        return ""
    return "".join(c for c in value.upper() if c.isalnum())


def name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    0.0-1.0 similarity over identifying tokens.

    Uses a token-set comparison so word order does not matter, combined with a
    character-level ratio to tolerate OCR noise.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0

    set_a, set_b = set(ta), set(tb)
    overlap = len(set_a & set_b) / max(len(set_a), len(set_b))
    sequence = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round((overlap * 0.6) + (sequence * 0.4), 4)


def surnames_match(a: Optional[str], b: Optional[str]) -> bool:
    """
    True when the two names share a surname-like token.

    Requiring this is what stops a shared given name from producing a hit: the
    old matcher accepted "JOHN" alone, so JOHN SMITH matched JOHN THIEF.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    # Compare the last two tokens of each: naming order varies by convention.
    tail_a, tail_b = set(ta[-2:]), set(tb[-2:])
    if tail_a & tail_b:
        return True
    # Allow one transcription error in the final token.
    return SequenceMatcher(None, ta[-1], tb[-1]).ratio() >= 0.9


# ---------------------------------------------------------------------------
# OpenSanctions
# ---------------------------------------------------------------------------

class OpenSanctionsClient:
    """
    Minimal OpenSanctions REST client (stdlib only).

    Uses the /match endpoint, which is designed for exactly this: submit the
    properties you hold and receive scored candidate entities back.
    """

    def __init__(self) -> None:
        self._base = (settings.OPENSANCTIONS_API_URL or "https://api.opensanctions.org").rstrip("/")
        self._key = settings.OPENSANCTIONS_API_KEY or ""
        self._dataset = settings.OPENSANCTIONS_DATASET or "default"
        self._timeout = settings.OPENSANCTIONS_TIMEOUT_SECONDS
        self._threshold = settings.OPENSANCTIONS_MATCH_THRESHOLD

    @property
    def enabled(self) -> bool:
        return bool(settings.OPENSANCTIONS_ENABLED and self._key)

    def match(
        self,
        *,
        name: Optional[str],
        birth_date: Optional[str] = None,
        nationality: Optional[str] = None,
        document_number: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns normalised hits, or [] when disabled/unavailable."""
        if not self.enabled or not (name or document_number):
            return []

        props: Dict[str, List[str]] = {}
        if name:
            props["name"] = [name]
        if birth_date:
            props["birthDate"] = [birth_date]
        if nationality:
            props["nationality"] = [nationality]
        if document_number:
            props["idNumber"] = [document_number]

        payload = json.dumps({
            "queries": {
                "traveller": {"schema": "Person", "properties": props}
            }
        }).encode()

        url = f"{self._base}/match/{urllib.parse.quote(self._dataset)}?algorithm=logic-v1"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"ApiKey {self._key}",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout, context=_SSL_CONTEXT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            logger.warning("[OpenSanctions] HTTP %s: %s", exc.code, detail)
            return []
        except Exception as exc:  # noqa: BLE001 - screening must never break a scan
            logger.warning("[OpenSanctions] unavailable: %s", exc)
            return []

        results = (body.get("responses", {}).get("traveller", {}) or {}).get("results", [])
        hits: List[Dict[str, Any]] = []

        for entity in results:
            score = float(entity.get("score") or 0.0)
            if score < self._threshold:
                continue
            props_out = entity.get("properties", {}) or {}
            topics = props_out.get("topics", []) or []
            hits.append(self._normalize(entity, score, props_out, topics))

        return hits

    @staticmethod
    def _normalize(entity, score, props, topics) -> Dict[str, Any]:
        """Map an OpenSanctions entity onto our hit shape."""
        # Topic codes carry the meaning: sanction, crime.terror, role.pep, ...
        topic_str = ", ".join(topics)
        is_sanctioned = any(t.startswith("sanction") for t in topics)
        is_terror = any("terror" in t for t in topics)
        is_crime = any(t.startswith("crime") for t in topics)
        is_pep = any(t.startswith("role.pep") for t in topics)

        if is_terror:
            severity, label = "critical", "TERRORISM LISTING"
        elif is_sanctioned:
            severity, label = "critical", "SANCTIONS DESIGNATION"
        elif is_crime:
            severity, label = "high", "INTERNATIONAL CRIME LISTING"
        elif is_pep:
            severity, label = "medium", "POLITICALLY EXPOSED PERSON"
        else:
            severity, label = "medium", "WATCHLIST ENTITY"

        datasets = entity.get("datasets", []) or []
        countries = props.get("country", []) or []

        return {
            "name": entity.get("caption") or "UNKNOWN ENTITY",
            "document_number": (props.get("idNumber") or [None])[0],
            "reason": (
                f"OpenSanctions match ({score:.0%} confidence) — topics: "
                f"{topic_str or 'unclassified'}; sources: {', '.join(datasets[:3]) or 'n/a'}"
            ),
            "category": "OPENSANCTIONS",
            "severity": severity,
            "confidence": round(score, 4),
            "source": "opensanctions",
            # An entity match is a lead for adjudication, not identity proof.
            "verified": False,
            "is_criminal": is_crime or is_terror or is_sanctioned,
            "is_thief": False,
            "crime_type": topic_str or "Unclassified",
            "alert_level": f"⚠️ {label} (UNVERIFIED)",
            "display_label": f"{label} — UNVERIFIED LEAD",
            "action_required": "Adjudicate against the listing before any decision",
            "entity_id": entity.get("id"),
            "datasets": datasets,
            "countries": countries,
            "topics": topics,
        }


opensanctions_client = OpenSanctionsClient()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class WatchlistService:
    def check_watchlist(
        self,
        document_number: Optional[str],
        holder_name: Optional[str],
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Screen a traveller against the local list and OpenSanctions.

        Returns one dict per hit. Each carries `source`, `verified` and
        `match_basis` so the UI can distinguish a hard document-number match
        from a probabilistic name lead.
        """
        hits: List[Dict[str, Any]] = []
        if not document_number and not holder_name:
            return hits

        hits.extend(self._check_local(document_number, holder_name))

        if settings.SYNTHETIC_WATCHLIST_ENABLED is False:
            hits = [h for h in hits if h.get("source") != "local_synthetic"]

        try:
            hits.extend(
                opensanctions_client.match(
                    name=holder_name,
                    birth_date=date_of_birth,
                    nationality=nationality,
                    document_number=document_number,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Watchlist] OpenSanctions step skipped: %s", exc)

        return hits

    # ── local list ──────────────────────────────────────────────────────────
    def _check_local(
        self, document_number: Optional[str], holder_name: Optional[str]
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        doc = normalize_doc_number(document_number)

        for entry in KNOWN_WATCHLIST_ENTRIES:
            match_basis = None
            confidence = 0.0

            if doc and normalize_doc_number(entry["document_number"]) == doc:
                match_basis, confidence = "document_number", 1.0
            else:
                similarity = name_similarity(holder_name, entry["holder_name"])
                # Both conditions required. Similarity alone is not enough —
                # a shared given name must never produce a hit.
                if similarity >= MIN_NAME_SIMILARITY and surnames_match(
                    holder_name, entry["holder_name"]
                ):
                    match_basis, confidence = "name_similarity", similarity

            if not match_basis:
                continue

            is_thief = entry.get("is_thief", False)
            is_criminal = entry.get("is_criminal", False)
            if is_thief:
                label = "CRIMINAL — WANTED"
                action = "Detain and notify authorities"
            elif is_criminal:
                label = "CRIMINAL RECORD"
                action = "Secondary inspection required"
            else:
                label = "WATCHLIST HIT"
                action = "Verify and escalate"

            hits.append({
                "name": entry["holder_name"],
                "document_number": entry["document_number"],
                "reason": f"SIMULATED — {entry['reason']}",
                "category": entry["category"],
                "severity": entry["severity"],
                "confidence": round(confidence, 4),
                "source": "local_synthetic",
                # Document-number equality is a hard identifier; a name is not.
                "verified": match_basis == "document_number",
                "match_basis": match_basis,
                "is_criminal": is_criminal,
                "is_thief": is_thief,
                "crime_type": entry.get("crime_type", "Unknown"),
                "alert_level": f"🚨 {label}" if is_criminal else f"⚠️ {label}",
                "display_label": label,
                "action_required": action,
            })

        return hits

    # ── convenience summary ─────────────────────────────────────────────────
    def is_known_criminal(
        self,
        document_number: Optional[str],
        holder_name: Optional[str],
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Condensed verdict for the pipeline.

        `requires_adjudication` is True when the only evidence is an unverified
        probabilistic match. The pipeline uses it to route to secondary review
        rather than auto-detaining on a name collision.
        """
        hits = self.check_watchlist(document_number, holder_name, date_of_birth, nationality)
        if not hits:
            return {
                "is_criminal": False,
                "is_thief": False,
                "alert": None,
                "hit_count": 0,
                "requires_adjudication": False,
            }

        verified = [h for h in hits if h.get("verified")]
        criminal_hits = [h for h in hits if h.get("is_criminal")]

        severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        most_severe = max(hits, key=lambda h: severity_rank.get(h.get("severity", "low"), 0))

        return {
            # Only a verified (document-number) criminal hit asserts criminality
            # outright. Everything else is a lead.
            "is_criminal": any(h.get("is_criminal") for h in verified),
            "is_thief": any(h.get("is_thief") for h in verified),
            "alert": most_severe.get("display_label"),
            "reason": most_severe.get("reason"),
            "action_required": most_severe.get("action_required"),
            "crime_type": most_severe.get("crime_type"),
            # Severity of the worst listing. The pipeline escalates on this: a
            # critical designation (terrorism, sanctions) holds the traveller,
            # whereas a PEP note only routes to review. Without it every
            # unverified lead was treated identically.
            "severity": most_severe.get("severity", "high"),
            "topics": most_severe.get("topics", []),
            "hit_count": len(hits),
            "verified_hit_count": len(verified),
            "sources": sorted({h.get("source", "unknown") for h in hits}),
            "requires_adjudication": bool(criminal_hits) and not verified,
        }


watchlist_service = WatchlistService()

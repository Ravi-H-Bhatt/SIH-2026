"""
Identity & Document Fraud Intelligence Graph.

Performs a 1:N biometric search of the current encounter against prior
encounters, then reasons about what a match *means*:

  - same face, different name       -> possible synthetic identity hopping
  - same face, different document   -> multi-document holder
  - same face, same identity        -> ordinary repeat crossing

Correctness rules
-----------------
1. Similarity is the raw cosine between two 128-d SFace embeddings. It is not
   rescaled. The previous implementation used `(cos + 1) / 2`, which maps
   orthogonal vectors — meaning no relationship at all — to 0.50, and made the
   0.62 threshold equivalent to a raw cosine of only 0.24.

2. Embeddings of differing length are NOT compared. They are counted and
   reported. The previous implementation truncated both to the shorter length,
   which compared genuine 128-d SFace features against 512-d synthetic seed
   ramps and against 16x16 raw-pixel fallback vectors.

3. The 1:N threshold is at least as strict as the 1:1 threshold, because false
   match probability grows with gallery size.

4. An anomaly is only raised between two *resolved* identities. Comparing a
   real name against an OCR placeholder like "TRAVELER" is a failed read, not
   identity hopping, and previously produced a CRITICAL alert on every scan
   whose OCR had failed.
"""

import uuid
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from app.models.extracted_data import ExtractedData
from app.models.face_result import FaceResult
from app.models.scan import ScanRecord
from app.services.face.face_service import (
    SFACE_DIM,
    _effective_1toN_threshold,
    cosine_similarity,
)

# Values the OCR layer emits when a field could not be read. These are not
# identities and must never take part in a name/document contradiction.
PLACEHOLDER_IDENTITIES = {
    "", "TRAVELER", "TRAVELLER", "UNKNOWN", "NOT_DETECTED", "UNREADABLE NAME",
    "UNKNOWN_PAST_NAME", "CURRENT_TRAVELER", "JOHN DOE", "N/A", "NONE",
}

MAX_GALLERY = 500


def _is_resolved(value: Optional[str]) -> bool:
    """True when a field holds a real, usable identity value."""
    if not value:
        return False
    cleaned = str(value).strip().upper()
    if cleaned in PLACEHOLDER_IDENTITIES:
        return False
    return len(cleaned) >= 2


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip().upper()


class IdentityGraphService:
    def evaluate_identity_continuity(
        self,
        current_scan_id: str,
        current_face_embedding: Optional[List[float]],
        current_document_number: Optional[str],
        current_holder_name: Optional[str],
        current_dob: Optional[str],
        db: Session,
    ) -> Dict[str, Any]:
        graph = nx.Graph()
        anomalies: List[Dict[str, Any]] = []
        continuity_links: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        threshold = _effective_1toN_threshold()

        name_resolved = _is_resolved(current_holder_name)
        doc_resolved = _is_resolved(current_document_number)

        curr_person_id = current_holder_name if name_resolved else "CURRENT_TRAVELER"
        curr_doc_id = current_document_number if doc_resolved else "UNKNOWN_DOC"

        graph.add_node(curr_person_id, type="person", label=curr_person_id, is_current=True)
        graph.add_node(curr_doc_id, type="document", label=f"Document {curr_doc_id}", is_current=True)
        graph.add_edge(curr_person_id, curr_doc_id, relation="presented_document")

        def payload(reason: Optional[str] = None) -> Dict[str, Any]:
            return self._build_graph_payload(
                graph, anomalies, continuity_links, threshold, skipped, reason
            )

        # No usable biometric means no 1:N search. Returning early with an
        # explicit reason is important: an empty result must be distinguishable
        # from "searched and found nothing clean".
        if not current_face_embedding:
            return payload("No biometric embedding available — 1:N search not performed")

        if len(current_face_embedding) != SFACE_DIM:
            return payload(
                f"Embedding dimensionality {len(current_face_embedding)} is not the "
                f"expected {SFACE_DIM} — 1:N search not performed"
            )

        target_uuid: Any = current_scan_id
        if isinstance(current_scan_id, str):
            try:
                target_uuid = uuid.UUID(current_scan_id)
            except (ValueError, AttributeError, TypeError):
                target_uuid = current_scan_id

        past_scans = (
            db.query(ScanRecord)
            .join(FaceResult, ScanRecord.id == FaceResult.scan_id)
            .filter(ScanRecord.id != target_uuid)
            .order_by(ScanRecord.created_at.desc())
            .limit(MAX_GALLERY)
            .all()
        )

        for past in past_scans:
            face_res = past.face_result
            if not face_res or not face_res.face_embedding:
                continue

            past_emb = face_res.face_embedding
            cos = cosine_similarity(current_face_embedding, past_emb)

            if cos is None:
                # Wrong length, zero vector, or otherwise incomparable. Recorded
                # so a stale/synthetic gallery is visible rather than silently
                # producing matches.
                skipped.append({
                    "scan_id": str(past.id),
                    "stored_dimension": len(past_emb) if past_emb else 0,
                    "expected_dimension": SFACE_DIM,
                })
                continue

            if cos < threshold:
                continue

            past_fields = (past.extracted_data.fields or {}) if past.extracted_data else {}
            past_doc_num = past_fields.get("document_number") or f"SCAN_{str(past.id)[:8]}"
            past_name = past_fields.get("holder_name") or "UNKNOWN_PAST_NAME"
            past_dob = past_fields.get("date_of_birth")
            past_date = past.created_at.strftime("%d %b %Y") if past.created_at else "Unknown date"

            past_name_resolved = _is_resolved(past_name)
            past_doc_resolved = _is_resolved(past_doc_num)

            link_info = {
                "scan_id": str(past.id),
                "document_number": past_doc_num,
                "holder_name": past_name,
                "date_of_birth": past_dob,
                # Raw cosine, plus a percentage purely for display. Both refer
                # to the same number.
                "cosine_similarity": round(cos, 4),
                "biometric_similarity": round(cos, 4),
                "similarity_percent": round(max(0.0, cos) * 100, 2),
                "threshold": round(threshold, 4),
                "encounter_date": past_date,
                "identity_resolved": past_name_resolved,
            }
            continuity_links.append(link_info)

            past_person_node = f"{past_name} ({past_doc_num})"
            graph.add_node(
                past_person_node, type="historical_identity", label=past_name, doc=past_doc_num
            )
            graph.add_node(past_doc_num, type="document", label=f"Document {past_doc_num}")
            graph.add_edge(past_person_node, past_doc_num, relation="held_document")
            graph.add_edge(
                curr_person_id,
                past_person_node,
                relation="biometric_match",
                similarity=round(cos, 4),
            )

            # ── Anomaly reasoning ───────────────────────────────────────────
            #
            # Both sides must be resolved identities. Without this guard a scan
            # whose OCR failed (holder_name="TRAVELER") raised a CRITICAL
            # "synthetic identity hopping" alert against every prior traveller
            # it matched, which is what flooded the console.
            names_differ = (
                name_resolved
                and past_name_resolved
                and _norm(current_holder_name) != _norm(past_name)
            )
            docs_differ = (
                doc_resolved
                and past_doc_resolved
                and _norm(current_document_number) != _norm(past_doc_num)
            )

            if names_differ:
                anomalies.append({
                    "type": "IDENTITY_LINK_DIFF_NAME",
                    "severity": "CRITICAL",
                    "confidence": round(cos, 4),
                    "description": (
                        f"Identity graph link: this face matches an encounter from "
                        f"{past_date} (document {past_doc_num}) recorded under a "
                        f"DIFFERENT NAME ('{past_name}') at cosine {cos:.3f}. "
                        f"Possible synthetic identity hopping."
                    ),
                    "past_identity": link_info,
                })
            elif docs_differ:
                anomalies.append({
                    "type": "IDENTITY_LINK_DIFF_DOCUMENT",
                    "severity": "HIGH",
                    "confidence": round(cos, 4),
                    "description": (
                        f"Same biometric profile previously presented document "
                        f"{past_doc_num} on {past_date} (cosine {cos:.3f}) under the "
                        f"same name. Multi-document holder — verify both are valid."
                    ),
                    "past_identity": link_info,
                })
            elif not (name_resolved and past_name_resolved):
                # A biometric link exists but at least one side has no readable
                # identity. Worth an officer's attention, but it is an
                # unresolved-identity finding, not proof of identity fraud.
                anomalies.append({
                    "type": "IDENTITY_LINK_UNRESOLVED",
                    "severity": "MEDIUM",
                    "confidence": round(cos, 4),
                    "description": (
                        f"This face matches an encounter from {past_date} at cosine "
                        f"{cos:.3f}, but at least one of the two records has no "
                        f"readable name, so the identities cannot be compared. "
                        f"Re-capture the document to resolve."
                    ),
                    "past_identity": link_info,
                })

        continuity_links.sort(key=lambda link: link["cosine_similarity"], reverse=True)
        return payload()

    def _build_graph_payload(
        self,
        graph: nx.Graph,
        anomalies: List[Dict[str, Any]],
        continuity_links: List[Dict[str, Any]],
        threshold: float,
        skipped: List[Dict[str, Any]],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        nodes = [
            {
                "id": str(n),
                "label": attrs.get("label", str(n)),
                "type": attrs.get("type", "entity"),
                "is_current": attrs.get("is_current", False),
            }
            for n, attrs in graph.nodes(data=True)
        ]

        edges = [
            {
                "source": str(u),
                "target": str(v),
                "relation": attrs.get("relation", "connected"),
                "similarity": attrs.get("similarity"),
            }
            for u, v, attrs in graph.edges(data=True)
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "anomalies": anomalies,
            "continuity_links": continuity_links,
            "has_graph_anomalies": len(anomalies) > 0,
            "match_threshold": round(threshold, 4),
            "search_performed": reason is None,
            "search_note": reason,
            # Surfaces a gallery holding legacy or fabricated embeddings that
            # could not participate in the search.
            "incomparable_records": len(skipped),
            "incomparable_detail": skipped[:20],
        }


identity_graph_service = IdentityGraphService()

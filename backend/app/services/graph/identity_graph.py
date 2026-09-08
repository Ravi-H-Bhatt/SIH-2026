"""
Identity & Document Fraud Intelligence Graph Service.

Evaluates Identity Continuity across encounters:
- Traces 512-dimensional facial biometric embeddings across historical database encounters
- Detects synthetic identity creation, identity-hopping, and multi-passport reuse
- Constructs NetworkX entity resolution graphs connecting Persons, Passports, and Encounters
"""

import math
from typing import Dict, Any, List, Optional
import numpy as np
import networkx as nx
from sqlalchemy.orm import Session

from app.models.scan import ScanRecord
from app.models.face_result import FaceResult
from app.models.extracted_data import ExtractedData


class IdentityGraphService:
    def evaluate_identity_continuity(
        self,
        current_scan_id: str,
        current_face_embedding: Optional[List[float]],
        current_document_number: Optional[str],
        current_holder_name: Optional[str],
        current_dob: Optional[str],
        db: Session
    ) -> Dict[str, Any]:
        """
        Queries historical encounters, calculates biometric cosine distances,
        and constructs the identity entity graph.
        """
        graph = nx.Graph()
        anomalies: List[Dict[str, Any]] = []
        continuity_links: List[Dict[str, Any]] = []

        # Current Node definition
        curr_doc_id = current_document_number or "UNKNOWN_DOC"
        curr_person_id = current_holder_name or "CURRENT_TRAVELER"

        graph.add_node(curr_person_id, type="person", label=curr_person_id, is_current=True)
        graph.add_node(curr_doc_id, type="document", label=f"Passport {curr_doc_id}", is_current=True)
        graph.add_edge(curr_person_id, curr_doc_id, relation="presented_document")

        if not current_face_embedding or len(current_face_embedding) < 100:
            return self._build_graph_payload(graph, anomalies, continuity_links)

        u = np.array(current_face_embedding, dtype=np.float32)
        norm_u = np.linalg.norm(u) + 1e-7

        # Query past encounters from database (excluding current scan)
        target_uuid = current_scan_id
        if isinstance(current_scan_id, str):
            try:
                import uuid
                target_uuid = uuid.UUID(current_scan_id)
            except Exception:
                target_uuid = current_scan_id

        past_scans = (
            db.query(ScanRecord)
            .join(FaceResult, ScanRecord.id == FaceResult.scan_id)
            .filter(ScanRecord.id != target_uuid)
            .order_by(ScanRecord.created_at.desc())
            .limit(100)
            .all()
        )

        for past in past_scans:
            face_res = past.face_result
            if not face_res or not face_res.face_embedding:
                continue

            v = np.array(face_res.face_embedding, dtype=np.float32)
            if len(u) != len(v):
                min_dim = min(len(u), len(v))
                u_sub = u[:min_dim]
                v_sub = v[:min_dim]
                nu = np.linalg.norm(u_sub) + 1e-7
                nv = np.linalg.norm(v_sub) + 1e-7
                cos_sim = float(np.dot(u_sub, v_sub) / (nu * nv))
            else:
                norm_v = np.linalg.norm(v) + 1e-7
                cos_sim = float(np.dot(u, v) / (norm_u * norm_v))

            # Scaled biometric match score
            biometric_sim = (cos_sim + 1.0) / 2.0

            # Significant biometric match threshold (72%+)
            if biometric_sim >= 0.72:
                past_extracted = past.extracted_data.fields if past.extracted_data else {}
                past_doc_num = past_extracted.get("document_number", f"SCAN_{str(past.id)[:8]}")
                past_name = past_extracted.get("holder_name", "UNKNOWN_PAST_NAME")
                past_dob = past_extracted.get("date_of_birth")

                past_encounter_date = past.created_at.strftime("%d %b %Y") if past.created_at else "Previous Date"

                link_info = {
                    "scan_id": str(past.id),
                    "document_number": past_doc_num,
                    "holder_name": past_name,
                    "date_of_birth": past_dob,
                    "biometric_similarity": round(biometric_sim, 3),
                    "encounter_date": past_encounter_date,
                }
                continuity_links.append(link_info)

                # Add past identity to NetworkX Graph
                past_person_node = f"{past_name} ({past_doc_num})"
                graph.add_node(past_person_node, type="historical_identity", label=past_name, doc=past_doc_num)
                graph.add_node(past_doc_num, type="document", label=f"Passport {past_doc_num}")
                graph.add_edge(past_person_node, past_doc_num, relation="held_document")

                # Connect via Biometric Match
                graph.add_edge(
                    curr_person_id,
                    past_person_node,
                    relation="biometric_match",
                    similarity=round(biometric_sim, 3)
                )

                # Check for Anomalies
                # 1. Same face, DIFFERENT name
                if current_holder_name and past_name and current_holder_name.strip().lower() != past_name.strip().lower():
                    anomalies.append({
                        "type": "IDENTITY_LINK_DIFF_NAME",
                        "severity": "CRITICAL",
                        "confidence": round(biometric_sim, 2),
                        "description": (
                            f"Identity Graph Link Anomaly: Face matches encounter from {past_encounter_date} "
                            f"(Passport: {past_doc_num}), but under a DIFFERENT NAME ('{past_name}'). Potential synthetic identity hopping."
                        ),
                        "past_identity": link_info,
                    })

                # 2. Same face, DIFFERENT passport number
                elif current_document_number and past_doc_num and current_document_number.strip().upper() != past_doc_num.strip().upper():
                    anomalies.append({
                        "type": "IDENTITY_LINK_DIFF_DOCUMENT",
                        "severity": "HIGH",
                        "confidence": round(biometric_sim, 2),
                        "description": (
                            f"Multi-Document Encounter: Same biometric profile previously registered with "
                            f"Passport {past_doc_num} on {past_encounter_date}."
                        ),
                        "past_identity": link_info,
                    })

        return self._build_graph_payload(graph, anomalies, continuity_links)

    def _build_graph_payload(
        self,
        graph: nx.Graph,
        anomalies: List[Dict[str, Any]],
        continuity_links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Converts NetworkX graph to D3/React-friendly node-link dictionary.
        """
        nodes = []
        for n, attrs in graph.nodes(data=True):
            nodes.append({
                "id": str(n),
                "label": attrs.get("label", str(n)),
                "type": attrs.get("type", "entity"),
                "is_current": attrs.get("is_current", False),
            })

        edges = []
        for u, v, attrs in graph.edges(data=True):
            edges.append({
                "source": str(u),
                "target": str(v),
                "relation": attrs.get("relation", "connected"),
                "similarity": attrs.get("similarity"),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "anomalies": anomalies,
            "continuity_links": continuity_links,
            "has_graph_anomalies": len(anomalies) > 0,
        }


identity_graph_service = IdentityGraphService()

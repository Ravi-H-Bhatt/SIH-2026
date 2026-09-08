"""
Scan schemas — request/response models for scan operations.
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel


class ScanCreate(BaseModel):
    document_type: str  # passport, visa, id_card, driving_license, permit
    checkpoint_id: Optional[str] = None
    notes: Optional[str] = None


class ExtractedDataResponse(BaseModel):
    fields: Optional[dict[str, Any]] = None
    mrz_data: Optional[dict[str, Any]] = None
    mrz_valid: Optional[bool] = None

    class Config:
        from_attributes = True


class ForgeryResultResponse(BaseModel):
    anomaly_score: Optional[float] = None
    detected_issues: Optional[list[dict[str, Any]]] = None

    class Config:
        from_attributes = True


class FaceResultResponse(BaseModel):
    match_score: Optional[float] = None
    liveness_passed: Optional[bool] = None
    continuity_links: Optional[list[dict[str, Any]]] = None
    watchlist_hits: Optional[list[dict[str, Any]]] = None

    class Config:
        from_attributes = True


class RiskScoreResponse(BaseModel):
    score: Optional[float] = None
    risk_level: Optional[str] = None
    explanations: Optional[list[Any]] = None
    decision: Optional[str] = None
    # Stored as dict or list — accept Any to avoid validation errors on legacy data
    contradiction_matrix: Optional[Any] = None
    identity_graph_summary: Optional[Any] = None
    fraud_patterns_matched: Optional[Any] = None
    canonical_hash: Optional[str] = None

    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    id: UUID
    document_type: str
    status: str
    checkpoint_id: Optional[str] = None
    officer_id: Optional[UUID] = None
    officer_name: Optional[str] = None
    # Canonical storage locations (supabase://bucket/path)
    document_image_path: Optional[str] = None
    face_image_path: Optional[str] = None
    # Short-lived signed URLs for browser rendering (single-scan reads only)
    document_image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    notes: Optional[str] = None
    # Decision fields — both included for frontend compatibility
    decision: Optional[str] = None   # alias to final_decision for frontend
    final_decision: Optional[str] = None
    chip_pki_status: Optional[str] = None
    canonical_hash: Optional[str] = None
    # Document fields
    document_number: Optional[str] = None
    holder_name: Optional[str] = None
    issuing_country: Optional[str] = None
    # Geolocation — powers the operations map
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    origin_country_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    checkpoint_latitude: Optional[float] = None
    checkpoint_longitude: Optional[float] = None
    # Watchlist status
    is_criminal: Optional[str] = None
    criminal_record: Optional[str] = None
    is_wanted: Optional[str] = None
    wanted_details: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    extracted_data: Optional[ExtractedDataResponse] = None
    # Support both naming variants for forgery/face
    forgery_result: Optional[ForgeryResultResponse] = None
    forgery_results: Optional[ForgeryResultResponse] = None
    face_result: Optional[FaceResultResponse] = None
    face_results: Optional[FaceResultResponse] = None
    risk_score: Optional[RiskScoreResponse] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class ScanListResponse(BaseModel):
    scans: list[ScanResponse]
    total: int
    page: int
    page_size: int


class ScanDecisionRequest(BaseModel):
    decision: str  # approved, flagged, detained
    notes: Optional[str] = None

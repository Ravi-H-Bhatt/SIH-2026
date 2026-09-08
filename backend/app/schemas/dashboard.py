"""
Dashboard schemas — statistics and summary responses.
"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_scans_today: int = 0
    total_scans_all: int = 0
    approved_today: int = 0
    flagged_today: int = 0
    detained_today: int = 0
    pending_review: int = 0
    risk_distribution: dict[str, int] = {}  # {"low": 10, "medium": 5, "high": 2, "critical": 1}
    avg_processing_time: float = 0.0  # seconds

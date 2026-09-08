"""
User model — border officers, supervisors, admins, investigators.
With admin approval system.
"""

import uuid
import os
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, Text, Uuid

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="officer")  # officer, supervisor, admin, investigator
    is_active = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)  # Requires admin approval
    approved_by = Column(Uuid(as_uuid=True), nullable=True)  # Admin who approved
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def should_auto_approve(self) -> bool:
        """Check if user should be auto-approved based on env settings."""
        return os.getenv("AUTO_APPROVE_USERS", "true").lower() == "true"

"""
MRZ reference registry — known-good document records.

Stands in for the issuing authority's database. A scanned passport is compared
field-by-field against the reference row with the same document number, which
catches a class of forgery that per-document checks cannot: a technically
well-formed document whose data simply does not match what the issuer holds
(altered date of birth, substituted name, extended expiry).

Records are stored plainly here because this is a demo registry of synthetic
documents. A production deployment would hold salted hashes of the identifying
fields and compare digests, so a database leak would not expose traveller PII.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, Uuid

from app.core.database import Base


class MRZReference(Base):
    __tablename__ = "mrz_references"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Normalised (alphanumeric, upper-case) document number — the lookup key.
    document_number = Column(String(64), nullable=False, unique=True, index=True)

    document_type = Column(String(50), nullable=False, default="passport")
    issuing_country = Column(String(3), nullable=True)
    nationality = Column(String(3), nullable=True)

    surname = Column(String(255), nullable=True)
    given_names = Column(String(255), nullable=True)
    holder_name = Column(String(500), nullable=True)

    date_of_birth = Column(String(10), nullable=True)   # YYYY-MM-DD
    expiry_date = Column(String(10), nullable=True)     # YYYY-MM-DD
    sex = Column(String(1), nullable=True)

    # Full MRZ lines as issued, when known.
    mrz_line1 = Column(Text, nullable=True)
    mrz_line2 = Column(Text, nullable=True)

    # Issuer-reported status. A document can be genuine yet revoked.
    is_revoked = Column(Boolean, nullable=False, default=False)
    is_reported_stolen = Column(Boolean, nullable=False, default=False)
    revocation_reason = Column(Text, nullable=True)

    source = Column(String(100), nullable=True)  # e.g. "uae_reference_fixture"
    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


Index("ix_mrz_references_holder", MRZReference.holder_name)

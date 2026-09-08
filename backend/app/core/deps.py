"""
FastAPI dependency injection functions.
Provides database sessions and current user extraction from JWT.
"""

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ─── Dev bypass ───────────────────────────────────────────────────────────────
import uuid

from app.core.config import settings

DEMO_BYPASS_TOKEN = "demo-bypass-token-sih26188"
DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_USER_EMAIL = "dev-bypass@borderguard.local"


def _get_or_create_demo_user(db: Session) -> User:
    """
    Returns the dev-bypass user, creating the row if it is missing.

    This previously returned a synthetic in-memory User that was never
    persisted. `scan_records.officer_id` is a FK to `users.id`, so every scan
    created in bypass mode died with:

        ForeignKeyViolation: Key (officer_id)=(00000000-...-0001)
        is not present in table "users"

    which surfaced in the UI as "Failed to fetch" on the scanner and a generic
    "SYSTEM ERROR" screen on the kiosk. The account is only reachable via the
    hardcoded demo token and is locked out of password login.
    """
    user = db.query(User).filter(User.id == DEMO_USER_ID).first()
    if user is not None:
        return user

    user = User(
        id=DEMO_USER_ID,
        email=DEMO_USER_EMAIL,
        full_name="Dev Bypass Officer",
        # Not a valid hash, so this account can never authenticate by password.
        hashed_password="!locked:dev-bypass-only",
        role="admin",
        is_active=True,
        is_approved=True,
    )
    db.add(user)
    try:
        db.commit()
    except Exception:
        # Another concurrent request won the race; reuse its row.
        db.rollback()
        user = db.query(User).filter(User.id == DEMO_USER_ID).first()
        if user is None:
            raise
    else:
        db.refresh(user)
    return user


def get_db() -> Generator:
    """Yield a database session, auto-close after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract the current user from JWT token.
    
    In development bypass mode (BYPASS_AUTH=true), returns a synthetic admin user
    so you can test the full UI without a real login flow.
    """
    # ── Dev bypass: accept the demo token ────────────────────────────────────
    # The user must be a real, persisted row — scan_records.officer_id has a
    # foreign key onto it.
    if token == DEMO_BYPASS_TOKEN or (settings.BYPASS_AUTH and not token):
        return _get_or_create_demo_user(db)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: str):
    """Dependency factory: require the current user to have one of the specified roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. Required: {', '.join(roles)}",
            )
        return current_user
    return role_checker

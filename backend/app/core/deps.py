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

# Role hierarchy. A user holding a role implicitly holds every role beneath it,
# so `require_min_role("supervisor")` also admits admins without each endpoint
# having to enumerate the full list.
ROLE_RANK = {
    "auditor": 10,
    "investigator": 20,
    "officer": 30,
    "supervisor": 40,
    "admin": 100,
}


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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # The dev bypass that used to sit here is gone. It accepted a hardcoded
    # token string and returned a synthetic admin, which meant anyone who knew
    # the constant had full admin access and every role check was a no-op.
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    # Approval is enforced on every request, not just at login, so revoking a
    # user takes effect immediately instead of when their token expires.
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending administrator approval.",
        )

    return user


def require_role(*roles: str):
    """
    Require the current user to hold one of `roles` exactly.

    Admins are always permitted — they are the superset of every capability, and
    without this every admin-facing route would have to list "admin" explicitly.
    """
    allowed = set(roles) | {"admin"}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role}' is not authorized for this action. "
                    f"Required: {', '.join(sorted(roles))}."
                ),
            )
        return current_user

    return role_checker


def require_min_role(minimum: str):
    """Require the current user's role to rank at or above `minimum`."""
    threshold = ROLE_RANK.get(minimum, 999)

    def rank_checker(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(current_user.role, 0) < threshold:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role}' is not authorized for this action. "
                    f"Requires '{minimum}' or higher."
                ),
            )
        return current_user

    return rank_checker

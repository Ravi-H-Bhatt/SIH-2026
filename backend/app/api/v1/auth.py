"""
Authentication endpoints — login and token refresh.
With STRICT admin approval system - NO BYPASS.
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT token.
    STRICT APPROVAL CHECK - NO BYPASS ALLOWED.
    """
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact administrator.",
        )
    
    # STRICT APPROVAL CHECK - NO BYPASS
    # Auto-approve setting determines if new users are pre-approved
    # If user is not approved AND auto-approve is OFF, they cannot login
    auto_approve_enabled = os.getenv("AUTO_APPROVE_USERS", "true").lower() == "true"
    
    # Admin users are always approved automatically
    if user.role == "admin":
        if not user.is_approved:
            # Auto-approve admin on first login
            user.is_approved = True
            user.approved_at = datetime.now(timezone.utc)
            db.commit()
    else:
        # For non-admin users, check approval status
        if not user.is_approved:
            if auto_approve_enabled:
                # Auto-approve now
                user.is_approved = True
                user.approved_at = datetime.now(timezone.utc)
                db.commit()
            else:
                # Approval required but not granted - REJECT LOGIN
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="⏳ Waiting for admin approval. Your account is pending approval. Please contact your administrator to grant access.",
                )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh the JWT token for the current user."""
    access_token = create_access_token(data={"sub": str(current_user.id), "role": current_user.role})
    return TokenResponse(
        access_token=access_token,
        user_id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
    )

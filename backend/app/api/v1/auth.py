"""
Authentication endpoints — login and token refresh.
With STRICT admin approval system - NO BYPASS.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import GoogleAuthRequest, LoginRequest, TokenResponse
from app.services.auth.supabase_auth import SupabaseAuthError, supabase_auth

logger = logging.getLogger(__name__)

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
    #
    # Read from `settings`, not os.getenv. pydantic-settings parses .env into the
    # Settings object without exporting it to the process environment, so the old
    # `os.getenv("AUTO_APPROVE_USERS", "true")` always fell through to its "true"
    # default — the approval gate was permanently open even with
    # AUTO_APPROVE_USERS=false in .env.
    auto_approve_enabled = settings.AUTO_APPROVE_USERS
    
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


@router.get("/providers")
def auth_providers():
    """
    Tells the login page which sign-in methods this server actually supports, so
    the Google button is only rendered when the backend can honour it.
    """
    return {
        "password": True,
        "google": supabase_auth.enabled,
    }


@router.post("/google", response_model=TokenResponse)
def google_login(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Exchange a verified Supabase/Google session for an application JWT.

    Security model:
      * The Supabase access token is verified server-side against Supabase's own
        /auth/v1/user endpoint. Nothing the browser asserts about itself is used.
      * The Google address must be verified by Google.
      * The domain must be in GOOGLE_ALLOWED_EMAIL_DOMAINS when that list is set.
      * A first-time Google account is created UNAPPROVED with the configured
        default role, so signing in with Google grants no access until an admin
        approves it. Role is never taken from the OAuth payload.
    """
    if not supabase_auth.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not enabled on this server.",
        )

    try:
        identity = supabase_auth.verify_access_token(request.access_token)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your Google account's email address is not verified.",
        )

    allowed = settings.google_allowed_domains
    if allowed and identity.email_domain not in allowed:
        logger.warning("Rejected Google sign-in from disallowed domain: %s", identity.email_domain)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This email domain is not permitted to access the system. "
                f"Allowed: {', '.join(allowed)}."
            ),
        )

    user = db.query(User).filter(User.email == identity.email).first()
    is_superadmin = settings.is_superadmin_email(identity.email)

    if user is None:
        # Provision unapproved. Role comes from config and is deliberately not
        # derived from anything in the OAuth response.
        default_role = settings.GOOGLE_DEFAULT_ROLE.strip().lower() or "officer"
        if default_role == "admin":
            default_role = "officer"

        pre_approved = (
            settings.AUTO_APPROVE_USERS and not settings.GOOGLE_REQUIRE_ADMIN_APPROVAL
        )

        # Bootstrap owner accounts (ADMIN_EMAILS) come in as approved admins so
        # the deployment always has a way in.
        if is_superadmin:
            default_role, pre_approved = "admin", True

        user = User(
            email=identity.email,
            full_name=identity.full_name or identity.email.split("@")[0],
            # OAuth accounts have no local password. Store an unusable hash so
            # the password login path can never authenticate this row.
            hashed_password="!google-oauth-no-password",
            role=default_role,
            is_active=True,
            is_approved=pre_approved,
            approved_at=datetime.now(timezone.utc) if pre_approved else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(
            "Provisioned Google account %s (role=%s, approved=%s)",
            user.email, user.role, user.is_approved,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact administrator.",
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account has been registered and is awaiting administrator "
                "approval before you can sign in."
            ),
        )

    # Keep the display name fresh from Google without touching role/approval.
    if identity.full_name and user.full_name != identity.full_name:
        user.full_name = identity.full_name
        db.commit()

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

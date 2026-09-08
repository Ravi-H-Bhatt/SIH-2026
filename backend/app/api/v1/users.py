"""
User management endpoints — admin only CRUD.
With admin approval system.
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 50,
    pending_approval: bool = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List all users (admin only)."""
    query = db.query(User)
    
    # Filter by approval status if requested
    if pending_approval is not None:
        if pending_approval:
            query = query.filter(User.is_approved == False, User.role != "admin")
        else:
            query = query.filter(User.is_approved == True)
    
    total = query.count()
    users = query.offset(skip).limit(limit).all()
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Create a new user (admin only)."""
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{request.email}' already exists",
        )

    # Check auto-approve setting
    auto_approve = os.getenv("AUTO_APPROVE_USERS", "true").lower() == "true"
    
    user = User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hash_password(request.password),
        role=request.role,
        is_approved=auto_approve or request.role == "admin",
        approved_by=current_user.id if (auto_approve or request.role == "admin") else None,
        approved_at=datetime.now(timezone.utc) if (auto_approve or request.role == "admin") else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Get a single user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a user's details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/approve", response_model=UserResponse)
def approve_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Approve a pending user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_approved:
        raise HTTPException(status_code=400, detail="User is already approved")
    
    user.is_approved = True
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/revoke-approval", response_model=UserResponse)
def revoke_approval(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Revoke approval from a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_approved:
        raise HTTPException(status_code=400, detail="User is not approved")
    
    user.is_approved = False
    user.approved_by = None
    user.approved_at = None
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/settings/auto-approve", status_code=status.HTTP_200_OK)
def toggle_auto_approve(
    enabled: bool = Body(..., embed=True),
    current_user: User = Depends(require_role("admin")),
):
    """
    Toggle auto-approve setting (admin only).
    NOTE: This is a runtime toggle. For persistent changes, update .env file.
    """
    os.environ["AUTO_APPROVE_USERS"] = "true" if enabled else "false"
    return {
        "success": True,
        "auto_approve_enabled": enabled,
        "message": f"Auto-approve {'enabled' if enabled else 'disabled'}. Note: This is runtime only. Update .env for persistence."
    }


@router.get("/settings/auto-approve")
def get_auto_approve_status(
    current_user: User = Depends(require_role("admin")),
):
    """Get current auto-approve setting status (admin only)."""
    auto_approve = os.getenv("AUTO_APPROVE_USERS", "true").lower() == "true"
    require_approval = os.getenv("REQUIRE_ADMIN_APPROVAL", "false").lower() == "true"
    return {
        "auto_approve_enabled": auto_approve,
        "require_admin_approval": require_approval,
        "message": "Auto-approve controls whether new users need admin approval before login."
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deactivate a user (admin only). Soft delete."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()

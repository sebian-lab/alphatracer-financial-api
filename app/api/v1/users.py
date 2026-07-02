"""
User profile endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.user import UserResponse, UserUpdate
from app.db.models import User as UserModel
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(
    user: UserModel = Depends(get_current_user),
):
    """Get current authenticated user's profile."""
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    user_update: UserUpdate,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update current authenticated user's profile."""
    update_data = user_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete current authenticated user's account."""
    db.delete(user)
    db.commit()

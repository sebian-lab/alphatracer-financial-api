"""
Authentication service for user login and token management.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.models import User as UserModel
from app.core.database import get_db_session
from app.core.security import verify_password, hash_password, \
    create_access_token, create_refresh_token


class AuthService:
    """
    Service for authentication operations.
    """
    
    def authenticate_user(
        self,
        email: str,
        password: str,
        db: Session = Depends(get_db_session)
    ) -> Optional[UserModel]:
        """
        Authenticate user by email and password.
        
        Args:
            email: User's email
            password: User's password
            db: Database session
            
        Returns:
            Authenticated user or None
        """
        user = db.query(UserModel).filter(
            UserModel.email == email.lower()
        ).first()
        
        if not user or not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    def create_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        db: Session = Depends(get_db_session)
    ) -> UserModel:
        """
        Create a new user.
        
        Args:
            email: User's email
            password: Plain text password
            full_name: User's full name (optional)
            db: Database session
            
        Returns:
            Created user object
        """
        hashed_password = hash_password(password)
        new_user = UserModel(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    
    def get_user_by_email(
        self,
        email: str,
        db: Session = Depends(get_db_session)
    ) -> Optional[UserModel]:
        """
        Get user by email.
        
        Args:
            email: User's email
            db: Database session
            
        Returns:
            User object or None
        """
        return db.query(UserModel).filter(
            UserModel.email == email.lower()
        ).first()
    
    def get_current_user(
        self,
        token: str,
        db: Session = Depends(get_db_session)
    ) -> Optional[UserModel]:
        """
        Get current user from JWT token.
        
        Args:
            token: JWT access token
            db: Database session
            
        Returns:
            Current user object or None
        """
        import jwt
        payload = jwt.decode(
            token, 
            secret_key=settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email = payload.get("email")
        if not email:
            return None
        return self.get_user_by_email(email, db)

"""Authentication business logic service."""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.auth.jwt import jwt_manager
from app.auth.password import password_manager
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserResponse


class AuthService:
    """Service class for authentication operations."""
    
    def register_user(self, db: Session, user_data: UserCreate) -> Optional[User]:
        """Register a new user.
        
        Args:
            db: Database session
            user_data: User registration data
            
        Returns:
            Created user or None if registration fails
        """
        # Check password strength
        is_valid, error_msg = password_manager.check_password_strength(user_data.password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check if user already exists
        existing_user = db.query(User).filter(
            User.email == user_data.email
        ).first()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create new user
        hashed_password = password_manager.hash_password(user_data.password)
        
        try:
            new_user = User(
                email=user_data.email,
                username=user_data.username,
                password_hash=hashed_password,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            return new_user
            
        except IntegrityError:
            db.rollback()
            raise ValueError("User registration failed")
    
    def authenticate_user(
        self, 
        db: Session, 
        user_data: UserLogin
    ) -> Optional[User]:
        """Authenticate a user with email and password.
        
        Args:
            db: Database session
            user_data: Login credentials
            
        Returns:
            Authenticated user or None
        """
        user = db.query(User).filter(
            User.email == user_data.email
        ).first()
        
        if not user:
            return None
        
        if not password_manager.verify_password(
            user_data.password, 
            user.password_hash
        ):
            return None
        
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        return user
    
    def create_tokens(self, user: User) -> TokenResponse:
        """Create access and refresh tokens for a user.
        
        Args:
            user: User object
            
        Returns:
            Token response with access and refresh tokens
        """
        tokens = jwt_manager.create_token_pair(
            user_id=user.id,
            email=user.email
        )
        
        return TokenResponse(**tokens)
    
    def refresh_access_token(
        self, 
        db: Session, 
        refresh_token: str
    ) -> Optional[TokenResponse]:
        """Refresh access token using refresh token.
        
        Args:
            db: Database session
            refresh_token: Refresh token
            
        Returns:
            New token pair or None if refresh fails
        """
        # Verify refresh token
        token_data = jwt_manager.verify_token(refresh_token, token_type="refresh")
        if not token_data:
            return None
        
        # Get user
        user = db.query(User).filter(
            User.id == token_data.user_id
        ).first()
        
        if not user or not user.is_active:
            return None
        
        # Create new token pair
        return self.create_tokens(user)
    
    def get_current_user(
        self, 
        db: Session, 
        token: str
    ) -> Optional[User]:
        """Get current user from access token.
        
        Args:
            db: Database session
            token: Access token
            
        Returns:
            Current user or None
        """
        token_data = jwt_manager.verify_token(token, token_type="access")
        if not token_data:
            return None
        
        user = db.query(User).filter(
            User.id == token_data.user_id
        ).first()
        
        if not user or not user.is_active:
            return None
        
        return user
    
    def change_password(
        self,
        db: Session,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password.
        
        Args:
            db: Database session
            user: User object
            current_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully
        """
        # Verify current password
        if not password_manager.verify_password(
            current_password,
            user.password_hash
        ):
            raise ValueError("Current password is incorrect")
        
        # Check new password strength
        is_valid, error_msg = password_manager.check_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Update password
        user.password_hash = password_manager.hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        return True
    
    def deactivate_user(self, db: Session, user: User) -> bool:
        """Deactivate a user account.
        
        Args:
            db: Database session
            user: User to deactivate
            
        Returns:
            True if deactivated successfully
        """
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        return True
    
    def reactivate_user(self, db: Session, user: User) -> bool:
        """Reactivate a user account.
        
        Args:
            db: Database session
            user: User to reactivate
            
        Returns:
            True if reactivated successfully
        """
        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        return True


# Global auth service instance
auth_service = AuthService()

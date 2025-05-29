"""Authentication API endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefresh,
    LoginSuccess,
    RegistrationSuccess,
    PasswordChange,
    UserUpdate,
    UserProfile
)
from app.services.auth_service import auth_service
from app.auth.dependencies import get_current_active_user
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegistrationSuccess, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> RegistrationSuccess:
    """Register a new user.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Registration success response
        
    Raises:
        HTTPException: If registration fails
    """
    try:
        user = auth_service.register_user(db, user_data)
        
        return RegistrationSuccess(
            message="User registered successfully",
            user=UserResponse.from_orm(user)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=LoginSuccess)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
) -> LoginSuccess:
    """Login with email and password.
    
    Args:
        user_data: Login credentials
        db: Database session
        
    Returns:
        Login success response with tokens
        
    Raises:
        HTTPException: If login fails
    """
    user = auth_service.authenticate_user(db, user_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = auth_service.create_tokens(user)
    
    # Get symphony count for the user
    symphony_count = len(user.symphonies) if hasattr(user, 'symphonies') else 0
    
    user_response = UserResponse.from_orm(user)
    user_response.symphony_count = symphony_count
    
    return LoginSuccess(
        message="Login successful",
        user=user_response,
        tokens=tokens
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Refresh access token using refresh token.
    
    Args:
        token_data: Refresh token
        db: Database session
        
    Returns:
        New token pair
        
    Raises:
        HTTPException: If refresh fails
    """
    tokens = auth_service.refresh_access_token(db, token_data.refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return tokens


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserProfile:
    """Get current user profile.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User profile with extended information
    """
    # Get additional user information
    symphony_count = len(current_user.symphonies) if hasattr(current_user, 'symphonies') else 0
    
    # Check if Alpaca account is connected
    alpaca_connected = bool(
        current_user.alpaca_access_token and 
        current_user.alpaca_refresh_token
    )
    
    # Get trade and position counts
    total_trades = len(current_user.trades) if hasattr(current_user, 'trades') else 0
    active_positions = sum(
        1 for p in current_user.positions 
        if hasattr(current_user, 'positions') and p.quantity > 0
    ) if hasattr(current_user, 'positions') else 0
    
    user_profile = UserProfile.from_orm(current_user)
    user_profile.symphony_count = symphony_count
    user_profile.alpaca_account_connected = alpaca_connected
    user_profile.total_trades = total_trades
    user_profile.active_positions = active_positions
    
    return user_profile


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """Update current user profile.
    
    Args:
        user_update: User update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated user information
        
    Raises:
        HTTPException: If update fails
    """
    try:
        # Update user fields if provided
        if user_update.username is not None:
            current_user.username = user_update.username
        
        if user_update.email is not None:
            # Check if email is already taken
            existing_user = db.query(User).filter(
                User.email == user_update.email,
                User.id != current_user.id
            ).first()
            
            if existing_user:
                raise ValueError("Email already in use")
            
            current_user.email = user_update.email
        
        db.commit()
        db.refresh(current_user)
        
        return UserResponse.from_orm(current_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.post("/change-password", response_model=Dict[str, str])
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Change current user password.
    
    Args:
        password_data: Password change data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If password change fails
    """
    try:
        auth_service.change_password(
            db,
            current_user,
            password_data.current_password,
            password_data.new_password
        )
        
        return {"message": "Password changed successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post("/logout", response_model=Dict[str, str])
async def logout(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Logout current user.
    
    Note: This is a placeholder endpoint. With JWT tokens,
    logout is typically handled on the client side by removing
    the stored tokens.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Logout message
    """
    return {"message": "Logged out successfully"}


@router.delete("/me", response_model=Dict[str, str])
async def deactivate_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Deactivate current user account.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If deactivation fails
    """
    try:
        auth_service.deactivate_user(db, current_user)
        return {"message": "Account deactivated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )

"""Pydantic models for authentication."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """Base user model."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """User registration model."""
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """User update model."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    """Password change model."""
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Token refresh request model."""
    refresh_token: str


class UserResponse(UserBase):
    """User response model."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    symphony_count: int = 0
    
    class Config:
        orm_mode = True


class UserProfile(UserResponse):
    """Extended user profile with additional details."""
    alpaca_account_connected: bool = False
    total_trades: int = 0
    active_positions: int = 0
    
    class Config:
        orm_mode = True


class AuthError(BaseModel):
    """Authentication error response."""
    detail: str
    status_code: int = 401


class RegistrationSuccess(BaseModel):
    """Registration success response."""
    message: str = "User registered successfully"
    user: UserResponse


class LoginSuccess(BaseModel):
    """Login success response."""
    message: str = "Login successful"
    user: UserResponse
    tokens: TokenResponse

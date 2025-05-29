"""Authentication GraphQL types."""

from typing import Optional
from datetime import datetime
import strawberry


@strawberry.type
class AuthTokens:
    """Authentication tokens response."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@strawberry.type
class LoginSuccess:
    """Successful login response."""
    
    user: 'User'  # Forward reference to User type
    tokens: AuthTokens
    message: str = "Login successful"


@strawberry.type
class RegisterSuccess:
    """Successful registration response."""
    
    user: 'User'  # Forward reference to User type
    message: str = "User registered successfully"


@strawberry.type
class AuthError:
    """Authentication error response."""
    
    message: str
    code: str
    field: Optional[str] = None


@strawberry.input
class LoginInput:
    """Login input type."""
    
    email: str
    password: str


@strawberry.input
class RegisterInput:
    """Registration input type."""
    
    email: str
    username: str
    password: str
    confirm_password: str


@strawberry.input
class ChangePasswordInput:
    """Change password input type."""
    
    current_password: str
    new_password: str
    confirm_password: str


@strawberry.input
class UpdateProfileInput:
    """Update profile input type."""
    
    username: Optional[str] = None
    email: Optional[str] = None


@strawberry.type
class TokenRefreshSuccess:
    """Token refresh success response."""
    
    tokens: AuthTokens
    message: str = "Tokens refreshed successfully"


# Import User type to resolve forward references
from app.graphql.types.user import User

# Update forward references
LoginSuccess.__annotations__['user'] = User
RegisterSuccess.__annotations__['user'] = User

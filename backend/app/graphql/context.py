"""GraphQL context and authentication."""

from typing import Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database.connection import get_db
from app.models.user import User
from app.services.auth_service import auth_service


security = HTTPBearer(auto_error=False)


@dataclass
class GraphQLContext:
    """GraphQL context containing request-scoped data."""
    
    db: Session
    current_user: Optional[User] = None
    request: Optional[Any] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.current_user is not None
    
    def require_auth(self) -> User:
        """Require authenticated user or raise exception."""
        if not self.current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return self.current_user


async def get_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> GraphQLContext:
    """Get GraphQL context with optional authentication.
    
    Args:
        credentials: Optional bearer token
        db: Database session
        
    Returns:
        GraphQL context
    """
    current_user = None
    
    if credentials:
        token = credentials.credentials
        current_user = auth_service.get_current_user(db, token)
    
    return GraphQLContext(
        db=db,
        current_user=current_user
    )


async def get_authenticated_context(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
) -> GraphQLContext:
    """Get GraphQL context with required authentication.
    
    Args:
        credentials: Required bearer token
        db: Database session
        
    Returns:
        Authenticated GraphQL context
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    current_user = auth_service.get_current_user(db, token)
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return GraphQLContext(
        db=db,
        current_user=current_user
    )

"""User GraphQL query resolvers."""

from typing import Optional, List
import strawberry
from strawberry.types import Info

from app.graphql.context import GraphQLContext
from app.graphql.types.user import User, UserProfile, UsersConnection
from app.models.user import User as UserModel


@strawberry.type
class UserQueries:
    """User-related queries."""
    
    @strawberry.field
    async def me(self, info: Info[GraphQLContext]) -> Optional[UserProfile]:
        """Get current authenticated user profile.
        
        Args:
            info: GraphQL context info
            
        Returns:
            UserProfile or None if not authenticated
        """
        if not info.context.is_authenticated:
            return None
        
        return UserProfile.from_model(info.context.current_user)
    
    @strawberry.field
    async def user(
        self,
        info: Info[GraphQLContext],
        id: int
    ) -> Optional[User]:
        """Get user by ID.
        
        Args:
            info: GraphQL context info
            id: User ID
            
        Returns:
            User or None if not found
        """
        # Require authentication
        info.context.require_auth()
        
        user = info.context.db.query(UserModel).filter(
            UserModel.id == id
        ).first()
        
        if user:
            return User.from_model(user)
        
        return None
    
    @strawberry.field
    async def users(
        self,
        info: Info[GraphQLContext],
        limit: int = 10,
        offset: int = 0
    ) -> UsersConnection:
        """Get paginated list of users.
        
        Args:
            info: GraphQL context info
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            UsersConnection with paginated results
        """
        # Require authentication
        info.context.require_auth()
        
        # Get total count
        total_count = info.context.db.query(UserModel).count()
        
        # Get paginated users
        users = info.context.db.query(UserModel).offset(offset).limit(limit).all()
        
        # Convert to GraphQL types
        user_nodes = [User.from_model(user) for user in users]
        
        return UsersConnection(
            nodes=user_nodes,
            total_count=total_count,
            has_next_page=(offset + limit) < total_count,
            has_previous_page=offset > 0
        )
    
    @strawberry.field
    async def user_by_email(
        self,
        info: Info[GraphQLContext],
        email: str
    ) -> Optional[User]:
        """Get user by email address.
        
        Args:
            info: GraphQL context info
            email: User email
            
        Returns:
            User or None if not found
        """
        # Require authentication
        info.context.require_auth()
        
        user = info.context.db.query(UserModel).filter(
            UserModel.email == email
        ).first()
        
        if user:
            return User.from_model(user)
        
        return None
    
    @strawberry.field
    async def check_email_available(
        self,
        info: Info[GraphQLContext],
        email: str
    ) -> bool:
        """Check if email is available for registration.
        
        Args:
            info: GraphQL context info
            email: Email to check
            
        Returns:
            True if email is available
        """
        existing_user = info.context.db.query(UserModel).filter(
            UserModel.email == email
        ).first()
        
        return existing_user is None
    
    @strawberry.field
    async def check_username_available(
        self,
        info: Info[GraphQLContext],
        username: str
    ) -> bool:
        """Check if username is available for registration.
        
        Args:
            info: GraphQL context info
            username: Username to check
            
        Returns:
            True if username is available
        """
        existing_user = info.context.db.query(UserModel).filter(
            UserModel.username == username
        ).first()
        
        return existing_user is None

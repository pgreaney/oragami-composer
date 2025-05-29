"""User GraphQL types and resolvers."""

from typing import List, Optional
from datetime import datetime
import strawberry
from strawberry.types import Info

from app.graphql.context import GraphQLContext
from app.models.user import User as UserModel


@strawberry.type
class User:
    """GraphQL User type."""
    
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    # Computed fields
    @strawberry.field
    def symphony_count(self, info: Info[GraphQLContext]) -> int:
        """Get count of user's symphonies."""
        user = info.context.db.query(UserModel).filter(
            UserModel.id == self.id
        ).first()
        
        if user and hasattr(user, 'symphonies'):
            return len(user.symphonies)
        return 0
    
    @strawberry.field
    def alpaca_connected(self, info: Info[GraphQLContext]) -> bool:
        """Check if Alpaca account is connected."""
        user = info.context.db.query(UserModel).filter(
            UserModel.id == self.id
        ).first()
        
        if user:
            return bool(
                user.alpaca_access_token and 
                user.alpaca_refresh_token
            )
        return False
    
    @strawberry.field
    def total_trades(self, info: Info[GraphQLContext]) -> int:
        """Get total number of trades."""
        user = info.context.db.query(UserModel).filter(
            UserModel.id == self.id
        ).first()
        
        if user and hasattr(user, 'trades'):
            return len(user.trades)
        return 0
    
    @strawberry.field
    def active_positions(self, info: Info[GraphQLContext]) -> int:
        """Get count of active positions."""
        user = info.context.db.query(UserModel).filter(
            UserModel.id == self.id
        ).first()
        
        if user and hasattr(user, 'positions'):
            return sum(
                1 for p in user.positions 
                if p.quantity > 0
            )
        return 0
    
    @classmethod
    def from_model(cls, user: UserModel) -> 'User':
        """Convert SQLAlchemy model to GraphQL type."""
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login
        )


@strawberry.type
class UserProfile(User):
    """Extended user profile with additional details."""
    
    @strawberry.field
    def portfolio_value(self, info: Info[GraphQLContext]) -> float:
        """Get current portfolio value."""
        # TODO: Implement portfolio value calculation
        return 0.0
    
    @strawberry.field
    def daily_change(self, info: Info[GraphQLContext]) -> float:
        """Get daily portfolio change."""
        # TODO: Implement daily change calculation
        return 0.0
    
    @strawberry.field
    def daily_change_percent(self, info: Info[GraphQLContext]) -> float:
        """Get daily portfolio change percentage."""
        # TODO: Implement daily change percentage calculation
        return 0.0


@strawberry.type
class UsersConnection:
    """Paginated users connection."""
    
    nodes: List[User]
    total_count: int
    has_next_page: bool
    has_previous_page: bool

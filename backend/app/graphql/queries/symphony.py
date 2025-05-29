"""Symphony GraphQL query resolvers."""

from typing import List, Optional
import strawberry
from strawberry.types import Info

from app.graphql.context import GraphQLContext
from app.graphql.types.symphony import (
    Symphony,
    SymphonyConnection,
    SymphonyExecutionStatus
)
from app.models.symphony import Symphony as SymphonyModel
from app.services.symphony_service import symphony_service
from datetime import datetime, timedelta


@strawberry.type
class SymphonyQueries:
    """Symphony-related queries."""
    
    @strawberry.field
    async def symphony(
        self,
        info: Info[GraphQLContext],
        id: int
    ) -> Optional[Symphony]:
        """Get symphony by ID.
        
        Args:
            info: GraphQL context info
            id: Symphony ID
            
        Returns:
            Symphony or None if not found
        """
        # Require authentication
        user = info.context.require_auth()
        
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            id,
            user
        )
        
        if symphony:
            return Symphony.from_model(symphony)
        
        return None
    
    @strawberry.field
    async def my_symphonies(
        self,
        info: Info[GraphQLContext],
        limit: int = 40,
        offset: int = 0,
        active_only: bool = False
    ) -> SymphonyConnection:
        """Get current user's symphonies.
        
        Args:
            info: GraphQL context info
            limit: Maximum results (default 40, max 100)
            offset: Result offset
            active_only: Only return active symphonies
            
        Returns:
            SymphonyConnection with paginated results
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Limit max results
        limit = min(limit, 100)
        
        # Get symphonies
        symphonies = symphony_service.get_user_symphonies(
            info.context.db,
            user,
            limit=limit,
            offset=offset,
            active_only=active_only
        )
        
        # Get total count
        total_count = symphony_service.count_user_symphonies(info.context.db, user)
        
        # Convert to GraphQL types
        symphony_nodes = [Symphony.from_model(s) for s in symphonies]
        
        return SymphonyConnection(
            nodes=symphony_nodes,
            total_count=total_count,
            has_next_page=(offset + limit) < total_count,
            has_previous_page=offset > 0
        )
    
    @strawberry.field
    async def symphony_count(
        self,
        info: Info[GraphQLContext]
    ) -> int:
        """Get current user's symphony count.
        
        Args:
            info: GraphQL context info
            
        Returns:
            Symphony count
        """
        # Require authentication
        user = info.context.require_auth()
        
        return symphony_service.count_user_symphonies(info.context.db, user)
    
    @strawberry.field
    async def symphony_execution_status(
        self,
        info: Info[GraphQLContext],
        id: int
    ) -> Optional[SymphonyExecutionStatus]:
        """Get symphony execution status.
        
        Args:
            info: GraphQL context info
            id: Symphony ID
            
        Returns:
            SymphonyExecutionStatus or None
        """
        # Require authentication
        user = info.context.require_auth()
        
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            id,
            user
        )
        
        if not symphony:
            return None
        
        # Calculate next execution time based on rebalance frequency
        next_execution = None
        if symphony.is_active and symphony.rebalance_frequency == "daily":
            # Daily execution at 15:50 EST
            now = datetime.utcnow()
            today_execution = now.replace(hour=20, minute=50, second=0, microsecond=0)  # 15:50 EST = 20:50 UTC
            
            if now < today_execution:
                next_execution = today_execution
            else:
                next_execution = today_execution + timedelta(days=1)
        
        return SymphonyExecutionStatus(
            symphony_id=symphony.id,
            is_executing=False,  # Will be updated when execution engine is implemented
            last_executed_at=symphony.last_executed_at,
            next_execution_at=next_execution,
            last_error=symphony.last_execution_error,
            execution_count=symphony.execution_count
        )
    
    @strawberry.field
    async def symphony_quota(
        self,
        info: Info[GraphQLContext]
    ) -> dict:
        """Get symphony quota information.
        
        Args:
            info: GraphQL context info
            
        Returns:
            Quota information
        """
        # Require authentication
        user = info.context.require_auth()
        
        count = symphony_service.count_user_symphonies(info.context.db, user)
        
        return {
            "used": count,
            "limit": symphony_service.MAX_SYMPHONIES_PER_USER,
            "remaining": max(0, symphony_service.MAX_SYMPHONIES_PER_USER - count)
        }
    
    @strawberry.field
    async def active_symphonies(
        self,
        info: Info[GraphQLContext]
    ) -> List[Symphony]:
        """Get all active symphonies for current user.
        
        Args:
            info: GraphQL context info
            
        Returns:
            List of active symphonies
        """
        # Require authentication
        user = info.context.require_auth()
        
        symphonies = symphony_service.get_user_symphonies(
            info.context.db,
            user,
            active_only=True
        )
        
        return [Symphony.from_model(s) for s in symphonies]

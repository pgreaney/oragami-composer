"""
Position Update Subscriptions

Real-time GraphQL subscriptions for position updates and changes.
"""

from typing import AsyncGenerator, Optional
import strawberry
from strawberry.types import Info
import asyncio
import logging

from app.graphql.types.trading import PositionType
from app.graphql.context import GraphQLContext
from app.services.pubsub_service import PubSubService
from app.models.position import Position


logger = logging.getLogger(__name__)


@strawberry.type
class PositionUpdate:
    """Position update event"""
    
    type: str  # 'created', 'updated', 'closed'
    position: PositionType
    timestamp: str


@strawberry.type
class PositionSubscription:
    """Position-related subscriptions"""
    
    @strawberry.subscription
    async def position_updates(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None
    ) -> AsyncGenerator[PositionUpdate, None]:
        """
        Subscribe to position updates for the authenticated user
        
        Args:
            symphony_id: Optional filter for specific symphony positions
            
        Yields:
            Position update events
        """
        # Verify authentication
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to user's position channel
        channel = f"positions:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        logger.info(f"User {user_id} subscribed to position updates")
        
        try:
            while True:
                # Wait for message
                message = await queue.get()
                
                if message['type'] == 'position_update':
                    position_data = message['position']
                    
                    # Filter by symphony if specified
                    if symphony_id and position_data.get('symphony_id') != symphony_id:
                        continue
                        
                    # Convert to GraphQL type
                    position = await _convert_to_position_type(
                        info.context.db,
                        position_data
                    )
                    
                    yield PositionUpdate(
                        type='updated',
                        position=position,
                        timestamp=message['timestamp']
                    )
                    
        except asyncio.CancelledError:
            logger.info(f"User {user_id} unsubscribed from position updates")
            await pubsub.unsubscribe(channel, queue)
            raise
            
    @strawberry.subscription
    async def portfolio_value(
        self, info: Info[GraphQLContext]
    ) -> AsyncGenerator[strawberry.scalars.JSON, None]:
        """
        Subscribe to real-time portfolio value updates
        
        Yields:
            Portfolio value and metrics
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        channel = f"portfolio:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'portfolio_metrics':
                    yield message['metrics']
                    
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise


async def _convert_to_position_type(db, position_data: dict) -> PositionType:
    """Convert position data to GraphQL type"""
    # If we have just the data dict, create a PositionType directly
    if isinstance(position_data, dict):
        return PositionType(
            id=position_data.get('id'),
            symbol=position_data.get('symbol'),
            quantity=position_data.get('quantity'),
            cost_basis=position_data.get('cost_basis'),
            current_price=position_data.get('current_price'),
            current_value=position_data.get('current_value'),
            unrealized_pnl=position_data.get('unrealized_pnl'),
            unrealized_pnl_percentage=(
                position_data.get('unrealized_pnl', 0) / position_data.get('cost_basis', 1) * 100
                if position_data.get('cost_basis', 0) > 0 else 0
            ),
            opened_at=position_data.get('opened_at'),
            updated_at=position_data.get('updated_at')
        )
    
    # If we have a Position model instance
    return PositionType.from_model(position_data)


# Export subscription instance
position_subscription = PositionSubscription()

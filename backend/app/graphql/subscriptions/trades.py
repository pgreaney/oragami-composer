"""
Trade Execution Subscriptions

Real-time GraphQL subscriptions for trade executions and updates.
"""

from typing import AsyncGenerator, Optional
import strawberry
from strawberry.types import Info
import asyncio
import logging
from datetime import datetime

from app.graphql.types.trading import TradeType
from app.graphql.context import GraphQLContext
from app.services.pubsub_service import PubSubService
from app.models.trade import Trade


logger = logging.getLogger(__name__)


@strawberry.type
class TradeExecution:
    """Trade execution event"""
    
    trade: TradeType
    status: str  # 'pending', 'executed', 'failed', 'cancelled'
    message: Optional[str] = None
    timestamp: str


@strawberry.type
class TradeSubscription:
    """Trade-related subscriptions"""
    
    @strawberry.subscription
    async def trade_executions(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None,
        status_filter: Optional[str] = None
    ) -> AsyncGenerator[TradeExecution, None]:
        """
        Subscribe to trade execution updates
        
        Args:
            symphony_id: Optional filter for specific symphony trades
            status_filter: Optional filter for trade status ('executed', 'failed', etc.)
            
        Yields:
            Trade execution events
        """
        # Verify authentication
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to user's trades channel
        channel = f"trades:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        logger.info(f"User {user_id} subscribed to trade executions")
        
        try:
            while True:
                # Wait for message
                message = await queue.get()
                
                if message['type'] == 'trade_execution':
                    trade_data = message['trade']
                    
                    # Apply filters
                    if symphony_id and trade_data.get('symphony_id') != symphony_id:
                        continue
                        
                    if status_filter and trade_data.get('status') != status_filter:
                        continue
                        
                    # Convert to GraphQL type
                    trade = await _convert_to_trade_type(
                        info.context.db,
                        trade_data
                    )
                    
                    yield TradeExecution(
                        trade=trade,
                        status=trade_data.get('status', 'unknown'),
                        message=trade_data.get('message'),
                        timestamp=message['timestamp']
                    )
                    
        except asyncio.CancelledError:
            logger.info(f"User {user_id} unsubscribed from trade executions")
            await pubsub.unsubscribe(channel, queue)
            raise
            
    @strawberry.subscription
    async def rebalancing_progress(
        self,
        info: Info[GraphQLContext],
        symphony_id: int
    ) -> AsyncGenerator[strawberry.scalars.JSON, None]:
        """
        Subscribe to rebalancing progress for a specific symphony
        
        Args:
            symphony_id: Symphony ID to monitor
            
        Yields:
            Rebalancing progress updates
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to symphony-specific channel
        channel = f"rebalancing:{user_id}:{symphony_id}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'rebalancing_progress':
                    yield {
                        'symphony_id': symphony_id,
                        'progress': message['progress'],
                        'total_trades': message.get('total_trades', 0),
                        'completed_trades': message.get('completed_trades', 0),
                        'failed_trades': message.get('failed_trades', 0),
                        'status': message.get('status', 'in_progress'),
                        'timestamp': message['timestamp']
                    }
                    
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise
    
    @strawberry.subscription
    async def order_updates(
        self,
        info: Info[GraphQLContext]
    ) -> AsyncGenerator[strawberry.scalars.JSON, None]:
        """
        Subscribe to Alpaca order updates
        
        Yields:
            Order status updates from Alpaca
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to order updates channel
        channel = f"orders:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'order_update':
                    yield {
                        'order_id': message['order']['id'],
                        'symbol': message['order']['symbol'],
                        'side': message['order']['side'],
                        'qty': message['order']['qty'],
                        'status': message['order']['status'],
                        'filled_qty': message['order'].get('filled_qty', 0),
                        'filled_avg_price': message['order'].get('filled_avg_price'),
                        'updated_at': message['timestamp']
                    }
                    
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise


async def _convert_to_trade_type(db, trade_data: dict) -> TradeType:
    """Convert trade data to GraphQL type"""
    # If we have just the data dict, create a TradeType directly
    if isinstance(trade_data, dict):
        return TradeType(
            id=trade_data.get('id'),
            symphony_id=trade_data.get('symphony_id'),
            symbol=trade_data.get('symbol'),
            side=trade_data.get('side'),
            quantity=trade_data.get('quantity'),
            price=trade_data.get('price'),
            total_value=trade_data.get('total_value'),
            status=trade_data.get('status'),
            alpaca_order_id=trade_data.get('alpaca_order_id'),
            executed_at=trade_data.get('executed_at'),
            created_at=trade_data.get('created_at')
        )
    
    # If we have a Trade model instance
    return TradeType.from_model(trade_data)


# Export subscription instance
trade_subscription = TradeSubscription()

"""
Performance Metrics Subscriptions

Real-time GraphQL subscriptions for performance metrics and analytics.
"""

from typing import AsyncGenerator, Optional
import strawberry
from strawberry.types import Info
import asyncio
import logging
from datetime import datetime, date

from app.graphql.context import GraphQLContext
from app.services.pubsub_service import PubSubService


logger = logging.getLogger(__name__)


@strawberry.type
class MetricUpdate:
    """Performance metric update"""
    
    metric_type: str  # 'daily_return', 'total_return', 'sharpe_ratio', etc.
    value: float
    timestamp: str
    period: Optional[str] = None  # '1D', '1W', '1M', '3M', '1Y', 'ALL'


@strawberry.type
class PerformanceUpdate:
    """Complete performance update"""
    
    total_value: float
    total_return: float
    total_return_percentage: float
    daily_return: float
    daily_return_percentage: float
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    volatility: Optional[float]
    win_rate: Optional[float]
    timestamp: str


@strawberry.type
class MetricsSubscription:
    """Performance metrics subscriptions"""
    
    @strawberry.subscription
    async def performance_updates(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None
    ) -> AsyncGenerator[PerformanceUpdate, None]:
        """
        Subscribe to performance metric updates
        
        Args:
            symphony_id: Optional filter for specific symphony metrics
            
        Yields:
            Performance update events
        """
        # Verify authentication
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to metrics channel
        channel = f"metrics:{user_id}"
        if symphony_id:
            channel = f"metrics:{user_id}:{symphony_id}"
            
        queue = await pubsub.subscribe(channel)
        
        logger.info(f"User {user_id} subscribed to performance metrics")
        
        try:
            while True:
                # Wait for message
                message = await queue.get()
                
                if message['type'] == 'performance_update':
                    metrics = message['metrics']
                    
                    yield PerformanceUpdate(
                        total_value=metrics.get('total_value', 0),
                        total_return=metrics.get('total_return', 0),
                        total_return_percentage=metrics.get('total_return_percentage', 0),
                        daily_return=metrics.get('daily_return', 0),
                        daily_return_percentage=metrics.get('daily_return_percentage', 0),
                        sharpe_ratio=metrics.get('sharpe_ratio'),
                        max_drawdown=metrics.get('max_drawdown'),
                        volatility=metrics.get('volatility'),
                        win_rate=metrics.get('win_rate'),
                        timestamp=message['timestamp']
                    )
                    
        except asyncio.CancelledError:
            logger.info(f"User {user_id} unsubscribed from performance metrics")
            await pubsub.unsubscribe(channel, queue)
            raise
            
    @strawberry.subscription
    async def metric_stream(
        self,
        info: Info[GraphQLContext],
        metric_types: Optional[list[str]] = None
    ) -> AsyncGenerator[MetricUpdate, None]:
        """
        Subscribe to specific metric type updates
        
        Args:
            metric_types: List of metric types to subscribe to
            
        Yields:
            Individual metric updates
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Default to all metrics if not specified
        if not metric_types:
            metric_types = [
                'total_return', 'daily_return', 'sharpe_ratio',
                'volatility', 'max_drawdown', 'win_rate'
            ]
            
        # Subscribe to metric stream channel
        channel = f"metric_stream:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'metric_update':
                    metric_type = message['metric']['type']
                    
                    # Filter by requested metric types
                    if metric_type in metric_types:
                        yield MetricUpdate(
                            metric_type=metric_type,
                            value=message['metric']['value'],
                            timestamp=message['timestamp'],
                            period=message['metric'].get('period')
                        )
                        
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise
            
    @strawberry.subscription
    async def benchmark_comparison(
        self,
        info: Info[GraphQLContext],
        benchmark: str = "SPY"
    ) -> AsyncGenerator[strawberry.scalars.JSON, None]:
        """
        Subscribe to benchmark comparison updates
        
        Args:
            benchmark: Benchmark symbol to compare against
            
        Yields:
            Benchmark comparison data
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to benchmark channel
        channel = f"benchmark:{user_id}:{benchmark}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'benchmark_update':
                    yield {
                        'benchmark': benchmark,
                        'portfolio_return': message['data']['portfolio_return'],
                        'benchmark_return': message['data']['benchmark_return'],
                        'excess_return': message['data']['excess_return'],
                        'correlation': message['data'].get('correlation'),
                        'beta': message['data'].get('beta'),
                        'alpha': message['data'].get('alpha'),
                        'period': message['data'].get('period', 'YTD'),
                        'timestamp': message['timestamp']
                    }
                    
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise
            
    @strawberry.subscription  
    async def symphony_execution_metrics(
        self,
        info: Info[GraphQLContext]
    ) -> AsyncGenerator[strawberry.scalars.JSON, None]:
        """
        Subscribe to symphony execution metrics
        
        Yields:
            Symphony execution statistics
        """
        if not info.context.user:
            raise Exception("Authentication required")
            
        user_id = info.context.user.id
        pubsub = PubSubService()
        
        # Subscribe to execution metrics channel
        channel = f"execution_metrics:{user_id}"
        queue = await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await queue.get()
                
                if message['type'] == 'execution_metrics':
                    yield {
                        'total_executions': message['metrics']['total_executions'],
                        'successful_executions': message['metrics']['successful_executions'],
                        'failed_executions': message['metrics']['failed_executions'],
                        'average_execution_time': message['metrics']['average_execution_time'],
                        'last_execution_time': message['metrics']['last_execution_time'],
                        'symphonies': message['metrics'].get('symphonies', []),
                        'timestamp': message['timestamp']
                    }
                    
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel, queue)
            raise


# Export subscription instance
metrics_subscription = MetricsSubscription()

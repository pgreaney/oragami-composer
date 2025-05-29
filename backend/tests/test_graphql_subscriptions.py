"""
Tests for GraphQL Subscriptions

This module tests the real-time GraphQL subscription functionality
for positions, trades, and performance metrics.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import strawberry
from strawberry.types import Info

from app.graphql.subscriptions.positions import PositionSubscription, PositionUpdate
from app.graphql.subscriptions.trades import TradeSubscription, TradeExecution
from app.graphql.subscriptions.metrics import MetricsSubscription, PerformanceUpdate
from app.graphql.context import GraphQLContext
from app.services.pubsub_service import PubSubService


class TestPositionSubscriptions:
    """Test position-related subscriptions"""
    
    @pytest.fixture
    def mock_context(self):
        """Create mock GraphQL context"""
        context = Mock(spec=GraphQLContext)
        context.user = Mock(id=1)
        context.db = Mock()
        return context
    
    @pytest.fixture
    def mock_info(self, mock_context):
        """Create mock info object"""
        info = Mock(spec=Info)
        info.context = mock_context
        return info
    
    @pytest.fixture
    def position_subscription(self):
        """Create position subscription instance"""
        return PositionSubscription()
    
    async def test_position_updates_subscription(self, position_subscription, mock_info):
        """Test subscribing to position updates"""
        # Mock PubSubService
        with patch('app.graphql.subscriptions.positions.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add test message to queue
            await mock_queue.put({
                'type': 'position_update',
                'position': {
                    'id': 1,
                    'symbol': 'SPY',
                    'quantity': 10,
                    'cost_basis': 4000,
                    'current_price': 450,
                    'current_value': 4500,
                    'unrealized_pnl': 500
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe to updates
            updates = []
            async for update in position_subscription.position_updates(mock_info):
                updates.append(update)
                if len(updates) >= 1:
                    break
                    
            # Verify subscription
            assert len(updates) == 1
            assert isinstance(updates[0], PositionUpdate)
            assert updates[0].type == 'updated'
            assert updates[0].position.symbol == 'SPY'
    
    async def test_portfolio_value_subscription(self, position_subscription, mock_info):
        """Test subscribing to portfolio value updates"""
        with patch('app.graphql.subscriptions.positions.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add test message
            await mock_queue.put({
                'type': 'portfolio_metrics',
                'metrics': {
                    'total_value': 100000,
                    'total_return': 5000,
                    'total_return_percentage': 5.0
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe
            values = []
            async for value in position_subscription.portfolio_value(mock_info):
                values.append(value)
                if len(values) >= 1:
                    break
                    
            assert len(values) == 1
            assert values[0]['total_value'] == 100000
    
    async def test_authentication_required(self, position_subscription, mock_info):
        """Test that authentication is required for subscriptions"""
        mock_info.context.user = None
        
        with pytest.raises(Exception, match="Authentication required"):
            async for _ in position_subscription.position_updates(mock_info):
                pass


class TestTradeSubscriptions:
    """Test trade-related subscriptions"""
    
    @pytest.fixture
    def trade_subscription(self):
        """Create trade subscription instance"""
        return TradeSubscription()
    
    async def test_trade_executions_subscription(self, trade_subscription, mock_info):
        """Test subscribing to trade executions"""
        with patch('app.graphql.subscriptions.trades.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add test trade execution
            await mock_queue.put({
                'type': 'trade_execution',
                'trade': {
                    'id': 1,
                    'symphony_id': 1,
                    'symbol': 'SPY',
                    'side': 'buy',
                    'quantity': 10,
                    'price': 450.50,
                    'status': 'executed'
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe
            executions = []
            async for execution in trade_subscription.trade_executions(mock_info):
                executions.append(execution)
                if len(executions) >= 1:
                    break
                    
            assert len(executions) == 1
            assert isinstance(executions[0], TradeExecution)
            assert executions[0].status == 'executed'
    
    async def test_rebalancing_progress_subscription(self, trade_subscription, mock_info):
        """Test subscribing to rebalancing progress"""
        with patch('app.graphql.subscriptions.trades.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add progress update
            await mock_queue.put({
                'type': 'rebalancing_progress',
                'progress': 0.5,
                'total_trades': 10,
                'completed_trades': 5,
                'failed_trades': 0,
                'status': 'in_progress',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe
            updates = []
            async for update in trade_subscription.rebalancing_progress(mock_info, symphony_id=1):
                updates.append(update)
                if len(updates) >= 1:
                    break
                    
            assert len(updates) == 1
            assert updates[0]['progress'] == 0.5
            assert updates[0]['total_trades'] == 10
    
    async def test_status_filter(self, trade_subscription, mock_info):
        """Test filtering trade executions by status"""
        with patch('app.graphql.subscriptions.trades.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add multiple trades with different statuses
            await mock_queue.put({
                'type': 'trade_execution',
                'trade': {'id': 1, 'status': 'pending'},
                'timestamp': datetime.utcnow().isoformat()
            })
            await mock_queue.put({
                'type': 'trade_execution',
                'trade': {'id': 2, 'status': 'executed'},
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe with filter
            executions = []
            async for execution in trade_subscription.trade_executions(
                mock_info, status_filter='executed'
            ):
                executions.append(execution)
                if len(executions) >= 1:
                    break
                    
            # Should only receive executed trades
            assert len(executions) == 1
            assert executions[0].trade.id == 2


class TestMetricsSubscriptions:
    """Test metrics-related subscriptions"""
    
    @pytest.fixture
    def metrics_subscription(self):
        """Create metrics subscription instance"""
        return MetricsSubscription()
    
    async def test_performance_updates_subscription(self, metrics_subscription, mock_info):
        """Test subscribing to performance updates"""
        with patch('app.graphql.subscriptions.metrics.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add performance update
            await mock_queue.put({
                'type': 'performance_update',
                'metrics': {
                    'total_value': 100000,
                    'total_return': 5000,
                    'total_return_percentage': 5.0,
                    'daily_return': 100,
                    'daily_return_percentage': 0.1,
                    'sharpe_ratio': 1.5,
                    'max_drawdown': -0.1,
                    'volatility': 0.15
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe
            updates = []
            async for update in metrics_subscription.performance_updates(mock_info):
                updates.append(update)
                if len(updates) >= 1:
                    break
                    
            assert len(updates) == 1
            assert isinstance(updates[0], PerformanceUpdate)
            assert updates[0].total_value == 100000
            assert updates[0].sharpe_ratio == 1.5
    
    async def test_benchmark_comparison_subscription(self, metrics_subscription, mock_info):
        """Test subscribing to benchmark comparisons"""
        with patch('app.graphql.subscriptions.metrics.PubSubService') as mock_pubsub_class:
            mock_pubsub = AsyncMock()
            mock_queue = asyncio.Queue()
            
            # Add benchmark comparison
            await mock_queue.put({
                'type': 'benchmark_update',
                'data': {
                    'portfolio_return': 0.12,
                    'benchmark_return': 0.10,
                    'excess_return': 0.02,
                    'correlation': 0.85,
                    'beta': 0.9,
                    'alpha': 0.015
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
            mock_pubsub.subscribe = AsyncMock(return_value=mock_queue)
            mock_pubsub_class.return_value = mock_pubsub
            
            # Subscribe
            comparisons = []
            async for comparison in metrics_subscription.benchmark_comparison(mock_info):
                comparisons.append(comparison)
                if len(comparisons) >= 1:
                    break
                    
            assert len(comparisons) == 1
            assert comparisons[0]['excess_return'] == 0.02
            assert comparisons[0]['alpha'] == 0.015


class TestSubscriptionIntegration:
    """Test subscription integration with pub/sub system"""
    
    async def test_subscription_cleanup_on_disconnect(self):
        """Test that subscriptions are cleaned up on disconnect"""
        pubsub = PubSubService()
        channel = "test:channel"
        queue = await pubsub.subscribe(channel)
        
        # Verify subscription exists
        assert channel in pubsub._subscribers
        assert queue in pubsub._subscribers[channel]
        
        # Unsubscribe
        await pubsub.unsubscribe(channel, queue)
        
        # Verify cleanup
        if channel in pubsub._subscribers:
            assert queue not in pubsub._subscribers[channel]
    
    def test_subscription_error_handling(self):
        """Test error handling in subscriptions"""
        # This would test various error scenarios
        # such as connection failures, invalid messages, etc.
        pass

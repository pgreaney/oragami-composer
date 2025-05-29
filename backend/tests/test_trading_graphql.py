"""Trading GraphQL API testing."""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from app.graphql.types.trading import (
    Position,
    Trade,
    PerformanceMetric,
    PortfolioSummary
)
from app.models.position import Position as PositionModel
from app.models.trade import Trade as TradeModel
from app.services.trading_service import TradingService


class TestTradingTypes:
    """Test trading GraphQL types."""
    
    def test_position_type(self):
        """Test Position GraphQL type."""
        position_model = Mock(spec=PositionModel)
        position_model.id = 1
        position_model.user_id = 1
        position_model.symphony_id = 1
        position_model.symbol = "AAPL"
        position_model.quantity = Decimal("100")
        position_model.average_price = Decimal("150.00")
        position_model.current_price = Decimal("155.00")
        position_model.market_value = Decimal("15500.00")
        position_model.cost_basis = Decimal("15000.00")
        position_model.unrealized_pnl = Decimal("500.00")
        position_model.unrealized_pnl_percent = Decimal("3.33")
        position_model.last_updated = datetime.utcnow()
        position_model.created_at = datetime.utcnow()
        
        position = Position.from_model(position_model)
        
        assert position.symbol == "AAPL"
        assert position.quantity == Decimal("100")
        assert position.total_return() == Decimal("3.33")
    
    def test_trade_type(self):
        """Test Trade GraphQL type."""
        trade_model = Mock(spec=TradeModel)
        trade_model.id = 1
        trade_model.user_id = 1
        trade_model.symphony_id = 1
        trade_model.symbol = "AAPL"
        trade_model.side = "buy"
        trade_model.quantity = Decimal("100")
        trade_model.price = Decimal("150.00")
        trade_model.total_value = Decimal("15000.00")
        trade_model.commission = Decimal("0.00")
        trade_model.status = "executed"
        trade_model.alpaca_order_id = "test-order-id"
        trade_model.executed_at = datetime.utcnow()
        trade_model.created_at = datetime.utcnow()
        trade_model.error_message = None
        
        trade = Trade.from_model(trade_model)
        
        assert trade.symbol == "AAPL"
        assert trade.side == "buy"
        assert trade.net_value() == Decimal("15000.00")
    
    def test_portfolio_summary(self):
        """Test PortfolioSummary type."""
        summary = PortfolioSummary(
            total_value=Decimal("100000.00"),
            cash_balance=Decimal("20000.00"),
            positions_value=Decimal("80000.00"),
            daily_pnl=Decimal("1000.00"),
            daily_pnl_percent=Decimal("1.01"),
            total_pnl=Decimal("5000.00"),
            total_pnl_percent=Decimal("5.26"),
            position_count=10
        )
        
        assert summary.cash_percentage() == Decimal("20.00")
        assert summary.invested_percentage() == Decimal("80.00")


class TestTradingService:
    """Test trading service functionality."""
    
    @pytest.fixture
    def trading_service(self):
        """Create trading service instance."""
        service = TradingService()
        service.market_data = AsyncMock()
        return service
    
    def test_create_position(self, trading_service):
        """Test creating a new position."""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        
        user = Mock(id=1)
        
        position = trading_service.create_or_update_position(
            db=db,
            user=user,
            symphony_id=1,
            symbol="AAPL",
            quantity=Decimal("100"),
            price=Decimal("150.00")
        )
        
        assert db.add.called
        assert db.commit.called
    
    def test_update_position(self, trading_service):
        """Test updating an existing position."""
        existing_position = Mock()
        existing_position.quantity = Decimal("100")
        existing_position.average_price = Decimal("150.00")
        existing_position.cost_basis = Decimal("15000.00")
        
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = existing_position
        db.commit = Mock()
        db.refresh = Mock()
        
        user = Mock(id=1)
        
        position = trading_service.create_or_update_position(
            db=db,
            user=user,
            symphony_id=1,
            symbol="AAPL",
            quantity=Decimal("50"),  # Adding 50 more shares
            price=Decimal("160.00")
        )
        
        assert existing_position.quantity == Decimal("150")  # 100 + 50
        assert db.commit.called
    
    def test_record_trade(self, trading_service):
        """Test recording a trade."""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        
        user = Mock(id=1)
        
        # Mock position update
        trading_service.create_or_update_position = Mock()
        
        trade = trading_service.record_trade(
            db=db,
            user=user,
            symphony_id=1,
            symbol="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            status="executed"
        )
        
        assert db.add.called
        assert db.commit.called
        assert trading_service.create_or_update_position.called
    
    def test_calculate_portfolio_value(self, trading_service):
        """Test portfolio value calculation."""
        positions = [
            Mock(market_value=Decimal("10000.00")),
            Mock(market_value=Decimal("20000.00")),
            Mock(market_value=Decimal("30000.00"))
        ]
        
        db = Mock()
        user = Mock(id=1)
        
        trading_service.get_positions = Mock(return_value=positions)
        
        total, positions_value, cash_pct = trading_service.calculate_portfolio_value(
            db=db,
            user=user,
            cash_balance=Decimal("40000.00")
        )
        
        assert total == Decimal("100000.00")  # 60k positions + 40k cash
        assert positions_value == Decimal("60000.00")
        assert cash_pct == Decimal("40.00")
    
    def test_close_all_positions(self, trading_service):
        """Test closing all positions."""
        positions = [
            Mock(
                symbol="AAPL",
                quantity=Decimal("100"),
                current_price=Decimal("150.00")
            ),
            Mock(
                symbol="GOOGL",
                quantity=Decimal("50"),
                current_price=Decimal("2500.00")
            )
        ]
        
        db = Mock()
        user = Mock(id=1)
        
        trading_service.get_positions = Mock(return_value=positions)
        trading_service.record_trade = Mock()
        
        trades = trading_service.close_all_positions(
            db=db,
            user=user,
            symphony_id=1,
            reason="Test liquidation"
        )
        
        assert len(trades) == 2
        assert trading_service.record_trade.call_count == 2


class TestAlpacaTradingService:
    """Test Alpaca trading service."""
    
    @pytest.mark.asyncio
    async def test_calculate_rebalancing_orders(self):
        """Test rebalancing order calculation."""
        from app.services.alpaca_trading_service import AlpacaTradingService
        
        service = AlpacaTradingService()
        
        total_equity = Decimal("100000.00")
        current_positions = {
            "AAPL": {
                "quantity": Decimal("100"),
                "market_value": Decimal("15000.00"),
                "current_price": Decimal("150.00")
            },
            "GOOGL": {
                "quantity": Decimal("10"),
                "market_value": Decimal("25000.00"),
                "current_price": Decimal("2500.00")
            }
        }
        target_allocations = {
            "AAPL": Decimal("20"),  # 20% = $20,000 (need +$5,000)
            "MSFT": Decimal("30"),  # 30% = $30,000 (new position)
            # GOOGL not in target, so should be sold
        }
        
        orders = service._calculate_rebalancing_orders(
            total_equity,
            current_positions,
            target_allocations
        )
        
        # Should buy more AAPL
        assert "AAPL" in orders
        assert orders["AAPL"]["quantity"] > 0
        
        # Should buy MSFT
        assert "MSFT" in orders
        
        # Should sell all GOOGL
        assert "GOOGL" in orders
        assert orders["GOOGL"]["quantity"] < 0


class TestErrorHandlerService:
    """Test error handler service."""
    
    @pytest.mark.asyncio
    async def test_should_liquidate(self):
        """Test liquidation decision logic."""
        from app.services.error_handler_service import ErrorHandlerService
        
        service = ErrorHandlerService()
        
        # Critical errors should always liquidate
        assert service.should_liquidate("algorithm_exception")
        assert service.should_liquidate("market_data_unavailable")
        
        # Threshold errors need multiple occurrences
        assert not service.should_liquidate("order_rejected", error_count=1)
        assert not service.should_liquidate("order_rejected", error_count=2)
        assert service.should_liquidate("order_rejected", error_count=3)
    
    @pytest.mark.asyncio
    async def test_handle_symphony_error(self):
        """Test symphony error handling."""
        from app.services.error_handler_service import ErrorHandlerService
        
        service = ErrorHandlerService()
        
        db = Mock()
        db.commit = Mock()
        
        user = Mock(id=1)
        symphony = Mock(id=1, status="active")
        error = Exception("Test error")
        
        # Mock alpaca trading service
        with pytest.mock.patch(
            "app.services.error_handler_service.alpaca_trading_service"
        ) as mock_alpaca:
            mock_alpaca.close_all_positions = AsyncMock(return_value=[
                Mock(total_value=Decimal("10000.00")),
                Mock(total_value=Decimal("5000.00"))
            ])
            
            event = await service.handle_symphony_error(
                db=db,
                user=user,
                symphony=symphony,
                error=error,
                liquidate=True
            )
            
            assert symphony.status == "error"
            assert symphony.last_error == "Test error"
            assert event is not None
            assert event.total_value == Decimal("15000.00")
            assert event.positions_closed == 2

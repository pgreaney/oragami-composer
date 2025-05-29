"""Trading GraphQL types (Position, Trade, PerformanceMetric)."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import strawberry
from strawberry.types import Info

from app.graphql.context import GraphQLContext
from app.models.position import Position as PositionModel
from app.models.trade import Trade as TradeModel
from app.models.performance import PerformanceMetric as PerformanceModel


@strawberry.type
class Position:
    """Current position in an asset."""
    
    id: int
    user_id: int
    symphony_id: int
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    cost_basis: Decimal
    last_updated: datetime
    created_at: datetime
    
    @strawberry.field
    def total_return(self) -> Decimal:
        """Calculate total return percentage."""
        if self.cost_basis == 0:
            return Decimal("0")
        return ((self.market_value - self.cost_basis) / self.cost_basis) * 100
    
    @strawberry.field
    def weight(self, info: Info[GraphQLContext]) -> Optional[Decimal]:
        """Calculate position weight in portfolio."""
        # Would calculate based on total portfolio value
        # For now, return None
        return None
    
    @classmethod
    def from_model(cls, position: PositionModel) -> 'Position':
        """Convert SQLAlchemy model to GraphQL type."""
        return cls(
            id=position.id,
            user_id=position.user_id,
            symphony_id=position.symphony_id,
            symbol=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price,
            current_price=position.current_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_percent=position.unrealized_pnl_percent,
            cost_basis=position.cost_basis,
            last_updated=position.last_updated,
            created_at=position.created_at
        )


@strawberry.type
class Trade:
    """Executed trade record."""
    
    id: int
    user_id: int
    symphony_id: int
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    commission: Decimal
    status: str
    alpaca_order_id: Optional[str] = None
    executed_at: datetime
    created_at: datetime
    error_message: Optional[str] = None
    
    @strawberry.field
    def net_value(self) -> Decimal:
        """Calculate net value after commission."""
        if self.side == "buy":
            return self.total_value + self.commission
        else:
            return self.total_value - self.commission
    
    @classmethod
    def from_model(cls, trade: TradeModel) -> 'Trade':
        """Convert SQLAlchemy model to GraphQL type."""
        return cls(
            id=trade.id,
            user_id=trade.user_id,
            symphony_id=trade.symphony_id,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=trade.price,
            total_value=trade.total_value,
            commission=trade.commission,
            status=trade.status,
            alpaca_order_id=trade.alpaca_order_id,
            executed_at=trade.executed_at,
            created_at=trade.created_at,
            error_message=trade.error_message
        )


@strawberry.type
class PerformanceMetric:
    """Performance metrics for a portfolio or symphony."""
    
    id: int
    user_id: int
    symphony_id: Optional[int] = None
    date: datetime
    total_value: Decimal
    daily_return: Decimal
    cumulative_return: Decimal
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    volatility: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    profit_factor: Optional[Decimal] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    @strawberry.field
    def annualized_return(self) -> Optional[Decimal]:
        """Calculate annualized return."""
        # Simplified calculation
        if self.cumulative_return:
            # Assuming daily data
            return self.cumulative_return * Decimal("252")
        return None
    
    @classmethod
    def from_model(cls, metric: PerformanceModel) -> 'PerformanceMetric':
        """Convert SQLAlchemy model to GraphQL type."""
        return cls(
            id=metric.id,
            user_id=metric.user_id,
            symphony_id=metric.symphony_id,
            date=metric.date,
            total_value=metric.total_value,
            daily_return=metric.daily_return,
            cumulative_return=metric.cumulative_return,
            sharpe_ratio=metric.sharpe_ratio,
            max_drawdown=metric.max_drawdown,
            volatility=metric.volatility,
            win_rate=metric.win_rate,
            profit_factor=metric.profit_factor,
            total_trades=metric.total_trades,
            winning_trades=metric.winning_trades,
            losing_trades=metric.losing_trades
        )


@strawberry.type
class PortfolioSummary:
    """Overall portfolio summary."""
    
    total_value: Decimal
    cash_balance: Decimal
    positions_value: Decimal
    daily_pnl: Decimal
    daily_pnl_percent: Decimal
    total_pnl: Decimal
    total_pnl_percent: Decimal
    position_count: int
    
    @strawberry.field
    def cash_percentage(self) -> Decimal:
        """Calculate cash percentage of portfolio."""
        if self.total_value == 0:
            return Decimal("100")
        return (self.cash_balance / self.total_value) * 100
    
    @strawberry.field
    def invested_percentage(self) -> Decimal:
        """Calculate invested percentage of portfolio."""
        if self.total_value == 0:
            return Decimal("0")
        return (self.positions_value / self.total_value) * 100


@strawberry.type
class TradingError:
    """Trading operation error."""
    
    code: str
    message: str
    symbol: Optional[str] = None
    symphony_id: Optional[int] = None
    timestamp: datetime = strawberry.field(default_factory=datetime.utcnow)


@strawberry.type
class ExecutionResult:
    """Result of a trading execution."""
    
    success: bool
    symphony_id: int
    trades: List[Trade]
    errors: List[TradingError]
    execution_time: datetime
    
    @strawberry.field
    def trade_count(self) -> int:
        """Get number of trades executed."""
        return len(self.trades)
    
    @strawberry.field
    def error_count(self) -> int:
        """Get number of errors."""
        return len(self.errors)


@strawberry.type
class PositionUpdate:
    """Real-time position update."""
    
    position: Position
    action: str  # 'created', 'updated', 'closed'
    timestamp: datetime


@strawberry.type
class TradeUpdate:
    """Real-time trade update."""
    
    trade: Trade
    timestamp: datetime


@strawberry.type
class PerformanceUpdate:
    """Real-time performance update."""
    
    metric: PerformanceMetric
    timestamp: datetime


@strawberry.type
class LiquidationEvent:
    """Liquidation event due to error."""
    
    symphony_id: int
    reason: str
    positions_closed: int
    total_value: Decimal
    timestamp: datetime
    error_details: Optional[str] = None

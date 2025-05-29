"""
Trade model for tracking executed trades
TimescaleDB hypertable for time-series trade data
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.models import BaseModel


class TradeSide(enum.Enum):
    """
    Trade side enumeration
    
    Values:
        BUY: Purchase of securities
        SELL: Sale of securities
    """
    BUY = "buy"
    SELL = "sell"


class TradeStatus(enum.Enum):
    """
    Trade execution status enumeration
    
    Values:
        PENDING: Trade submitted but not yet executed
        FILLED: Trade successfully executed
        PARTIAL: Trade partially filled
        CANCELLED: Trade cancelled before execution
        REJECTED: Trade rejected by broker
    """
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Trade(BaseModel):
    """
    Trade model for tracking all executed trades
    
    This table is configured as a TimescaleDB hypertable for efficient
    time-series queries. Tracks every trade execution for audit trail
    and performance analysis. Includes algorithm decision data for
    understanding why trades were made.
    
    Attributes:
        symphony_id: Foreign key to Symphony model
        symbol: Stock/ETF ticker symbol
        side: Trade direction (buy/sell)
        quantity: Number of shares traded
        price: Execution price per share
        commission: Trading commission/fees
        status: Trade execution status
        order_id: Alpaca order ID for tracking
        filled_at: Actual execution timestamp
        submitted_at: Order submission timestamp
        algorithm_decision: JSON data explaining trade decision
        
    Relationships:
        symphony: Many-to-one relationship with Symphony model
    
    Indexes:
        - Composite index on (symphony_id, executed_at) for time-series queries
        - Index on symbol for asset-based queries
        - Index on order_id for order tracking
    """
    __tablename__ = "trades"
    
    # Foreign keys
    symphony_id = Column(
        UUID(as_uuid=True),
        ForeignKey("symphonies.id"),
        nullable=False
    )
    
    # Trade data
    symbol = Column(String(20), nullable=False)
    side = Column(Enum(TradeSide), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0, nullable=False)
    status = Column(
        Enum(TradeStatus),
        default=TradeStatus.PENDING,
        nullable=False
    )
    
    # Order tracking
    order_id = Column(String(100), unique=True, nullable=True, index=True)
    
    # Timestamps
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(  # Primary time dimension for TimescaleDB
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Algorithm decision tracking
    algorithm_decision = Column(JSONB, nullable=True)
    rebalance_reason = Column(Text, nullable=True)
    
    # Relationships
    symphony = relationship("Symphony", back_populates="trades")
    
    # Indexes for efficient queries
    __table_args__ = (
        # Composite index for time-series queries by symphony
        Index(
            "idx_trades_symphony_executed",
            "symphony_id",
            "executed_at",
            postgresql_using="btree"
        ),
        # Index for symbol-based queries
        Index(
            "idx_trades_symbol",
            "symbol",
            postgresql_using="btree"
        ),
        # This will be converted to TimescaleDB hypertable
        {"timescaledb_hypertable": True}
    )
    
    def __repr__(self):
        """String representation of Trade object"""
        return (
            f"<Trade(symbol='{self.symbol}', side={self.side.value}, "
            f"quantity={self.quantity}, price={self.price}, status={self.status.value})>"
        )
    
    @property
    def total_value(self) -> float:
        """
        Calculate total trade value including commission
        
        Returns:
            float: Total trade value
        """
        base_value = self.quantity * self.price
        if self.side == TradeSide.BUY:
            return base_value + self.commission
        else:
            return base_value - self.commission
    
    @property
    def is_complete(self) -> bool:
        """
        Check if trade is complete
        
        Returns:
            bool: True if trade is filled
        """
        return self.status == TradeStatus.FILLED
    
    @property
    def algorithm_summary(self) -> dict:
        """
        Extract summary from algorithm decision data
        
        Returns:
            dict: Summary of why trade was made
        """
        if not self.algorithm_decision:
            return {}
        
        return {
            "trigger": self.algorithm_decision.get("trigger", "unknown"),
            "conditions_met": self.algorithm_decision.get("conditions_met", []),
            "target_weight": self.algorithm_decision.get("target_weight", 0),
            "current_weight": self.algorithm_decision.get("current_weight", 0),
            "rebalance_type": self.algorithm_decision.get("rebalance_type", "unknown")
        }
    
    def to_dict(self) -> dict:
        """
        Convert trade to dictionary for API responses
        
        Returns:
            dict: Trade data suitable for JSON serialization
        """
        return {
            "id": str(self.id),
            "symphony_id": str(self.symphony_id),
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "commission": round(self.commission, 2),
            "total_value": round(self.total_value, 2),
            "status": self.status.value,
            "order_id": self.order_id,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "executed_at": self.executed_at.isoformat(),
            "algorithm_summary": self.algorithm_summary,
            "rebalance_reason": self.rebalance_reason
        }

"""
Position model for tracking portfolio holdings
TimescaleDB hypertable for time-series position data
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models import BaseModel


class Position(BaseModel):
    """
    Position model for tracking real-time portfolio holdings
    
    This table is configured as a TimescaleDB hypertable for efficient
    time-series queries. Tracks positions for each symphony over time,
    enabling historical position analysis and performance calculations.
    
    Attributes:
        symphony_id: Foreign key to Symphony model
        symbol: Stock/ETF ticker symbol
        quantity: Number of shares held
        average_cost: Average purchase price per share
        current_price: Latest market price per share
        market_value: Total position value (quantity * current_price)
        cost_basis: Total cost of position (quantity * average_cost)
        unrealized_pnl: Unrealized profit/loss
        unrealized_pnl_percent: Unrealized P&L as percentage
        weight: Position weight in portfolio (0-100)
        timestamp: Time of position snapshot
        
    Relationships:
        symphony: Many-to-one relationship with Symphony model
    
    Indexes:
        - Composite index on (symphony_id, timestamp) for time-series queries
        - Index on symbol for asset-based queries
    """
    __tablename__ = "positions"
    
    # Foreign keys
    symphony_id = Column(
        UUID(as_uuid=True),
        ForeignKey("symphonies.id"),
        nullable=False
    )
    
    # Position data
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    average_cost = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    unrealized_pnl_percent = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)  # Portfolio weight percentage
    
    # Time-series field - primary dimension for TimescaleDB
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Relationships
    symphony = relationship("Symphony", back_populates="positions")
    
    # Indexes for efficient queries
    __table_args__ = (
        # Composite index for time-series queries by symphony
        Index(
            "idx_positions_symphony_timestamp",
            "symphony_id",
            "timestamp",
            postgresql_using="btree"
        ),
        # Index for symbol-based queries
        Index(
            "idx_positions_symbol",
            "symbol",
            postgresql_using="btree"
        ),
        # This will be converted to TimescaleDB hypertable
        {"timescaledb_hypertable": True}
    )
    
    def __repr__(self):
        """String representation of Position object"""
        return (
            f"<Position(symbol='{self.symbol}', quantity={self.quantity}, "
            f"market_value={self.market_value}, timestamp={self.timestamp})>"
        )
    
    @property
    def total_return(self) -> float:
        """
        Calculate total return including realized and unrealized gains
        
        Returns:
            float: Total return amount
        """
        return self.unrealized_pnl
    
    @property
    def is_profitable(self) -> bool:
        """
        Check if position is currently profitable
        
        Returns:
            bool: True if unrealized P&L is positive
        """
        return self.unrealized_pnl > 0
    
    def to_dict(self) -> dict:
        """
        Convert position to dictionary for API responses
        
        Returns:
            dict: Position data suitable for JSON serialization
        """
        return {
            "id": str(self.id),
            "symphony_id": str(self.symphony_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "average_cost": round(self.average_cost, 2),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "cost_basis": round(self.cost_basis, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_percent": round(self.unrealized_pnl_percent, 2),
            "weight": round(self.weight, 2),
            "timestamp": self.timestamp.isoformat(),
            "is_profitable": self.is_profitable
        }

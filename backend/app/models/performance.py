"""
Performance metrics model for tracking quantstats calculations
TimescaleDB hypertable for time-series performance data
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.models import BaseModel


class MetricType(enum.Enum):
    """
    Performance metric type enumeration
    
    Values represent various quantstats metrics calculated
    for symphony performance analysis
    """
    TOTAL_RETURN = "total_return"
    DAILY_RETURN = "daily_return"
    CUMULATIVE_RETURN = "cumulative_return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_RETURN = "expected_return"
    VALUE_AT_RISK = "value_at_risk"
    BETA = "beta"
    ALPHA = "alpha"
    PORTFOLIO_VALUE = "portfolio_value"


class TimeFrame(enum.Enum):
    """
    Time frame for metric calculation
    
    Values represent the period over which metrics are calculated
    """
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class PerformanceMetric(BaseModel):
    """
    Performance metrics model for tracking quantstats calculations
    
    This table is configured as a TimescaleDB hypertable for efficient
    time-series queries. Stores calculated performance metrics for each
    symphony over time, enabling performance tracking and comparison.
    
    Attributes:
        symphony_id: Foreign key to Symphony model
        metric_type: Type of performance metric
        value: Calculated metric value
        time_frame: Period over which metric was calculated
        benchmark_symbol: Benchmark used for comparison (e.g., SPY)
        benchmark_value: Benchmark's metric value for comparison
        calculated_at: Timestamp of calculation
        
    Relationships:
        symphony: Many-to-one relationship with Symphony model
    
    Indexes:
        - Composite index on (symphony_id, calculated_at) for time-series queries
        - Composite index on (symphony_id, metric_type) for metric queries
    """
    __tablename__ = "performance_metrics"
    
    # Foreign keys
    symphony_id = Column(
        UUID(as_uuid=True),
        ForeignKey("symphonies.id"),
        nullable=False
    )
    
    # Metric data
    metric_type = Column(Enum(MetricType), nullable=False)
    value = Column(Float, nullable=False)
    time_frame = Column(
        Enum(TimeFrame),
        default=TimeFrame.DAILY,
        nullable=False
    )
    
    # Benchmark comparison
    benchmark_symbol = Column(String(20), default="SPY", nullable=False)
    benchmark_value = Column(Float, nullable=True)
    
    # Time-series field - primary dimension for TimescaleDB
    calculated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Additional context
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    symphony = relationship("Symphony", back_populates="performance_metrics")
    
    # Indexes for efficient queries
    __table_args__ = (
        # Composite index for time-series queries by symphony
        Index(
            "idx_performance_symphony_calculated",
            "symphony_id",
            "calculated_at",
            postgresql_using="btree"
        ),
        # Composite index for metric type queries
        Index(
            "idx_performance_symphony_metric",
            "symphony_id",
            "metric_type",
            postgresql_using="btree"
        ),
        # This will be converted to TimescaleDB hypertable
        {"timescaledb_hypertable": True}
    )
    
    def __repr__(self):
        """String representation of PerformanceMetric object"""
        return (
            f"<PerformanceMetric(type={self.metric_type.value}, value={self.value}, "
            f"time_frame={self.time_frame.value}, calculated_at={self.calculated_at})>"
        )
    
    @property
    def is_positive(self) -> bool:
        """
        Check if metric indicates positive performance
        
        Returns:
            bool: True if metric is positive (context-dependent)
        """
        # Metrics where higher is better
        positive_metrics = [
            MetricType.TOTAL_RETURN,
            MetricType.DAILY_RETURN,
            MetricType.CUMULATIVE_RETURN,
            MetricType.SHARPE_RATIO,
            MetricType.SORTINO_RATIO,
            MetricType.CALMAR_RATIO,
            MetricType.WIN_RATE,
            MetricType.PROFIT_FACTOR,
            MetricType.EXPECTED_RETURN,
            MetricType.ALPHA,
            MetricType.PORTFOLIO_VALUE
        ]
        
        if self.metric_type in positive_metrics:
            return self.value > 0
        
        # Metrics where lower is better (invert logic)
        if self.metric_type in [MetricType.MAX_DRAWDOWN, MetricType.VALUE_AT_RISK]:
            return self.value > -0.2  # Less than 20% drawdown/VaR is acceptable
        
        # Volatility - moderate is best
        if self.metric_type == MetricType.VOLATILITY:
            return 0.1 <= self.value <= 0.3  # 10-30% annualized volatility
        
        return True
    
    @property
    def outperforms_benchmark(self) -> bool:
        """
        Check if metric outperforms benchmark
        
        Returns:
            bool: True if performance exceeds benchmark
        """
        if self.benchmark_value is None:
            return None
        
        # For most metrics, higher is better
        if self.metric_type not in [MetricType.MAX_DRAWDOWN, MetricType.VALUE_AT_RISK]:
            return self.value > self.benchmark_value
        else:
            # For drawdown and VaR, less negative is better
            return self.value > self.benchmark_value
    
    def to_dict(self) -> dict:
        """
        Convert metric to dictionary for API responses
        
        Returns:
            dict: Metric data suitable for JSON serialization
        """
        return {
            "id": str(self.id),
            "symphony_id": str(self.symphony_id),
            "metric_type": self.metric_type.value,
            "value": round(self.value, 4),
            "time_frame": self.time_frame.value,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_value": round(self.benchmark_value, 4) if self.benchmark_value else None,
            "calculated_at": self.calculated_at.isoformat(),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "is_positive": self.is_positive,
            "outperforms_benchmark": self.outperforms_benchmark
        }

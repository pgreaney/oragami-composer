"""
Backtest model for storing historical algorithm simulation results
Tracks backtest runs with performance metrics and decision paths
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Date, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models import BaseModel


class Backtest(BaseModel):
    """
    Backtest model for historical strategy simulation results
    
    Stores results from backtesting symphonies against historical data
    from 2007 to present. Includes complete algorithm decision history,
    performance metrics, and comparison data for live vs. backtest analysis.
    
    Attributes:
        symphony_id: Foreign key to Symphony model
        name: User-friendly backtest name
        description: Optional description of backtest parameters
        start_date: Backtest period start date
        end_date: Backtest period end date
        initial_capital: Starting portfolio value
        final_value: Ending portfolio value
        total_return: Overall return percentage
        algorithm_decisions: Complete decision tree history
        performance_summary: Calculated performance metrics
        execution_time_seconds: Time taken to run backtest
        completed_at: Timestamp when backtest finished
        
    Relationships:
        symphony: Many-to-one relationship with Symphony model
    """
    __tablename__ = "backtests"
    
    # Foreign keys
    symphony_id = Column(
        UUID(as_uuid=True),
        ForeignKey("symphonies.id"),
        nullable=False,
        index=True
    )
    
    # Backtest metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Backtest parameters
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Float, default=100000.0, nullable=False)
    
    # Results
    final_value = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)
    total_trades = Column(Float, default=0, nullable=False)
    
    # Algorithm decision history
    algorithm_decisions = Column(JSONB, nullable=False)
    
    # Performance metrics summary
    performance_summary = Column(JSONB, nullable=False)
    
    # Execution tracking
    execution_time_seconds = Column(Float, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    symphony = relationship("Symphony", back_populates="backtests")
    
    def __repr__(self):
        """String representation of Backtest object"""
        return (
            f"<Backtest(name='{self.name}', symphony_id={self.symphony_id}, "
            f"total_return={self.total_return:.2%}, period={self.start_date} to {self.end_date})>"
        )
    
    @property
    def return_percentage(self) -> float:
        """
        Calculate return as percentage
        
        Returns:
            float: Return percentage (e.g., 0.15 for 15%)
        """
        return ((self.final_value - self.initial_capital) / self.initial_capital)
    
    @property
    def annualized_return(self) -> float:
        """
        Calculate annualized return
        
        Returns:
            float: Annualized return percentage
        """
        if not self.start_date or not self.end_date:
            return 0.0
        
        days = (self.end_date - self.start_date).days
        if days <= 0:
            return 0.0
        
        years = days / 365.25
        return ((self.final_value / self.initial_capital) ** (1 / years)) - 1
    
    @property
    def metrics_summary(self) -> dict:
        """
        Extract key metrics from performance summary
        
        Returns:
            dict: Key performance metrics
        """
        if not self.performance_summary:
            return {}
        
        return {
            "sharpe_ratio": self.performance_summary.get("sharpe_ratio", 0),
            "max_drawdown": self.performance_summary.get("max_drawdown", 0),
            "volatility": self.performance_summary.get("volatility", 0),
            "win_rate": self.performance_summary.get("win_rate", 0),
            "sortino_ratio": self.performance_summary.get("sortino_ratio", 0),
            "calmar_ratio": self.performance_summary.get("calmar_ratio", 0),
            "total_trades": self.total_trades,
            "annualized_return": round(self.annualized_return * 100, 2)
        }
    
    @property
    def decision_summary(self) -> dict:
        """
        Extract summary statistics from algorithm decisions
        
        Returns:
            dict: Decision statistics
        """
        if not self.algorithm_decisions:
            return {}
        
        decisions = self.algorithm_decisions.get("decisions", [])
        
        # Count different types of decisions
        rebalance_count = len(decisions)
        conditional_decisions = sum(
            1 for d in decisions if d.get("type") == "conditional"
        )
        filter_decisions = sum(
            1 for d in decisions if d.get("type") == "filter"
        )
        
        # Extract unique assets traded
        all_assets = set()
        for decision in decisions:
            assets = decision.get("selected_assets", [])
            all_assets.update(assets)
        
        return {
            "total_rebalances": rebalance_count,
            "conditional_decisions": conditional_decisions,
            "filter_decisions": filter_decisions,
            "unique_assets_traded": len(all_assets),
            "assets_list": sorted(list(all_assets))
        }
    
    def to_dict(self) -> dict:
        """
        Convert backtest to dictionary for API responses
        
        Returns:
            dict: Backtest data suitable for JSON serialization
        """
        return {
            "id": str(self.id),
            "symphony_id": str(self.symphony_id),
            "name": self.name,
            "description": self.description,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_value": round(self.final_value, 2),
            "total_return": round(self.total_return * 100, 2),  # As percentage
            "annualized_return": round(self.annualized_return * 100, 2),
            "metrics_summary": self.metrics_summary,
            "decision_summary": self.decision_summary,
            "execution_time_seconds": self.execution_time_seconds,
            "completed_at": self.completed_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }
    
    def get_decision_at_date(self, date: Date) -> dict:
        """
        Get algorithm decision for a specific date
        
        Args:
            date: Date to query
            
        Returns:
            dict: Decision data for that date or empty dict
        """
        if not self.algorithm_decisions:
            return {}
        
        decisions = self.algorithm_decisions.get("decisions", [])
        for decision in decisions:
            decision_date = decision.get("date")
            if decision_date and decision_date == date.isoformat():
                return decision
        
        return {}

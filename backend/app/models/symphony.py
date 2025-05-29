"""
Symphony model for storing Composer.trade algorithmic strategies
Manages complex JSON algorithm data and execution status
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.models import BaseModel


class SymphonyStatus(enum.Enum):
    """
    Symphony execution status enumeration
    
    Values:
        ACTIVE: Symphony is actively executing trades
        INACTIVE: Symphony is uploaded but not executing
        STOPPED: Symphony execution was stopped by user or error
        ERROR: Symphony encountered an error during execution
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    STOPPED = "stopped"
    ERROR = "error"


class Symphony(BaseModel):
    """
    Symphony model for algorithmic trading strategies
    
    Stores Composer.trade JSON files containing complex algorithmic
    logic including conditional statements, technical indicators,
    asset filtering, and rebalancing schedules. Supports up to 40
    symphonies per user.
    
    Attributes:
        user_id: Foreign key to User model
        name: User-friendly symphony name
        description: Optional description of strategy
        status: Current execution status (active/inactive/stopped/error)
        json_data: Complete algorithm JSON from Composer.trade
        original_filename: Original uploaded filename for reference
        version: Symphony version for tracking changes
        last_executed_at: Timestamp of last successful execution
        next_execution_at: Scheduled next execution time
        execution_count: Total number of successful executions
        error_message: Last error message if status is ERROR
        is_deleted: Soft delete flag
        
    Relationships:
        user: Many-to-one relationship with User model
        positions: One-to-many relationship with Position model
        trades: One-to-many relationship with Trade model
        performance_metrics: One-to-many relationship with PerformanceMetric
        backtests: One-to-many relationship with Backtest model
    """
    __tablename__ = "symphonies"
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Symphony metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(SymphonyStatus),
        default=SymphonyStatus.INACTIVE,
        nullable=False,
        index=True
    )
    
    # Algorithm data - stores complete Composer.trade JSON
    json_data = Column(JSONB, nullable=False)
    original_filename = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    
    # Execution tracking
    last_executed_at = Column(DateTime(timezone=True), nullable=True)
    next_execution_at = Column(DateTime(timezone=True), nullable=True)
    execution_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="symphonies")
    positions = relationship(
        "Position",
        back_populates="symphony",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    trades = relationship(
        "Trade",
        back_populates="symphony",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    performance_metrics = relationship(
        "PerformanceMetric",
        back_populates="symphony",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    backtests = relationship(
        "Backtest",
        back_populates="symphony",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self):
        """String representation of Symphony object"""
        return f"<Symphony(name='{self.name}', status={self.status.value}, user_id={self.user_id})>"
    
    @property
    def is_active(self) -> bool:
        """
        Check if symphony is actively executing
        
        Returns:
            bool: True if status is ACTIVE
        """
        return self.status == SymphonyStatus.ACTIVE
    
    @property
    def can_execute(self) -> bool:
        """
        Check if symphony can be executed
        
        Returns:
            bool: True if symphony is not deleted and has valid JSON data
        """
        return not self.is_deleted and self.json_data is not None
    
    @property
    def algorithm_summary(self) -> dict:
        """
        Extract summary information from algorithm JSON
        
        Returns:
            dict: Summary with rebalance frequency, asset count, etc.
        """
        if not self.json_data:
            return {}
        
        return {
            "rebalance": self.json_data.get("rebalance", "unknown"),
            "step_count": self._count_steps(self.json_data),
            "has_conditionals": self._has_conditionals(self.json_data),
            "uses_technical_indicators": self._uses_technical_indicators(self.json_data)
        }
    
    def _count_steps(self, node: dict, count: int = 0) -> int:
        """Recursively count algorithm steps"""
        if not isinstance(node, dict):
            return count
        
        count += 1
        children = node.get("children", [])
        for child in children:
            count = self._count_steps(child, count)
        
        return count
    
    def _has_conditionals(self, node: dict) -> bool:
        """Check if algorithm uses conditional logic"""
        if not isinstance(node, dict):
            return False
        
        if node.get("step") == "if":
            return True
        
        children = node.get("children", [])
        for child in children:
            if self._has_conditionals(child):
                return True
        
        return False
    
    def _uses_technical_indicators(self, node: dict) -> bool:
        """Check if algorithm uses technical indicators"""
        if not isinstance(node, dict):
            return False
        
        # Check for indicator functions
        indicator_funcs = [
            "relative-strength-index",
            "moving-average-price",
            "exponential-moving-average-price",
            "standard-deviation",
            "max-drawdown"
        ]
        
        for key in ["lhs_fn", "rhs_fn", "sort_by_fn"]:
            if node.get(key) in indicator_funcs:
                return True
        
        children = node.get("children", [])
        for child in children:
            if self._uses_technical_indicators(child):
                return True
        
        return False

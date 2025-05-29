"""
SQLAlchemy model definitions for Origami Composer
This module contains all database models and base configuration
"""

from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Create the declarative base
Base = declarative_base()


class BaseModel(Base):
    """
    Abstract base model that provides common fields for all models
    
    Attributes:
        id: UUID primary key for all tables
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# Import all models to ensure they are registered with SQLAlchemy
from app.models.user import User
from app.models.symphony import Symphony
from app.models.position import Position
from app.models.trade import Trade
from app.models.performance import PerformanceMetric
from app.models.backtest import Backtest

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Symphony",
    "Position",
    "Trade",
    "PerformanceMetric",
    "Backtest",
]

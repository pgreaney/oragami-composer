"""Alpaca API Pydantic models."""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class OAuthInitResponse(BaseModel):
    """OAuth initialization response."""
    auth_url: str
    message: str = "Redirect user to the authorization URL"


class AlpacaAccountInfo(BaseModel):
    """Alpaca account information."""
    account_number: str
    buying_power: float
    cash: float
    portfolio_value: float
    pattern_day_trader: bool = False
    trading_blocked: bool = False
    account_blocked: bool = False


class AlpacaConnectionStatus(BaseModel):
    """Alpaca connection status."""
    connected: bool
    account_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    account_info: Optional[AlpacaAccountInfo] = None


class AlpacaPosition(BaseModel):
    """Alpaca position model."""
    symbol: str
    qty: float
    side: str
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    lastday_price: float
    change_today: float


class AlpacaOrder(BaseModel):
    """Alpaca order model."""
    id: str
    client_order_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    symbol: str
    qty: float
    filled_qty: float = 0
    side: str  # buy or sell
    type: str  # market, limit, stop, stop_limit
    time_in_force: str  # day, gtc, ioc, fok
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_avg_price: Optional[float] = None
    status: str
    extended_hours: bool = False
    order_class: str = "simple"


class PlaceOrderRequest(BaseModel):
    """Place order request model."""
    symbol: str = Field(..., description="Stock symbol")
    qty: float = Field(..., gt=0, description="Quantity to trade")
    side: str = Field(..., pattern="^(buy|sell)$", description="Buy or sell")
    type: str = Field(
        default="market",
        pattern="^(market|limit|stop|stop_limit)$",
        description="Order type"
    )
    time_in_force: str = Field(
        default="day",
        pattern="^(day|gtc|ioc|fok)$",
        description="Time in force"
    )
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price")
    extended_hours: bool = Field(default=False, description="Allow extended hours")


class PortfolioSnapshot(BaseModel):
    """Portfolio snapshot model."""
    timestamp: datetime
    portfolio_value: float
    cash: float
    positions_value: float
    daily_change: float
    daily_change_percent: float
    total_return: float
    total_return_percent: float


class TradingError(BaseModel):
    """Trading error model."""
    error_type: str
    message: str
    symbol: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None

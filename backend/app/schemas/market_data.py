"""Market data Pydantic models."""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field
from enum import Enum


class DataSource(str, Enum):
    """Available market data sources."""
    ALPHA_VANTAGE = "alpha_vantage"
    EOD_HISTORICAL = "eod_historical"
    ALPACA = "alpaca"
    CACHE = "cache"


class PriceInterval(str, Enum):
    """Price data intervals."""
    MINUTE_1 = "1min"
    MINUTE_5 = "5min"
    MINUTE_15 = "15min"
    MINUTE_30 = "30min"
    MINUTE_60 = "60min"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PriceBar(BaseModel):
    """OHLCV price bar."""
    
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Optional[Decimal] = None
    
    class Config:
        json_encoders = {
            Decimal: str
        }


class Quote(BaseModel):
    """Real-time quote data."""
    
    symbol: str
    timestamp: datetime
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: int
    daily_change: Decimal
    daily_change_percent: Decimal
    source: DataSource
    
    class Config:
        json_encoders = {
            Decimal: str
        }


class HistoricalData(BaseModel):
    """Historical price data."""
    
    symbol: str
    interval: PriceInterval
    bars: List[PriceBar]
    start_date: datetime
    end_date: datetime
    source: DataSource
    
    def get_prices(self) -> List[float]:
        """Get closing prices as list (newest first)."""
        return [float(bar.close) for bar in reversed(self.bars)]
    
    def get_returns(self) -> List[float]:
        """Calculate returns from price bars."""
        prices = self.get_prices()
        returns = []
        
        for i in range(len(prices) - 1):
            if prices[i + 1] != 0:
                ret = (prices[i] - prices[i + 1]) / prices[i + 1]
                returns.append(ret)
        
        return returns


class MarketDataRequest(BaseModel):
    """Request for market data."""
    
    symbols: List[str]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    interval: PriceInterval = PriceInterval.DAILY
    source: Optional[DataSource] = None


class AssetInfo(BaseModel):
    """Basic asset information."""
    
    symbol: str
    name: str
    exchange: str
    asset_type: str  # stock, etf, crypto, etc.
    currency: str = "USD"
    market_cap: Optional[Decimal] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


class MarketStatus(BaseModel):
    """Market status information."""
    
    is_open: bool
    current_time: datetime
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    timezone: str = "America/New_York"


class DataCacheEntry(BaseModel):
    """Cache entry for market data."""
    
    key: str
    data: Any
    timestamp: datetime
    ttl_seconds: int
    source: DataSource
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl_seconds


class MarketDataError(BaseModel):
    """Market data error response."""
    
    error: str
    symbol: Optional[str] = None
    source: Optional[DataSource] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

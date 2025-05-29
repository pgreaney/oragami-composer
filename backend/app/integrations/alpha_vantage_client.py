"""Alpha Vantage API client."""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
import asyncio
from urllib.parse import urlencode

from app.config import settings
from app.schemas.market_data import (
    PriceBar,
    Quote,
    HistoricalData,
    AssetInfo,
    DataSource,
    PriceInterval
)


class AlphaVantageError(Exception):
    """Alpha Vantage API error."""
    pass


class AlphaVantageClient:
    """Client for Alpha Vantage API (Free tier: 5 calls/minute, 500 calls/day)."""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    # Rate limiting: 5 calls per minute for free tier
    RATE_LIMIT = 5
    RATE_WINDOW = 60  # seconds
    
    # Map our intervals to Alpha Vantage intervals
    INTERVAL_MAPPING = {
        PriceInterval.MINUTE_1: "1min",
        PriceInterval.MINUTE_5: "5min",
        PriceInterval.MINUTE_15: "15min",
        PriceInterval.MINUTE_30: "30min",
        PriceInterval.MINUTE_60: "60min",
        PriceInterval.DAILY: "daily",
        PriceInterval.WEEKLY: "weekly",
        PriceInterval.MONTHLY: "monthly"
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Alpha Vantage client.
        
        Args:
            api_key: Alpha Vantage API key
        """
        self.api_key = api_key or settings.ALPHA_VANTAGE_API_KEY
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not configured")
        
        self.client = httpx.AsyncClient(timeout=30.0)
        self._call_times: List[datetime] = []
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def _rate_limit(self):
        """Enforce rate limiting."""
        now = datetime.utcnow()
        
        # Remove old calls outside the rate window
        self._call_times = [
            t for t in self._call_times 
            if (now - t).total_seconds() < self.RATE_WINDOW
        ]
        
        # If at rate limit, wait
        if len(self._call_times) >= self.RATE_LIMIT:
            oldest_call = min(self._call_times)
            wait_time = self.RATE_WINDOW - (now - oldest_call).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 1)  # Add 1 second buffer
        
        # Record this call
        self._call_times.append(now)
    
    async def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with rate limiting.
        
        Args:
            params: Query parameters
            
        Returns:
            API response data
            
        Raises:
            AlphaVantageError: If API request fails
        """
        await self._rate_limit()
        
        params["apikey"] = self.api_key
        
        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data:
                raise AlphaVantageError(data["Error Message"])
            
            if "Note" in data:
                # Rate limit message
                raise AlphaVantageError("Rate limit reached: " + data["Note"])
            
            return data
            
        except httpx.HTTPError as e:
            raise AlphaVantageError(f"HTTP error: {str(e)}")
        except Exception as e:
            raise AlphaVantageError(f"Request failed: {str(e)}")
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Quote data
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol
        }
        
        data = await self._request(params)
        
        if "Global Quote" not in data:
            raise AlphaVantageError(f"No quote data for {symbol}")
        
        quote_data = data["Global Quote"]
        
        return Quote(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            price=Decimal(quote_data["05. price"]),
            volume=int(quote_data["06. volume"]),
            daily_change=Decimal(quote_data["09. change"]),
            daily_change_percent=Decimal(quote_data["10. change percent"].rstrip("%")),
            source=DataSource.ALPHA_VANTAGE
        )
    
    async def get_daily_data(
        self,
        symbol: str,
        outputsize: str = "compact"
    ) -> HistoricalData:
        """Get daily historical data.
        
        Args:
            symbol: Stock symbol
            outputsize: "compact" (100 days) or "full" (20+ years)
            
        Returns:
            Historical data
        """
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize
        }
        
        data = await self._request(params)
        
        if "Time Series (Daily)" not in data:
            raise AlphaVantageError(f"No daily data for {symbol}")
        
        time_series = data["Time Series (Daily)"]
        bars = []
        
        for date_str, values in time_series.items():
            bar = PriceBar(
                timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
                open=Decimal(values["1. open"]),
                high=Decimal(values["2. high"]),
                low=Decimal(values["3. low"]),
                close=Decimal(values["4. close"]),
                volume=int(values["6. volume"]),
                adjusted_close=Decimal(values["5. adjusted close"])
            )
            bars.append(bar)
        
        # Sort by date (oldest first)
        bars.sort(key=lambda x: x.timestamp)
        
        return HistoricalData(
            symbol=symbol,
            interval=PriceInterval.DAILY,
            bars=bars,
            start_date=bars[0].timestamp if bars else datetime.utcnow(),
            end_date=bars[-1].timestamp if bars else datetime.utcnow(),
            source=DataSource.ALPHA_VANTAGE
        )
    
    async def get_intraday_data(
        self,
        symbol: str,
        interval: PriceInterval = PriceInterval.MINUTE_5,
        outputsize: str = "compact"
    ) -> HistoricalData:
        """Get intraday historical data.
        
        Args:
            symbol: Stock symbol
            interval: Time interval
            outputsize: "compact" (100 points) or "full" (extended)
            
        Returns:
            Historical data
        """
        if interval not in [
            PriceInterval.MINUTE_1,
            PriceInterval.MINUTE_5,
            PriceInterval.MINUTE_15,
            PriceInterval.MINUTE_30,
            PriceInterval.MINUTE_60
        ]:
            raise ValueError("Invalid interval for intraday data")
        
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": self.INTERVAL_MAPPING[interval],
            "outputsize": outputsize
        }
        
        data = await self._request(params)
        
        time_series_key = f"Time Series ({self.INTERVAL_MAPPING[interval]})"
        if time_series_key not in data:
            raise AlphaVantageError(f"No intraday data for {symbol}")
        
        time_series = data[time_series_key]
        bars = []
        
        for datetime_str, values in time_series.items():
            bar = PriceBar(
                timestamp=datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S"),
                open=Decimal(values["1. open"]),
                high=Decimal(values["2. high"]),
                low=Decimal(values["3. low"]),
                close=Decimal(values["4. close"]),
                volume=int(values["5. volume"])
            )
            bars.append(bar)
        
        # Sort by date (oldest first)
        bars.sort(key=lambda x: x.timestamp)
        
        return HistoricalData(
            symbol=symbol,
            interval=interval,
            bars=bars,
            start_date=bars[0].timestamp if bars else datetime.utcnow(),
            end_date=bars[-1].timestamp if bars else datetime.utcnow(),
            source=DataSource.ALPHA_VANTAGE
        )
    
    async def search_symbols(self, keywords: str) -> List[AssetInfo]:
        """Search for symbols.
        
        Args:
            keywords: Search keywords
            
        Returns:
            List of matching assets
        """
        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": keywords
        }
        
        data = await self._request(params)
        
        if "bestMatches" not in data:
            return []
        
        assets = []
        for match in data["bestMatches"]:
            asset = AssetInfo(
                symbol=match["1. symbol"],
                name=match["2. name"],
                exchange=match["4. region"],
                asset_type=match["3. type"],
                currency=match["8. currency"]
            )
            assets.append(asset)
        
        return assets
    
    async def get_technical_indicator(
        self,
        symbol: str,
        indicator: str,
        interval: PriceInterval = PriceInterval.DAILY,
        time_period: int = 14,
        series_type: str = "close"
    ) -> Dict[str, Any]:
        """Get technical indicator data.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name (RSI, SMA, EMA, etc.)
            interval: Time interval
            time_period: Period for calculation
            series_type: Price type (close, open, high, low)
            
        Returns:
            Indicator data
        """
        params = {
            "function": indicator.upper(),
            "symbol": symbol,
            "interval": self.INTERVAL_MAPPING[interval],
            "time_period": time_period,
            "series_type": series_type
        }
        
        return await self._request(params)


# Global client instance (to be initialized with API key)
alpha_vantage_client: Optional[AlphaVantageClient] = None


def get_alpha_vantage_client() -> AlphaVantageClient:
    """Get or create Alpha Vantage client."""
    global alpha_vantage_client
    
    if alpha_vantage_client is None:
        alpha_vantage_client = AlphaVantageClient()
    
    return alpha_vantage_client

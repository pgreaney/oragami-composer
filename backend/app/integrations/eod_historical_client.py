"""EOD Historical Data API client."""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
import asyncio

from app.config import settings
from app.schemas.market_data import (
    PriceBar,
    Quote,
    HistoricalData,
    AssetInfo,
    DataSource,
    PriceInterval
)


class EODHistoricalError(Exception):
    """EOD Historical Data API error."""
    pass


class EODHistoricalClient:
    """Client for EOD Historical Data API."""
    
    BASE_URL = "https://eodhistoricaldata.com/api"
    
    # Rate limiting based on plan (adjust based on your subscription)
    RATE_LIMIT = 20  # calls per second for paid plans
    RATE_WINDOW = 1  # seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize EOD Historical Data client.
        
        Args:
            api_key: EOD Historical Data API key
        """
        self.api_key = api_key or settings.EOD_HISTORICAL_API_KEY
        if not self.api_key:
            raise ValueError("EOD Historical Data API key not configured")
        
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
            await asyncio.sleep(0.1)  # Small delay
        
        # Record this call
        self._call_times.append(now)
    
    async def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make API request with rate limiting.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response data
            
        Raises:
            EODHistoricalError: If API request fails
        """
        await self._rate_limit()
        
        if params is None:
            params = {}
        
        params["api_token"] = self.api_key
        params["fmt"] = "json"
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            raise EODHistoricalError(f"HTTP error: {str(e)}")
        except Exception as e:
            raise EODHistoricalError(f"Request failed: {str(e)}")
    
    async def get_realtime_quote(self, symbol: str, exchange: str = "US") -> Quote:
        """Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code (default "US")
            
        Returns:
            Quote data
        """
        endpoint = f"/real-time/{symbol}.{exchange}"
        
        data = await self._request(endpoint)
        
        if not data:
            raise EODHistoricalError(f"No quote data for {symbol}")
        
        return Quote(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
            price=Decimal(str(data["close"])),
            volume=int(data.get("volume", 0)),
            daily_change=Decimal(str(data.get("change", 0))),
            daily_change_percent=Decimal(str(data.get("change_p", 0))),
            source=DataSource.EOD_HISTORICAL
        )
    
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str = "US",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: str = "d"  # d=daily, w=weekly, m=monthly
    ) -> HistoricalData:
        """Get historical price data.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            start_date: Start date for data
            end_date: End date for data
            period: Period (d/w/m)
            
        Returns:
            Historical data
        """
        endpoint = f"/eod/{symbol}.{exchange}"
        
        params = {"period": period}
        
        if start_date:
            params["from"] = start_date.strftime("%Y-%m-%d")
        else:
            # Default to 2 years of data
            params["from"] = (date.today() - timedelta(days=730)).strftime("%Y-%m-%d")
        
        if end_date:
            params["to"] = end_date.strftime("%Y-%m-%d")
        
        data = await self._request(endpoint, params)
        
        if not data:
            raise EODHistoricalError(f"No historical data for {symbol}")
        
        bars = []
        for item in data:
            bar = PriceBar(
                timestamp=datetime.strptime(item["date"], "%Y-%m-%d"),
                open=Decimal(str(item["open"])),
                high=Decimal(str(item["high"])),
                low=Decimal(str(item["low"])),
                close=Decimal(str(item["close"])),
                volume=int(item.get("volume", 0)),
                adjusted_close=Decimal(str(item.get("adjusted_close", item["close"])))
            )
            bars.append(bar)
        
        # Map period to interval
        interval_map = {
            "d": PriceInterval.DAILY,
            "w": PriceInterval.WEEKLY,
            "m": PriceInterval.MONTHLY
        }
        
        return HistoricalData(
            symbol=symbol,
            interval=interval_map.get(period, PriceInterval.DAILY),
            bars=bars,
            start_date=bars[0].timestamp if bars else datetime.utcnow(),
            end_date=bars[-1].timestamp if bars else datetime.utcnow(),
            source=DataSource.EOD_HISTORICAL
        )
    
    async def get_extended_historical_data(
        self,
        symbol: str,
        exchange: str = "US",
        start_date: date = date(2007, 1, 1)  # BIL inception
    ) -> HistoricalData:
        """Get extended historical data back to 2007.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            start_date: Start date (default 2007)
            
        Returns:
            Historical data
        """
        return await self.get_historical_data(
            symbol=symbol,
            exchange=exchange,
            start_date=start_date,
            end_date=date.today(),
            period="d"
        )
    
    async def search_symbols(self, query: str) -> List[AssetInfo]:
        """Search for symbols.
        
        Args:
            query: Search query
            
        Returns:
            List of matching assets
        """
        endpoint = "/search"
        params = {
            "q": query,
            "limit": 50
        }
        
        data = await self._request(endpoint, params)
        
        assets = []
        for item in data:
            asset = AssetInfo(
                symbol=item["Code"],
                name=item["Name"],
                exchange=item["Exchange"],
                asset_type=item.get("Type", "Stock"),
                currency=item.get("Currency", "USD")
            )
            assets.append(asset)
        
        return assets
    
    async def get_exchanges(self) -> List[Dict[str, Any]]:
        """Get list of supported exchanges.
        
        Returns:
            List of exchanges
        """
        endpoint = "/exchanges-list"
        return await self._request(endpoint)
    
    async def get_fundamentals(self, symbol: str, exchange: str = "US") -> Dict[str, Any]:
        """Get fundamental data for a symbol.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            
        Returns:
            Fundamental data
        """
        endpoint = f"/fundamentals/{symbol}.{exchange}"
        return await self._request(endpoint)
    
    async def get_dividends(
        self,
        symbol: str,
        exchange: str = "US",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get dividend history.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            start_date: Start date
            end_date: End date
            
        Returns:
            List of dividends
        """
        endpoint = f"/div/{symbol}.{exchange}"
        
        params = {}
        if start_date:
            params["from"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["to"] = end_date.strftime("%Y-%m-%d")
        
        return await self._request(endpoint, params)
    
    async def get_splits(
        self,
        symbol: str,
        exchange: str = "US",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get stock split history.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            start_date: Start date
            end_date: End date
            
        Returns:
            List of splits
        """
        endpoint = f"/splits/{symbol}.{exchange}"
        
        params = {}
        if start_date:
            params["from"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["to"] = end_date.strftime("%Y-%m-%d")
        
        return await self._request(endpoint, params)
    
    async def get_intraday_data(
        self,
        symbol: str,
        exchange: str = "US",
        interval: str = "5m",
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None
    ) -> HistoricalData:
        """Get intraday data (requires higher tier subscription).
        
        Args:
            symbol: Stock symbol
            exchange: Exchange code
            interval: Time interval (1m, 5m, 1h)
            start_timestamp: Unix timestamp
            end_timestamp: Unix timestamp
            
        Returns:
            Historical intraday data
        """
        endpoint = f"/intraday/{symbol}.{exchange}"
        
        params = {"interval": interval}
        if start_timestamp:
            params["from"] = start_timestamp
        if end_timestamp:
            params["to"] = end_timestamp
        
        data = await self._request(endpoint, params)
        
        bars = []
        for item in data:
            bar = PriceBar(
                timestamp=datetime.fromtimestamp(item["timestamp"]),
                open=Decimal(str(item["open"])),
                high=Decimal(str(item["high"])),
                low=Decimal(str(item["low"])),
                close=Decimal(str(item["close"])),
                volume=int(item.get("volume", 0))
            )
            bars.append(bar)
        
        # Map interval to our enum
        interval_map = {
            "1m": PriceInterval.MINUTE_1,
            "5m": PriceInterval.MINUTE_5,
            "1h": PriceInterval.MINUTE_60
        }
        
        return HistoricalData(
            symbol=symbol,
            interval=interval_map.get(interval, PriceInterval.MINUTE_5),
            bars=bars,
            start_date=bars[0].timestamp if bars else datetime.utcnow(),
            end_date=bars[-1].timestamp if bars else datetime.utcnow(),
            source=DataSource.EOD_HISTORICAL
        )


# Global client instance (to be initialized with API key)
eod_historical_client: Optional[EODHistoricalClient] = None


def get_eod_historical_client() -> EODHistoricalClient:
    """Get or create EOD Historical client."""
    global eod_historical_client
    
    if eod_historical_client is None:
        eod_historical_client = EODHistoricalClient()
    
    return eod_historical_client

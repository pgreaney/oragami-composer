"""Market data service with Alpha Vantage + EOD Historical Data integration."""

from typing import List, Dict, Optional, Any, Set
from datetime import datetime, date, timedelta
from decimal import Decimal
import asyncio
from collections import defaultdict

from app.config import settings
from app.schemas.market_data import (
    Quote,
    HistoricalData,
    AssetInfo,
    MarketStatus,
    DataSource,
    PriceInterval,
    MarketDataRequest,
    MarketDataError
)
from app.integrations.alpha_vantage_client import (
    AlphaVantageClient,
    AlphaVantageError,
    get_alpha_vantage_client
)
from app.integrations.eod_historical_client import (
    EODHistoricalClient,
    EODHistoricalError,
    get_eod_historical_client
)
from app.services.data_cache_service import (
    DataCacheService,
    get_data_cache_service
)
from app.algorithms.indicators import technical_indicators


class MarketDataService:
    """Unified market data service with intelligent source selection and caching."""
    
    # Data source priority for different data types
    QUOTE_SOURCES = [DataSource.EOD_HISTORICAL, DataSource.ALPHA_VANTAGE]
    HISTORICAL_SOURCES = [DataSource.EOD_HISTORICAL, DataSource.ALPHA_VANTAGE]
    INTRADAY_SOURCES = [DataSource.ALPHA_VANTAGE, DataSource.EOD_HISTORICAL]
    
    def __init__(
        self,
        cache_service: Optional[DataCacheService] = None,
        alpha_vantage: Optional[AlphaVantageClient] = None,
        eod_historical: Optional[EODHistoricalClient] = None
    ):
        """Initialize market data service.
        
        Args:
            cache_service: Cache service instance
            alpha_vantage: Alpha Vantage client
            eod_historical: EOD Historical client
        """
        self.cache = cache_service or get_data_cache_service()
        self.alpha_vantage = alpha_vantage
        self.eod_historical = eod_historical
        
        # Track API usage for budgeting
        self._api_calls = defaultdict(int)
        self._last_reset = datetime.utcnow()
    
    async def _get_alpha_vantage(self) -> AlphaVantageClient:
        """Get or create Alpha Vantage client."""
        if self.alpha_vantage is None:
            self.alpha_vantage = get_alpha_vantage_client()
        return self.alpha_vantage
    
    async def _get_eod_historical(self) -> EODHistoricalClient:
        """Get or create EOD Historical client."""
        if self.eod_historical is None:
            self.eod_historical = get_eod_historical_client()
        return self.eod_historical
    
    def _track_api_call(self, source: DataSource):
        """Track API usage for budgeting.
        
        Args:
            source: Data source used
        """
        # Reset daily counters
        now = datetime.utcnow()
        if (now - self._last_reset).days >= 1:
            self._api_calls.clear()
            self._last_reset = now
        
        self._api_calls[source] += 1
    
    async def get_quote(
        self,
        symbol: str,
        source: Optional[DataSource] = None,
        use_cache: bool = True
    ) -> Quote:
        """Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol
            source: Preferred data source
            use_cache: Whether to use cache
            
        Returns:
            Quote data
            
        Raises:
            MarketDataError: If quote cannot be retrieved
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get("quote", symbol, DataSource.CACHE)
            if cached:
                return Quote(**cached)
        
        # Determine sources to try
        sources = [source] if source else self.QUOTE_SOURCES
        
        last_error = None
        for src in sources:
            try:
                if src == DataSource.ALPHA_VANTAGE:
                    client = await self._get_alpha_vantage()
                    quote = await client.get_quote(symbol)
                elif src == DataSource.EOD_HISTORICAL:
                    client = await self._get_eod_historical()
                    quote = await client.get_realtime_quote(symbol)
                else:
                    continue
                
                # Track API usage
                self._track_api_call(src)
                
                # Cache the result
                if use_cache:
                    self.cache.set("quote", symbol, src, quote.dict())
                
                return quote
                
            except Exception as e:
                last_error = e
                continue
        
        raise MarketDataError(
            error=f"Failed to get quote: {str(last_error)}",
            symbol=symbol
        )
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: PriceInterval = PriceInterval.DAILY,
        source: Optional[DataSource] = None,
        use_cache: bool = True
    ) -> HistoricalData:
        """Get historical price data.
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval
            source: Preferred data source
            use_cache: Whether to use cache
            
        Returns:
            Historical data
            
        Raises:
            MarketDataError: If data cannot be retrieved
        """
        # Generate cache key components
        cache_kwargs = {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
            "interval": interval.value
        }
        
        # Check cache first
        if use_cache:
            cached = self.cache.get("historical", symbol, DataSource.CACHE, **cache_kwargs)
            if cached:
                return HistoricalData(**cached)
        
        # Default dates if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=365 if interval == PriceInterval.DAILY else 30)
        
        # Determine sources to try
        if interval in [PriceInterval.MINUTE_1, PriceInterval.MINUTE_5, PriceInterval.MINUTE_15]:
            sources = [source] if source else self.INTRADAY_SOURCES
        else:
            sources = [source] if source else self.HISTORICAL_SOURCES
        
        last_error = None
        for src in sources:
            try:
                if src == DataSource.ALPHA_VANTAGE:
                    client = await self._get_alpha_vantage()
                    if interval == PriceInterval.DAILY:
                        data = await client.get_daily_data(symbol, "full")
                    else:
                        data = await client.get_intraday_data(symbol, interval)
                        
                elif src == DataSource.EOD_HISTORICAL:
                    client = await self._get_eod_historical()
                    data = await client.get_historical_data(
                        symbol,
                        start_date=start_date.date() if start_date else None,
                        end_date=end_date.date() if end_date else None
                    )
                else:
                    continue
                
                # Filter by date range
                if start_date or end_date:
                    filtered_bars = []
                    for bar in data.bars:
                        if start_date and bar.timestamp < start_date:
                            continue
                        if end_date and bar.timestamp > end_date:
                            continue
                        filtered_bars.append(bar)
                    data.bars = filtered_bars
                
                # Track API usage
                self._track_api_call(src)
                
                # Cache the result
                if use_cache:
                    self.cache.set("historical", symbol, src, data.dict(), **cache_kwargs)
                
                return data
                
            except Exception as e:
                last_error = e
                continue
        
        raise MarketDataError(
            error=f"Failed to get historical data: {str(last_error)}",
            symbol=symbol
        )
    
    async def get_extended_historical_data(
        self,
        symbol: str,
        start_date: date = date(2007, 1, 1),
        use_cache: bool = True
    ) -> HistoricalData:
        """Get extended historical data back to 2007 for backtesting.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (default 2007)
            use_cache: Whether to use cache
            
        Returns:
            Historical data
        """
        # EOD Historical is preferred for extended data
        return await self.get_historical_data(
            symbol=symbol,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.utcnow(),
            interval=PriceInterval.DAILY,
            source=DataSource.EOD_HISTORICAL,
            use_cache=use_cache
        )
    
    async def get_batch_quotes(
        self,
        symbols: List[str],
        use_cache: bool = True
    ) -> Dict[str, Quote]:
        """Get quotes for multiple symbols.
        
        Args:
            symbols: List of symbols
            use_cache: Whether to use cache
            
        Returns:
            Dict of symbol -> Quote
        """
        results = {}
        
        # Try cache first
        if use_cache:
            cached = self.cache.batch_get("quote", symbols, DataSource.CACHE)
            for symbol, data in cached.items():
                results[symbol] = Quote(**data)
        
        # Get remaining symbols
        remaining = [s for s in symbols if s not in results]
        
        if remaining:
            # Get quotes concurrently
            tasks = [self.get_quote(symbol, use_cache=False) for symbol in remaining]
            quotes = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, quote in zip(remaining, quotes):
                if isinstance(quote, Quote):
                    results[symbol] = quote
                    if use_cache:
                        self.cache.set("quote", symbol, quote.source, quote.dict())
        
        return results
    
    async def search_symbols(self, query: str) -> List[AssetInfo]:
        """Search for symbols across data sources.
        
        Args:
            query: Search query
            
        Returns:
            List of matching assets
        """
        results = []
        seen_symbols = set()
        
        # Try both sources
        for src in [DataSource.EOD_HISTORICAL, DataSource.ALPHA_VANTAGE]:
            try:
                if src == DataSource.ALPHA_VANTAGE:
                    client = await self._get_alpha_vantage()
                    assets = await client.search_symbols(query)
                elif src == DataSource.EOD_HISTORICAL:
                    client = await self._get_eod_historical()
                    assets = await client.search_symbols(query)
                else:
                    continue
                
                # De-duplicate
                for asset in assets:
                    if asset.symbol not in seen_symbols:
                        seen_symbols.add(asset.symbol)
                        results.append(asset)
                
                # Track API usage
                self._track_api_call(src)
                
            except Exception:
                continue
        
        return results
    
    async def get_market_status(self) -> MarketStatus:
        """Get current market status.
        
        Returns:
            Market status
        """
        now = datetime.utcnow()
        
        # Convert to EST
        est_offset = timedelta(hours=-5)  # EST
        est_time = now + est_offset
        
        # Market hours: 9:30 AM - 4:00 PM EST
        market_open = est_time.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = est_time.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Check if weekend
        if est_time.weekday() >= 5:  # Saturday or Sunday
            is_open = False
            # Next open is Monday 9:30 AM
            days_to_monday = 7 - est_time.weekday()
            next_open = (est_time + timedelta(days=days_to_monday)).replace(
                hour=9, minute=30, second=0, microsecond=0
            )
            next_close = next_open.replace(hour=16, minute=0)
        else:
            # Weekday
            if est_time < market_open:
                is_open = False
                next_open = market_open
                next_close = market_close
            elif est_time > market_close:
                is_open = False
                # Next open is tomorrow (or Monday if Friday)
                if est_time.weekday() == 4:  # Friday
                    next_open = (est_time + timedelta(days=3)).replace(
                        hour=9, minute=30, second=0, microsecond=0
                    )
                else:
                    next_open = (est_time + timedelta(days=1)).replace(
                        hour=9, minute=30, second=0, microsecond=0
                    )
                next_close = next_open.replace(hour=16, minute=0)
            else:
                is_open = True
                next_open = None
                next_close = market_close
        
        return MarketStatus(
            is_open=is_open,
            current_time=now,
            next_open=next_open - est_offset if next_open else None,  # Convert back to UTC
            next_close=next_close - est_offset if next_close else None
        )
    
    async def calculate_indicators(
        self,
        symbol: str,
        indicators: List[str],
        window: int = 20,
        use_cache: bool = True
    ) -> Dict[str, Optional[float]]:
        """Calculate technical indicators for a symbol.
        
        Args:
            symbol: Stock symbol
            indicators: List of indicator names
            window: Lookback window
            use_cache: Whether to use cache
            
        Returns:
            Dict of indicator -> value
        """
        # Get historical data
        data = await self.get_historical_data(
            symbol=symbol,
            interval=PriceInterval.DAILY,
            use_cache=use_cache
        )
        
        prices = data.get_prices()
        returns = data.get_returns()
        
        results = {}
        
        for indicator in indicators:
            if indicator == "sma":
                results[indicator] = technical_indicators.simple_moving_average(prices, window)
            elif indicator == "ema":
                results[indicator] = technical_indicators.exponential_moving_average(prices, window)
            elif indicator == "rsi":
                results[indicator] = technical_indicators.relative_strength_index(prices, window)
            elif indicator == "volatility":
                results[indicator] = technical_indicators.volatility(returns, window)
            elif indicator == "max_drawdown":
                results[indicator] = technical_indicators.max_drawdown(prices, window)
            elif indicator == "cumulative_return":
                results[indicator] = technical_indicators.cumulative_return(prices, window)
            elif indicator == "sharpe_ratio":
                results[indicator] = technical_indicators.sharpe_ratio(returns, window)
            else:
                results[indicator] = None
        
        return results
    
    def get_api_usage(self) -> Dict[str, int]:
        """Get API usage statistics.
        
        Returns:
            Dict of source -> call count
        """
        return dict(self._api_calls)
    
    async def warmup_cache(self, symbols: List[str]):
        """Pre-fetch data for symbols to warm up cache.
        
        Args:
            symbols: List of symbols to cache
        """
        # Get quotes
        await self.get_batch_quotes(symbols)
        
        # Get daily data
        tasks = []
        for symbol in symbols:
            tasks.append(self.get_historical_data(symbol, interval=PriceInterval.DAILY))
        
        await asyncio.gather(*tasks, return_exceptions=True)


# Global service instance
market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Get or create market data service."""
    global market_data_service
    
    if market_data_service is None:
        market_data_service = MarketDataService()
    
    return market_data_service

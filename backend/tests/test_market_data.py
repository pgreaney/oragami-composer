"""Market data service testing."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from app.services.market_data_service import MarketDataService, get_market_data_service
from app.schemas.market_data import (
    Quote,
    HistoricalData,
    PriceBar,
    AssetInfo,
    DataSource,
    PriceInterval,
    MarketStatus
)


class TestMarketDataService:
    """Test market data service functionality."""
    
    @pytest.fixture
    def mock_cache(self):
        """Mock cache service."""
        cache = Mock()
        cache.get = Mock(return_value=None)
        cache.set = Mock(return_value=True)
        cache.batch_get = Mock(return_value={})
        return cache
    
    @pytest.fixture
    def mock_alpha_vantage(self):
        """Mock Alpha Vantage client."""
        client = AsyncMock()
        client.get_quote = AsyncMock(return_value=Quote(
            symbol="AAPL",
            timestamp=datetime.utcnow(),
            price=Decimal("150.00"),
            volume=1000000,
            daily_change=Decimal("2.50"),
            daily_change_percent=Decimal("1.69"),
            source=DataSource.ALPHA_VANTAGE
        ))
        return client
    
    @pytest.fixture
    def mock_eod_historical(self):
        """Mock EOD Historical client."""
        client = AsyncMock()
        client.get_realtime_quote = AsyncMock(return_value=Quote(
            symbol="AAPL",
            timestamp=datetime.utcnow(),
            price=Decimal("150.00"),
            volume=1000000,
            daily_change=Decimal("2.50"),
            daily_change_percent=Decimal("1.69"),
            source=DataSource.EOD_HISTORICAL
        ))
        return client
    
    @pytest.fixture
    def market_data_service(self, mock_cache, mock_alpha_vantage, mock_eod_historical):
        """Create market data service with mocks."""
        return MarketDataService(
            cache_service=mock_cache,
            alpha_vantage=mock_alpha_vantage,
            eod_historical=mock_eod_historical
        )
    
    @pytest.mark.asyncio
    async def test_get_quote_from_cache(self, market_data_service, mock_cache):
        """Test getting quote from cache."""
        # Setup cache to return data
        cached_quote = {
            "symbol": "AAPL",
            "timestamp": datetime.utcnow().isoformat(),
            "price": "150.00",
            "volume": 1000000,
            "daily_change": "2.50",
            "daily_change_percent": "1.69",
            "source": "cache"
        }
        mock_cache.get.return_value = cached_quote
        
        quote = await market_data_service.get_quote("AAPL")
        
        assert quote.symbol == "AAPL"
        assert quote.price == Decimal("150.00")
        mock_cache.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_quote_from_api(self, market_data_service, mock_cache):
        """Test getting quote from API when not cached."""
        quote = await market_data_service.get_quote("AAPL")
        
        assert quote.symbol == "AAPL"
        assert quote.source in [DataSource.ALPHA_VANTAGE, DataSource.EOD_HISTORICAL]
        
        # Verify cache was set
        mock_cache.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self, market_data_service):
        """Test getting historical data."""
        # Mock historical data response
        bars = [
            PriceBar(
                timestamp=datetime.utcnow() - timedelta(days=i),
                open=Decimal("150.00"),
                high=Decimal("152.00"),
                low=Decimal("149.00"),
                close=Decimal("151.00"),
                volume=1000000
            )
            for i in range(5)
        ]
        
        historical_data = HistoricalData(
            symbol="AAPL",
            interval=PriceInterval.DAILY,
            bars=bars,
            start_date=bars[-1].timestamp,
            end_date=bars[0].timestamp,
            source=DataSource.EOD_HISTORICAL
        )
        
        market_data_service.eod_historical.get_historical_data = AsyncMock(
            return_value=historical_data
        )
        
        data = await market_data_service.get_historical_data("AAPL")
        
        assert data.symbol == "AAPL"
        assert len(data.bars) == 5
        assert data.interval == PriceInterval.DAILY
    
    @pytest.mark.asyncio
    async def test_get_batch_quotes(self, market_data_service):
        """Test getting quotes for multiple symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        
        quotes = await market_data_service.get_batch_quotes(symbols)
        
        # Should have attempted to get all symbols
        assert len(quotes) > 0
    
    @pytest.mark.asyncio
    async def test_market_status(self, market_data_service):
        """Test market status calculation."""
        status = await market_data_service.get_market_status()
        
        assert isinstance(status, MarketStatus)
        assert isinstance(status.is_open, bool)
        assert isinstance(status.current_time, datetime)
    
    @pytest.mark.asyncio
    async def test_calculate_indicators(self, market_data_service):
        """Test technical indicator calculation."""
        # Mock historical data for indicators
        bars = [
            PriceBar(
                timestamp=datetime.utcnow() - timedelta(days=i),
                open=Decimal(str(150 + i)),
                high=Decimal(str(152 + i)),
                low=Decimal(str(149 + i)),
                close=Decimal(str(151 + i)),
                volume=1000000
            )
            for i in range(30)
        ]
        
        historical_data = HistoricalData(
            symbol="AAPL",
            interval=PriceInterval.DAILY,
            bars=bars,
            start_date=bars[-1].timestamp,
            end_date=bars[0].timestamp,
            source=DataSource.EOD_HISTORICAL
        )
        
        market_data_service.get_historical_data = AsyncMock(
            return_value=historical_data
        )
        
        indicators = await market_data_service.calculate_indicators(
            "AAPL",
            ["sma", "rsi", "volatility"],
            window=20
        )
        
        assert "sma" in indicators
        assert "rsi" in indicators
        assert "volatility" in indicators
    
    @pytest.mark.asyncio
    async def test_api_usage_tracking(self, market_data_service):
        """Test API usage tracking."""
        # Make some API calls
        await market_data_service.get_quote("AAPL", use_cache=False)
        
        usage = market_data_service.get_api_usage()
        assert usage[DataSource.EOD_HISTORICAL] > 0 or usage[DataSource.ALPHA_VANTAGE] > 0
    
    @pytest.mark.asyncio
    async def test_extended_historical_data(self, market_data_service):
        """Test getting extended historical data back to 2007."""
        # Mock extended data
        start_date = date(2007, 1, 1)
        bars = []
        current_date = date.today()
        
        # Create sparse data (monthly samples)
        while current_date > start_date:
            bars.append(PriceBar(
                timestamp=datetime.combine(current_date, datetime.min.time()),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("95.00"),
                close=Decimal("102.00"),
                volume=1000000
            ))
            current_date = current_date - timedelta(days=30)
        
        historical_data = HistoricalData(
            symbol="BIL",
            interval=PriceInterval.DAILY,
            bars=bars,
            start_date=bars[-1].timestamp,
            end_date=bars[0].timestamp,
            source=DataSource.EOD_HISTORICAL
        )
        
        market_data_service.eod_historical.get_historical_data = AsyncMock(
            return_value=historical_data
        )
        
        data = await market_data_service.get_extended_historical_data("BIL")
        
        assert data.symbol == "BIL"
        assert data.start_date.year >= 2007
        assert len(data.bars) > 100  # Should have many years of data


class TestDataCaching:
    """Test data caching functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_ttl_settings(self):
        """Test cache TTL configurations."""
        from app.services.data_cache_service import DataCacheService
        
        cache = DataCacheService()
        
        assert cache.TTL_QUOTE == 60  # 1 minute
        assert cache.TTL_DAILY == 3600  # 1 hour
        assert cache.TTL_HISTORICAL == 86400  # 24 hours


class TestIndicatorCalculations:
    """Test technical indicator calculations."""
    
    def test_simple_moving_average(self):
        """Test SMA calculation."""
        from app.algorithms.indicators import technical_indicators
        
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
        sma = technical_indicators.simple_moving_average(prices, 5)
        
        assert sma is not None
        # SMA of last 5: (109 + 107 + 108 + 106 + 104) / 5 = 106.8
        assert abs(sma - 106.8) < 0.1
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        from app.algorithms.indicators import technical_indicators
        
        # Create price series with clear trend
        prices = list(range(100, 115)) + list(range(115, 100, -1))
        rsi = technical_indicators.relative_strength_index(prices, 14)
        
        assert rsi is not None
        assert 0 <= rsi <= 100

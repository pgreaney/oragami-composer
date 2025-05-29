"""
Tests for Technical Indicators

This module tests the technical indicator calculations
used in symphony algorithm execution.
"""

import pytest
import numpy as np
from decimal import Decimal
from unittest.mock import Mock, patch

from app.algorithms.indicators import TechnicalIndicators


class TestTechnicalIndicators:
    """Test technical indicator calculations"""
    
    @pytest.fixture
    def indicators(self):
        """Create technical indicators instance"""
        return TechnicalIndicators()
    
    @pytest.fixture
    def sample_prices(self):
        """Generate sample price data"""
        # Generate trending price data with some noise
        days = 100
        trend = np.linspace(100, 120, days)
        noise = np.random.normal(0, 2, days)
        prices = trend + noise
        return prices.tolist()
    
    def test_calculate_sma(self, indicators, sample_prices):
        """Test Simple Moving Average calculation"""
        # Test 20-day SMA
        sma_20 = indicators.calculate_sma(sample_prices, period=20)
        
        assert isinstance(sma_20, float)
        assert sma_20 > 0
        
        # Manual calculation for last 20 prices
        expected_sma = sum(sample_prices[-20:]) / 20
        assert abs(sma_20 - expected_sma) < 0.01
        
        # Test edge cases
        assert indicators.calculate_sma(sample_prices[:5], period=10) == 0  # Not enough data
        assert indicators.calculate_sma([], period=20) == 0  # Empty data
    
    def test_calculate_ema(self, indicators, sample_prices):
        """Test Exponential Moving Average calculation"""
        ema_20 = indicators.calculate_ema(sample_prices, period=20)
        
        assert isinstance(ema_20, float)
        assert ema_20 > 0
        
        # EMA should be closer to recent prices than SMA
        sma_20 = indicators.calculate_sma(sample_prices, period=20)
        last_price = sample_prices[-1]
        
        # EMA should be between SMA and last price
        if last_price > sma_20:
            assert ema_20 > sma_20
        else:
            assert ema_20 < sma_20
    
    def test_calculate_rsi(self, indicators):
        """Test RSI (Relative Strength Index) calculation"""
        # Create prices with known pattern
        # Uptrend followed by downtrend
        prices = [100, 102, 104, 106, 108, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92]
        
        rsi = indicators.calculate_rsi(prices, period=14)
        
        assert isinstance(rsi, float)
        assert 0 <= rsi <= 100
        
        # With this pattern, RSI should be below 50 (more losses than gains recently)
        assert rsi < 50
        
        # Test extreme cases
        all_up = [100 + i for i in range(20)]
        rsi_up = indicators.calculate_rsi(all_up)
        assert rsi_up > 70  # Should be overbought
        
        all_down = [100 - i for i in range(20)]
        rsi_down = indicators.calculate_rsi(all_down)
        assert rsi_down < 30  # Should be oversold
    
    def test_calculate_macd(self, indicators, sample_prices):
        """Test MACD (Moving Average Convergence Divergence) calculation"""
        macd, signal, histogram = indicators.calculate_macd(sample_prices)
        
        assert all(isinstance(x, float) for x in [macd, signal, histogram])
        
        # Histogram should be the difference between MACD and signal
        assert abs(histogram - (macd - signal)) < 0.01
        
        # Test with insufficient data
        short_prices = sample_prices[:10]
        macd_short, signal_short, hist_short = indicators.calculate_macd(short_prices)
        assert all(x == 0 for x in [macd_short, signal_short, hist_short])
    
    def test_calculate_bollinger_bands(self, indicators, sample_prices):
        """Test Bollinger Bands calculation"""
        upper, middle, lower = indicators.calculate_bollinger_bands(sample_prices, period=20)
        
        assert all(isinstance(x, float) for x in [upper, middle, lower])
        assert upper > middle > lower
        
        # Middle band should be the SMA
        sma = indicators.calculate_sma(sample_prices, period=20)
        assert abs(middle - sma) < 0.01
        
        # Bands should be symmetric around middle
        upper_diff = upper - middle
        lower_diff = middle - lower
        assert abs(upper_diff - lower_diff) < 0.1
    
    def test_calculate_volatility(self, indicators):
        """Test volatility calculation"""
        # Test with constant prices (no volatility)
        constant_prices = [100] * 30
        vol_constant = indicators.calculate_volatility(constant_prices)
        assert vol_constant < 0.001  # Should be near zero
        
        # Test with volatile prices
        volatile_prices = [100, 110, 95, 115, 90, 120, 85, 125, 80]
        vol_volatile = indicators.calculate_volatility(volatile_prices)
        assert vol_volatile > 0.1  # Should have significant volatility
        
        # Volatility should always be positive
        assert vol_volatile > 0
    
    def test_calculate_atr(self, indicators):
        """Test Average True Range calculation"""
        # Need high, low, close for ATR
        high_prices = [102, 105, 103, 107, 104, 108, 106, 109, 107, 110]
        low_prices = [98, 101, 99, 103, 100, 104, 102, 105, 103, 106]
        close_prices = [100, 103, 101, 105, 102, 106, 104, 107, 105, 108]
        
        atr = indicators.calculate_atr(high_prices, low_prices, close_prices, period=9)
        
        assert isinstance(atr, float)
        assert atr > 0
        
        # ATR should be roughly the average of daily ranges
        daily_ranges = [high_prices[i] - low_prices[i] for i in range(len(high_prices))]
        avg_range = sum(daily_ranges) / len(daily_ranges)
        assert atr > avg_range * 0.5  # ATR should be at least half of average range
    
    def test_calculate_obv(self, indicators):
        """Test On Balance Volume calculation"""
        prices = [100, 102, 101, 103, 102, 104]
        volumes = [1000, 1200, 900, 1100, 800, 1300]
        
        obv = indicators.calculate_obv(prices, volumes)
        
        assert isinstance(obv, float)
        
        # OBV should increase when price goes up with volume
        # Manual calculation:
        # Day 1->2: price up, +1200
        # Day 2->3: price down, -900
        # Day 3->4: price up, +1100
        # Day 4->5: price down, -800
        # Day 5->6: price up, +1300
        # Total: 1200 - 900 + 1100 - 800 + 1300 = 1900
        assert obv == 1900
    
    def test_calculate_stochastic(self, indicators):
        """Test Stochastic Oscillator calculation"""
        high_prices = [52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]
        low_prices = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]
        close_prices = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63]
        
        k_percent, d_percent = indicators.calculate_stochastic(
            high_prices, low_prices, close_prices
        )
        
        assert all(isinstance(x, float) for x in [k_percent, d_percent])
        assert 0 <= k_percent <= 100
        assert 0 <= d_percent <= 100
        
        # With steadily rising prices, stochastic should be high
        assert k_percent > 80
    
    def test_edge_cases(self, indicators):
        """Test edge cases and error handling"""
        # Empty data
        assert indicators.calculate_sma([]) == 0
        assert indicators.calculate_rsi([]) == 50  # Default neutral RSI
        
        # Single data point
        assert indicators.calculate_sma([100], period=5) == 0
        
        # Negative prices (should still work)
        negative_prices = [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10]
        sma = indicators.calculate_sma(negative_prices, period=5)
        assert sma == 6.0  # Average of last 5: [2, 4, 6, 8, 10]
    
    def test_indicator_consistency(self, indicators, sample_prices):
        """Test that indicators are consistent across multiple calls"""
        # Calculate indicators twice
        rsi1 = indicators.calculate_rsi(sample_prices)
        rsi2 = indicators.calculate_rsi(sample_prices)
        
        sma1 = indicators.calculate_sma(sample_prices, period=20)
        sma2 = indicators.calculate_sma(sample_prices, period=20)
        
        # Should get same results
        assert rsi1 == rsi2
        assert sma1 == sma2


class TestIndicatorIntegration:
    """Test indicator integration with algorithm execution"""
    
    def test_indicators_with_decimal_prices(self, indicators):
        """Test that indicators work with Decimal prices"""
        decimal_prices = [Decimal('100.50'), Decimal('101.25'), Decimal('99.75'), 
                         Decimal('102.00'), Decimal('101.50')]
        
        # Convert to float for calculation
        float_prices = [float(p) for p in decimal_prices]
        
        sma = indicators.calculate_sma(float_prices, period=3)
        assert isinstance(sma, float)
        assert sma > 0
    
    def test_indicator_performance(self, indicators):
        """Test indicator calculation performance"""
        import time
        
        # Generate large dataset
        large_prices = list(np.random.uniform(90, 110, 1000))
        
        # Time indicator calculations
        start = time.time()
        
        indicators.calculate_sma(large_prices, period=50)
        indicators.calculate_ema(large_prices, period=50)
        indicators.calculate_rsi(large_prices, period=14)
        indicators.calculate_macd(large_prices)
        indicators.calculate_bollinger_bands(large_prices)
        indicators.calculate_volatility(large_prices)
        
        elapsed = time.time() - start
        
        # All indicators should calculate in under 1 second
        assert elapsed < 1.0

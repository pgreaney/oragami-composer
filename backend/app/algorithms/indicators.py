"""Technical indicator calculation functions using TA-Lib."""

from typing import List, Optional, Dict, Any
import numpy as np
from datetime import datetime, timedelta

# Note: TA-Lib will be imported when available
# For now, we'll implement basic versions of the indicators

class TechnicalIndicators:
    """Technical indicator calculations for algorithm execution."""
    
    @staticmethod
    def simple_moving_average(prices: List[float], window: int) -> Optional[float]:
        """Calculate Simple Moving Average.
        
        Args:
            prices: List of prices (newest first)
            window: Period for calculation
            
        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < window:
            return None
        
        return sum(prices[:window]) / window
    
    @staticmethod
    def exponential_moving_average(prices: List[float], window: int) -> Optional[float]:
        """Calculate Exponential Moving Average.
        
        Args:
            prices: List of prices (newest first)
            window: Period for calculation
            
        Returns:
            EMA value or None if insufficient data
        """
        if len(prices) < window:
            return None
        
        # Simple implementation
        multiplier = 2 / (window + 1)
        ema = prices[window - 1]  # Start with SMA
        
        for i in range(window - 2, -1, -1):
            ema = (prices[i] - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def relative_strength_index(prices: List[float], window: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index.
        
        Args:
            prices: List of prices (newest first)
            window: Period for calculation (default 14)
            
        Returns:
            RSI value (0-100) or None if insufficient data
        """
        if len(prices) < window + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(window):
            change = prices[i] - prices[i + 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / window
        avg_loss = sum(losses) / window
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def standard_deviation(values: List[float], window: int) -> Optional[float]:
        """Calculate standard deviation.
        
        Args:
            values: List of values (newest first)
            window: Period for calculation
            
        Returns:
            Standard deviation or None if insufficient data
        """
        if len(values) < window:
            return None
        
        subset = values[:window]
        mean = sum(subset) / window
        variance = sum((x - mean) ** 2 for x in subset) / window
        
        return variance ** 0.5
    
    @staticmethod
    def volatility(returns: List[float], window: int) -> Optional[float]:
        """Calculate annualized volatility.
        
        Args:
            returns: List of returns (newest first)
            window: Period for calculation
            
        Returns:
            Annualized volatility or None if insufficient data
        """
        std_dev = TechnicalIndicators.standard_deviation(returns, window)
        if std_dev is None:
            return None
        
        # Annualize (assuming daily returns)
        return std_dev * (252 ** 0.5)
    
    @staticmethod
    def max_drawdown(prices: List[float], window: int) -> Optional[float]:
        """Calculate maximum drawdown.
        
        Args:
            prices: List of prices (newest first)
            window: Period for calculation
            
        Returns:
            Maximum drawdown (as positive percentage) or None
        """
        if len(prices) < window:
            return None
        
        # Reverse to chronological order for this calculation
        window_prices = list(reversed(prices[:window]))
        
        peak = window_prices[0]
        max_dd = 0
        
        for price in window_prices[1:]:
            if price > peak:
                peak = price
            else:
                drawdown = (peak - price) / peak
                max_dd = max(max_dd, drawdown)
        
        return max_dd * 100
    
    @staticmethod
    def cumulative_return(prices: List[float], window: int) -> Optional[float]:
        """Calculate cumulative return.
        
        Args:
            prices: List of prices (newest first)
            window: Period for calculation
            
        Returns:
            Cumulative return (as percentage) or None
        """
        if len(prices) < window + 1:
            return None
        
        start_price = prices[window]
        end_price = prices[0]
        
        if start_price == 0:
            return None
        
        return ((end_price - start_price) / start_price) * 100
    
    @staticmethod
    def sharpe_ratio(returns: List[float], window: int, risk_free_rate: float = 0.02) -> Optional[float]:
        """Calculate Sharpe ratio.
        
        Args:
            returns: List of returns (newest first)
            window: Period for calculation
            risk_free_rate: Annual risk-free rate (default 2%)
            
        Returns:
            Sharpe ratio or None if insufficient data
        """
        if len(returns) < window:
            return None
        
        window_returns = returns[:window]
        avg_return = sum(window_returns) / window
        std_dev = TechnicalIndicators.standard_deviation(window_returns, window)
        
        if std_dev is None or std_dev == 0:
            return None
        
        # Convert risk-free rate to daily
        daily_rf = risk_free_rate / 252
        
        # Calculate Sharpe ratio
        excess_return = avg_return - daily_rf
        sharpe = (excess_return * 252) / (std_dev * (252 ** 0.5))
        
        return sharpe
    
    @staticmethod
    def beta(asset_returns: List[float], market_returns: List[float], window: int) -> Optional[float]:
        """Calculate beta coefficient.
        
        Args:
            asset_returns: List of asset returns (newest first)
            market_returns: List of market returns (newest first)
            window: Period for calculation
            
        Returns:
            Beta or None if insufficient data
        """
        if len(asset_returns) < window or len(market_returns) < window:
            return None
        
        # Use numpy for covariance calculation if available
        try:
            asset_subset = np.array(asset_returns[:window])
            market_subset = np.array(market_returns[:window])
            
            covariance = np.cov(asset_subset, market_subset)[0, 1]
            market_variance = np.var(market_subset)
            
            if market_variance == 0:
                return None
            
            return covariance / market_variance
        except:
            # Fallback implementation
            return None
    
    @staticmethod
    def calculate_returns(prices: List[float]) -> List[float]:
        """Calculate returns from prices.
        
        Args:
            prices: List of prices (newest first)
            
        Returns:
            List of returns (newest first)
        """
        returns = []
        for i in range(len(prices) - 1):
            if prices[i + 1] != 0:
                ret = (prices[i] - prices[i + 1]) / prices[i + 1]
                returns.append(ret)
        
        return returns


# Global instance
technical_indicators = TechnicalIndicators()

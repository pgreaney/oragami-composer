"""
Technical Indicators Tasks

This module contains Celery tasks for calculating technical indicators
used by symphony algorithms.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
import numpy as np

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.algorithms.indicators import TechnicalIndicators
from app.services.market_data_service import MarketDataService
from app.services.data_cache_service import DataCacheService


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.technical_indicators.calculate_indicators')
def calculate_indicators(
    self,
    symbol: str,
    indicators: List[str],
    period: int = 252,
    end_date: Optional[str] = None
) -> Dict[str, float]:
    """
    Calculate technical indicators for a symbol
    
    Args:
        symbol: Stock symbol
        indicators: List of indicators to calculate
        period: Number of trading days to use for calculations
        end_date: End date for historical data (defaults to today)
        
    Returns:
        Dictionary of indicator values
    """
    db: Session = SessionLocal()
    
    try:
        # Update task state
        self.update_state(
            state='CALCULATING',
            meta={'symbol': symbol, 'indicators': indicators}
        )
        
        # Initialize services
        market_data_service = MarketDataService(db)
        cache_service = DataCacheService()
        technical_indicators = TechnicalIndicators()
        
        # Check cache first
        cache_key = f"indicators:{symbol}:{','.join(sorted(indicators))}:{period}:{end_date or 'latest'}"
        cached_result = cache_service.get(cache_key)
        if cached_result:
            logger.info(f"Using cached indicators for {symbol}")
            return cached_result
            
        # Parse end date
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_dt = date.today()
            
        # Calculate start date based on period
        start_dt = end_dt - timedelta(days=int(period * 1.5))  # Extra buffer for holidays
        
        # Fetch historical prices
        prices = market_data_service.get_historical_prices(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            limit=period
        )
        
        if len(prices) < 20:  # Minimum required for most indicators
            raise ValueError(f"Insufficient price data for {symbol}: only {len(prices)} points")
            
        # Convert to float array for calculations
        price_array = np.array([float(p) for p in prices])
        
        # Calculate requested indicators
        results = {}
        
        for indicator in indicators:
            try:
                if indicator == 'rsi':
                    results['rsi'] = technical_indicators.calculate_rsi(price_array)
                    
                elif indicator == 'volatility':
                    results['volatility'] = technical_indicators.calculate_volatility(price_array)
                    
                elif indicator.startswith('sma_'):
                    period_str = indicator.split('_')[1]
                    sma_period = int(period_str)
                    results[indicator] = technical_indicators.calculate_sma(price_array, sma_period)
                    
                elif indicator.startswith('ema_'):
                    period_str = indicator.split('_')[1]
                    ema_period = int(period_str)
                    results[indicator] = technical_indicators.calculate_ema(price_array, ema_period)
                    
                elif indicator == 'macd':
                    macd, signal, histogram = technical_indicators.calculate_macd(price_array)
                    results['macd'] = macd
                    results['macd_signal'] = signal
                    results['macd_histogram'] = histogram
                    
                elif indicator == 'bollinger_bands':
                    upper, middle, lower = technical_indicators.calculate_bollinger_bands(price_array)
                    results['bb_upper'] = upper
                    results['bb_middle'] = middle
                    results['bb_lower'] = lower
                    
                elif indicator == 'stochastic':
                    k, d = technical_indicators.calculate_stochastic(price_array)
                    results['stoch_k'] = k
                    results['stoch_d'] = d
                    
                elif indicator == 'atr':
                    # For ATR, we need high, low, close data
                    # This is a simplified version using just close prices
                    results['atr'] = technical_indicators.calculate_atr_simplified(price_array)
                    
                elif indicator == 'adx':
                    results['adx'] = technical_indicators.calculate_adx_simplified(price_array)
                    
                elif indicator == 'obv':
                    # OBV requires volume data
                    volumes = market_data_service.get_historical_volumes(symbol, start_dt, end_dt, period)
                    if volumes:
                        volume_array = np.array([float(v) for v in volumes])
                        results['obv'] = technical_indicators.calculate_obv(price_array, volume_array)
                        
                elif indicator == 'momentum':
                    results['momentum'] = technical_indicators.calculate_momentum(price_array)
                    
                elif indicator == 'roc':
                    results['roc'] = technical_indicators.calculate_roc(price_array)
                    
                else:
                    logger.warning(f"Unknown indicator: {indicator}")
                    
            except Exception as e:
                logger.error(f"Failed to calculate {indicator} for {symbol}: {str(e)}")
                results[indicator] = None
                
        # Cache results for 1 hour
        cache_service.set(cache_key, results, ttl=3600)
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to calculate indicators for {symbol}: {str(e)}")
        raise
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.technical_indicators.batch_calculate_indicators')
def batch_calculate_indicators(
    symbols: List[str],
    indicators: List[str],
    period: int = 252
) -> Dict[str, Dict[str, float]]:
    """
    Calculate indicators for multiple symbols in batch
    
    Args:
        symbols: List of stock symbols
        indicators: List of indicators to calculate
        period: Number of trading days to use
        
    Returns:
        Dictionary mapping symbols to their indicator values
    """
    results = {}
    
    # Create subtasks for parallel execution
    from celery import group
    
    tasks = []
    for symbol in symbols:
        task = calculate_indicators.signature(
            args=[symbol, indicators, period],
            queue='indicators',
            immutable=True
        )
        tasks.append(task)
        
    # Execute in parallel
    job = group(tasks)
    task_results = job.apply_async()
    
    # Collect results
    for i, symbol in enumerate(symbols):
        try:
            indicator_values = task_results[i].get(timeout=30)
            results[symbol] = indicator_values
        except Exception as e:
            logger.error(f"Failed to get indicators for {symbol}: {str(e)}")
            results[symbol] = {}
            
    return results


@celery_app.task(name='app.tasks.technical_indicators.calculate_correlation_matrix')
def calculate_correlation_matrix(
    symbols: List[str],
    period: int = 252,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate correlation matrix for a list of symbols
    
    Args:
        symbols: List of stock symbols
        period: Number of trading days to use
        end_date: End date for calculations
        
    Returns:
        Dictionary containing correlation matrix and metadata
    """
    db: Session = SessionLocal()
    
    try:
        market_data_service = MarketDataService(db)
        
        # Parse end date
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_dt = date.today()
            
        start_dt = end_dt - timedelta(days=int(period * 1.5))
        
        # Fetch price data for all symbols
        price_data = {}
        returns_data = {}
        
        for symbol in symbols:
            try:
                prices = market_data_service.get_historical_prices(
                    symbol=symbol,
                    start_date=start_dt,
                    end_date=end_dt,
                    limit=period
                )
                
                if len(prices) >= period * 0.8:  # Allow 20% missing data
                    price_array = np.array([float(p) for p in prices])
                    # Calculate returns
                    returns = np.diff(np.log(price_array))
                    returns_data[symbol] = returns
                    
            except Exception as e:
                logger.error(f"Failed to get prices for {symbol}: {str(e)}")
                
        # Create returns matrix
        valid_symbols = list(returns_data.keys())
        if len(valid_symbols) < 2:
            raise ValueError("Need at least 2 symbols with valid data for correlation")
            
        # Align returns to same length
        min_length = min(len(returns_data[s]) for s in valid_symbols)
        returns_matrix = np.array([returns_data[s][-min_length:] for s in valid_symbols])
        
        # Calculate correlation matrix
        correlation_matrix = np.corrcoef(returns_matrix)
        
        # Convert to dictionary format
        result = {
            'symbols': valid_symbols,
            'correlation_matrix': correlation_matrix.tolist(),
            'period': period,
            'end_date': end_date or str(date.today()),
            'data_points': min_length
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to calculate correlation matrix: {str(e)}")
        raise
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.technical_indicators.detect_signals')
def detect_signals(
    symbol: str,
    signal_types: List[str],
    period: int = 50
) -> Dict[str, Any]:
    """
    Detect trading signals based on technical indicators
    
    Args:
        symbol: Stock symbol
        signal_types: Types of signals to detect
        period: Lookback period
        
    Returns:
        Dictionary of detected signals
    """
    # Calculate necessary indicators
    indicators_needed = set()
    
    for signal_type in signal_types:
        if signal_type == 'golden_cross':
            indicators_needed.update(['sma_50', 'sma_200'])
        elif signal_type == 'death_cross':
            indicators_needed.update(['sma_50', 'sma_200'])
        elif signal_type == 'rsi_oversold':
            indicators_needed.add('rsi')
        elif signal_type == 'rsi_overbought':
            indicators_needed.add('rsi')
        elif signal_type == 'macd_crossover':
            indicators_needed.add('macd')
        elif signal_type == 'bollinger_squeeze':
            indicators_needed.add('bollinger_bands')
            
    # Calculate indicators
    indicators = calculate_indicators(
        symbol=symbol,
        indicators=list(indicators_needed),
        period=max(period, 200)  # Need at least 200 days for SMA 200
    )
    
    # Detect signals
    signals = {}
    
    for signal_type in signal_types:
        if signal_type == 'golden_cross':
            # SMA 50 crosses above SMA 200
            sma_50 = indicators.get('sma_50')
            sma_200 = indicators.get('sma_200')
            if sma_50 and sma_200 and sma_50 > sma_200:
                signals['golden_cross'] = True
                
        elif signal_type == 'death_cross':
            # SMA 50 crosses below SMA 200
            sma_50 = indicators.get('sma_50')
            sma_200 = indicators.get('sma_200')
            if sma_50 and sma_200 and sma_50 < sma_200:
                signals['death_cross'] = True
                
        elif signal_type == 'rsi_oversold':
            # RSI below 30
            rsi = indicators.get('rsi')
            if rsi and rsi < 30:
                signals['rsi_oversold'] = True
                
        elif signal_type == 'rsi_overbought':
            # RSI above 70
            rsi = indicators.get('rsi')
            if rsi and rsi > 70:
                signals['rsi_overbought'] = True
                
        elif signal_type == 'macd_crossover':
            # MACD crosses above signal line
            macd = indicators.get('macd')
            macd_signal = indicators.get('macd_signal')
            if macd and macd_signal and macd > macd_signal:
                signals['macd_crossover'] = True
                
        elif signal_type == 'bollinger_squeeze':
            # Bollinger bands are narrowing (low volatility)
            bb_upper = indicators.get('bb_upper')
            bb_lower = indicators.get('bb_lower')
            bb_middle = indicators.get('bb_middle')
            if bb_upper and bb_lower and bb_middle:
                band_width = (bb_upper - bb_lower) / bb_middle
                if band_width < 0.1:  # Less than 10% band width
                    signals['bollinger_squeeze'] = True
                    
    return {
        'symbol': symbol,
        'signals': signals,
        'indicators': indicators,
        'timestamp': datetime.utcnow().isoformat()
    }


@celery_app.task(name='app.tasks.technical_indicators.calculate_portfolio_metrics')
def calculate_portfolio_metrics(
    positions: List[Dict[str, Any]],
    benchmark: str = 'SPY',
    period: int = 252
) -> Dict[str, float]:
    """
    Calculate portfolio-level technical metrics
    
    Args:
        positions: List of position dictionaries
        benchmark: Benchmark symbol for comparison
        period: Calculation period
        
    Returns:
        Dictionary of portfolio metrics
    """
    if not positions:
        return {
            'total_value': 0,
            'beta': 0,
            'correlation': 0,
            'sharpe_ratio': 0,
            'volatility': 0
        }
        
    # Implementation would calculate portfolio-wide metrics
    # This is a placeholder for the actual implementation
    return {
        'total_value': sum(p.get('value', 0) for p in positions),
        'beta': 1.0,
        'correlation': 0.85,
        'sharpe_ratio': 1.2,
        'volatility': 0.15
    }

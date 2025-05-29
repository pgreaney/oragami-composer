"""
Market Data Tasks

This module contains Celery tasks for market data operations,
including pre-fetching, caching, and validation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import logging

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.services.market_data_service import MarketDataService
from app.services.data_cache_service import DataCacheService
from app.models.symphony import Symphony


logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.market_data_tasks.prefetch_market_data')
def prefetch_market_data() -> Dict[str, Any]:
    """
    Pre-fetch market data before daily execution window
    
    This task runs at 15:45 EST to cache market data for all active assets
    before the 15:50-16:00 execution window.
    
    Returns:
        Dictionary containing prefetch results
    """
    db: Session = SessionLocal()
    
    result = {
        'prefetch_time': datetime.utcnow().isoformat(),
        'assets_cached': 0,
        'cache_failures': 0,
        'total_assets': 0
    }
    
    try:
        market_data_service = MarketDataService(db)
        cache_service = DataCacheService()
        
        # Get all unique assets from active symphonies
        active_symphonies = db.query(Symphony).filter_by(is_active=True).all()
        
        all_assets = set()
        for symphony in active_symphonies:
            universe = symphony.algorithm_config.get('universe', [])
            all_assets.update(universe)
            
        # Add default universe if needed
        if not all_assets:
            all_assets = {'SPY', 'AGG', 'GLD', 'VNQ', 'EFA', 'EEM', 'TLT', 'IEF', 'SHY', 'BIL'}
            
        result['total_assets'] = len(all_assets)
        
        # Pre-fetch current prices and quotes
        for symbol in all_assets:
            try:
                # Get current price
                price = market_data_service.get_current_price(symbol)
                
                # Get quote data
                quote = market_data_service.get_quote(symbol)
                
                # Get recent historical data (last 252 days)
                end_date = date.today()
                start_date = end_date - timedelta(days=365)
                
                historical_prices = market_data_service.get_historical_prices(
                    symbol, start_date, end_date, 252
                )
                
                # Cache the data
                cache_key = f"prefetch:{symbol}:{date.today()}"
                cache_service.set(cache_key, {
                    'price': float(price),
                    'quote': quote,
                    'historical_count': len(historical_prices)
                }, ttl=7200)  # 2 hour TTL
                
                result['assets_cached'] += 1
                logger.info(f"Pre-fetched data for {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to prefetch data for {symbol}: {str(e)}")
                result['cache_failures'] += 1
                
        logger.info(
            f"Market data prefetch completed: "
            f"{result['assets_cached']}/{result['total_assets']} assets cached"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Market data prefetch failed: {str(e)}")
        result['error'] = str(e)
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.market_data_tasks.refresh_cache')
def refresh_cache() -> Dict[str, Any]:
    """
    Refresh market data cache during market hours
    
    Returns:
        Dictionary containing refresh results
    """
    db: Session = SessionLocal()
    
    try:
        market_data_service = MarketDataService(db)
        cache_service = DataCacheService()
        
        # Check if market is open
        if not market_data_service.is_market_open():
            return {
                'status': 'skipped',
                'reason': 'market_closed'
            }
            
        # Get most frequently accessed symbols from cache stats
        cache_stats = cache_service.get_stats()
        top_symbols = cache_stats.get('top_symbols', [])[:50]  # Top 50 symbols
        
        refreshed = 0
        for symbol in top_symbols:
            try:
                # Refresh current price
                price = market_data_service.get_current_price(symbol)
                
                # Update cache
                cache_key = f"price:{symbol}"
                cache_service.set(cache_key, float(price), ttl=300)  # 5 minute TTL
                
                refreshed += 1
                
            except Exception as e:
                logger.error(f"Failed to refresh {symbol}: {str(e)}")
                
        return {
            'status': 'completed',
            'symbols_refreshed': refreshed,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache refresh failed: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.market_data_tasks.validate_market_data_apis')
def validate_market_data_apis() -> Dict[str, Any]:
    """
    Validate market data API connections and quotas
    
    Returns:
        Dictionary containing validation results
    """
    db: Session = SessionLocal()
    
    result = {
        'alpha_vantage': {'status': 'unknown', 'quota_remaining': None},
        'eod_historical': {'status': 'unknown', 'quota_remaining': None},
        'validation_time': datetime.utcnow().isoformat()
    }
    
    try:
        market_data_service = MarketDataService(db)
        
        # Test Alpha Vantage
        try:
            # Try to get SPY quote
            test_quote = market_data_service.alpha_vantage_client.get_quote('SPY')
            if test_quote:
                result['alpha_vantage']['status'] = 'operational'
                # Check API usage
                usage = market_data_service.get_api_usage()
                result['alpha_vantage']['quota_remaining'] = usage.get('alpha_vantage', {}).get('remaining')
        except Exception as e:
            result['alpha_vantage']['status'] = 'error'
            result['alpha_vantage']['error'] = str(e)
            
        # Test EOD Historical Data
        try:
            # Try to get SPY data
            test_data = market_data_service.eod_historical_client.get_historical_data(
                'SPY', date.today() - timedelta(days=7), date.today()
            )
            if test_data:
                result['eod_historical']['status'] = 'operational'
                usage = market_data_service.get_api_usage()
                result['eod_historical']['quota_remaining'] = usage.get('eod_historical', {}).get('remaining')
        except Exception as e:
            result['eod_historical']['status'] = 'error'
            result['eod_historical']['error'] = str(e)
            
        return result
        
    except Exception as e:
        logger.error(f"API validation failed: {str(e)}")
        result['error'] = str(e)
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.market_data_tasks.cleanup_old_cache')
def cleanup_old_cache(days: int = 7) -> Dict[str, int]:
    """
    Clean up old cached market data
    
    Args:
        days: Number of days of cache to keep
        
    Returns:
        Dictionary containing cleanup statistics
    """
    try:
        cache_service = DataCacheService()
        
        # Get cache keys older than specified days
        cutoff_timestamp = datetime.utcnow() - timedelta(days=days)
        
        # This would be implemented based on the cache backend
        # For Redis, we'd scan keys and check TTL
        deleted_count = 0
        
        # Placeholder implementation
        logger.info(f"Cleaned up cache entries older than {days} days")
        
        return {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {str(e)}")
        return {'error': str(e)}

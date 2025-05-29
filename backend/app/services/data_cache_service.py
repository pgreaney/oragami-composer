"""Redis caching for market data optimization."""

import json
import redis
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal

from app.config import settings
from app.schemas.market_data import DataCacheEntry, DataSource


class DataCacheService:
    """Service for caching market data in Redis."""
    
    # Cache TTL settings (in seconds)
    TTL_QUOTE = 60  # 1 minute for real-time quotes
    TTL_INTRADAY = 300  # 5 minutes for intraday data
    TTL_DAILY = 3600  # 1 hour for daily data
    TTL_HISTORICAL = 86400  # 24 hours for historical data
    TTL_ASSET_INFO = 604800  # 7 days for asset info
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize cache service.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
    
    @property
    def redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    def _get_cache_key(
        self,
        data_type: str,
        symbol: str,
        source: DataSource,
        **kwargs
    ) -> str:
        """Generate cache key.
        
        Args:
            data_type: Type of data (quote, historical, etc.)
            symbol: Asset symbol
            source: Data source
            **kwargs: Additional key components
            
        Returns:
            Cache key string
        """
        parts = [
            "market_data",
            data_type,
            symbol.upper(),
            source.value
        ]
        
        # Add additional key components
        for key, value in sorted(kwargs.items()):
            if value is not None:
                parts.append(f"{key}:{value}")
        
        return ":".join(parts)
    
    def _serialize_decimal(self, obj: Any) -> Any:
        """Serialize Decimal values for JSON.
        
        Args:
            obj: Object to serialize
            
        Returns:
            Serialized object
        """
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._serialize_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_decimal(item) for item in obj]
        return obj
    
    def _deserialize_decimal(self, obj: Any) -> Any:
        """Deserialize Decimal values from JSON.
        
        Args:
            obj: Object to deserialize
            
        Returns:
            Deserialized object
        """
        if isinstance(obj, dict):
            # Check if this looks like a Decimal value
            if all(k in obj for k in ["__decimal__", "value"]):
                return Decimal(obj["value"])
            return {k: self._deserialize_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deserialize_decimal(item) for item in obj]
        return obj
    
    def get(
        self,
        data_type: str,
        symbol: str,
        source: DataSource,
        **kwargs
    ) -> Optional[Any]:
        """Get data from cache.
        
        Args:
            data_type: Type of data
            symbol: Asset symbol
            source: Data source
            **kwargs: Additional key components
            
        Returns:
            Cached data or None
        """
        try:
            key = self._get_cache_key(data_type, symbol, source, **kwargs)
            data = self.redis.get(key)
            
            if data:
                parsed = json.loads(data)
                return self._deserialize_decimal(parsed)
            
            return None
            
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            return None
    
    def set(
        self,
        data_type: str,
        symbol: str,
        source: DataSource,
        data: Any,
        ttl_seconds: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Set data in cache.
        
        Args:
            data_type: Type of data
            symbol: Asset symbol
            source: Data source
            data: Data to cache
            ttl_seconds: Custom TTL (uses default if None)
            **kwargs: Additional key components
            
        Returns:
            True if successful
        """
        try:
            # Determine TTL
            if ttl_seconds is None:
                ttl_map = {
                    "quote": self.TTL_QUOTE,
                    "intraday": self.TTL_INTRADAY,
                    "daily": self.TTL_DAILY,
                    "historical": self.TTL_HISTORICAL,
                    "asset_info": self.TTL_ASSET_INFO
                }
                ttl_seconds = ttl_map.get(data_type, self.TTL_DAILY)
            
            key = self._get_cache_key(data_type, symbol, source, **kwargs)
            
            # Serialize data
            serialized = self._serialize_decimal(data)
            json_data = json.dumps(serialized)
            
            # Set with TTL
            self.redis.setex(key, ttl_seconds, json_data)
            
            return True
            
        except Exception as e:
            print(f"Cache set error: {str(e)}")
            return False
    
    def delete(
        self,
        data_type: str,
        symbol: str,
        source: DataSource,
        **kwargs
    ) -> bool:
        """Delete data from cache.
        
        Args:
            data_type: Type of data
            symbol: Asset symbol
            source: Data source
            **kwargs: Additional key components
            
        Returns:
            True if deleted
        """
        try:
            key = self._get_cache_key(data_type, symbol, source, **kwargs)
            return self.redis.delete(key) > 0
            
        except Exception as e:
            print(f"Cache delete error: {str(e)}")
            return False
    
    def clear_symbol_cache(self, symbol: str) -> int:
        """Clear all cache entries for a symbol.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Number of entries deleted
        """
        try:
            pattern = f"market_data:*:{symbol.upper()}:*"
            keys = self.redis.keys(pattern)
            
            if keys:
                return self.redis.delete(*keys)
            
            return 0
            
        except Exception as e:
            print(f"Cache clear error: {str(e)}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        try:
            info = self.redis.info()
            
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "0"),
                "total_keys": self.redis.dbsize(),
                "hit_rate": info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
            
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
    def batch_get(
        self,
        data_type: str,
        symbols: List[str],
        source: DataSource,
        **kwargs
    ) -> Dict[str, Any]:
        """Get multiple items from cache.
        
        Args:
            data_type: Type of data
            symbols: List of symbols
            source: Data source
            **kwargs: Additional key components
            
        Returns:
            Dict of symbol -> data
        """
        result = {}
        
        for symbol in symbols:
            data = self.get(data_type, symbol, source, **kwargs)
            if data is not None:
                result[symbol] = data
        
        return result
    
    def batch_set(
        self,
        data_type: str,
        data_map: Dict[str, Any],
        source: DataSource,
        ttl_seconds: Optional[int] = None,
        **kwargs
    ) -> int:
        """Set multiple items in cache.
        
        Args:
            data_type: Type of data
            data_map: Dict of symbol -> data
            source: Data source
            ttl_seconds: Custom TTL
            **kwargs: Additional key components
            
        Returns:
            Number of items cached
        """
        count = 0
        
        for symbol, data in data_map.items():
            if self.set(data_type, symbol, source, data, ttl_seconds, **kwargs):
                count += 1
        
        return count
    
    def ping(self) -> bool:
        """Check if Redis is available.
        
        Returns:
            True if Redis is responsive
        """
        try:
            return self.redis.ping()
        except:
            return False


# Global cache instance
data_cache_service: Optional[DataCacheService] = None


def get_data_cache_service() -> DataCacheService:
    """Get or create data cache service."""
    global data_cache_service
    
    if data_cache_service is None:
        data_cache_service = DataCacheService()
    
    return data_cache_service

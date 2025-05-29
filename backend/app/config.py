"""
Configuration management using pydantic-settings
Reads from .env files based on environment
"""

from typing import List, Optional
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application settings
    APP_NAME: str = "Origami Composer"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Origami Composer API"
    
    # Security
    SECRET_KEY: str = "change-this-in-production-to-a-secure-random-string"
    JWT_SECRET: str = "change-this-in-production-to-a-secure-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Database
    DATABASE_URL: str = "postgresql://origami:origami@localhost:5432/origami_composer"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Market Data APIs
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    EOD_HISTORICAL_API_KEY: Optional[str] = None
    MARKET_DATA_CACHE_TTL: int = 300  # 5 minutes
    
    # Alpaca Paper Trading OAuth
    ALPACA_CLIENT_ID: Optional[str] = None
    ALPACA_CLIENT_SECRET: Optional[str] = None
    ALPACA_REDIRECT_URI: str = "http://localhost:3000/oauth/callback"
    ALPACA_PAPER_BASE_URL: str = "https://paper-api.alpaca.markets"
    ALPACA_OAUTH_BASE_URL: str = "https://app.alpaca.markets/oauth"
    
    # Trading Settings
    MAX_SYMPHONIES_PER_USER: int = 40
    DAILY_EXECUTION_HOUR: int = 15  # 3:50 PM
    DAILY_EXECUTION_MINUTE: int = 50
    DAILY_EXECUTION_TIMEZONE: str = "America/New_York"
    EXECUTION_TIMEOUT_SECONDS: int = 480  # 8 minutes (must complete by 15:58)
    
    # Performance Settings
    BACKTEST_START_DATE: str = "2007-05-30"  # BIL inception
    PERFORMANCE_CALCULATION_WORKERS: int = 4
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance
    Use dependency injection in FastAPI: Depends(get_settings)
    """
    return Settings()


# Create a global settings instance for imports
settings = get_settings()

"""
Alphatracer Backend - A Delta-like portfolio tracking application.
Built with FastAPI for user authentication, portfolio management,
stock data ingestion, and fuzzy search capabilities.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from datetime import datetime

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Configuration - No defaults, MUST be in .env
    DATABASE_URL: str
    DATABASE_POOL_PREPARED: bool = True
    
    # JWT Security - No defaults, MUST be in .env
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Stock Data Sources
    PRIMARY_TICKER_CSV: str
    SECONDARY_TICKER_CSV: str
    TICKER_UPDATE_INTERVAL_HOURS: int = 12
    PRICE_API_PROVIDER: str = "yfinance"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = "*"

    # Pydantic Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False, # Allows matching DATABASE_URL to database_url
        extra="ignore"        # Ignores helper vars like DB_HOST, DB_PORT in your .env
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def api_v1_prefix(self) -> str:
        return self.API_V1_PREFIX

# This will now fail immediately if your .env is missing 
# DATABASE_URL or SECRET_KEY, preventing "localhost" errors.
settings = Settings()

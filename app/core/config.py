"""
Alphatracer Backend - A Delta-like portfolio tracking application.
Built with FastAPI for user authentication, portfolio management,
stock data ingestion, and fuzzy search capabilities.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # Database Configuration - Defaults to local SQLite in development; overridden by Kubernetes / HashiCorp Secret
    DATABASE_URL: str = "sqlite:///./trading.db"
    DATABASE_POOL_PREPARED: bool = True

    # JWT Security - Overridden by Kubernetes / HashiCorp Secret
    SECRET_KEY: str = "devsecops-ephemeral-local-jwt-signing-key-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stock Data Sources
    PRIMARY_TICKER_CSV: str = (
        "https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/all.csv"
    )
    SECONDARY_TICKER_CSV: str = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
    TICKER_UPDATE_INTERVAL_HOURS: int = 12
    PRICE_API_PROVIDER: str = "yfinance"


    # HashiCorp Vault Configuration (Optional Central Secret Engine)
    VAULT_ADDR: str = ""
    VAULT_TOKEN: str = "root"
    VAULT_SECRET_PATH: str = "alphatracer"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"

    # CORS Configuration
    ALLOWED_ORIGINS: str = "*"

    # Pydantic Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Allows matching DATABASE_URL to database_url
        extra="ignore",  # Ignores helper vars like DB_HOST, DB_PORT in your .env
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def api_v1_prefix(self) -> str:
        return self.API_V1_PREFIX

    def load_vault_secrets(self) -> None:
        """Dynamically retrieves production secrets from HashiCorp Vault if configured."""
        if not self.VAULT_ADDR:
            return

        import httpx

        url = f"{self.VAULT_ADDR.rstrip('/')}/v1/secret/data/{self.VAULT_SECRET_PATH}"
        try:
            resp = httpx.get(
                url, headers={"X-Vault-Token": self.VAULT_TOKEN}, timeout=2.5
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get("data", {})
                if "database_url" in data:
                    self.DATABASE_URL = data["database_url"]
                if "secret_key" in data:
                    self.SECRET_KEY = data["secret_key"]
                print(f"[vault] Successfully loaded secrets from {url}")
        except Exception as exc:
            print(f"[vault] Could not load secrets from Vault (falling back to env): {exc}")


settings = Settings()
settings.load_vault_secrets()


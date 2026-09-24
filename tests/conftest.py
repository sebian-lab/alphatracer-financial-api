import os

# Set testing credentials in-process before app imports Settings
# Zero hardcoded .env file required, adhering to DevSecOps zero-cleartext-file practices
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-devsecops-in-memory-ephemeral-key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("PRIMARY_TICKER_CSV", "https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/all.csv")
os.environ.setdefault("SECONDARY_TICKER_CSV", "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv")

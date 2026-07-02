# Alphatracer Backend

A FastAPI portfolio-tracking API. Uses **PostgreSQL** in production (via Docker Compose) and supports **SQLite** for zero-setup local development. Uses **Yahoo Finance (yfinance)** for real-time prices, candles, and technical indicators.

---

## Quick Start (Docker / Production Setup)

The easiest way to run the application with a production-ready PostgreSQL database is via Docker Compose:

```bash
# 1. Start the FastAPI application and PostgreSQL database containers
docker compose up --build
```

- API base: `http://localhost:8011/api/v1`
- Interactive docs (Swagger): `http://localhost:8011/docs`
- Health check: `http://localhost:8011/health`

---

## Local Development (SQLite Setup)

If you prefer to run the application locally without Docker:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy the example environment file and configure variables
cp .env.example .env

# 3. Start the application (SQLite database will be created automatically)
uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

---

## Running Tests

You can run the test suite to verify the application is working correctly:

```bash
# Run pytest unit tests
pytest

# Run the full endpoint integration tests (requires server running on localhost:8011)
bash tests/test_all_endpoints.sh

# Run end-to-end demo script
bash demo.sh
```

---

## Security Features

This API includes production-ready cybersecurity measures:
- **Rate Limiting**: Limits login requests on `/auth/login` and `/auth/login/json` to 5 requests per minute to prevent brute-force attacks.
- **Security Headers**: Standard secure HTTP headers are injected automatically via custom middleware (e.g. `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`).
- **Dynamic CORS**: Allowed origins can be dynamically configured via the `ALLOWED_ORIGINS` environment variable.
- **CI/CD Security Pipelines**: Automated security checks run on push and PR to `main`:
  - **Bandit**: Static Application Security Testing (SAST) to check for insecure code or hardcoded keys.
  - **Trivy**: Dependency vulnerability scanner to flag outdated packages.

---

## Environment Variables (`.env`)

```env
# Database URL (PostgreSQL container connection)
DATABASE_URL=postgresql://postgres:postgres_secure_pass@db:5432/trading_db

# JWT Configuration
SECRET_KEY=change-this-to-a-very-secure-random-secret-key-for-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS allowed origins (comma-separated list, e.g., http://localhost:3000,http://localhost:8000)
ALLOWED_ORIGINS=*

# Ticker universe
PRIMARY_TICKER_CSV=https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/all.csv
SECONDARY_TICKER_CSV=https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv
TICKER_UPDATE_INTERVAL_HOURS=12
PRICE_API_PROVIDER=yfinance
```

All real-time prices, historical candles, and financial metrics come from **Yahoo Finance via yfinance** — completely free, no API key or account required.

---

## API Reference

### Base URL: `http://localhost:8011/api/v1`

---

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | OAuth2 form login → JWT tokens |
| POST | `/auth/login/json` | No | JSON body login → JWT tokens |
| POST | `/auth/refresh` | Bearer | Refresh access token |

**Register:**
```bash
curl -X POST http://localhost:8011/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123", "full_name": "Alice"}'
# → 201 {"id": 1, "email": "alice@example.com", "full_name": "Alice", ...}
```

**Login (OAuth2 form — `username` field holds the email):**
```bash
curl -X POST http://localhost:8011/api/v1/auth/login \
  -F "username=alice@example.com" \
  -F "password=secret123"
# → {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

**Login (JSON body — alternative):**
```bash
curl -X POST http://localhost:8011/api/v1/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'
```

**Refresh:**
```bash
curl -X POST http://localhost:8011/api/v1/auth/refresh \
  -H "Authorization: Bearer $TOKEN"
```

---

### Users

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/users/me` | Bearer | Get profile |
| PUT | `/users/me` | Bearer | Update full_name |
| DELETE | `/users/me` | Bearer | Delete account |

```bash
TOKEN="your_access_token_here"

# Get profile
curl http://localhost:8011/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"

# Update name
curl -X PUT http://localhost:8011/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Alice Smith"}'

# Delete account
curl -X DELETE http://localhost:8011/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

---

### Stocks

Stock search queries the **local SQLite database**, which is populated from both CSV sources at startup. This means every ticker in either CSV — including AAPL, TSLA, MSFT — is always searchable from the first request.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/stocks/search?q=` | No | Search by ticker or company name |
| GET | `/stocks/{ticker}` | No | Stock detail (from DB / CSV) |
| GET | `/stocks/{ticker}/price` | No | Live price via Yahoo Finance |
| GET | `/stocks/{ticker}/metrics` | No | Full financials via Yahoo Finance |

**Search** — fuzzy match on ticker symbol and company name:
```bash
# Search by company name
curl "http://localhost:8011/api/v1/stocks/search?q=apple&limit=5"

# Search by ticker prefix
curl "http://localhost:8011/api/v1/stocks/search?q=AAPL"

# Search with higher limit
curl "http://localhost:8011/api/v1/stocks/search?q=microsoft&limit=10"
```

Search scoring (higher = more relevant):
- `20` — exact ticker or full name match
- `15` — ticker starts with query
- `12` — company name starts with query
- `10` — query appears inside ticker
- `7` — query appears inside company name
- `6` — any word in company name starts with query
- `≤4` — character overlap fallback

**Detail + price:**
```bash
# Stock info from DB
curl http://localhost:8011/api/v1/stocks/AAPL

# Live price (Yahoo Finance, cached 60 s)
curl http://localhost:8011/api/v1/stocks/AAPL/price
# → {"ticker": "AAPL", "price": 187.42}
```

**Financial metrics** (all from Yahoo Finance, cached 5 min):
```bash
curl http://localhost:8011/api/v1/stocks/AAPL/metrics
```
Returns: EPS, P/E (trailing + forward), PEG, P/B, P/S, gross/operating/net margin, ROE, ROA, ROI/ROIC, current ratio, quick ratio, debt/equity, revenue growth, earnings growth, beta, 52-week high/low.

---

### Portfolio & Transactions

All portfolio data is per-user (JWT required). Live prices are fetched from Yahoo Finance when viewing holdings.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/portfolio` | Bearer | Holdings snapshot with live P&L |
| GET | `/portfolio/metrics` | Bearer | Aggregated metrics (weighted P/E, beta) |
| POST | `/portfolio/transactions` | Bearer | Record a buy or sell |
| GET | `/portfolio/transactions` | Bearer | List transactions (filterable) |
| PUT | `/portfolio/transactions/{id}` | Bearer | Correct a transaction |
| DELETE | `/portfolio/transactions/{id}` | Bearer | Delete a transaction |

**Buy:**
```bash
curl -X POST http://localhost:8011/api/v1/portfolio/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_ticker": "AAPL",
    "type": "buy",
    "quantity": 10,
    "price_per_share": 175.50,
    "transaction_date": "2026-01-15"
  }'
# → 201 {"id": 1, "stock_ticker": "AAPL", "stock_name": "Apple Inc.", "type": "buy", ...}
```

**Sell** (validated — cannot sell more than held):
```bash
curl -X POST http://localhost:8011/api/v1/portfolio/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stock_ticker": "AAPL", "type": "sell", "quantity": 5, "price_per_share": 190.00}'
```

**Portfolio snapshot** (with live prices and P&L):
```bash
curl http://localhost:8011/api/v1/portfolio \
  -H "Authorization: Bearer $TOKEN"
# → {"user_id": 1, "total_cost": 1755.0, "current_value": 1874.2,
#    "holdings": [{"stock_ticker": "AAPL", "quantity": 5, "gain_loss": 119.2, ...}]}
```

**Filter transactions:**
```bash
# By ticker
curl "http://localhost:8011/api/v1/portfolio/transactions?stock_ticker=AAPL" \
  -H "Authorization: Bearer $TOKEN"

# By type
curl "http://localhost:8011/api/v1/portfolio/transactions?transaction_type=buy" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Watchlist

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/watchlist` | Bearer | Watchlist with live prices |
| POST | `/watchlist/{ticker}` | Bearer | Add ticker (201 / 409 if duplicate) |
| DELETE | `/watchlist/{ticker}` | Bearer | Remove ticker |

```bash
# Add
curl -X POST http://localhost:8011/api/v1/watchlist/TSLA \
  -H "Authorization: Bearer $TOKEN"

# View (includes live price per ticker)
curl http://localhost:8011/api/v1/watchlist \
  -H "Authorization: Bearer $TOKEN"

# Remove
curl -X DELETE http://localhost:8011/api/v1/watchlist/TSLA \
  -H "Authorization: Bearer $TOKEN"
```

---

### Market Data

All market data comes from **Yahoo Finance (yfinance) — free, no API key**. Every candle fetch is saved to the local `stock_price_history` SQLite table so history accumulates over time.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/market/{ticker}/quote` | No | Live OHLC quote |
| GET | `/market/{ticker}/analysis` | No | Full TradingView-style analysis |
| GET | `/market/{ticker}/analysis/max` | No | Fetch + save maximum available history |
| GET | `/market/{ticker}/candles` | No | Raw OHLCV bars from Yahoo Finance |
| GET | `/market/{ticker}/candles/stored` | No | Candles from local DB (no API call) |
| GET | `/market/{ticker}/indicators` | No | Indicators only (no candle list) |
| GET | `/market/compare/quotes` | No | Side-by-side quotes for up to 10 tickers |
| GET | `/market/info/max-periods` | No | Max history per interval reference |

**Live quote:**
```bash
curl http://localhost:8011/api/v1/market/AAPL/quote
# → {"ticker": "AAPL", "price": 187.42, "change_pct": 0.83,
#    "week_52_high": 199.62, "week_52_low": 164.08, ...}
```

**Full analysis** (quote + candles + all indicators + signal, candles saved to DB):
```bash
curl "http://localhost:8011/api/v1/market/AAPL/analysis?interval=1d&period=3mo"
```

Returns:
- **Quote**: price, OHLC, change %, amplitude %, market cap, 52-week range
- **Candles**: last 200 OHLCV bars
- **Moving averages**: SMA 20/50/200, EMA 9/21/50, VWAP
- **Oscillators**: RSI-14, Stochastic %K/%D, CCI-20, Williams %R, MACD (line/signal/histogram), ADX-14 (+DI/−DI)
- **Volatility**: Bollinger Bands (upper/middle/lower/width/%B), ATR-14
- **Volume**: OBV, relative volume
- **Signal**: overall rating (STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL) + per-indicator breakdown
- **bars_saved**: number of candles upserted to local DB this call

**Valid intervals:** `1m` `2m` `5m` `15m` `30m` `60m` `90m` `1h` `1d` `5d` `1wk` `1mo` `3mo`  
**Valid periods:** `1d` `5d` `1mo` `3mo` `6mo` `1y` `2y` `5y` `10y` `ytd` `max`

**Fetch + save maximum available history** (run once to populate DB):
```bash
# Daily candles — full history (decades for major stocks like AAPL)
curl "http://localhost:8011/api/v1/market/AAPL/analysis/max?interval=1d"

# 1-hour candles — ~2 years
curl "http://localhost:8011/api/v1/market/AAPL/analysis/max?interval=1h"
```

Maximum history yfinance provides per interval:

| Interval | Max history |
|----------|-------------|
| `1m` | 7 days |
| `2m` `5m` `15m` `30m` `90m` | 60 days |
| `1h` `60m` | ~2 years (730 days) |
| `1d` `5d` `1wk` `1mo` `3mo` | Full history (decades) |

**Query stored candles** (from local DB, no Yahoo Finance call):
```bash
# All stored daily candles for AAPL
curl "http://localhost:8011/api/v1/market/AAPL/candles/stored?interval=1d"

# Date range
curl "http://localhost:8011/api/v1/market/AAPL/candles/stored?interval=1d&start=2024-01-01&end=2024-12-31"

# Intraday with limit
curl "http://localhost:8011/api/v1/market/AAPL/candles/stored?interval=1h&limit=100"
```

**Compare quotes:**
```bash
curl "http://localhost:8011/api/v1/market/compare/quotes?tickers=AAPL,TSLA,MSFT,NVDA"
# → {"count": 4, "quotes": [{...}, {...}, {...}, {...}]}
```

**Indicators only** (no candle list in response — faster for dashboards):
```bash
curl "http://localhost:8011/api/v1/market/MSFT/indicators?interval=1d&period=6mo"
```

---

## Architecture

```
app/
├── main.py                      # FastAPI app + lifespan (creates tables, pre-warms CSV)
├── api/v1/
│   ├── auth.py                  # Register / login (form + JSON) / refresh
│   ├── users.py                 # GET / PUT / DELETE /users/me
│   ├── stocks.py                # Search (DB-backed), detail, price, metrics
│   ├── portfolio.py             # Holdings, buy/sell/update/delete transactions
│   ├── watchlist.py             # Add / list / remove watched stocks
│   └── market.py                # Live quotes, full analysis, candles, indicators
├── core/
│   ├── config.py                # Pydantic settings (reads .env)
│   ├── database.py              # SQLAlchemy engine + session (SQLite)
│   └── security.py              # JWT (PyJWT), bcrypt password hashing
├── db/
│   ├── models.py                # User, Stock, StockPriceHistory, Transaction, Watchlist
│   └── migrations/              # Alembic migrations (optional — auto-create used by default)
├── schemas/
│   ├── user.py                  # Pydantic user schemas (lenient email validator)
│   ├── stock.py                 # Stock + watchlist response schemas
│   └── transaction.py           # Transaction + portfolio schemas
├── services/
│   ├── price_service.py         # yfinance price fetch (60 s cache)
│   ├── market_data_service.py   # Full OHLCV + indicators + DB persistence
│   └── metrics_service.py       # Financial metrics (P/E, ROE, margins …)
└── utils/
    └── csv_loader.py            # GitHub CSV ticker loader + fuzzy scoring
```

**Database tables (SQLite `trading.db`):**

| Table | Purpose |
|-------|---------|
| `users` | Accounts + hashed passwords |
| `stocks` | Ticker universe (populated from CSVs at startup) |
| `stock_price_history` | Persistent OHLCV candles (upserted on every market fetch) |
| `transactions` | Buy/sell records per user |
| `watchlists` | Per-user watched tickers |

---

## Bug Fixes Applied

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `schemas/user.py` | `EmailStr` (pydantic) rejected valid test-domain emails like `@alphatracer.test` due to TLD registry checks | Replaced with `LenientEmail` — regex-only structural validation, no TLD lookup |
| 2 | `utils/csv_loader.py` | `fuzzy_match_score` character-overlap fallback only checked the **ticker** string, not the company name — noisy scores for unrelated results | Fallback now checks both ticker and name (`set(ticker + " " + name)`) |
| 3 | `api/v1/stocks.py` | Search iterated in-memory CSV dict — AAPL absent from primary CSV (OTC list), would miss common tickers | Search now queries SQLite directly with `LIKE` on both `ticker` and `name`, then re-scores. DB is pre-populated from both CSVs at startup |
| 4 | `api/v1/portfolio.py` | After `db.commit()`, SQLAlchemy identity-map could return a stale cached `Stock` row, causing wrong ticker on the transaction response (AAPL stored as AUMN) | Added `db.expire()` + `db.refresh()` post-commit; also resolved stock name from yfinance when CSV has no entry |
| 5 | `main.py` | CSV ticker data loaded lazily on first search request — tickers not in DB during concurrent startup requests | `lifespan` now calls `load_tickers()` at boot, pre-populating DB before any request is served |

---

## Data Sources

| Data | Source | Cost | Rate limit |
|------|--------|------|------------|
| Ticker universe | Two GitHub CSV files (configured in `.env`) | Free | Downloaded once per 12 h |
| Live prices | Yahoo Finance via `yfinance` | Free | ~2000 req/hour (cached 60 s) |
| Historical candles | Yahoo Finance via `yfinance` | Free | Cached 5 min; saved to SQLite |
| Financial metrics | Yahoo Finance via `yfinance` | Free | Cached 5 min per ticker |

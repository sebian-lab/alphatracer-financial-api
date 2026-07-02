# Alphatracer — Setup & Deployment Guide

## Prerequisites

```bash
python3 --version   # 3.10+ required
pip3 --version
curl --version
```

No database server needed — Alphatracer uses **SQLite** (single file, created automatically).

---

## Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure environment (defaults are fine for local dev)
#    Edit .env to change SECRET_KEY before deploying anywhere public
cp .env .env.backup   # optional backup

# 3. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

On first start:
- `trading.db` (SQLite file) is created automatically
- All tables are created via `create_tables()` in the app lifespan
- Both ticker CSV sources are downloaded and loaded into `stocks` table
- ~13 000 tickers are available for search immediately

---

## Environment Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./trading.db` | SQLite file path (relative to working dir) |
| `SECRET_KEY` | *(set in .env)* | JWT signing key — **change before production** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `PRIMARY_TICKER_CSV` | GitHub abbadata URL | Primary ticker list (~7 600 tickers) |
| `SECONDARY_TICKER_CSV` | GitHub Ate329 URL | Secondary ticker list (~5 300 tickers) |
| `TICKER_UPDATE_INTERVAL_HOURS` | `12` | CSV re-download interval |

---

## Running Tests

```bash
# Full endpoint test suite (requires server running on localhost:8011)
bash tests/test_all_endpoints.sh

# End-to-end demo
bash demo.sh
```

---

## Deploying on a Remote Host

```bash
# On the remote machine, change the BASE URL in demo/test scripts:
bash demo.sh --base http://YOUR_IP:8011/api/v1

# Or export before running:
export BASE=http://YOUR_IP:8011/api/v1
bash tests/test_all_endpoints.sh --base $BASE
```

The SQLite file (`trading.db`) lives in the working directory. Back it up with:
```bash
cp trading.db trading.db.bak
```

---

## Production Checklist

- [ ] Change `SECRET_KEY` in `.env` to a random 32+ byte value:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] Set `ACCESS_TOKEN_EXPIRE_MINUTES` to a shorter window (e.g. `15`)
- [ ] Run behind a reverse proxy (nginx / caddy) with HTTPS
- [ ] For high traffic, consider switching `DATABASE_URL` to PostgreSQL

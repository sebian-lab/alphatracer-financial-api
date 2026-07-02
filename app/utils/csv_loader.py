"""
CSV loader for stock ticker data from GitHub sources.
- Loads PRIMARY and SECONDARY CSV sources defined in .env
- Merges both, primary takes precedence for duplicate tickers
- In-memory cache refreshed every TICKER_UPDATE_INTERVAL_HOURS
- Also persists tickers to the local SQLite stocks table on first load
"""

import csv
import io
import re
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from threading import Lock

from app.core.config import settings

PRIMARY_TICKER_CSV   = settings.PRIMARY_TICKER_CSV
SECONDARY_TICKER_CSV = settings.SECONDARY_TICKER_CSV
CACHE_TTL_HOURS      = settings.TICKER_UPDATE_INTERVAL_HOURS

# ── in-memory cache ──────────────────────────────────────────────────────────
_cache: Dict[str, dict] = {}
_cache_ts: Optional[datetime] = None
_lock = Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_tickers(force_refresh: bool = False) -> Dict[str, dict]:
    """
    Return merged ticker dict  {TICKER: {name, sector, industry, source}}.

    Uses both CSV URLs defined in .env (PRIMARY_TICKER_CSV, SECONDARY_TICKER_CSV).
    Results are cached for TICKER_UPDATE_INTERVAL_HOURS hours.
    On first successful load the tickers are also saved to the local DB.
    """
    global _cache, _cache_ts

    with _lock:
        if not force_refresh and _cache and _cache_ts:
            age = datetime.now() - _cache_ts
            if age < timedelta(hours=CACHE_TTL_HOURS):
                return _cache

        merged: Dict[str, dict] = {}

        # -- primary source (higher priority) ---------------------------------
        primary_rows = _download_csv(PRIMARY_TICKER_CSV, "PRIMARY")
        for row in primary_rows:
            ticker = _extract_ticker(row)
            if ticker:
                merged[ticker] = {
                    "name":     _extract_name(row, ticker),
                    "sector":   row.get("sector", "").strip() or "Unknown",
                    "industry": row.get("industry", "").strip() or None,
                    "source":   "primary",
                }

        # -- secondary source (fills gaps, never overwrites primary) ----------
        secondary_rows = _download_csv(SECONDARY_TICKER_CSV, "SECONDARY")
        for row in secondary_rows:
            ticker = _extract_ticker(row)
            if not ticker:
                continue
            if ticker not in merged:
                merged[ticker] = {
                    "name":     _extract_name(row, ticker),
                    "sector":   row.get("sector", "").strip() or "Unknown",
                    "industry": row.get("industry", "").strip() or None,
                    "source":   "secondary",
                }
            else:
                # primary exists — only fill truly empty fields
                existing = merged[ticker]
                if not existing.get("sector") or existing["sector"] == "Unknown":
                    existing["sector"] = row.get("sector", "").strip() or "Unknown"
                if not existing.get("industry"):
                    existing["industry"] = row.get("industry", "").strip() or None

        if merged:
            _cache    = merged
            _cache_ts = datetime.now()
            # Persist new tickers to DB in the background (best-effort)
            _persist_to_db(merged)

        return _cache


def fuzzy_match_score(ticker: str, name: str, query: str) -> float:
    """
    Score how well a ticker/name matches a query string.
    Higher = better match.

    Priority ladder (exact → prefix → substring → token → character overlap):
      20 — exact ticker or full name match
      15 — ticker starts with query
      12 — name starts with query
      10 — query is substring of ticker
       7 — query is substring of name
       6 — any word in name starts with query
       ≤4 — character overlap fallback (checks BOTH ticker AND name)
    """
    q  = query.lower().strip()
    t  = ticker.lower()
    n  = name.lower() if name else ""

    if t == q or n == q:          return 20.0
    if t.startswith(q):           return 15.0
    if n.startswith(q):           return 12.0
    if q in t:                    return 10.0
    if q in n:                    return  7.0

    # token match: any word in the company name starts with query
    for token in n.split():
        if token.startswith(q):   return  6.0

    # character overlap fallback — check BOTH ticker AND name (bug fix: was ticker-only)
    combined = t + " " + n
    unique_chars_in_combined = set(combined)
    hits = sum(1 for c in q if c in unique_chars_in_combined)
    return round(hits / max(len(q), 1) * 4, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _download_csv(url: str, label: str) -> List[dict]:
    """Download and parse a CSV from a URL into a list of row-dicts."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        text = resp.content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        # Normalise header keys to lowercase with no extra spaces
        rows = []
        for row in reader:
            rows.append({k.strip().lower(): (v or "").strip() for k, v in row.items()})
        print(f"[csv_loader] {label}: loaded {len(rows)} rows from {url}")
        return rows
    except Exception as exc:
        print(f"[csv_loader] {label}: failed to load {url} — {exc}")
        return []


_TICKER_KEYS = ("symbol", "ticker", "sym", "code")
_NAME_KEYS   = ("name", "company", "companyname", "company_name", "description")


def _extract_ticker(row: dict) -> Optional[str]:
    for k in _TICKER_KEYS:
        val = row.get(k, "").strip().upper()
        if val and re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', val):
            return val
    return None


def _extract_name(row: dict, fallback: str) -> str:
    for k in _NAME_KEYS:
        val = row.get(k, "").strip()
        if val:
            return val
    return fallback


def _persist_to_db(tickers: Dict[str, dict]) -> None:
    """
    Upsert tickers into the local stocks table so they are queryable by ticker
    even without re-hitting the CSV URLs (e.g. for transaction/watchlist lookup).
    Safe to call multiple times — only inserts rows that don't already exist.
    """
    try:
        from app.core.database import SessionLocal
        from app.db.models import Stock

        db = SessionLocal()
        try:
            existing_tickers = {
                s.ticker for s in db.query(Stock.ticker).all()
            }
            new_stocks = []
            for ticker, data in tickers.items():
                if ticker not in existing_tickers:
                    new_stocks.append(Stock(
                        ticker   = ticker,
                        name     = data.get("name") or ticker,
                        sector   = data.get("sector") or "Unknown",
                        industry = data.get("industry"),
                    ))
            if new_stocks:
                db.bulk_save_objects(new_stocks)
                db.commit()
                print(f"[csv_loader] persisted {len(new_stocks)} new tickers to DB")
        finally:
            db.close()
    except Exception as exc:
        # Never crash the search endpoint because of a DB write failure
        print(f"[csv_loader] DB persist error (non-fatal): {exc}")

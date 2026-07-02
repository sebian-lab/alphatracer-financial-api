"""
Market Data endpoints — TradingView-style analysis.
All free, no API key or token required (yfinance / Yahoo Finance).

Routes:
  GET /market/{ticker}/quote          — live quote (price, OHLC, change%)
  GET /market/{ticker}/analysis       — full technical analysis + saves candles to DB
  GET /market/{ticker}/analysis/max   — fetch MAX history yfinance allows, save all to DB
  GET /market/{ticker}/candles        — OHLCV bars only
  GET /market/{ticker}/candles/stored — return candles saved in local DB (no yfinance call)
  GET /market/{ticker}/indicators     — MA + oscillators + volatility (no candle list)
  GET /market/compare/quotes          — side-by-side quote for multiple tickers

Max history per interval (yfinance limits):
  1m → 7d | 5m/15m/30m/90m → 60d | 1h/60m → 730d | 1d/1wk/1mo/3mo → full history
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.api.dependencies import get_db_session
from app.services.market_data_service import (
    get_market_data, get_market_data_max, get_quote_only,
    FullAnalysis, Quote, OHLCVBar, _MAX_PERIOD,
)

router = APIRouter(prefix="/market", tags=["Market Data"])

VALID_INTERVALS = {"1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo"}
VALID_PERIODS   = {"1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"}


def _validate(interval: str, period: str):
    if interval not in VALID_INTERVALS:
        raise HTTPException(400, f"Invalid interval '{interval}'. Choose from: {sorted(VALID_INTERVALS)}")
    if period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period '{period}'. Choose from: {sorted(VALID_PERIODS)}")


# ── quote ─────────────────────────────────────────────────────────────────────

@router.get("/{ticker}/quote", response_model=Quote, summary="Live quote")
def get_quote(ticker: str):
    """
    Live price snapshot — no auth needed. Cached 60 s.

    Returns: price, open, high, low, prev_close, volume, change%, amplitude%,
             market cap, 52-week high/low.
    """
    q = get_quote_only(ticker.upper())
    if q.price is None:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    return q


# ── analysis ──────────────────────────────────────────────────────────────────

@router.get("/{ticker}/analysis", response_model=FullAnalysis,
            summary="Full TradingView-style analysis")
def get_analysis(
    ticker:   str,
    interval: str = Query("1d",  description="Candle interval: 1m 5m 15m 30m 1h 1d 1wk 1mo"),
    period:   str = Query("3mo", description="Lookback period: 1d 5d 1mo 3mo 6mo 1y 2y 5y"),
):
    """
    Full TradingView-style technical analysis — no auth, no API key.

    Includes quote, last 200 candles, all indicators, and buy/sell signal.
    **Candles are saved to the local DB** on every call so history accumulates.

    `bars_saved` in the response tells you how many candles were upserted this call.
    """
    _validate(interval, period)
    result = get_market_data(ticker.upper(), interval=interval, period=period)
    if result.quote.price is None:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    return result


@router.get("/{ticker}/analysis/max", response_model=FullAnalysis,
            summary="Fetch & save maximum available history")
def get_analysis_max(
    ticker:   str,
    interval: str = Query("1d", description="Candle interval"),
):
    """
    Fetches the **maximum history** yfinance allows for this interval and saves
    every candle to the local DB.

    Max periods per interval:
    - `1m`  → 7 days
    - `5m` / `15m` / `30m` / `90m` → 60 days
    - `1h` / `60m`  → 730 days (~2 years)
    - `1d` / `1wk` / `1mo` / `3mo` → full history (decades for major stocks)

    After calling this once for `1d`, your DB will hold AAPL's complete daily
    history — no repeated API calls needed for historical analysis.
    """
    if interval not in VALID_INTERVALS:
        raise HTTPException(400, f"Invalid interval '{interval}'")
    result = get_market_data_max(ticker.upper(), interval=interval)
    if result.quote.price is None:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    return result


# ── candles ───────────────────────────────────────────────────────────────────

@router.get("/{ticker}/candles", summary="OHLCV candles from yfinance")
def get_candles(
    ticker:   str,
    interval: str = Query("1d",  description="Candle interval"),
    period:   str = Query("3mo", description="Lookback period"),
):
    """Raw OHLCV bars fetched from yfinance and saved to DB."""
    _validate(interval, period)
    data = get_market_data(ticker.upper(), interval=interval, period=period)
    return {
        "ticker":     ticker.upper(),
        "interval":   interval,
        "period":     period,
        "count":      len(data.candles),
        "bars_saved": data.bars_saved,
        "candles":    data.candles,
    }


@router.get("/{ticker}/candles/stored", summary="OHLCV candles from local DB (no yfinance)")
def get_stored_candles(
    ticker:   str,
    interval: str = Query("1d", description="Candle interval"),
    start:    Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end:      Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit:    int = Query(500, ge=1, le=10000, description="Max bars to return"),
    db:       Session = Depends(get_db_session),
):
    """
    Return candles that are already saved in the **local database** — no yfinance
    call is made. Useful for dashboards and backtests that need historical data
    without rate-limiting concerns.

    Call `GET /market/{ticker}/analysis/max` first to populate the DB with
    the maximum available history for a given interval.
    """
    from app.db.models import Stock as StockModel, StockPriceHistory
    from sqlalchemy import asc

    stock = db.query(StockModel).filter(StockModel.ticker == ticker.upper()).first()
    if not stock:
        return {"ticker": ticker.upper(), "interval": interval, "count": 0, "candles": []}

    q = db.query(StockPriceHistory).filter(
        StockPriceHistory.stock_id == stock.id,
        StockPriceHistory.interval == interval,
    )
    if start:
        try:
            q = q.filter(StockPriceHistory.bar_datetime >= datetime.fromisoformat(start))
        except ValueError:
            raise HTTPException(400, f"Invalid start date '{start}'. Use YYYY-MM-DD.")
    if end:
        try:
            q = q.filter(StockPriceHistory.bar_datetime <= datetime.fromisoformat(end))
        except ValueError:
            raise HTTPException(400, f"Invalid end date '{end}'. Use YYYY-MM-DD.")

    rows = q.order_by(asc(StockPriceHistory.bar_datetime)).limit(limit).all()

    candles = [
        OHLCVBar(
            datetime = r.bar_datetime.isoformat()[:19],
            open     = round(r.open,  4),
            high     = round(r.high,  4),
            low      = round(r.low,   4),
            close    = round(r.close, 4),
            volume   = r.volume or 0.0,
        )
        for r in rows
    ]
    return {
        "ticker":   ticker.upper(),
        "interval": interval,
        "count":    len(candles),
        "candles":  candles,
    }


# ── indicators ────────────────────────────────────────────────────────────────

@router.get("/{ticker}/indicators", summary="Technical indicators only (no candles)")
def get_indicators(
    ticker:   str,
    interval: str = Query("1d",  description="Candle interval"),
    period:   str = Query("3mo", description="Lookback period"),
):
    """
    Returns MA, oscillators, volatility, volume, and signal — without the
    full candle list (faster response for dashboards). Candles still saved to DB.
    """
    _validate(interval, period)
    data = get_market_data(ticker.upper(), interval=interval, period=period)
    return {
        "ticker":      ticker.upper(),
        "interval":    interval,
        "period":      period,
        "bars_saved":  data.bars_saved,
        "quote":       data.quote,
        "ma":          data.ma,
        "oscillators": data.oscillators,
        "volatility":  data.volatility,
        "volume":      data.volume,
        "signal":      data.signal,
    }


# ── compare ───────────────────────────────────────────────────────────────────

@router.get("/compare/quotes", summary="Compare live quotes for multiple tickers")
def compare_quotes(
    tickers: str = Query(..., description="Comma-separated list, e.g. AAPL,TSLA,MSFT"),
):
    """Side-by-side live quote for up to 10 tickers."""
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not symbols:
        raise HTTPException(400, "No tickers provided")
    if len(symbols) > 10:
        raise HTTPException(400, "Maximum 10 tickers per compare request")

    results = []
    for sym in symbols:
        try:
            results.append(get_quote_only(sym))
        except Exception as exc:
            results.append({"ticker": sym, "error": str(exc)})

    return {"count": len(results), "quotes": results}


# ── max period info ───────────────────────────────────────────────────────────

@router.get("/info/max-periods", summary="Max history periods per interval")
def max_periods():
    """
    Returns the maximum period yfinance allows for each interval.
    Use `GET /market/{ticker}/analysis/max` to fetch and persist full history.
    """
    return {
        "intervals": {
            k: {"max_period": v, "note": _period_note(k)}
            for k, v in _MAX_PERIOD.items()
        }
    }


def _period_note(interval: str) -> str:
    notes = {
        "1m":  "7 days max — yfinance hard limit",
        "2m":  "60 days max",
        "5m":  "60 days max",
        "15m": "60 days max",
        "30m": "60 days max",
        "60m": "~2 years (730 days)",
        "90m": "60 days max",
        "1h":  "~2 years (730 days)",
        "1d":  "Full history — decades for major stocks",
        "5d":  "Full history",
        "1wk": "Full history",
        "1mo": "Full history",
        "3mo": "Full history",
    }
    return notes.get(interval, "")

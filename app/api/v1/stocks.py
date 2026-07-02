"""
Stock endpoints: fuzzy search, detail, live price, and financial metrics.

Ticker universe:
  - Fetched from PRIMARY_TICKER_CSV + SECONDARY_TICKER_CSV defined in .env
  - Both CSVs are merged (primary wins on duplicates) and persisted to DB
  - Search queries the DB directly (fast indexed LIKE) so every ticker that
    has ever been loaded — including AAPL, TSLA, MSFT — is always reachable
  - CSV in-memory cache is kept for offline fallback on /stocks/{ticker}

Price + financial metrics:
  - yfinance (Yahoo Finance) — completely free, no API key needed
  - Prices cached 60 s, full metrics cached 5 min
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.dependencies import get_db_session
from app.schemas.stock import StockResponse
from app.db.models import Stock as StockModel
from app.services.price_service import get_current_price
from app.services.metrics_service import get_financial_metrics, FinancialMetrics
from app.utils.csv_loader import load_tickers, fuzzy_match_score

router = APIRouter(prefix="/stocks", tags=["Stocks"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_or_create_stock(
    db: Session, ticker: str,
    name: str = "", sector: str = "Unknown", industry: Optional[str] = None,
) -> StockModel:
    stock = db.query(StockModel).filter(StockModel.ticker == ticker.upper()).first()
    if not stock:
        stock = StockModel(
            ticker   = ticker.upper(),
            name     = name or ticker.upper(),
            sector   = sector,
            industry = industry,
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)
    return stock


def _ensure_csv_loaded() -> None:
    """
    Trigger CSV download + DB persist if not done yet.
    Called lazily on first search so startup stays fast.
    """
    try:
        load_tickers()
    except Exception as exc:
        print(f"[stocks] CSV load warning (non-fatal): {exc}")


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("/search", response_model=List[StockResponse])
def search_stocks(
    q:     str     = Query(..., min_length=1, description="Ticker symbol or company name"),
    limit: int     = Query(default=10, ge=1, le=100),
    db:    Session = Depends(get_db_session),
):
    """
    Search stocks by ticker symbol or company name.

    Searches the **local database** (which is auto-populated from both GitHub
    CSV sources on first request). This means AAPL, TSLA, MSFT and every
    other ticker in either CSV always surfaces correctly.

    Two-pass strategy:
    1. SQL query: exact ticker match + LIKE on ticker + LIKE on name  →  fast candidates
    2. Python re-score with fuzzy_match_score  →  sort by relevance

    Scoring:
    - Exact ticker/name match  → 20 pts
    - Ticker prefix match      → 15 pts
    - Name prefix match        → 12 pts
    - Ticker substring match   → 10 pts
    - Name substring match     →  7 pts
    - Name word-start match    →  6 pts
    - Character-overlap fallback (ticker AND name)
    """
    # Ensure CSVs have been loaded into the DB at least once
    _ensure_csv_loaded()

    q_clean = q.strip()
    q_upper = q_clean.upper()
    q_like  = f"%{q_clean}%"

    # SQL: pull broad candidates — exact ticker OR ticker LIKE OR name LIKE
    # Fetch up to 500 candidates then re-rank in Python for precision
    candidates = (
        db.query(StockModel)
        .filter(
            or_(
                func.upper(StockModel.ticker) == q_upper,
                StockModel.ticker.ilike(q_like),
                StockModel.name.ilike(q_like),
            )
        )
        .limit(500)
        .all()
    )

    if not candidates:
        return []

    scored = []
    for stock in candidates:
        score = fuzzy_match_score(stock.ticker, stock.name or "", q_clean)
        if score > 0:
            scored.append((score, stock))

    # Sort: highest score first; ties broken by shorter name (more specific)
    scored.sort(key=lambda x: (-x[0], len(x[1].name or "")))

    return [
        StockResponse(
            id       = s.id,
            ticker   = s.ticker,
            name     = s.name or s.ticker,
            industry = s.industry,
            sector   = s.sector or "Unknown",
        )
        for _, s in scored[:limit]
    ]


@router.get("/{ticker}/price")
def get_stock_price(ticker: str):
    """
    Current live price via **yfinance** (Yahoo Finance — free, no API key).
    Cached per ticker for 60 seconds.
    """
    price = get_current_price(ticker.upper())
    if not price:
        raise HTTPException(status_code=404, detail=f"Price unavailable for '{ticker.upper()}'")
    return {"ticker": ticker.upper(), "price": price}


@router.get("/{ticker}/metrics", response_model=FinancialMetrics)
def get_stock_metrics(ticker: str):
    """
    Full financial metrics pulled from Yahoo Finance (free, no API key).

    **Valuation**: current price, market cap, P/E (trailing + forward), PEG, P/B, P/S

    **Per-share**: EPS (TTM + forward), book value, dividend yield %

    **Profitability** (all in %):
    - Gross margin, operating margin, net margin
    - ROE (Return on Equity)
    - ROA (Return on Assets)
    - ROI / ROIC — *manually calculated* as Net Income ÷ (Equity + Debt) × 100
      when yfinance doesn't provide it directly

    **Liquidity / Leverage**: current ratio, quick ratio, debt-to-equity

    **Growth (YoY %)**: revenue growth, earnings growth

    **Risk**: beta, 52-week high/low, average volume

    Missing fields are `null` — never fabricated. Cached for 5 minutes.
    """
    return get_financial_metrics(ticker.upper())


@router.get("/{ticker}", response_model=StockResponse)
def get_stock(
    ticker: str,
    db:     Session = Depends(get_db_session),
):
    """
    Stock detail by ticker. Checks local DB first, then falls back to the
    cached CSV data. If found in CSV but not yet in DB, the row is persisted.
    """
    ticker = ticker.upper()

    # 1. local DB (fastest — already persisted from CSV load)
    stock = db.query(StockModel).filter(StockModel.ticker == ticker).first()
    if stock:
        return stock

    # 2. CSV cache (may require a network fetch if cache cold)
    try:
        ticker_data = load_tickers()
    except Exception:
        ticker_data = {}

    if ticker in ticker_data:
        data  = ticker_data[ticker]
        stock = _get_or_create_stock(
            db, ticker,
            name     = data.get("name", ticker),
            sector   = data.get("sector", "Unknown"),
            industry = data.get("industry"),
        )
        return StockResponse(
            id=stock.id, ticker=stock.ticker, name=stock.name,
            industry=stock.industry, sector=stock.sector,
        )

    raise HTTPException(status_code=404, detail=f"Stock '{ticker}' not found")

"""
Financial metrics service.
All calculations are derived from yfinance data — no paid API required.

Metrics provided per ticker:
  EPS, P/E, Forward P/E, PEG, Price/Book, Price/Sales,
  ROE, ROI (ROIC), Net Margin, Gross Margin, Operating Margin,
  Debt/Equity, Current Ratio, Quick Ratio,
  Dividend Yield, Beta, 52-week high/low, Market Cap,
  Revenue Growth (YoY), Earnings Growth (YoY)
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta
from typing import Optional
from pydantic import BaseModel

# ── schema ────────────────────────────────────────────────────────────────────

class FinancialMetrics(BaseModel):
    ticker: str

    # Valuation
    current_price:      Optional[float] = None
    market_cap:         Optional[float] = None
    pe_ratio:           Optional[float] = None   # trailing P/E
    forward_pe:         Optional[float] = None
    peg_ratio:          Optional[float] = None
    price_to_book:      Optional[float] = None
    price_to_sales:     Optional[float] = None

    # Per-share
    eps_ttm:            Optional[float] = None   # trailing twelve months
    eps_forward:        Optional[float] = None
    book_value:         Optional[float] = None
    dividend_yield:     Optional[float] = None   # percentage, e.g. 1.5 = 1.5 %

    # Profitability
    gross_margin:       Optional[float] = None   # percentage
    operating_margin:   Optional[float] = None   # percentage
    net_margin:         Optional[float] = None   # percentage
    roe:                Optional[float] = None   # Return on Equity, percentage
    roa:                Optional[float] = None   # Return on Assets, percentage
    roi:                Optional[float] = None   # Return on Invested Capital (ROIC), percentage

    # Liquidity / Leverage
    current_ratio:      Optional[float] = None
    quick_ratio:        Optional[float] = None
    debt_to_equity:     Optional[float] = None

    # Growth
    revenue_growth_yoy: Optional[float] = None   # percentage
    earnings_growth_yoy:Optional[float] = None   # percentage

    # Risk / Price momentum
    beta:               Optional[float] = None
    week_52_high:       Optional[float] = None
    week_52_low:        Optional[float] = None
    avg_volume:         Optional[int]   = None

    # Meta
    fetched_at: str = ""


class PortfolioMetrics(BaseModel):
    """Aggregated metrics for a user's entire portfolio."""
    total_cost:          float
    current_value:       float
    total_gain_loss:     float
    total_gain_loss_pct: float
    weighted_pe:         Optional[float] = None
    weighted_beta:       Optional[float] = None
    holdings_count:      int
    profitable_holdings: int


# ── fetching ──────────────────────────────────────────────────────────────────

# 60-second in-memory cache  {ticker: (FinancialMetrics, fetched_at_datetime)}
_metrics_cache: dict[str, tuple[FinancialMetrics, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes for full metrics (heavier than price-only)


def get_financial_metrics(ticker: str, use_cache: bool = True) -> FinancialMetrics:
    """
    Fetch all financial metrics for a ticker using yfinance (free, no API key).

    Returns a FinancialMetrics object — missing fields are None (never raises).
    """
    ticker = ticker.upper()

    if use_cache and ticker in _metrics_cache:
        cached, ts = _metrics_cache[ticker]
        if (datetime.now() - ts).seconds < _CACHE_TTL_SECONDS:
            return cached

    metrics = _fetch_from_yfinance(ticker)
    _metrics_cache[ticker] = (metrics, datetime.now())
    return metrics


def _fetch_from_yfinance(ticker: str) -> FinancialMetrics:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        print(f"[metrics] yfinance error for {ticker}: {exc}")
        info = {}

    def _pct(val) -> Optional[float]:
        """Convert a 0-1 decimal ratio to a rounded percentage."""
        if val is None:
            return None
        try:
            return round(float(val) * 100, 2)
        except (TypeError, ValueError):
            return None

    def _f(val) -> Optional[float]:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        try:
            return round(float(val), 4)
        except (TypeError, ValueError):
            return None

    def _i(val) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    # ── raw values from yfinance ──────────────────────────────────────────────
    price         = _f(info.get("regularMarketPrice") or info.get("currentPrice"))
    eps_ttm       = _f(info.get("trailingEps"))
    eps_fwd       = _f(info.get("forwardEps"))
    pe_trailing   = _f(info.get("trailingPE"))
    pe_forward    = _f(info.get("forwardPE"))

    # Manually compute P/E if yfinance is missing it but we have price & EPS
    if pe_trailing is None and price and eps_ttm and eps_ttm != 0:
        pe_trailing = round(price / eps_ttm, 2)
    if pe_forward is None and price and eps_fwd and eps_fwd != 0:
        pe_forward = round(price / eps_fwd, 2)

    # ROI = ROIC = Net Income / (Total Equity + Total Debt)
    net_income     = info.get("netIncomeToCommon")
    total_equity   = info.get("totalStockholderEquity") or info.get("bookValue")
    total_debt     = info.get("totalDebt", 0) or 0
    roi: Optional[float] = None
    if net_income and total_equity:
        try:
            invested_capital = float(total_equity) + float(total_debt)
            roi = round(float(net_income) / invested_capital * 100, 2) if invested_capital else None
        except (TypeError, ValueError):
            roi = None

    return FinancialMetrics(
        ticker              = ticker,

        # Valuation
        current_price       = price,
        market_cap          = _f(info.get("marketCap")),
        pe_ratio            = pe_trailing,
        forward_pe          = pe_forward,
        peg_ratio           = _f(info.get("pegRatio")),
        price_to_book       = _f(info.get("priceToBook")),
        price_to_sales      = _f(info.get("priceToSalesTrailing12Months")),

        # Per-share
        eps_ttm             = eps_ttm,
        eps_forward         = eps_fwd,
        book_value          = _f(info.get("bookValue")),
        dividend_yield      = _pct(info.get("dividendYield")),

        # Profitability  (yfinance returns 0-1 ratios)
        gross_margin        = _pct(info.get("grossMargins")),
        operating_margin    = _pct(info.get("operatingMargins")),
        net_margin          = _pct(info.get("profitMargins")),
        roe                 = _pct(info.get("returnOnEquity")),
        roa                 = _pct(info.get("returnOnAssets")),
        roi                 = roi,

        # Liquidity / Leverage
        current_ratio       = _f(info.get("currentRatio")),
        quick_ratio         = _f(info.get("quickRatio")),
        debt_to_equity      = _f(info.get("debtToEquity")),

        # Growth
        revenue_growth_yoy  = _pct(info.get("revenueGrowth")),
        earnings_growth_yoy = _pct(info.get("earningsGrowth")),

        # Risk / Momentum
        beta                = _f(info.get("beta")),
        week_52_high        = _f(info.get("fiftyTwoWeekHigh")),
        week_52_low         = _f(info.get("fiftyTwoWeekLow")),
        avg_volume          = _i(info.get("averageVolume")),

        fetched_at          = datetime.now().isoformat(timespec="seconds"),
    )


# ── portfolio-level aggregation ───────────────────────────────────────────────

def compute_portfolio_metrics(holdings: list) -> PortfolioMetrics:
    """
    Given a list of StockHolding objects, compute portfolio-level statistics.
    Fetches metrics for every held ticker (uses cache to avoid hammering yfinance).
    """
    total_cost    = sum(h.total_cost for h in holdings)
    current_value = sum(h.current_value or h.total_cost for h in holdings)
    gain_loss     = current_value - total_cost
    gain_loss_pct = round(gain_loss / total_cost * 100, 2) if total_cost else 0.0
    profitable    = sum(1 for h in holdings if (h.current_value or 0) > h.total_cost)

    # Weighted-average P/E and Beta (weighted by current holding value)
    weighted_pe   = _weighted_avg(holdings, "pe_ratio",  current_value)
    weighted_beta = _weighted_avg(holdings, "beta",      current_value)

    return PortfolioMetrics(
        total_cost          = round(total_cost,    2),
        current_value       = round(current_value, 2),
        total_gain_loss     = round(gain_loss,     2),
        total_gain_loss_pct = gain_loss_pct,
        weighted_pe         = weighted_pe,
        weighted_beta       = weighted_beta,
        holdings_count      = len(holdings),
        profitable_holdings = profitable,
    )


def _weighted_avg(holdings: list, metric_field: str, total_value: float) -> Optional[float]:
    if not total_value:
        return None
    total_weighted = 0.0
    total_weight   = 0.0
    for h in holdings:
        try:
            m     = get_financial_metrics(h.stock_ticker)
            val   = getattr(m, metric_field)
            weight = h.current_value or h.total_cost
            if val is not None and weight:
                total_weighted += val * weight
                total_weight   += weight
        except Exception:
            continue
    if not total_weight:
        return None
    return round(total_weighted / total_weight, 2)

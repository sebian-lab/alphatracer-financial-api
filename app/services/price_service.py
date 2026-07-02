"""
Price service for fetching real-time and historical stock prices.
Uses Yahoo Finance API (yfinance) as primary data source.
"""

import yfinance as yf
import pandas as pd
from typing import List, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel


class PricePoint(BaseModel):
    """Single price point in time."""
    date: date
    open_price: float
    high: float
    low: float
    close_price: float
    volume: int = 0
    
    class Config:
        from_orm = True


# In-memory cache with TTL of 60 seconds
_price_cache: dict[str, tuple[float, datetime]] = {}

def _get_cached_price(ticker: str) -> Optional[float]:
    """Get price from cache if still valid."""
    if ticker in _price_cache:
        price, timestamp = _price_cache[ticker]
        if datetime.now() - timestamp < timedelta(seconds=60):
            return price
    return None

def _set_cached_price(ticker: str, price: float) -> None:
    """Store price in cache with current timestamp."""
    _price_cache[ticker] = (price, datetime.now())


def get_current_price_with_cache(ticker: str) -> Optional[float]:
    """
    Get current stock price using cached data from Yahoo Finance.

    This function wraps get_current_price() and uses the internal cache
    mechanism to reduce API calls and improve performance for portfolio calculations.

    Args:
        ticker: Stock symbol (e.g., 'AAPL')

    Returns:
        Current price as float if available, None on error
    """
    try:
        # Use the existing get_current_price which already has caching
        return get_current_price(ticker)
    except Exception as e:
        print(f"Error in get_current_price_with_cache for {ticker}: {e}")
        return None


def get_prices_batch(tickers: List[str]) -> dict[str, float]:
    """
    Get prices for multiple tickers efficiently using yfinance's batch API.

    This is more efficient than calling get_current_price() individually
    because it makes fewer HTTP requests to Yahoo Finance.

    Args:
        tickers: List of stock symbols

    Returns:
        Dictionary mapping ticker to price, or empty dict on error
    """
    if not tickers:
        return {}

    try:
        # yfinance supports batch fetching via Tickers class
        ticker_data = yf.Tickers([t.upper() for t in tickers])

        prices = {}
        for symbol, data in ticker_data.__dict__.items():
            if hasattr(data, '__dict__') and 'ticker' in data.__dict__:
                try:
                    price = float(data.ticker.info.get('regularMarketPrice', 0))
                    if price > 0:
                        prices[symbol.lower()] = round(price, 2)
                except (ValueError, TypeError):
                    pass

        return prices
    except Exception as e:
        print(f"Batch price fetch error for {tickers}: {e}")
        # Fallback to individual fetching if batch fails
        return {t: get_current_price(t) for t in tickers}


def get_current_price(ticker: str) -> float:
    """
    Get current price for a stock using Yahoo Finance.
    
    Args:
        ticker: Stock symbol
        
    Returns:
        Current price as float, or 0.0 if unavailable
    """
    # Check cache first
    cached_price = _get_cached_price(ticker)
    if cached_price is not None:
        return round(cached_price, 2)
    
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        # Try regularMarketPrice first (more reliable), then currentPrice as fallback
        info = ticker_obj.info
        
        price = info.get('regularMarketPrice') or \
                info.get('currentPrice') or \
                info.get('price')
        
        if price is None:
            raise ValueError(f"No price found for {ticker}")
        
        # Round to 2 decimal places (standard for stock prices)
        rounded_price = round(float(price), 2)
        
        # Cache the result
        _set_cached_price(ticker, rounded_price)
        
        return rounded_price
        
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return 0.0


def get_historical_prices(
    ticker: str,
    start_date: date,
    end_date: date
) -> List[PricePoint]:
    """
    Get historical price data using Yahoo Finance.
    
    Args:
        ticker: Stock symbol
        start_date: Start date (YYYY-MM-DD format string or date object)
        end_date: End date (YYYY-MM-DD format string or date object)
        
    Returns:
        List of PricePoint objects
    """
    try:
        # Convert to strings if needed
        start_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else str(start_date)
        end_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else str(end_date)
        
        ticker_obj = yf.Ticker(ticker.upper())
        hist = ticker_obj.history(start=start_str, end=end_str)
        
        if hist.empty:
            return []
        
        # Reset index and convert to list of PricePoint objects
        df = hist.reset_index()
        records = []
        
        for _, row in df.iterrows():
            price_point = PricePoint(
                date=row['date'].date(),
                open_price=float(row['Open']) if pd.notna(row['Open']) else 0.0,
                high=float(row['High']) if pd.notna(row['High']) else 0.0,
                low=float(row['Low']) if pd.notna(row['Low']) else 0.0,
                close_price=float(row['Close']) if pd.notna(row['Close']) else 0.0,
                volume=int(row['Volume']) if pd.notna(row['Volume']) else 0
            )
            records.append(price_point)
        
        return records
        
    except Exception as e:
        print(f"Error fetching historical prices for {ticker}: {e}")
        return []

"""Portfolio service for calculating holdings and transactions."""

import yfinance as yf
from app.services.price_service import get_current_price_with_cache
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from app.db.models import User as UserModel, Stock as StockModel, \
    Transaction as TxModel


def calculate_holdings(user: UserModel) -> dict:
    """
    Calculate current portfolio holdings.
    
    Returns:
        Dictionary with 'holdings' list and 'total_value' amount
    """
    # Get all transactions for this user
    buys = TxModel.query.filter(
        TxModel.user_id == user.id,
        TxModel.type == 'buy'
    ).all()
    
    sells = TxModel.query.filter(
        TxModel.user_id == user.id,
        TxModel.type == 'sell'
    ).all()
    
    # Aggregate by ticker
    buy_totals: dict[str, float] = {}
    sell_totals: dict[str, float] = {}
    
    for tx in buys:
        key = (tx.stock.ticker if tx.stock else "Unknown")
        buy_totals[key] = buy_totals.get(key, 0) + (tx.price * tx.quantity)
    
    for tx in sells:
        key = (tx.stock.ticker if tx.stock else "Unknown")
        sell_totals[key] = sell_totals.get(key, 0) + (tx.price * tx.quantity)
    
    # Calculate net holdings
    holdings: List[dict] = []
    total_value = 0.0  # Initialize total value accumulator
    
    for ticker, buy_total in buy_totals.items():
        sell_amount = sell_totals.get(ticker, 0)
        net_price = buy_total - sell_amount
        net_quantity = sum(b.quantity for b in buys if (b.stock and b.stock.ticker == ticker))

        if net_quantity > 0:
            # Fetch current market price for accurate total_value calculation
            try:
                current_price = get_current_price_with_cache(ticker)
            except Exception as e:
                print(f"Warning: Could not fetch price for {ticker}: {e}")
                current_price = net_price  # fallback to historical price
            total_value += current_price * max(net_quantity, 1)
            holdings.append({
                'stock_ticker': ticker,
                'quantity': net_quantity,
                'average_price': round(net_price / max(net_quantity, 1), 2),
                'total_value': round(current_price * max(net_quantity, 1), 2)
            })
    
    return {
        'holdings': holdings,
        'total_value': round(total_value, 2)
    }


def get_portfolio(user: UserModel) -> dict:
    """
    Get user portfolio with total value and current holdings.
    
    Args:
        user: Authenticated user object
        
    Returns:
        Dictionary with 'holdings' and 'total_value'
    """
    return calculate_holdings(user)

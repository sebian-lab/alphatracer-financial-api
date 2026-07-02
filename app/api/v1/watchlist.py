"""
Watchlist endpoints: add, list, and remove watched stocks.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.stock import WatchlistItem
from app.db.models import User as UserModel, Stock as StockModel, Watchlist as WatchlistModel
from app.services.price_service import get_current_price

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _resolve_stock(db: Session, ticker: str) -> StockModel:
    """Find stock by ticker or raise 404."""
    stock = db.query(StockModel).filter(StockModel.ticker == ticker.upper()).first()
    if not stock:
        # Try enriching from CSV before giving up
        try:
            from app.utils.csv_loader import load_tickers
            ticker_data = load_tickers()
            data = ticker_data.get(ticker.upper())
            if data:
                stock = StockModel(
                    ticker=ticker.upper(),
                    name=data.get("name", ticker.upper()),
                    sector=data.get("sector", "Unknown"),
                )
                db.add(stock)
                db.commit()
                db.refresh(stock)
        except Exception:
            pass

    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{ticker.upper()}' not found. Search /api/v1/stocks/search first.",
        )
    return stock


@router.get("", response_model=List[WatchlistItem])
def get_watchlist(
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get current user's watchlist with live prices."""
    entries = (
        db.query(WatchlistModel)
        .filter(WatchlistModel.user_id == user.id)
        .all()
    )

    return [
        WatchlistItem(
            id=entry.id,
            stock_ticker=entry.stock.ticker,
            stock_name=entry.stock.name,
            industry=entry.stock.industry,
            current_price=get_current_price(entry.stock.ticker) or None,
        )
        for entry in entries
    ]


@router.post("/{ticker}", status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    ticker: str,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Add a stock to the watchlist."""
    stock = _resolve_stock(db, ticker)

    existing = db.query(WatchlistModel).filter(
        WatchlistModel.user_id == user.id,
        WatchlistModel.stock_id == stock.id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{stock.ticker}' is already in your watchlist",
        )

    entry = WatchlistModel(user_id=user.id, stock_id=stock.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "message": f"'{stock.ticker}' added to watchlist",
        "stock_ticker": stock.ticker,
        "stock_name": stock.name,
    }


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(
    ticker: str,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Remove a stock from the watchlist."""
    stock = db.query(StockModel).filter(StockModel.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{ticker.upper()}' not found",
        )

    entry = db.query(WatchlistModel).filter(
        WatchlistModel.user_id == user.id,
        WatchlistModel.stock_id == stock.id,
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{stock.ticker}' is not in your watchlist",
        )

    db.delete(entry)
    db.commit()

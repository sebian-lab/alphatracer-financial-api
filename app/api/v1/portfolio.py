"""
Portfolio endpoints: holdings (with live P&L), transactions (buy/sell/delete),
and a portfolio-level metrics summary.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from collections import defaultdict

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.transaction import (
    TransactionCreate, TransactionResponse, StockHolding, PortfolioResponse,
    PortfolioMetricsSummary,
)
from app.db.models import User as UserModel, Stock as StockModel, Transaction as TransactionModel
from app.services.price_service import get_current_price
from app.services.metrics_service import compute_portfolio_metrics

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


# ── internal helpers ───────────────────────────────────────────────────────────

def _get_or_create_stock(db: Session, ticker: str) -> StockModel:
    """
    Lookup stock by ticker (DB first, then CSV cache). Creates row if missing.
    Always expires the session after commit so the returned object reflects
    the actual DB state — prevents stale identity-map rows from prior requests
    causing wrong ticker associations.
    """
    ticker = ticker.upper().strip()
    stock = db.query(StockModel).filter(StockModel.ticker == ticker).first()
    if stock:
        return stock

    # Not in DB yet — resolve name from CSV cache or yfinance
    name = ticker
    sector = "Unknown"
    industry = None
    try:
        from app.utils.csv_loader import load_tickers
        data = load_tickers().get(ticker, {})
        name     = data.get("name", ticker) or ticker
        sector   = data.get("sector", "Unknown") or "Unknown"
        industry = data.get("industry")
    except Exception:
        pass

    # If CSV had nothing, try yfinance for the name (best-effort)
    if name == ticker:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info or {}
            yf_name = info.get("longName") or info.get("shortName")
            if yf_name:
                name = yf_name
        except Exception:
            pass

    stock = StockModel(ticker=ticker, name=name, sector=sector, industry=industry)
    db.add(stock)
    db.commit()
    db.expire(stock)      # force reload from DB so .ticker etc. are fresh
    db.refresh(stock)
    return stock


def _calculate_holdings(transactions: List[TransactionModel]) -> List[StockHolding]:
    """
    Aggregate raw transactions into per-ticker holdings with live price + P&L.
    Only returns positions with net quantity > 0.
    """
    qty_map:  dict[str, float] = defaultdict(float)
    cost_map: dict[str, float] = defaultdict(float)
    name_map: dict[str, str]   = {}

    for tx in transactions:
        t = tx.stock.ticker
        name_map[t] = tx.stock.name or t
        if tx.type == "buy":
            qty_map[t]  += tx.quantity
            cost_map[t] += tx.quantity * tx.price_per_share
        elif tx.type == "sell":
            qty_map[t]  -= tx.quantity
            cost_map[t] -= tx.quantity * tx.price_per_share

    holdings: List[StockHolding] = []
    for ticker, qty in qty_map.items():
        if qty <= 0:
            continue
        total_cost    = round(cost_map[ticker], 2)
        avg_price     = round(total_cost / qty, 4) if qty else 0.0
        current_price = get_current_price(ticker)
        current_value = round(qty * current_price, 2) if current_price else None
        gain_loss     = round(current_value - total_cost, 2) if current_value is not None else None
        gain_loss_pct = (
            round(gain_loss / total_cost * 100, 2)
            if (gain_loss is not None and total_cost)
            else None
        )
        holdings.append(StockHolding(
            stock_ticker  = ticker,
            stock_name    = name_map.get(ticker),
            quantity      = round(qty, 4),
            average_price = avg_price,
            current_price = current_price if current_price else None,
            total_cost    = total_cost,
            current_value = current_value,
            gain_loss     = gain_loss,
            gain_loss_pct = gain_loss_pct,
        ))

    return holdings


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=PortfolioResponse)
def get_portfolio(
    user: UserModel = Depends(get_current_user),
    db:   Session   = Depends(get_db_session),
):
    """Current portfolio snapshot with live prices and P&L for all open positions."""
    txns     = db.query(TransactionModel).filter(TransactionModel.user_id == user.id).all()
    holdings = _calculate_holdings(txns)
    total_cost    = round(sum(h.total_cost for h in holdings), 2)
    current_value = round(sum(h.current_value or h.total_cost for h in holdings), 2)
    return PortfolioResponse(
        user_id       = user.id,
        total_cost    = total_cost,
        current_value = current_value,
        holdings      = holdings,
    )


@router.get("/metrics", response_model=PortfolioMetricsSummary)
def get_portfolio_metrics(
    user: UserModel = Depends(get_current_user),
    db:   Session   = Depends(get_db_session),
):
    """Aggregated portfolio metrics: weighted P/E, Beta, total P&L."""
    txns     = db.query(TransactionModel).filter(TransactionModel.user_id == user.id).all()
    holdings = _calculate_holdings(txns)
    return compute_portfolio_metrics(holdings)


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def add_transaction(
    tx_data: TransactionCreate,
    user:    UserModel = Depends(get_current_user),
    db:      Session   = Depends(get_db_session),
):
    """
    Record a **buy** or **sell** transaction.

    - `stock_ticker`: e.g. `"AAPL"` — auto-created in DB if not already present
    - `type`: `"buy"` or `"sell"`
    - `quantity`: number of shares (positive)
    - `price_per_share`: price paid / received per share
    - `transaction_date`: defaults to today if omitted

    Sell validation: you cannot sell more shares than you currently hold.
    """
    stock = _get_or_create_stock(db, tx_data.stock_ticker)

    if tx_data.type == "sell":
        all_txns = db.query(TransactionModel).filter(
            TransactionModel.user_id  == user.id,
            TransactionModel.stock_id == stock.id,
        ).all()
        net_qty = sum(
            t.quantity if t.type == "buy" else -t.quantity
            for t in all_txns
        )
        if tx_data.quantity > net_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot sell {tx_data.quantity} shares of {stock.ticker}; "
                    f"you currently hold {net_qty:.4f}."
                ),
            )

    txn = TransactionModel(
        user_id          = user.id,
        stock_id         = stock.id,
        type             = tx_data.type,
        quantity         = tx_data.quantity,
        price_per_share  = tx_data.price_per_share,
        transaction_date = tx_data.transaction_date or date.today(),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    db.refresh(stock)   # ensure stock.ticker is the one we just committed

    return TransactionResponse(
        id               = txn.id,
        stock_ticker     = stock.ticker,
        stock_name       = stock.name,
        type             = txn.type,
        quantity         = txn.quantity,
        price_per_share  = txn.price_per_share,
        total_value      = round(txn.quantity * txn.price_per_share, 2),
        transaction_date = txn.transaction_date,
    )


@router.get("/transactions", response_model=List[TransactionResponse])
def list_transactions(
    stock_ticker:     Optional[str] = Query(None, description="Filter by ticker symbol"),
    transaction_type: Optional[str] = Query(None, description="Filter by 'buy' or 'sell'"),
    user: UserModel = Depends(get_current_user),
    db:   Session   = Depends(get_db_session),
):
    """List all transactions for the current user, with optional filters."""
    query = db.query(TransactionModel).filter(TransactionModel.user_id == user.id)
    if stock_ticker:
        query = query.join(StockModel).filter(StockModel.ticker == stock_ticker.upper())
    if transaction_type:
        query = query.filter(TransactionModel.type == transaction_type.lower())
    txns = query.order_by(TransactionModel.transaction_date.desc()).all()
    return [
        TransactionResponse(
            id               = tx.id,
            stock_ticker     = tx.stock.ticker,
            stock_name       = tx.stock.name,
            type             = tx.type,
            quantity         = tx.quantity,
            price_per_share  = tx.price_per_share,
            total_value      = round(tx.quantity * tx.price_per_share, 2),
            transaction_date = tx.transaction_date,
        )
        for tx in txns
    ]


@router.put("/transactions/{tx_id}", response_model=TransactionResponse)
def update_transaction(
    tx_id:   int,
    tx_data: TransactionCreate,
    user:    UserModel = Depends(get_current_user),
    db:      Session   = Depends(get_db_session),
):
    """Correct a transaction (e.g. wrong price or quantity)."""
    txn = db.query(TransactionModel).filter(
        TransactionModel.id      == tx_id,
        TransactionModel.user_id == user.id,
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    stock = _get_or_create_stock(db, tx_data.stock_ticker)
    txn.stock_id         = stock.id
    txn.type             = tx_data.type
    txn.quantity         = tx_data.quantity
    txn.price_per_share  = tx_data.price_per_share
    txn.transaction_date = tx_data.transaction_date or txn.transaction_date
    db.commit()
    db.refresh(txn)
    db.refresh(stock)

    return TransactionResponse(
        id               = txn.id,
        stock_ticker     = stock.ticker,
        stock_name       = stock.name,
        type             = txn.type,
        quantity         = txn.quantity,
        price_per_share  = txn.price_per_share,
        total_value      = round(txn.quantity * txn.price_per_share, 2),
        transaction_date = txn.transaction_date,
    )


@router.delete("/transactions/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    tx_id: int,
    user:  UserModel = Depends(get_current_user),
    db:    Session   = Depends(get_db_session),
):
    """Delete a transaction record."""
    txn = db.query(TransactionModel).filter(
        TransactionModel.id      == tx_id,
        TransactionModel.user_id == user.id,
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(txn)
    db.commit()

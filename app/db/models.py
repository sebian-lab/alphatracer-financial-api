"""
Database models using SQLAlchemy ORM.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(255), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, onupdate=func.now())

    transactions    = relationship("Transaction",  back_populates="user", cascade="all, delete-orphan")
    watchlist_items = relationship("Watchlist",    back_populates="user", cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"

    id       = Column(Integer, primary_key=True, index=True)
    ticker   = Column(String(20),  unique=True, nullable=False, index=True)
    name     = Column(String(255), nullable=False, index=True)
    industry = Column(String(100), nullable=True)
    sector   = Column(String(100), default="Unknown")

    transactions    = relationship("Transaction", back_populates="stock")
    watchlist_items = relationship("Watchlist",   back_populates="stock")
    price_history   = relationship("StockPriceHistory", back_populates="stock",
                                   cascade="all, delete-orphan")


class StockPriceHistory(Base):
    """
    Persistent OHLCV candle storage.

    Every time a market-data endpoint is called for a ticker+interval combo,
    the returned candles are upserted here so the data accumulates over time
    and is available offline / without hitting yfinance again.

    Unique constraint: (ticker, interval, datetime) — safe to re-insert.
    """
    __tablename__ = "stock_price_history"

    id          = Column(Integer, primary_key=True, index=True)
    stock_id    = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    interval    = Column(String(10),  nullable=False)   # 1m, 5m, 1h, 1d, 1wk …
    bar_datetime= Column(DateTime,    nullable=False)    # candle open time (UTC)
    open        = Column(Float,       nullable=False)
    high        = Column(Float,       nullable=False)
    low         = Column(Float,       nullable=False)
    close       = Column(Float,       nullable=False)
    volume      = Column(Float,       nullable=True)
    saved_at    = Column(DateTime,    default=func.now(), onupdate=func.now())

    stock = relationship("Stock", back_populates="price_history")

    __table_args__ = (
        UniqueConstraint("stock_id", "interval", "bar_datetime",
                         name="uq_price_history_stock_interval_dt"),
        Index("ix_price_history_lookup", "stock_id", "interval", "bar_datetime"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id",  ondelete="CASCADE"), nullable=False, index=True)
    stock_id         = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    type             = Column(String(10), nullable=False)   # "buy" or "sell"
    quantity         = Column(Float,   nullable=False)
    price_per_share  = Column(Float,   nullable=False)
    transaction_date = Column(Date,    nullable=False)
    created_at       = Column(DateTime, default=func.now())

    user  = relationship("User",  back_populates="transactions")
    stock = relationship("Stock", back_populates="transactions")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id       = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey("users.id",   ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    added_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_watchlist_user_stock"),
    )

    user  = relationship("User",  back_populates="watchlist_items")
    stock = relationship("Stock", back_populates="watchlist_items")

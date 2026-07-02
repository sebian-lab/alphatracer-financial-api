"""
Pydantic schemas for portfolio and transaction models.
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class TransactionType(str, Enum):
    buy  = "buy"
    sell = "sell"


class TransactionCreate(BaseModel):
    """Payload to create a new buy or sell transaction."""
    stock_ticker:     str             = Field(..., min_length=1, max_length=20,
                                              description="Ticker symbol, e.g. 'AAPL'")
    type:             TransactionType = Field(default=TransactionType.buy)
    quantity:         float           = Field(..., gt=0, description="Number of shares")
    price_per_share:  float           = Field(..., gt=0, description="Price per share")
    transaction_date: Optional[date]  = Field(None, description="Defaults to today")


class TransactionResponse(BaseModel):
    """Full transaction record returned to the client."""
    id:               int
    stock_ticker:     str
    stock_name:       Optional[str]   = None
    type:             TransactionType
    quantity:         float
    price_per_share:  float
    total_value:      float           # quantity * price_per_share
    transaction_date: date

    model_config = {"from_attributes": True}


class StockHolding(BaseModel):
    """Single open position in a portfolio."""
    stock_ticker:  str
    stock_name:    Optional[str]   = None
    quantity:      float
    average_price: float           # cost-basis per share
    current_price: Optional[float] = None  # live from yfinance
    total_cost:    float           # quantity * average_price
    current_value: Optional[float] = None  # quantity * current_price
    gain_loss:     Optional[float] = None  # current_value - total_cost
    gain_loss_pct: Optional[float] = None  # gain_loss / total_cost * 100


class PortfolioResponse(BaseModel):
    """Full portfolio snapshot."""
    user_id:       int
    total_cost:    float
    current_value: Optional[float] = None
    holdings:      List[StockHolding]


class PortfolioMetricsSummary(BaseModel):
    """
    Aggregated financial summary across all holdings.
    Weighted averages use current holding value as weight.
    """
    total_cost:          float
    current_value:       float
    total_gain_loss:     float
    total_gain_loss_pct: float
    weighted_pe:         Optional[float] = None   # value-weighted avg P/E
    weighted_beta:       Optional[float] = None   # value-weighted avg Beta
    holdings_count:      int
    profitable_holdings: int

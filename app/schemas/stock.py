"""
Pydantic schemas for stock-related models.
"""

from typing import Optional
from pydantic import BaseModel, Field


class StockBase(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., max_length=255)
    industry: Optional[str] = None
    sector: str = Field(default="Unknown")


class StockCreate(StockBase):
    pass


class StockResponse(BaseModel):
    id: int
    ticker: str
    name: str
    industry: Optional[str] = None
    sector: str = Field(default="Unknown")

    model_config = {"from_attributes": True}


class WatchlistItem(BaseModel):
    id: int
    stock_ticker: str
    stock_name: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[float] = None

    model_config = {"from_attributes": True}

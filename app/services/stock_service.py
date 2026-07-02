"""
Stock service for loading CSV data and fuzzy search operations.
Updated to support dual GitHub CSV sources with intelligent merging.
"""

import requests
import csv
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import Stock as StockModel
from app.core.database import get_db_session


class StockService:
    """
    Service for stock data management and fuzzy search.
    Now supports multiple GitHub CSV sources with intelligent merging.
    """
    
    # Default GitHub CSV sources (can be overridden by config)
    PRIMARY_TICKER_CSV = "https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/all.csv"
    SECONDARY_TICKER_CSV = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
    
    def __init__(self):
        self._ticker_cache: Dict[str, dict] = {}  # ticker -> {name, sector, industry}
        self._cache_timestamp: Optional[datetime] = None
    
    def load_tickers_from_csvs(
        self,
        db: Session = None
    ) -> List[StockModel]:
        """
        Load tickers from multiple GitHub CSV sources and merge them.
        
        Args:
            db: Database session (optional, for upserting into DB)
            
        Returns:
            List of loaded stock models (if db provided)
        """
        merged_data = self._merge_csv_sources()
        
        stocks_to_add = []
        
        if db is not None:
            # Upsert each ticker into database
            for ticker, data in merged_data.items():
                existing = StockModel.query.filter(
                    StockModel.ticker == ticker.upper()
                ).first()
                
                if existing:
                    # Update existing record
                    existing.name = data.get('name', '')
                    existing.sector = data.get('sector', 'Consumer Discretionary')
                    stocks_to_add.append(existing)
                else:
                    # Create new stock model
                    new_stock = StockModel(
                        ticker=ticker.upper(),
                        name=data.get('name', ''),
                        sector=data.get('sector', 'Consumer Discretionary'),
                        industry=data.get('industry')
                    )
                    db.add(new_stock)
                    stocks_to_add.append(new_stock)
        
        # Update in-memory cache
        self._ticker_cache = merged_data
        self._cache_timestamp = datetime.now()
        
        return stocks_to_add
    
    def _merge_csv_sources(self) -> Dict[str, dict]:
        """
        Download and merge multiple CSV sources.
        Returns a dictionary with ticker as key.
        Primary source takes precedence for duplicate tickers.
        """
        merged: Dict[str, dict] = {}
        
        # Load primary source
        primary_data = self._load_and_parse_csv(self.PRIMARY_TICKER_CSV)
        merged.update(primary_data)
        
        # Load secondary source (as fallback/supplement)
        secondary_data = self._load_and_parse_csv(self.SECONDARY_TICKER_CSV)
        for ticker, data in secondary_data.items():
            if ticker not in merged:
                merged[ticker] = data
        
        return merged
    
    def _load_and_parse_csv(self, csv_url: str) -> Dict[str, dict]:
        """
        Download and parse a single CSV source.
        
        Args:
            csv_url: URL of the CSV file
            
        Returns:
            Dictionary mapping ticker to stock data
        """
        try:
            response = requests.get(csv_url, timeout=15)
            response.raise_for_status()
            
            # Parse CSV with proper error handling for malformed lines
            parsed_data: Dict[str, dict] = {}
            
            reader = csv.DictReader(response.iter_lines())
            if reader.fieldnames is None:
                return parsed_data
            
            # Map common column names to our expected format
            symbol_idx = self._find_column_index(reader.fieldnames, 'symbol')
            name_idx = self._find_column_index(reader.fieldnames, 'name')
            sector_idx = self._find_column_index(reader.fieldnames, 'sector')
            industry_idx = self._find_column_index(reader.fieldnames, 'industry')
            
            for row in reader:
                try:
                    ticker = row.get(symbol_idx) if callable(symbol_idx) else symbol_idx(row) if isinstance(symbol_idx, int) else None
                    
                    # Skip if no ticker found
                    if not ticker or not ticker.strip():
                        continue
                    
                    data = {
                        'ticker': ticker.upper().strip(),
                        'name': row.get(name_idx).strip() if callable(name_idx) else name_idx(row).strip() if isinstance(name_idx, int) else '',
                        'sector': row.get(sector_idx).strip() if callable(sector_idx) else sector_idx(row).strip() if isinstance(sector_idx, int) else 'Consumer Discretionary',
                        'industry': row.get(industry_idx).strip() if callable(industry_idx) else industry_idx(row).strip() if isinstance(industry_idx, int) else None
                    }
                    
                    # Skip duplicates within same source (keep first)
                    if data['ticker'] not in parsed_data:
                        parsed_data[data['ticker']] = data
                        
                except Exception as row_error:
                    # Log and skip malformed rows
                    continue
            
            return parsed_data
            
        except Exception as e:
            print(f"Warning: Failed to load CSV from {csv_url}: {e}")
            return {}
    
    def _find_column_index(self, fieldnames: List[str], target: str) -> int:
        """Find column index by name (case-insensitive)."""
        if not fieldnames:
            return 0
        for i, name in enumerate(fieldnames):
            if name.lower() == target.lower():
                return i
        return 0
    
    def get_cached_ticker(self, ticker: str) -> Optional[dict]:
        """Get cached ticker data."""
        ticker_upper = ticker.upper().strip()
        if ticker_upper in self._ticker_cache:
            return self._ticker_cache[ticker_upper]
        return None
    
    def search_stocks(
        self,
        query: str,
        limit: int = 10,
        db: Session = None
    ) -> List[Dict]:
        """
        Search stocks using cached ticker data.
        
        Args:
            query: Search string
            limit: Maximum results
            db: Database session (optional)
            
        Returns:
            List of matching stock dictionaries sorted by relevance
        """
        # If cache is stale, refresh it
        if self._cache_timestamp and datetime.now() - self._cache_timestamp > timedelta(hours=1):
            self.load_tickers_from_csvs(db)
        
        results = []
        query_lower = query.lower().strip()
        
        for ticker, data in self._ticker_cache.items():
            ticker_lower = ticker.lower()
            name_lower = data.get('name', '').lower()
            
            # Calculate relevance score
            score = self._calculate_search_score(ticker_lower, name_lower, query_lower)
            
            if score > 0:
                results.append({
                    'ticker': data['ticker'],
                    'name': data.get('name', ''),
                    'sector': data.get('sector', 'Consumer Discretionary'),
                    'industry': data.get('industry'),
                    'score': score,
                    'model': StockModel(ticker=data['ticker'], name=data.get('name', ''), sector=data.get('sector', '')) if db else None
                })
        
        # Sort by score descending, then alphabetically
        results.sort(key=lambda x: (-x['score'], x['ticker'].lower()))
        return results[:limit]


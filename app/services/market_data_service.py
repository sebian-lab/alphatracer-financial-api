"""
Market Data Service — TradingView-style indicators, all computed from
yfinance (Yahoo Finance). Zero API keys. Zero tokens.

Intervals supported by yfinance:
  1m 2m 5m 15m 30m 60m 90m 1h 1d 5d 1wk 1mo 3mo

Max history yfinance allows per interval (hard limits):
  1m  → last  7 days
  2m  → last 60 days
  5m  → last 60 days
  15m → last 60 days
  30m → last 60 days
  60m → last730 days (~2 years)
  90m → last 60 days
  1h  → last730 days (~2 years)
  1d  → full history (decades)
  5d  → full history
  1wk → full history
  1mo → full history
  3mo → full history

Candles are saved to the local DB (stock_price_history table) every time
they are fetched, so history accumulates and the DB eventually holds
everything yfinance ever returns for each ticker.

Indicators computed in pure pandas/numpy (no TA-Lib required):
  Quote       : open, high, low, close, volume, vwap, change%, amplitude%
  Moving avgs : SMA 20/50/200, EMA 9/21/50
  Momentum    : RSI-14, Stochastic %K/%D, CCI-20, Williams %R-14
  Trend       : MACD line/signal/histogram, ADX-14 (+DI/-DI)
  Volatility  : Bollinger Bands (20,2), ATR-14
  Volume      : OBV, VWAP (intraday)
  Signals     : overall TradingView-style summary (BUY/SELL/NEUTRAL + score)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

import numpy as np
import pandas as pd


# ── response schemas ──────────────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    datetime: str
    open:     float
    high:     float
    low:      float
    close:    float
    volume:   float

class Quote(BaseModel):
    ticker:        str
    name:          Optional[str]  = None
    exchange:      Optional[str]  = None
    currency:      Optional[str]  = "USD"
    price:         Optional[float] = None
    open:          Optional[float] = None
    high:          Optional[float] = None
    low:           Optional[float] = None
    prev_close:    Optional[float] = None
    volume:        Optional[int]   = None
    avg_volume:    Optional[int]   = None
    change:        Optional[float] = None
    change_pct:    Optional[float] = None
    amplitude_pct: Optional[float] = None
    market_cap:    Optional[float] = None
    week_52_high:  Optional[float] = None
    week_52_low:   Optional[float] = None
    fetched_at:    str = ""

class MovingAverages(BaseModel):
    sma_20:  Optional[float] = None
    sma_50:  Optional[float] = None
    sma_200: Optional[float] = None
    ema_9:   Optional[float] = None
    ema_21:  Optional[float] = None
    ema_50:  Optional[float] = None
    vwap:    Optional[float] = None

class Oscillators(BaseModel):
    rsi_14:       Optional[float] = None
    stoch_k:      Optional[float] = None
    stoch_d:      Optional[float] = None
    cci_20:       Optional[float] = None
    williams_r:   Optional[float] = None
    macd:         Optional[float] = None
    macd_signal:  Optional[float] = None
    macd_hist:    Optional[float] = None
    adx:          Optional[float] = None
    di_plus:      Optional[float] = None
    di_minus:     Optional[float] = None

class VolatilityIndicators(BaseModel):
    bb_upper:    Optional[float] = None
    bb_middle:   Optional[float] = None
    bb_lower:    Optional[float] = None
    bb_width:    Optional[float] = None
    bb_pct_b:    Optional[float] = None
    atr_14:      Optional[float] = None

class VolumeIndicators(BaseModel):
    obv:         Optional[float] = None
    volume:      Optional[float] = None
    avg_volume:  Optional[float] = None
    rel_volume:  Optional[float] = None

class TradingSignal(BaseModel):
    rating:          str
    score:           float
    buy_signals:     int
    sell_signals:    int
    neutral_signals: int
    signals:         dict

class FullAnalysis(BaseModel):
    quote:       Quote
    candles:     List[OHLCVBar]        = []
    ma:          MovingAverages        = MovingAverages()
    oscillators: Oscillators           = Oscillators()
    volatility:  VolatilityIndicators  = VolatilityIndicators()
    volume:      VolumeIndicators      = VolumeIndicators()
    signal:      TradingSignal         = TradingSignal(
        rating="NEUTRAL", score=0, buy_signals=0, sell_signals=0,
        neutral_signals=0, signals={}
    )
    interval:    str = "1d"
    period:      str = "3mo"
    bars_saved:  int = 0   # how many candles were upserted to DB this call


# ── yfinance max-period map ───────────────────────────────────────────────────
# These are the maximum periods yfinance will return without error per interval.
# We use "max" for daily/weekly/monthly to grab full history.
_MAX_PERIOD: dict[str, str] = {
    "1m":  "7d",
    "2m":  "60d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "90m": "60d",
    "1h":  "730d",
    "1d":  "max",
    "5d":  "max",
    "1wk": "max",
    "1mo": "max",
    "3mo": "max",
}


# ── in-memory cache ───────────────────────────────────────────────────────────
_cache: dict[str, tuple[FullAnalysis, datetime]] = {}
_QUOTE_TTL = 60    # seconds
_TECH_TTL  = 300   # seconds


def _cache_key(ticker: str, interval: str, period: str) -> str:
    return f"{ticker}|{interval}|{period}"


# ── math helpers ──────────────────────────────────────────────────────────────

def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def _sma(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w).mean()

def _rsi(close: pd.Series, p: int = 14) -> pd.Series:
    d = close.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def _macd(close: pd.Series, fast=12, slow=26, sig=9):
    ml = _ema(close, fast) - _ema(close, slow)
    sl = _ema(ml, sig)
    return ml, sl, ml - sl

def _bollinger(close: pd.Series, w=20, mult=2.0):
    m = _sma(close, w)
    s = close.rolling(w).std()
    return m + mult * s, m, m - mult * s

def _stochastic(hi, lo, cl, kp=14, dp=3):
    lk = lo.rolling(kp).min()
    hk = hi.rolling(kp).max()
    k  = 100 * (cl - lk) / (hk - lk).replace(0, np.nan)
    return k, k.rolling(dp).mean()

def _cci(hi, lo, cl, w=20) -> pd.Series:
    tp  = (hi + lo + cl) / 3
    sma = tp.rolling(w).mean()
    mad = tp.rolling(w).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))

def _williams_r(hi, lo, cl, p=14) -> pd.Series:
    hh = hi.rolling(p).max()
    ll = lo.rolling(p).min()
    return -100 * (hh - cl) / (hh - ll).replace(0, np.nan)

def _atr(hi, lo, cl, p=14) -> pd.Series:
    tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()

def _adx(hi, lo, cl, p=14):
    up   = hi.diff();  down = -lo.diff()
    pdm  = np.where((up > down) & (up > 0), up,   0.0)
    mdm  = np.where((down > up) & (down > 0), down, 0.0)
    tr   = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
    atr_s = pd.Series(tr).ewm(span=p, adjust=False).mean()
    pdi  = 100 * pd.Series(pdm).ewm(span=p, adjust=False).mean() / atr_s.replace(0, np.nan)
    mdi  = 100 * pd.Series(mdm).ewm(span=p, adjust=False).mean() / atr_s.replace(0, np.nan)
    dx   = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(span=p, adjust=False).mean(), pdi, mdi

def _obv(cl: pd.Series, vol: pd.Series) -> pd.Series:
    return (np.sign(cl.diff()).fillna(0) * vol).cumsum()

def _vwap(hi, lo, cl, vol) -> pd.Series:
    tp = (hi + lo + cl) / 3
    return (tp * vol).cumsum() / vol.cumsum().replace(0, np.nan)

def _f(val) -> Optional[float]:
    try:
        v = float(val)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 4)
    except Exception:
        return None

def _last(s: pd.Series) -> Optional[float]:
    d = s.dropna()
    return _f(d.iloc[-1]) if not d.empty else None


# ── signal ────────────────────────────────────────────────────────────────────

def _ind_sig(val, buy_t, sell_t, inv=False):
    if val is None: return "NEUTRAL"
    if not inv:
        if val <= buy_t:  return "BUY"
        if val >= sell_t: return "SELL"
    else:
        if val >= buy_t:  return "BUY"
        if val <= sell_t: return "SELL"
    return "NEUTRAL"

def _compute_signal(price, ma: MovingAverages, osc: Oscillators, vol: VolatilityIndicators) -> TradingSignal:
    sig = {}
    for name, mv in [("SMA20", ma.sma_20), ("SMA50", ma.sma_50), ("SMA200", ma.sma_200),
                     ("EMA9",  ma.ema_9),  ("EMA21", ma.ema_21), ("EMA50",  ma.ema_50)]:
        sig[name] = ("BUY" if price > mv else "SELL") if (mv and price) else "NEUTRAL"
    sig["RSI14"]      = _ind_sig(osc.rsi_14,    30,   70)
    sig["STOCH_K"]    = _ind_sig(osc.stoch_k,   20,   80)
    sig["CCI20"]      = _ind_sig(osc.cci_20,  -100,  100)
    sig["WILLIAMS_R"] = _ind_sig(osc.williams_r, -80, -20)
    sig["MACD"]       = ("BUY" if osc.macd_hist > 0 else "SELL") if osc.macd_hist is not None else "NEUTRAL"
    sig["ADX"]        = ("BUY" if osc.di_plus > osc.di_minus else "SELL") \
                        if (osc.di_plus is not None and osc.di_minus is not None) else "NEUTRAL"
    if vol.bb_lower and vol.bb_upper and price:
        sig["BB"] = "BUY" if price < vol.bb_lower else ("SELL" if price > vol.bb_upper else "NEUTRAL")
    else:
        sig["BB"] = "NEUTRAL"
    buys = sum(1 for s in sig.values() if s == "BUY")
    sells= sum(1 for s in sig.values() if s == "SELL")
    neut = sum(1 for s in sig.values() if s == "NEUTRAL")
    score= round((buys - sells) / len(sig), 3) if sig else 0
    rating = ("STRONG BUY"  if score >= 0.6 else
              "BUY"         if score >= 0.2 else
              "STRONG SELL" if score <= -0.6 else
              "SELL"        if score <= -0.2 else "NEUTRAL")
    return TradingSignal(rating=rating, score=score, buy_signals=buys,
                         sell_signals=sells, neutral_signals=neut, signals=sig)


# ── DB persistence ────────────────────────────────────────────────────────────

def _save_candles_to_db(ticker: str, interval: str, df: pd.DataFrame) -> int:
    """
    Upsert OHLCV rows into stock_price_history.
    Returns number of rows inserted/updated.
    Uses INSERT OR REPLACE (SQLite) / ON CONFLICT DO UPDATE (Postgres) via
    a simple delete-then-insert pattern that works on both.
    """
    if df is None or df.empty:
        return 0
    try:
        from app.core.database import SessionLocal
        from app.db.models import Stock as StockModel, StockPriceHistory

        db = SessionLocal()
        try:
            # Resolve stock_id (create row if first time seeing this ticker)
            stock = db.query(StockModel).filter(StockModel.ticker == ticker).first()
            if not stock:
                stock = StockModel(ticker=ticker, name=ticker, sector="Unknown")
                db.add(stock)
                db.commit()
                db.refresh(stock)

            stock_id = stock.id
            saved = 0

            for idx, row in df.iterrows():
                try:
                    bar_dt = idx.to_pydatetime().replace(tzinfo=None)
                    o = float(row.get("open",  0) or 0)
                    h = float(row.get("high",  0) or 0)
                    l = float(row.get("low",   0) or 0)
                    c = float(row.get("close", 0) or 0)
                    v = float(row.get("volume", 0) or 0)
                    if c == 0:
                        continue

                    # Upsert: delete existing row for this exact candle then re-insert
                    db.query(StockPriceHistory).filter(
                        StockPriceHistory.stock_id     == stock_id,
                        StockPriceHistory.interval     == interval,
                        StockPriceHistory.bar_datetime == bar_dt,
                    ).delete(synchronize_session=False)

                    db.add(StockPriceHistory(
                        stock_id     = stock_id,
                        interval     = interval,
                        bar_datetime = bar_dt,
                        open         = o,
                        high         = h,
                        low          = l,
                        close        = c,
                        volume       = v,
                    ))
                    saved += 1
                except Exception:
                    continue

            db.commit()
            return saved
        finally:
            db.close()
    except Exception as exc:
        print(f"[market_data] DB save error (non-fatal): {exc}")
        return 0


# ── public API ────────────────────────────────────────────────────────────────

def get_market_data(
    ticker:   str,
    interval: str = "1d",
    period:   str = "3mo",
) -> FullAnalysis:
    """
    Fetch OHLCV + compute all TradingView-style indicators.
    Candles are saved to the DB on every call.
    Cache: 60 s for sub-minute intervals, 300 s otherwise.
    """
    ticker = ticker.upper()
    key    = _cache_key(ticker, interval, period)
    ttl    = _QUOTE_TTL if interval in ("1m", "2m", "5m") else _TECH_TTL

    if key in _cache:
        cached, ts = _cache[key]
        if (datetime.now() - ts).total_seconds() < ttl:
            return cached

    result = _build_analysis(ticker, interval, period)
    _cache[key] = (result, datetime.now())
    return result


def get_market_data_max(ticker: str, interval: str = "1d") -> FullAnalysis:
    """
    Fetch the **maximum history** yfinance allows for this interval,
    then save everything to the DB.
    """
    period = _MAX_PERIOD.get(interval, "max")
    return get_market_data(ticker, interval=interval, period=period)


def get_quote_only(ticker: str) -> Quote:
    """Lightweight live quote — cached 60 s."""
    ticker = ticker.upper()
    key    = f"quote|{ticker}"
    if key in _cache:
        cached, ts = _cache[key]
        if (datetime.now() - ts).total_seconds() < _QUOTE_TTL:
            return cached  # type: ignore

    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    q = Quote(
        ticker        = ticker,
        name          = info.get("longName") or info.get("shortName"),
        exchange      = info.get("exchange"),
        currency      = info.get("currency", "USD"),
        price         = _f(info.get("regularMarketPrice") or info.get("currentPrice")),
        open          = _f(info.get("regularMarketOpen")  or info.get("open")),
        high          = _f(info.get("regularMarketDayHigh") or info.get("dayHigh")),
        low           = _f(info.get("regularMarketDayLow")  or info.get("dayLow")),
        prev_close    = _f(info.get("regularMarketPreviousClose") or info.get("previousClose")),
        volume        = info.get("regularMarketVolume") or info.get("volume"),
        avg_volume    = info.get("averageVolume"),
        market_cap    = _f(info.get("marketCap")),
        week_52_high  = _f(info.get("fiftyTwoWeekHigh")),
        week_52_low   = _f(info.get("fiftyTwoWeekLow")),
        fetched_at    = datetime.now().isoformat(timespec="seconds"),
    )
    if q.price and q.prev_close:
        q.change     = _f(q.price - q.prev_close)
        q.change_pct = _f((q.price - q.prev_close) / q.prev_close * 100)
    if q.high and q.low and q.prev_close:
        q.amplitude_pct = _f((q.high - q.low) / q.prev_close * 100)

    _cache[key] = (q, datetime.now())  # type: ignore
    return q


def _build_analysis(ticker: str, interval: str, period: str) -> FullAnalysis:
    import yfinance as yf

    # ── fetch OHLCV ──────────────────────────────────────────────────────────
    try:
        yf_ticker = yf.Ticker(ticker)
        df        = yf_ticker.history(period=period, interval=interval)
        info      = yf_ticker.info or {}
    except Exception as exc:
        print(f"[market_data] yfinance error for {ticker}: {exc}")
        df   = pd.DataFrame()
        info = {}

    # Normalise column names
    if not df.empty:
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

    # ── persist candles to DB ────────────────────────────────────────────────
    bars_saved = _save_candles_to_db(ticker, interval, df)
    if bars_saved:
        print(f"[market_data] saved {bars_saved} {interval} bars for {ticker}")

    # ── build quote ──────────────────────────────────────────────────────────
    quote = Quote(
        ticker       = ticker,
        name         = info.get("longName") or info.get("shortName"),
        exchange     = info.get("exchange"),
        currency     = info.get("currency", "USD"),
        market_cap   = _f(info.get("marketCap")),
        week_52_high = _f(info.get("fiftyTwoWeekHigh")),
        week_52_low  = _f(info.get("fiftyTwoWeekLow")),
        avg_volume   = info.get("averageVolume"),
        fetched_at   = datetime.now().isoformat(timespec="seconds"),
    )

    if df.empty:
        return FullAnalysis(quote=quote, interval=interval, period=period, bars_saved=bars_saved)

    close  = df["close"]
    open_  = df["open"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

    last_close = _f(close.iloc[-1])
    prev_close = _f(close.iloc[-2]) if len(close) > 1 else None
    quote.price      = last_close
    quote.open       = _f(open_.iloc[-1])
    quote.high       = _f(high.iloc[-1])
    quote.low        = _f(low.iloc[-1])
    quote.prev_close = prev_close or _f(info.get("regularMarketPreviousClose"))
    if not volume.empty:
        quote.volume = int(volume.iloc[-1])
    if quote.price and quote.prev_close:
        quote.change     = _f(quote.price - quote.prev_close)
        quote.change_pct = _f((quote.price - quote.prev_close) / quote.prev_close * 100)
    if quote.high and quote.low and quote.prev_close:
        quote.amplitude_pct = _f((quote.high - quote.low) / quote.prev_close * 100)

    # ── candles (last 200 bars in response; all bars saved to DB) ────────────
    candles = []
    for idx, row in df.tail(200).iterrows():
        try:
            candles.append(OHLCVBar(
                datetime = str(idx)[:19],
                open     = round(float(row.get("open",  0)), 4),
                high     = round(float(row.get("high",  0)), 4),
                low      = round(float(row.get("low",   0)), 4),
                close    = round(float(row.get("close", 0)), 4),
                volume   = float(row.get("volume", 0)),
            ))
        except Exception:
            continue

    # ── indicators ───────────────────────────────────────────────────────────
    vwap_val = _last(_vwap(high, low, close, volume)) if not volume.empty else None
    ma = MovingAverages(
        sma_20=_last(_sma(close,20)), sma_50=_last(_sma(close,50)),
        sma_200=_last(_sma(close,200)),
        ema_9=_last(_ema(close,9)), ema_21=_last(_ema(close,21)),
        ema_50=_last(_ema(close,50)), vwap=vwap_val,
    )
    ml, sl, mh     = _macd(close)
    sk, sd         = _stochastic(high, low, close)
    adx_s, pdi, mdi= _adx(high, low, close)
    osc = Oscillators(
        rsi_14=_last(_rsi(close)), stoch_k=_last(sk), stoch_d=_last(sd),
        cci_20=_last(_cci(high, low, close)),
        williams_r=_last(_williams_r(high, low, close)),
        macd=_last(ml), macd_signal=_last(sl), macd_hist=_last(mh),
        adx=_last(adx_s), di_plus=_last(pdi), di_minus=_last(mdi),
    )
    bu, bm, bl = _bollinger(close)
    bu_v = _last(bu); bm_v = _last(bm); bl_v = _last(bl)
    vol_ind = VolatilityIndicators(
        bb_upper=bu_v, bb_middle=bm_v, bb_lower=bl_v,
        bb_width=_f((bu_v-bl_v)/bm_v*100) if (bu_v and bl_v and bm_v) else None,
        bb_pct_b=_f((last_close-bl_v)/(bu_v-bl_v)) if (bu_v and bl_v and last_close and bu_v!=bl_v) else None,
        atr_14=_last(_atr(high, low, close)),
    )
    obv_val = _last(_obv(close, volume)) if not volume.empty else None
    avg_vol = quote.avg_volume; cur_vol = quote.volume
    vol_ind2 = VolumeIndicators(
        obv=obv_val, volume=float(cur_vol) if cur_vol else None,
        avg_volume=float(avg_vol) if avg_vol else None,
        rel_volume=_f(cur_vol/avg_vol) if (cur_vol and avg_vol) else None,
    )
    signal = _compute_signal(last_close, ma, osc, vol_ind)

    return FullAnalysis(
        quote=quote, candles=candles, ma=ma, oscillators=osc,
        volatility=vol_ind, volume=vol_ind2, signal=signal,
        interval=interval, period=period, bars_saved=bars_saved,
    )

"""
data.py – SPY data download and preprocessing.
Uses yfinance with CSV fallback.
"""
import os
import pandas as pd
import numpy as np

CACHE_PATH = os.path.join(os.path.dirname(__file__), "spy_daily.csv")


def download_spy(start: str = "1993-01-29", end: str | None = None,
                 cache: bool = True) -> pd.DataFrame:
    """
    Download SPY daily OHLCV from yfinance (auto-adjusted for splits/dividends).
    Falls back to a local CSV if yfinance is unavailable.

    Returns DataFrame with columns: Open, High, Low, Close, Volume
    indexed by DatetimeIndex (tz-naive, daily).
    """
    if cache and os.path.exists(CACHE_PATH):
        df = pd.read_csv(CACHE_PATH, index_col=0, parse_dates=True)
        if len(df) > 100:
            print(f"[data] Loaded {len(df)} rows from cache: {CACHE_PATH}")
            return _clean(df)

    try:
        import yfinance as yf
        ticker = yf.Ticker("SPY")
        df = ticker.history(start=start, end=end, auto_adjust=True)
        if df.empty:
            raise ValueError("yfinance returned empty dataframe")
        # Keep only OHLCV
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        if cache:
            df.to_csv(CACHE_PATH)
            print(f"[data] Downloaded {len(df)} rows via yfinance, cached to {CACHE_PATH}")
        return _clean(df)
    except Exception as e:
        print(f"[data] yfinance failed ({e}), trying CSV fallback...")
        return _load_csv_fallback()


def _load_csv_fallback() -> pd.DataFrame:
    """
    Fallback: load from CSV.
    Expected columns: Date (or index), Open, High, Low, Close, Volume.
    Adjust column names case-insensitively.
    """
    if not os.path.exists(CACHE_PATH):
        raise FileNotFoundError(
            f"No cached data at {CACHE_PATH}. "
            "Please provide a CSV with columns: Date, Open, High, Low, Close, Volume"
        )
    df = pd.read_csv(CACHE_PATH, index_col=0, parse_dates=True)
    print(f"[data] Loaded {len(df)} rows from CSV fallback: {CACHE_PATH}")
    return _clean(df)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names, sort, drop NaN rows."""
    # Normalize column names
    col_map = {}
    for c in df.columns:
        cl = c.lower().strip()
        if "open" in cl:
            col_map[c] = "Open"
        elif "high" in cl:
            col_map[c] = "High"
        elif "low" in cl:
            col_map[c] = "Low"
        elif "close" in cl:
            col_map[c] = "Close"
        elif "vol" in cl:
            col_map[c] = "Volume"
    df = df.rename(columns=col_map)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"Missing column {c} in data")
    df = df[needed].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df.dropna(subset=["Close"])
    # Remove duplicate indices
    df = df[~df.index.duplicated(keep="first")]
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-compute common indicators used across strategies.
    All computed from Close (and High/Low for ATR).
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # EMAs
    for span in [10, 20, 50, 100, 150, 200]:
        df[f"EMA_{span}"] = close.ewm(span=span, adjust=False).mean()

    # ATR (14-day default, also 20-day)
    for period in [14, 20]:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        df[f"ATR_{period}"] = tr.ewm(span=period, adjust=False).mean()

    # RSI (14-day)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI_14"] = 100 - 100 / (1 + rs)

    # Realized volatility (20-day)
    df["RealVol_20"] = close.pct_change().rolling(20).std() * np.sqrt(252)

    return df

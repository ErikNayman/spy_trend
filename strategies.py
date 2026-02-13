"""
strategies.py – EMA-centric trend-following strategy candidates.

Each strategy function takes a DataFrame (with indicators pre-computed)
and a parameter dict, and returns a signal Series:
  - Binary (0/1) for strategies A-F, I
  - Fractional [0, 1] for strategies G, H (position sizing)

All signals are computed from Close and lagging indicators only —
no look-ahead is introduced here. The backtest engine handles the
1-day execution delay.

Strategy Catalog:
  A) ema_crossover         – Classic fast/slow EMA crossover
  B) regime_filter         – Long only when price > EMA(long) with slope filter
  C) buy_dip_in_uptrend    – Enter on pullbacks inside a bullish regime
  D) ema_atr_stop          – EMA crossover + ATR trailing stop
  E) composite             – Regime + dip entry + ATR stop (kitchen sink)
  F) hysteresis_regime     – Regime filter with hysteresis bands to reduce whipsaws
  G) sizing_regime         – Regime filter with volatility-scaled fractional sizing
  H) atr_dip_addon         – Base regime position + ATR-scaled dip add-on (fractional)
  I) breakout_or_dip       – Dual-mode: breakout OR dip entry inside regime
"""
import numpy as np
import pandas as pd
from itertools import product


# ─────────────────────────────────────────────────────────────────────
# Strategy A: EMA fast/slow crossover
# ─────────────────────────────────────────────────────────────────────
def ema_crossover(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Long when EMA(fast) > EMA(slow), else cash.

    Params:
      fast: int (EMA fast period)
      slow: int (EMA slow period)
    """
    fast = params["fast"]
    slow = params["slow"]
    ema_f = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["Close"].ewm(span=slow, adjust=False).mean()
    signal = (ema_f > ema_s).astype(int)
    return signal


def ema_crossover_grid() -> list[dict]:
    """Parameter grid for Strategy A."""
    grid = []
    for fast in [10, 20, 30, 50]:
        for slow in [50, 100, 150, 200]:
            if fast < slow:
                grid.append({"fast": fast, "slow": slow})
    return grid


# ─────────────────────────────────────────────────────────────────────
# Strategy B: Regime filter (price > EMA + slope)
# ─────────────────────────────────────────────────────────────────────
def regime_filter(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Long when:
      1) Close > EMA(regime_len)   AND
      2) EMA(regime_len) slope over `slope_window` days is positive
         (or slope check is disabled if slope_window == 0).

    Params:
      regime_len: int (EMA period for regime, e.g., 200)
      slope_window: int (days to compute EMA slope; 0 = disabled)
    """
    regime_len = params["regime_len"]
    slope_window = params["slope_window"]

    ema = df["Close"].ewm(span=regime_len, adjust=False).mean()
    above_ema = df["Close"] > ema

    if slope_window > 0:
        slope_positive = ema.diff(slope_window) > 0
        signal = (above_ema & slope_positive).astype(int)
    else:
        signal = above_ema.astype(int)

    return signal


def regime_filter_grid() -> list[dict]:
    """Parameter grid for Strategy B."""
    grid = []
    for regime_len in [100, 150, 200]:
        for slope_window in [0, 10, 20, 50]:
            grid.append({"regime_len": regime_len, "slope_window": slope_window})
    return grid


# ─────────────────────────────────────────────────────────────────────
# Strategy C: Buy-the-dip inside an uptrend
# ─────────────────────────────────────────────────────────────────────
def buy_dip_in_uptrend(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Regime: Close > EMA(regime_len).
    Entry: when in regime AND Close pulls back to within `dip_pct`%
           of EMA(dip_ema) (i.e., Close <= EMA(dip_ema) * (1 + dip_pct/100)).
    Exit: Close < EMA(regime_len) (regime break).

    This keeps you in the trade once entered until the regime breaks.

    Params:
      regime_len: int (e.g., 200)
      dip_ema: int (e.g., 20 or 50)
      dip_pct: float (e.g., 2.0 means within 2% above dip EMA)
    """
    regime_len = params["regime_len"]
    dip_ema = params["dip_ema"]
    dip_pct = params["dip_pct"]

    close = df["Close"]
    ema_regime = close.ewm(span=regime_len, adjust=False).mean()
    ema_dip = close.ewm(span=dip_ema, adjust=False).mean()

    in_regime = close > ema_regime
    near_dip_ema = close <= ema_dip * (1 + dip_pct / 100)
    entry_trigger = in_regime & near_dip_ema

    # State machine: enter on trigger, stay in until regime break
    signal = pd.Series(0, index=df.index)
    in_position = False
    for i in range(len(df)):
        if not in_position:
            if entry_trigger.iloc[i]:
                in_position = True
                signal.iloc[i] = 1
        else:
            if not in_regime.iloc[i]:
                in_position = False
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal


def buy_dip_in_uptrend_grid() -> list[dict]:
    """Parameter grid for Strategy C."""
    grid = []
    for regime_len in [150, 200]:
        for dip_ema in [20, 50]:
            for dip_pct in [0.0, 1.0, 2.0, 3.0]:
                grid.append({
                    "regime_len": regime_len,
                    "dip_ema": dip_ema,
                    "dip_pct": dip_pct,
                })
    return grid


# ─────────────────────────────────────────────────────────────────────
# Strategy D: EMA crossover + ATR trailing stop
# ─────────────────────────────────────────────────────────────────────
def ema_atr_stop(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Entry: EMA(fast) > EMA(slow).
    Exit: Close drops below trailing stop = highest_close_since_entry - atr_mult * ATR(atr_len).
    Re-enter when EMA crossover fires again after being stopped out.

    Params:
      fast: int
      slow: int
      atr_len: int (ATR period)
      atr_mult: float (ATR multiplier for stop)
    """
    fast = params["fast"]
    slow = params["slow"]
    atr_len = params["atr_len"]
    atr_mult = params["atr_mult"]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    crossover_bullish = ema_f > ema_s

    # Compute ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_len, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    in_position = False
    highest_close = 0.0

    for i in range(len(df)):
        c = close.iloc[i]
        a = atr.iloc[i]

        if not in_position:
            if crossover_bullish.iloc[i]:
                in_position = True
                highest_close = c
                signal.iloc[i] = 1
        else:
            highest_close = max(highest_close, c)
            stop_level = highest_close - atr_mult * a
            if c < stop_level or not crossover_bullish.iloc[i]:
                in_position = False
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal


def ema_atr_stop_grid() -> list[dict]:
    """Parameter grid for Strategy D."""
    grid = []
    for fast in [10, 20, 50]:
        for slow in [100, 150, 200]:
            if fast >= slow:
                continue
            for atr_len in [14, 20]:
                for atr_mult in [2.0, 3.0, 4.0]:
                    grid.append({
                        "fast": fast,
                        "slow": slow,
                        "atr_len": atr_len,
                        "atr_mult": atr_mult,
                    })
    return grid


# ─────────────────────────────────────────────────────────────────────
# Strategy E: Composite – Regime + dip entry + ATR stop
# ─────────────────────────────────────────────────────────────────────
def composite(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Combines regime filter, pullback entry, and ATR trailing stop.

    Regime: Close > EMA(regime_len) AND EMA slope > 0 over slope_window days.
    Entry: In regime AND (Close < EMA(entry_ema) * (1 + entry_band_pct/100)).
    Exit: ATR trailing stop (highest_close - atr_mult * ATR) OR regime break.

    Params:
      regime_len: int
      slope_window: int
      entry_ema: int
      entry_band_pct: float
      atr_len: int
      atr_mult: float
    """
    regime_len = params["regime_len"]
    slope_window = params["slope_window"]
    entry_ema = params["entry_ema"]
    entry_band_pct = params["entry_band_pct"]
    atr_len = params["atr_len"]
    atr_mult = params["atr_mult"]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema_regime = close.ewm(span=regime_len, adjust=False).mean()
    ema_entry = close.ewm(span=entry_ema, adjust=False).mean()

    in_regime = close > ema_regime
    if slope_window > 0:
        slope_pos = ema_regime.diff(slope_window) > 0
        in_regime = in_regime & slope_pos

    entry_trigger = in_regime & (close <= ema_entry * (1 + entry_band_pct / 100))

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_len, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    in_position = False
    highest_close = 0.0

    for i in range(len(df)):
        c = close.iloc[i]
        a = atr.iloc[i]

        if not in_position:
            if entry_trigger.iloc[i]:
                in_position = True
                highest_close = c
                signal.iloc[i] = 1
        else:
            highest_close = max(highest_close, c)
            stop_level = highest_close - atr_mult * a
            if c < stop_level or not in_regime.iloc[i]:
                in_position = False
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal


def composite_grid() -> list[dict]:
    """Parameter grid for Strategy E."""
    grid = []
    for regime_len in [150, 200]:
        for slope_window in [0, 20]:
            for entry_ema in [20, 50]:
                for entry_band_pct in [1.0, 3.0, 5.0]:
                    for atr_len in [14, 20]:
                        for atr_mult in [2.5, 3.5, 5.0]:
                            grid.append({
                                "regime_len": regime_len,
                                "slope_window": slope_window,
                                "entry_ema": entry_ema,
                                "entry_band_pct": entry_band_pct,
                                "atr_len": atr_len,
                                "atr_mult": atr_mult,
                            })
    return grid


# ─────────────────────────────────────────────────────────────────────
# Strategy F: Hysteresis Regime Filter
# ─────────────────────────────────────────────────────────────────────
def F_hysteresis_regime(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Regime filter with hysteresis bands to reduce whipsaw trades.

    Entry: Close crosses ABOVE EMA(regime_len) * (1 + upper_pct/100).
    Exit:  Close crosses BELOW EMA(regime_len) * (1 - lower_pct/100).
    Between the bands, the previous state persists (hysteresis).

    Optional slope filter: EMA slope over slope_window must be positive
    for entry (slope_window=0 disables).

    Returns binary signal (0 or 1).

    Params:
      regime_len:   int   (EMA period, e.g., 200)
      upper_pct:    float (entry band above EMA, e.g., 1.0 means +1%)
      lower_pct:    float (exit band below EMA, e.g., 2.0 means -2%)
      slope_window: int   (slope lookback; 0 = disabled)
    """
    regime_len = params["regime_len"]
    upper_pct = params["upper_pct"]
    lower_pct = params["lower_pct"]
    slope_window = params["slope_window"]

    close = df["Close"]
    ema = close.ewm(span=regime_len, adjust=False).mean()

    upper_band = ema * (1 + upper_pct / 100)
    lower_band = ema * (1 - lower_pct / 100)

    # Optional slope filter
    if slope_window > 0:
        slope_ok = ema.diff(slope_window) > 0
    else:
        slope_ok = pd.Series(True, index=df.index)

    signal = pd.Series(0, index=df.index)
    in_position = False

    for i in range(len(df)):
        c = close.iloc[i]
        if not in_position:
            if c > upper_band.iloc[i] and slope_ok.iloc[i]:
                in_position = True
                signal.iloc[i] = 1
            else:
                signal.iloc[i] = 0
        else:
            if c < lower_band.iloc[i]:
                in_position = False
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal


F_hysteresis_regime_grid = [
    {"regime_len": rl, "upper_pct": up, "lower_pct": lp, "slope_window": sw}
    for rl in [100, 150, 200]
    for up in [0.0, 1.0, 2.0]
    for lp in [1.0, 2.0, 3.0]
    for sw in [0, 20]
]  # 3 * 3 * 3 * 2 = 54 combos


# ─────────────────────────────────────────────────────────────────────
# Strategy G: Volatility-Scaled Regime Sizing
# ─────────────────────────────────────────────────────────────────────
def G_sizing_regime(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Regime filter with fractional position sizing based on inverse
    realized volatility (risk-parity-style within-strategy sizing).

    Regime: Close > EMA(regime_len) (and optional slope).
    When in regime, weight = clamp(target_vol / realized_vol, 0, 1).
    When out of regime, weight = 0.

    This allocates MORE when volatility is low (calm uptrend) and LESS
    when volatility is high (choppy uptrend), capping at 100%.

    Returns fractional weights in [0, 1].

    Params:
      regime_len:   int   (EMA period)
      slope_window: int   (0 = disabled)
      vol_window:   int   (realized vol lookback, e.g., 20)
      target_vol:   float (annualized target, e.g., 0.12 = 12%)
    """
    regime_len = params["regime_len"]
    slope_window = params["slope_window"]
    vol_window = params["vol_window"]
    target_vol = params["target_vol"]

    close = df["Close"]
    ema = close.ewm(span=regime_len, adjust=False).mean()

    in_regime = close > ema
    if slope_window > 0:
        slope_pos = ema.diff(slope_window) > 0
        in_regime = in_regime & slope_pos

    # Realized vol (annualized)
    real_vol = close.pct_change().rolling(vol_window).std() * np.sqrt(252)
    real_vol = real_vol.replace(0, np.nan).ffill().fillna(target_vol)

    raw_weight = target_vol / real_vol
    weight = raw_weight.clip(0.0, 1.0)

    signal = pd.Series(0.0, index=df.index)
    signal[in_regime] = weight[in_regime]

    return signal


G_sizing_regime_grid = [
    {"regime_len": rl, "slope_window": sw, "vol_window": vw, "target_vol": tv}
    for rl in [100, 150, 200]
    for sw in [0, 20]
    for vw in [20, 40, 60]
    for tv in [0.10, 0.15, 0.20]
]  # 3 * 2 * 3 * 3 = 54 combos


# ─────────────────────────────────────────────────────────────────────
# Strategy H: ATR Dip Add-On (Fractional)
# ─────────────────────────────────────────────────────────────────────
def H_atr_dip_addon(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Base regime position + ATR-scaled dip add-on for fractional sizing.

    Base: When Close > EMA(regime_len), hold base_weight (e.g., 0.5).
    Add-on: When Close dips below EMA(dip_ema) by more than
            dip_atr_mult * ATR(atr_len), add addon_weight on top.
    Total weight = min(1.0, base + addon).  Exit all when regime breaks.

    Returns fractional weights in [0, 1].

    Params:
      regime_len:   int   (long EMA for regime)
      dip_ema:      int   (short EMA to measure dips from)
      atr_len:      int   (ATR period)
      dip_atr_mult: float (how many ATRs below dip_ema triggers add-on)
      base_weight:  float (base allocation in regime, e.g., 0.5)
      addon_weight: float (extra weight on dip, e.g., 0.5)
    """
    regime_len = params["regime_len"]
    dip_ema = params["dip_ema"]
    atr_len = params["atr_len"]
    dip_atr_mult = params["dip_atr_mult"]
    base_weight = params["base_weight"]
    addon_weight = params["addon_weight"]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema_regime = close.ewm(span=regime_len, adjust=False).mean()
    ema_dip = close.ewm(span=dip_ema, adjust=False).mean()

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_len, adjust=False).mean()

    in_regime = close > ema_regime
    dip_threshold = ema_dip - dip_atr_mult * atr
    in_dip = close <= dip_threshold

    # State machine: enter on regime, add on dip, hold addon until regime
    # breaks or price recovers above dip_ema
    signal = pd.Series(0.0, index=df.index)
    holding_addon = False

    for i in range(len(df)):
        if not in_regime.iloc[i]:
            signal.iloc[i] = 0.0
            holding_addon = False
        else:
            w = base_weight
            if in_dip.iloc[i]:
                holding_addon = True
            if holding_addon:
                if close.iloc[i] > ema_dip.iloc[i]:
                    holding_addon = False  # dip recovery, drop addon
                else:
                    w = min(1.0, base_weight + addon_weight)
            signal.iloc[i] = w

    return signal


H_atr_dip_addon_grid = [
    {"regime_len": rl, "dip_ema": de, "atr_len": al,
     "dip_atr_mult": dm, "base_weight": bw, "addon_weight": aw}
    for rl in [150, 200]
    for de in [20, 50]
    for al in [14, 20]
    for dm in [1.0, 1.5, 2.0]
    for bw in [0.5, 0.7]
    for aw in [0.3, 0.5]
]  # 2 * 2 * 2 * 3 * 2 * 2 = 96 combos


# ─────────────────────────────────────────────────────────────────────
# Strategy I: Breakout OR Dip (Dual-Mode Entry)
# ─────────────────────────────────────────────────────────────────────
def I_breakout_or_dip(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Dual-mode entry inside a regime:
      Mode 1 (Breakout): Close makes a new N-day high -> enter long.
      Mode 2 (Dip):      Close pulls back within dip_pct% of EMA(dip_ema) -> enter long.
    Either mode triggers entry.

    Exit: ATR trailing stop OR regime break (Close < EMA(regime_len)).

    Returns binary signal (0 or 1).

    Params:
      regime_len:     int   (long EMA for regime)
      breakout_len:   int   (lookback for highest high)
      dip_ema:        int   (short EMA for dip reference)
      dip_pct:        float (max % above dip EMA for dip entry)
      atr_len:        int   (ATR period for trailing stop)
      atr_mult:       float (ATR multiplier for trailing stop)
    """
    regime_len = params["regime_len"]
    breakout_len = params["breakout_len"]
    dip_ema_len = params["dip_ema"]
    dip_pct = params["dip_pct"]
    atr_len = params["atr_len"]
    atr_mult = params["atr_mult"]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema_regime = close.ewm(span=regime_len, adjust=False).mean()
    ema_dip = close.ewm(span=dip_ema_len, adjust=False).mean()
    highest_n = high.rolling(breakout_len).max()

    in_regime = close > ema_regime

    # Breakout trigger: close >= highest high of last N bars
    breakout_trigger = close >= highest_n
    # Dip trigger: in regime and close near dip EMA
    dip_trigger = close <= ema_dip * (1 + dip_pct / 100)
    entry_trigger = in_regime & (breakout_trigger | dip_trigger)

    # ATR for trailing stop
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_len, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    in_position = False
    highest_close = 0.0

    for i in range(len(df)):
        c = close.iloc[i]
        a = atr.iloc[i]

        if not in_position:
            if entry_trigger.iloc[i]:
                in_position = True
                highest_close = c
                signal.iloc[i] = 1
        else:
            highest_close = max(highest_close, c)
            stop_level = highest_close - atr_mult * a
            if c < stop_level or not in_regime.iloc[i]:
                in_position = False
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal


I_breakout_or_dip_grid = [
    {"regime_len": rl, "breakout_len": bl, "dip_ema": de,
     "dip_pct": dp, "atr_len": al, "atr_mult": am}
    for rl in [150, 200]
    for bl in [20, 50]
    for de in [20, 50]
    for dp in [1.0, 3.0]
    for al in [14, 20]
    for am in [3.0, 4.0, 5.0]
]  # 2 * 2 * 2 * 2 * 2 * 3 = 96 combos


# ─────────────────────────────────────────────────────────────────────
# Registry: all strategies in one place
# ─────────────────────────────────────────────────────────────────────
STRATEGIES = {
    "A_ema_crossover": {
        "func": ema_crossover,
        "grid": ema_crossover_grid,
        "description": "EMA fast/slow crossover",
    },
    "B_regime_filter": {
        "func": regime_filter,
        "grid": regime_filter_grid,
        "description": "Regime filter (price > EMA + slope)",
    },
    "C_buy_dip_uptrend": {
        "func": buy_dip_in_uptrend,
        "grid": buy_dip_in_uptrend_grid,
        "description": "Buy-the-dip inside bullish regime",
    },
    "D_ema_atr_stop": {
        "func": ema_atr_stop,
        "grid": ema_atr_stop_grid,
        "description": "EMA crossover + ATR trailing stop",
    },
    "E_composite": {
        "func": composite,
        "grid": composite_grid,
        "description": "Composite: regime + dip entry + ATR stop",
    },
    "F_hysteresis_regime": {
        "func": F_hysteresis_regime,
        "grid": lambda: F_hysteresis_regime_grid,
        "description": "Regime filter with hysteresis bands (anti-whipsaw)",
    },
    "G_sizing_regime": {
        "func": G_sizing_regime,
        "grid": lambda: G_sizing_regime_grid,
        "description": "Vol-scaled regime sizing (fractional 0..1)",
    },
    "H_atr_dip_addon": {
        "func": H_atr_dip_addon,
        "grid": lambda: H_atr_dip_addon_grid,
        "description": "Regime + ATR dip add-on (fractional 0..1)",
    },
    "I_breakout_or_dip": {
        "func": I_breakout_or_dip,
        "grid": lambda: I_breakout_or_dip_grid,
        "description": "Dual-mode: breakout OR dip entry + ATR stop",
    },
}

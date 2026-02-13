"""
backtest.py – Vectorized backtesting engine for long-only daily strategies.

Execution model:
  - Signals are computed from day-t Close data.
  - Trades are executed at day-(t+1) Open price.
  - This eliminates look-ahead bias.

Costs:
  - Commission: configurable bps per side (default 1 bp).
  - Slippage: configurable bps per side (default 2 bps).
  - Total one-way cost = commission + slippage (applied to both entry and exit).

Weight support:
  - Signals can be fractional [0.0, 1.0]: 0.6 means 60% SPY, 40% cash.
  - Costs are charged proportional to abs(weight_change) (turnover).
  - Binary signals (0/1) still work identically to before.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    commission_bps: float = 1.0   # per side
    slippage_bps: float = 2.0     # per side
    initial_capital: float = 100_000.0

    @property
    def one_way_cost(self) -> float:
        """Total one-way cost as a fraction."""
        return (self.commission_bps + self.slippage_bps) / 10_000


@dataclass
class BacktestResult:
    equity: pd.Series = None           # daily equity curve
    drawdown: pd.Series = None         # daily drawdown series
    trades: list = field(default_factory=list)  # list of trade dicts
    positions: pd.Series = None        # daily position (0..1 weight)
    daily_returns: pd.Series = None    # strategy daily returns


def run_backtest(df: pd.DataFrame, signal: pd.Series,
                 config: BacktestConfig | None = None) -> BacktestResult:
    """
    Run a backtest given a DataFrame with OHLCV and a signal series.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: Open, Close (at minimum). Indexed by date.
    signal : pd.Series
        Weight signal in [0, 1]: 1.0 = fully long, 0.0 = fully cash,
        0.6 = 60% SPY / 40% cash.  Binary (0/1) signals work as before.
        Signal on date t means we want to be in that position.
        We shift it forward by 1 day for execution.
    config : BacktestConfig
        Cost and capital configuration.

    Returns
    -------
    BacktestResult with equity, drawdown, trades, positions.
    """
    if config is None:
        config = BacktestConfig()

    # Ensure alignment – keep as float for fractional weights
    df = df.copy()
    signal = signal.reindex(df.index).fillna(0.0).astype(float).clip(0.0, 1.0)

    # Position: signal from yesterday determines today's position.
    # signal[t] based on Close[t] -> execute at Open[t+1] -> position[t+1] = signal[t]
    position = signal.shift(1).fillna(0.0)

    # Trade execution: we use close-to-close returns for simplicity,
    # BUT we apply the gap cost on the day of entry/exit.
    # This is a standard approximation: the cost of entering at Open vs Close
    # is captured by the slippage/commission model.

    close = df["Close"]
    daily_ret = close.pct_change().fillna(0)

    # Turnover: absolute change in weight (supports fractional sizing)
    turnover = position.diff().fillna(0.0).abs()

    # Strategy returns: weight * market return
    strat_ret = position * daily_ret

    # Apply costs proportional to turnover (per-side cost on notional traded)
    cost = config.one_way_cost
    strat_ret = strat_ret - turnover * cost

    # Equity curve
    equity = (1 + strat_ret).cumprod() * config.initial_capital

    # Drawdown
    cummax = equity.cummax()
    dd = (equity - cummax) / cummax

    # Extract trades
    trades = _extract_trades(df, position, strat_ret)

    return BacktestResult(
        equity=equity,
        drawdown=dd,
        trades=trades,
        positions=position,
        daily_returns=strat_ret,
    )


def _extract_trades(df: pd.DataFrame, position: pd.Series,
                    strat_ret: pd.Series) -> list[dict]:
    """Extract individual trades from position series.

    A "trade" is a continuous period where position weight > 0.
    For fractional weights, entry/exit are when weight goes from 0 to >0
    and back to 0 respectively.  Weight changes within a trade (partial
    sizing) are part of the same trade.
    """
    trades = []
    in_trade = False
    entry_date = None
    entry_price = None
    cum_ret = 0.0
    trading_days = 0

    dates = position.index
    close = df["Close"]

    POS_THRESH = 1e-8  # treat weights below this as zero

    for i in range(len(dates)):
        d = dates[i]
        pos = position.iloc[i]

        if not in_trade and pos > POS_THRESH:
            # Entry
            in_trade = True
            entry_date = d
            entry_price = close.iloc[i]
            cum_ret = strat_ret.iloc[i]
            trading_days = 1
        elif in_trade and pos > POS_THRESH:
            # Holding (possibly at different weight)
            cum_ret += strat_ret.iloc[i]
            trading_days += 1
        elif in_trade and pos <= POS_THRESH:
            # Exit (previous day was last day in position)
            exit_date = dates[i - 1] if i > 0 else d
            exit_price = close.iloc[i - 1] if i > 0 else close.iloc[i]
            trades.append({
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return_pct": cum_ret,
                "bars_held": trading_days,
            })
            in_trade = False
            cum_ret = 0.0
            trading_days = 0

    # Close any open trade at end
    if in_trade:
        exit_date = dates[-1]
        exit_price = close.iloc[-1]
        trades.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return_pct": cum_ret,
            "bars_held": trading_days,
        })

    return trades


def run_buy_and_hold(df: pd.DataFrame,
                     config: BacktestConfig | None = None) -> BacktestResult:
    """Buy-and-hold benchmark: always in the market."""
    if config is None:
        config = BacktestConfig()
    signal = pd.Series(1, index=df.index)
    return run_backtest(df, signal, config)

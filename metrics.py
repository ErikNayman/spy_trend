"""
metrics.py – Performance metrics for strategy evaluation.
"""
import numpy as np
import pandas as pd
from typing import Any


def compute_metrics(equity: pd.Series, trades: list[dict],
                    risk_free: float = 0.0) -> dict[str, Any]:
    """
    Compute full performance metrics from an equity curve and trades list.

    Parameters
    ----------
    equity : pd.Series
        Daily equity curve (indexed by date).
    trades : list[dict]
        Each dict has: entry_date, exit_date, entry_price, exit_price, return_pct, bars_held.
    risk_free : float
        Annual risk-free rate (default 0).

    Returns
    -------
    dict with all metrics.
    """
    returns = equity.pct_change().dropna()
    n_days = len(returns)
    n_years = n_days / 252.0

    # CAGR
    total_return = equity.iloc[-1] / equity.iloc[0]
    cagr = total_return ** (1 / n_years) - 1 if n_years > 0 else 0.0

    # Annualized volatility
    vol = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0

    # Sharpe ratio
    excess = returns - risk_free / 252
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

    # Sortino ratio
    downside = returns[returns < 0]
    downside_std = downside.std() * np.sqrt(252) if len(downside) > 1 else 0.0
    sortino = ((returns.mean() - risk_free / 252) / (downside_std / np.sqrt(252))
               if downside_std > 0 else 0.0)
    # Fix: proper annualized sortino
    sortino = (returns.mean() * 252 - risk_free) / downside_std if downside_std > 0 else 0.0

    # Drawdown series
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_dd = drawdown.min()  # most negative

    # Calmar ratio
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0

    # Trade statistics
    n_trades = len(trades)
    trades_per_year = n_trades / n_years if n_years > 0 else 0

    if n_trades > 0:
        trade_returns = [t["return_pct"] for t in trades]
        winners = [r for r in trade_returns if r > 0]
        losers = [r for r in trade_returns if r <= 0]
        win_rate = len(winners) / n_trades

        gross_profit = sum(winners) if winners else 0.0
        gross_loss = abs(sum(losers)) if losers else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        avg_duration = np.mean([t["bars_held"] for t in trades])
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_duration = 0.0

    # Exposure: fraction of days in the market
    # We infer from trades
    days_in_market = 0
    for t in trades:
        days_in_market += t["bars_held"]
    exposure_pct = days_in_market / n_days * 100 if n_days > 0 else 0.0

    return {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDrawdown": max_dd,
        "Calmar": calmar,
        "WinRate": win_rate,
        "ProfitFactor": profit_factor,
        "ExposurePct": exposure_pct,
        "AvgTradeDuration": avg_duration,
        "TradesPerYear": trades_per_year,
        "TotalTrades": n_trades,
        "TotalReturn": total_return - 1,
        "NumYears": n_years,
    }


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Compute drawdown series from equity curve."""
    cummax = equity.cummax()
    return (equity - cummax) / cummax


def monthly_returns_table(equity: pd.Series) -> pd.DataFrame:
    """
    Create a monthly returns table (rows=years, columns=months).
    """
    monthly = equity.resample("ME").last().pct_change().dropna()
    table = pd.DataFrame({
        "Year": monthly.index.year,
        "Month": monthly.index.month,
        "Return": monthly.values
    })
    pivot = table.pivot_table(values="Return", index="Year", columns="Month",
                              aggfunc="sum")
    pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]
    # Annual column
    annual = equity.resample("YE").last().pct_change().dropna()
    annual_dict = {d.year: v for d, v in zip(annual.index, annual.values)}
    pivot["Annual"] = pivot.index.map(lambda y: annual_dict.get(y, np.nan))
    return pivot


def format_metrics(m: dict) -> str:
    """Format metrics dict as a readable string."""
    lines = [
        f"  CAGR:             {m['CAGR']:.2%}",
        f"  Volatility:       {m['Volatility']:.2%}",
        f"  Sharpe:           {m['Sharpe']:.2f}",
        f"  Sortino:          {m['Sortino']:.2f}",
        f"  Max Drawdown:     {m['MaxDrawdown']:.2%}",
        f"  Calmar:           {m['Calmar']:.2f}",
        f"  Win Rate:         {m['WinRate']:.1%}",
        f"  Profit Factor:    {m['ProfitFactor']:.2f}",
        f"  Exposure:         {m['ExposurePct']:.1f}%",
        f"  Avg Trade Days:   {m['AvgTradeDuration']:.1f}",
        f"  Trades/Year:      {m['TradesPerYear']:.1f}",
        f"  Total Return:     {m['TotalReturn']:.2%}",
    ]
    return "\n".join(lines)

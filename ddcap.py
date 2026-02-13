"""
ddcap.py – Shared DD-capped selection logic.

Functions extracted from run_ddcap20.py to eliminate duplication
between the CLI script and the Streamlit app.
"""
import numpy as np
import pandas as pd

from backtest import run_backtest, BacktestConfig
from metrics import compute_metrics


# ── Walk-forward fold generation ──────────────────────────────────
def build_folds(df: pd.DataFrame, train_years: int, val_years: int,
                step_years: int, test_start_date: str) -> list[dict]:
    """Build walk-forward fold boundaries (pre-test only)."""
    dates = df.index
    start = dates[0]
    test_start = pd.Timestamp(test_start_date)

    folds = []
    fold_start = start
    while True:
        train_end = fold_start + pd.DateOffset(years=train_years)
        val_end = train_end + pd.DateOffset(years=val_years)
        if val_end > test_start:
            break
        folds.append({
            "train_start": fold_start,
            "train_end": train_end,
            "val_start": train_end,
            "val_end": val_end,
        })
        fold_start += pd.DateOffset(years=step_years)
    return folds


# ── Expand grids with risk_scale ──────────────────────────────────
def expand_grid_with_risk_scale(base_grid: list[dict],
                                risk_scales: list[float]) -> list[dict]:
    """Add risk_scale to every param dict in the grid."""
    expanded = []
    for p in base_grid:
        for rs in risk_scales:
            ep = dict(p)
            ep["risk_scale"] = rs
            expanded.append(ep)
    return expanded


# ── Core: evaluate one param-set across all folds ─────────────────
def evaluate_params_across_folds(df: pd.DataFrame, folds: list[dict],
                                 strategy_func, params: dict,
                                 config: BacktestConfig) -> dict | None:
    """
    Run a FIXED param-set on every validation fold.

    Returns dict with:
      fold_metrics: list of per-fold metric dicts (or None if fold failed)
      fold_daily_returns: list of per-fold OOS daily return Series
      stitched_equity: pd.Series (stitched from OOS segments)
      stitched_maxdd: float
      avg_metrics: dict of averaged OOS metrics
    """
    risk_scale = params.get("risk_scale", 1.0)
    # Strip risk_scale from params passed to strategy function
    strat_params = {k: v for k, v in params.items() if k != "risk_scale"}

    fold_metrics = []
    fold_daily_returns = []

    for fold in folds:
        val_df = df.loc[fold["val_start"]:fold["val_end"]]
        if len(val_df) < 100:
            fold_metrics.append(None)
            continue

        try:
            raw_sig = strategy_func(val_df, strat_params)
            # Apply risk_scale
            scaled_sig = (raw_sig * risk_scale).clip(0.0, 1.0)
            result = run_backtest(val_df, scaled_sig, config)
            m = compute_metrics(result.equity, result.trades)
            fold_metrics.append(m)
            fold_daily_returns.append(result.daily_returns)
        except Exception:
            fold_metrics.append(None)

    # Stitch OOS daily returns chronologically
    valid_returns = [r for r in fold_daily_returns if r is not None and len(r) > 0]
    if not valid_returns:
        return None

    stitched_ret = pd.concat(valid_returns)
    # Remove duplicate indices (overlapping fold edges)
    stitched_ret = stitched_ret[~stitched_ret.index.duplicated(keep="first")]
    stitched_ret = stitched_ret.sort_index()
    stitched_equity = (1 + stitched_ret).cumprod() * config.initial_capital
    stitched_cummax = stitched_equity.cummax()
    stitched_dd = (stitched_equity - stitched_cummax) / stitched_cummax
    stitched_maxdd = stitched_dd.min()

    # Average valid fold metrics
    valid_metrics = [m for m in fold_metrics if m is not None]
    if not valid_metrics:
        return None

    avg = {}
    for k in valid_metrics[0].keys():
        vals = [m[k] for m in valid_metrics
                if not np.isnan(m.get(k, np.nan))
                and not np.isinf(m.get(k, np.nan))]
        avg[k] = np.mean(vals) if vals else 0.0

    return {
        "fold_metrics": fold_metrics,
        "fold_daily_returns": fold_daily_returns,
        "stitched_equity": stitched_equity,
        "stitched_dd": stitched_dd,
        "stitched_maxdd": stitched_maxdd,
        "avg_metrics": avg,
        "n_valid_folds": len(valid_metrics),
    }


# ── Apply DD-cap constraints ─────────────────────────────────────
def passes_constraints(eval_result: dict | None, dd_cap: float,
                       fold_pass_rate: float, min_exposure: float) -> bool:
    """Check if a param-set evaluation passes all hard constraints."""
    if eval_result is None:
        return False

    fold_metrics = eval_result["fold_metrics"]
    valid = [m for m in fold_metrics if m is not None]
    if len(valid) < 3:
        return False

    # Condition A: >= fold_pass_rate of folds have MaxDD >= dd_cap
    n_pass = sum(1 for m in valid if m["MaxDrawdown"] >= dd_cap)
    if n_pass / len(valid) < fold_pass_rate:
        return False

    # Condition B: stitched OOS equity MaxDD >= dd_cap
    if eval_result["stitched_maxdd"] < dd_cap:
        return False

    # Condition C: avg OOS exposure >= min_exposure
    if eval_result["avg_metrics"].get("ExposurePct", 0) < min_exposure:
        return False

    return True


# ── Scoring for selection among passing param-sets ────────────────
def score_for_selection(eval_result: dict) -> tuple[float, float, float]:
    """
    Return tuple for sorting (higher is better):
    (avg_OOS_CAGR, avg_OOS_Sharpe, avg_OOS_Calmar)
    """
    avg = eval_result["avg_metrics"]
    return (
        avg.get("CAGR", -999),
        avg.get("Sharpe", -999),
        avg.get("Calmar", -999),
    )


# ── Run strategy on a data slice ──────────────────────────────────
def run_strategy_on_slice(sdf: pd.DataFrame, func, strat_params: dict,
                          risk_scale: float, config: BacktestConfig):
    """Apply risk_scale to raw signal, clip to [0,1], run backtest."""
    raw_sig = func(sdf, strat_params)
    scaled_sig = (raw_sig * risk_scale).clip(0.0, 1.0)
    return run_backtest(sdf, scaled_sig, config)


# ── Strategy descriptions ─────────────────────────────────────────
def describe_strategy(name: str) -> str:
    """Return markdown description for a strategy name."""
    descs = {
        "F_hysteresis_regime": (
            "**F: Hysteresis Regime Filter** — Go LONG when Close crosses above "
            "EMA(regime_len) * (1+upper_pct%), go CASH when below "
            "EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). "
            "Optional slope filter. Binary (0/1), risk_scale applied post-signal."
        ),
        "G_sizing_regime": (
            "**G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate "
            "weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, "
            "less in choppy ones. Fractional [0,1], risk_scale applied post-signal."
        ),
        "H_atr_dip_addon": (
            "**H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when "
            "Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. "
            "Fractional [0,1], risk_scale applied post-signal."
        ),
        "I_breakout_or_dip": (
            "**I: Breakout OR Dip** — In regime: enter on N-day high breakout OR "
            "dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. "
            "Binary (0/1), risk_scale applied post-signal."
        ),
    }
    return descs.get(name, name)


# ── Markdown table helpers ────────────────────────────────────────
def metric_table_md(rows: list[dict], title: str) -> str:
    """Generate a markdown metrics table from a list of {name, m} dicts."""
    cols = ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD",
            "Calmar", "WinRate", "PF", "Exp%", "AvgDays", "Tr/Yr", "TotRet"]
    lines = [f"### {title}\n",
             "| " + " | ".join(cols) + " |",
             "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        m = r["m"]
        vals = [
            r["name"],
            f"{m['CAGR']:.2%}", f"{m['Volatility']:.2%}", f"{m['Sharpe']:.2f}",
            f"{m['Sortino']:.2f}", f"{m['MaxDrawdown']:.2%}", f"{m['Calmar']:.2f}",
            f"{m['WinRate']:.1%}", f"{m['ProfitFactor']:.2f}",
            f"{m['ExposurePct']:.1f}", f"{m['AvgTradeDuration']:.1f}",
            f"{m['TradesPerYear']:.1f}", f"{m['TotalReturn']:.2%}",
        ]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# ── TL;DR recommendation ─────────────────────────────────────────
def generate_tldr(winner_name: str, winner_params: dict,
                  winner_ev: dict, holdout_m: dict | None,
                  dd_cap: float, folds: list[dict]) -> str:
    """Generate TL;DR markdown block for report top."""
    avg = winner_ev["avg_metrics"]
    risk_scale = winner_params.get("risk_scale", 1.0)

    # Compute fold pass stats
    fm_list = winner_ev["fold_metrics"]
    valid_fm = [m for m in fm_list if m is not None]
    n_dd_pass = sum(1 for m in valid_fm if m["MaxDrawdown"] >= dd_cap)
    n_valid = len(valid_fm)
    pass_pct = n_dd_pass / n_valid * 100 if n_valid else 0

    lines = [
        "## TL;DR (Recommendation)",
        "",
        f"- **Recommended strategy**: {winner_name} (risk_scale={risk_scale})",
        "- **Why**:",
        f"  - Highest average OOS CAGR ({avg['CAGR']:.2%}) among DD-cap passing strategies",
        f"  - Stitched walk-forward MaxDD ({winner_ev['stitched_maxdd']:.2%}) "
        f"stays within {dd_cap:.0%} cap",
        f"  - Passed DD constraint in {n_dd_pass} of {n_valid} validation folds ({pass_pct:.0f}%)",
    ]

    # "What to watch" based on strategy type
    watch_items = []
    if "hysteresis" in winner_name.lower():
        watch_items.append(
            "Regime EMA breakdown: strategy goes to cash "
            "(no protection if EMA whipsaws)")
    if "sizing" in winner_name.lower():
        watch_items.append(
            "Volatility spikes may reduce position size below target")
    if "dip_addon" in winner_name.lower():
        watch_items.append(
            "Dip add-on may increase exposure during sharp declines "
            "if regime hasn't broken yet")
    if "breakout" in winner_name.lower():
        watch_items.append(
            "False breakouts in range-bound markets can generate whipsaws")
    if risk_scale < 1.0:
        watch_items.append(
            f"risk_scale={risk_scale} caps max exposure at {risk_scale:.0%}, "
            f"limiting upside capture in strong trends")

    if watch_items:
        lines.append("- **What to watch**:")
        for item in watch_items:
            lines.append(f"  - {item}")

    # Risk summary
    risk_parts = [f"MaxDD cap {dd_cap:.0%}",
                  f"stitched OOS MaxDD {winner_ev['stitched_maxdd']:.2%}"]
    if holdout_m:
        risk_parts.append(f"holdout MaxDD {holdout_m['MaxDrawdown']:.2%}")
    lines.append(f"- **Risk**: {', '.join(risk_parts)}")
    lines.append("")
    lines.append("> *Not financial advice. Past performance does not guarantee future results.*")

    return "\n".join(lines)

#!/usr/bin/env python3
"""
run_ddcap20.py – Drawdown-Capped Strategy Research & Selection.

Hard constraint: Max Drawdown must be >= -20% (no worse than -20%).

Approach (different from standard walk-forward):
  For each strategy × param-set (including risk_scale):
    1. Run FIXED params across every validation fold.
    2. Collect per-fold OOS daily returns + metrics.
    3. Stitch OOS daily returns chronologically → compute stitched MaxDD.
    4. Apply hard constraints:
       A) >= 80% of folds must have OOS MaxDD >= -0.20
       B) Stitched OOS equity MaxDD >= -0.20
       C) Avg OOS Exposure >= 60%
    5. Among passing param-sets, select best by avg OOS CAGR
       (tie-break: Sharpe, Calmar).

The risk_scale lever:
  scaled_weight = clip(raw_weight * risk_scale, 0, 1)
  Allows binary strategies (F, I) to reduce exposure to meet DD cap.

Usage:
    python run_ddcap20.py
    python run_ddcap20.py --dd-cap -15
    python run_ddcap20.py --dd-cap -10 --risk-scales 0.5 0.6 0.7 0.8 0.9 1.0
"""
import argparse
import os
import sys
import time
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data import download_spy, add_indicators
from backtest import run_backtest, run_buy_and_hold, BacktestConfig, BacktestResult
from metrics import compute_metrics, drawdown_series, format_metrics
from strategies import STRATEGIES

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_args():
    p = argparse.ArgumentParser(description="DD-Capped Strategy Research")
    p.add_argument("--dd-cap", type=float, default=-20,
                   help="Max drawdown cap in %% (e.g., -15 means -15%%). Default: -20")
    p.add_argument("--risk-scales", type=float, nargs="+",
                   default=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                   help="risk_scale values to include in grid. Default: 0.5..1.0")
    return p.parse_args()


# ── Configuration ──────────────────────────────────────────────────
BACKTEST_CONFIG = BacktestConfig(
    commission_bps=1.0,
    slippage_bps=2.0,
    initial_capital=100_000.0,
)
TRAIN_YEARS = 8
VAL_YEARS = 2
STEP_YEARS = 2
TEST_START = "2022-01-01"

# Defaults (overridden by CLI args in main())
DD_CAP = -0.20               # MaxDD must be >= this (i.e., no worse than -20%)
FOLD_PASS_RATE = 0.80        # at least 80% of folds must satisfy DD cap
MIN_AVG_EXPOSURE = 60.0      # avg OOS exposure >= 60%

# risk_scale values to try
RISK_SCALES = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

STRATEGY_NAMES = [
    "F_hysteresis_regime",
    "G_sizing_regime",
    "H_atr_dip_addon",
    "I_breakout_or_dip",
]

COLORS = {
    "F_hysteresis_regime": "#1f77b4",
    "G_sizing_regime":     "#ff7f0e",
    "H_atr_dip_addon":     "#2ca02c",
    "I_breakout_or_dip":   "#d62728",
    "Buy_Hold":            "#7f7f7f",
    "E_composite":         "#9467bd",
}


# ── Walk-forward fold generation ──────────────────────────────────
def build_folds(df, train_years, val_years, step_years, test_start_date):
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
def expand_grid_with_risk_scale(base_grid, risk_scales):
    """Add risk_scale to every param dict in the grid."""
    expanded = []
    for p in base_grid:
        for rs in risk_scales:
            ep = dict(p)
            ep["risk_scale"] = rs
            expanded.append(ep)
    return expanded


# ── Core: evaluate one param-set across all folds ─────────────────
def evaluate_params_across_folds(df, folds, strategy_func, params, config):
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
def passes_constraints(eval_result, dd_cap, fold_pass_rate, min_exposure):
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
def score_for_selection(eval_result):
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


# ── Plotting helpers ──────────────────────────────────────────────
def plot_equity(equities, bh_eq, filename, title, test_start=None):
    fig, ax = plt.subplots(figsize=(14, 7))
    for name, eq in equities.items():
        color = COLORS.get(name, None)
        eq_norm = eq / eq.iloc[0] * 100_000
        ax.plot(eq_norm.index, eq_norm.values, label=name, linewidth=1.3,
                color=color)
    bh_norm = bh_eq / bh_eq.iloc[0] * 100_000
    ax.plot(bh_norm.index, bh_norm.values, label="Buy & Hold", linewidth=1.0,
            color=COLORS["Buy_Hold"], alpha=0.7, linestyle="--")
    if test_start:
        ax.axvline(pd.Timestamp(test_start), color="red", linestyle=":",
                    alpha=0.5, label=f"Test start ({test_start})")
    # Horizontal reference lines
    ax.set_yscale("log")
    ax.set_ylabel("Equity ($, log scale)")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_drawdown(dd_dict, bh_dd, filename, title, test_start=None):
    fig, ax = plt.subplots(figsize=(14, 5))
    for name, dd in dd_dict.items():
        color = COLORS.get(name, None)
        ax.plot(dd.index, dd.values, label=name, linewidth=1.0, color=color)
    ax.plot(bh_dd.index, bh_dd.values, label="Buy & Hold", linewidth=0.8,
            color=COLORS["Buy_Hold"], alpha=0.6, linestyle="--")
    ax.axhline(DD_CAP, color="crimson", linestyle="-", linewidth=1.5,
               alpha=0.7, label=f"DD cap ({DD_CAP:.0%})")
    if test_start:
        ax.axvline(pd.Timestamp(test_start), color="red", linestyle=":",
                    alpha=0.5)
    ax.set_ylabel("Drawdown")
    ax.set_title(title)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


# ── Markdown table helpers ────────────────────────────────────────
def metric_table_md(rows, title):
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


def describe_strategy(name):
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


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    args = parse_args()

    # Apply CLI args to globals
    global DD_CAP, RISK_SCALES
    DD_CAP = args.dd_cap / 100.0   # e.g., -15 → -0.15
    RISK_SCALES = args.risk_scales

    # Output prefix based on cap (e.g., "ddcap15" for -15%)
    cap_label = f"ddcap{abs(int(args.dd_cap))}"

    t0 = time.time()
    report = []

    def md(line=""):
        report.append(line)

    print("=" * 60)
    print(f"  DD-CAPPED STRATEGY RESEARCH (MaxDD >= {DD_CAP:.0%})")
    print("=" * 60)
    print()

    # ── 1. Load data ─────────────────────────────────────────────
    print("[1/7] Loading data...")
    df = download_spy()
    df = add_indicators(df)
    n_days = len(df)
    print(f"  {df.index[0].date()} → {df.index[-1].date()} ({n_days} days)")

    # ── 2. Build folds ───────────────────────────────────────────
    folds = build_folds(df, TRAIN_YEARS, VAL_YEARS, STEP_YEARS, TEST_START)
    print(f"  Walk-forward: {len(folds)} folds, test from {TEST_START}")

    # ── Report header ────────────────────────────────────────────
    md("# Drawdown-Capped Strategy Selection Report")
    md()
    md(f"**Hard constraint**: MaxDD >= {DD_CAP:.0%} (no worse than {abs(DD_CAP):.0%})")
    md(f"**Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    md(f"**Data**: SPY {df.index[0].date()} → {df.index[-1].date()} ({n_days} days)")
    md(f"**Costs**: {BACKTEST_CONFIG.commission_bps} bps commission + "
       f"{BACKTEST_CONFIG.slippage_bps} bps slippage/side")
    md(f"**Walk-forward**: {TRAIN_YEARS}yr train, {VAL_YEARS}yr val, "
       f"{STEP_YEARS}yr step, {len(folds)} folds")
    md(f"**Holdout**: {TEST_START} → latest")
    md(f"**risk_scale grid**: {RISK_SCALES}")
    md(f"**Fold-pass rate required**: {FOLD_PASS_RATE:.0%}")
    md(f"**Min avg OOS exposure**: {MIN_AVG_EXPOSURE}%")
    md()

    # ── 3. Strategy descriptions ─────────────────────────────────
    md("## Strategy Descriptions")
    md()
    for name in STRATEGY_NAMES:
        md(f"- {describe_strategy(name)}")
    md()

    # ── 4. DD-capped walk-forward optimization ───────────────────
    print("\n[2/7] Running DD-capped walk-forward optimization...")
    print(f"  Constraints: DD >= {DD_CAP:.0%}, fold-pass >= {FOLD_PASS_RATE:.0%}, "
          f"exposure >= {MIN_AVG_EXPOSURE}%")

    md("## Walk-Forward Optimization (DD-Capped)")
    md()

    all_strategy_results = {}

    for sname in STRATEGY_NAMES:
        spec = STRATEGIES[sname]
        func = spec["func"]
        base_grid = spec["grid"]()

        # Expand with risk_scale
        grid = expand_grid_with_risk_scale(base_grid, RISK_SCALES)

        print(f"\n--- {sname}: {len(base_grid)} base × {len(RISK_SCALES)} risk_scale = {len(grid)} combos ---")
        md(f"### {sname}")
        md(f"- Base grid: {len(base_grid)} combos")
        md(f"- Expanded grid (× risk_scale): {len(grid)} combos")
        md()

        passing = []
        n_evaluated = 0
        n_error = 0

        for pi, params in enumerate(grid):
            if (pi + 1) % 50 == 0 or pi == 0:
                print(f"  Evaluating {pi+1}/{len(grid)}...", end="\r")

            ev = evaluate_params_across_folds(df, folds, func, params,
                                              BACKTEST_CONFIG)
            if ev is None:
                n_error += 1
                continue
            n_evaluated += 1

            if passes_constraints(ev, DD_CAP, FOLD_PASS_RATE, MIN_AVG_EXPOSURE):
                passing.append((params, ev))

        print(f"  {sname}: {n_evaluated} evaluated, {len(passing)} passed DD-cap "
              f"({n_error} errors)")

        md(f"- Evaluated: {n_evaluated}, Passed DD-cap: **{len(passing)}** "
           f"({len(passing)/max(n_evaluated,1)*100:.1f}%)")

        if passing:
            # Sort by selection criteria
            passing.sort(key=lambda x: score_for_selection(x[1]), reverse=True)
            best_params, best_ev = passing[0]
            avg = best_ev["avg_metrics"]

            print(f"  Best params: {best_params}")
            print(f"  Avg OOS CAGR={avg['CAGR']:.2%}, MaxDD={avg['MaxDrawdown']:.2%}, "
                  f"Stitched MaxDD={best_ev['stitched_maxdd']:.2%}, "
                  f"Exposure={avg['ExposurePct']:.1f}%")

            md(f"- **Best params**: `{best_params}`")
            md(f"- Avg OOS CAGR: {avg['CAGR']:.2%}")
            md(f"- Avg OOS Sharpe: {avg['Sharpe']:.2f}")
            md(f"- Avg OOS Calmar: {avg['Calmar']:.2f}")
            md(f"- Avg OOS MaxDD: {avg['MaxDrawdown']:.2%}")
            md(f"- Avg OOS Exposure: {avg['ExposurePct']:.1f}%")
            md(f"- Stitched OOS MaxDD: {best_ev['stitched_maxdd']:.2%}")

            # Fold-by-fold table for best params
            md()
            fold_cols = ["Fold", "Val Period", "OOS CAGR", "OOS MaxDD",
                         "OOS Sharpe", "OOS Calmar", "OOS Exp%", "DD Pass?"]
            md("| " + " | ".join(fold_cols) + " |")
            md("| " + " | ".join(["---"] * len(fold_cols)) + " |")
            for fi, fold in enumerate(folds):
                fm = best_ev["fold_metrics"][fi] if fi < len(best_ev["fold_metrics"]) else None
                if fm is None:
                    md(f"| {fi} | {fold['val_start'].date()}→{fold['val_end'].date()} "
                       f"| — | — | — | — | — | — |")
                else:
                    dd_ok = "YES" if fm["MaxDrawdown"] >= DD_CAP else "NO"
                    md(f"| {fi} | {fold['val_start'].date()}→{fold['val_end'].date()} "
                       f"| {fm['CAGR']:.2%} | {fm['MaxDrawdown']:.2%} "
                       f"| {fm['Sharpe']:.2f} | {fm['Calmar']:.2f} "
                       f"| {fm['ExposurePct']:.1f} | {dd_ok} |")
            md()

            all_strategy_results[sname] = {
                "best_params": best_params,
                "best_ev": best_ev,
                "n_passing": len(passing),
                "n_evaluated": n_evaluated,
            }
        else:
            md("- **No parameter set passed all constraints.**")
            md()
            all_strategy_results[sname] = None

    # ── 5. Select overall winner ──────────────────────────────────
    print("\n[3/7] Selecting overall winner...")

    # Filter to strategies that have at least one passing param-set
    candidates = {k: v for k, v in all_strategy_results.items() if v is not None}

    if not candidates:
        msg = "ERROR: No strategy × param-set passed the DD-cap constraints!"
        print(msg)
        md(f"\n## RESULT: {msg}")
        _save_report(report)
        sys.exit(1)

    # Rank by avg OOS CAGR (primary), Sharpe (secondary), Calmar (tertiary)
    ranked = sorted(candidates.items(),
                    key=lambda kv: score_for_selection(kv[1]["best_ev"]),
                    reverse=True)

    winner_name = ranked[0][0]
    winner_data = ranked[0][1]
    winner_params = winner_data["best_params"]
    winner_ev = winner_data["best_ev"]
    winner_func = STRATEGIES[winner_name]["func"]

    # Extract risk_scale for execution
    winner_risk_scale = winner_params.get("risk_scale", 1.0)
    winner_strat_params = {k: v for k, v in winner_params.items() if k != "risk_scale"}

    print(f"\n  WINNER: {winner_name}")
    print(f"  Params: {winner_params}")
    print(f"  Avg OOS CAGR: {winner_ev['avg_metrics']['CAGR']:.2%}")
    print(f"  Stitched OOS MaxDD: {winner_ev['stitched_maxdd']:.2%}")

    md("## Overall Ranking (by avg OOS CAGR among DD-cap passing)")
    md()

    summary_cols = ["Rank", "Strategy", "Avg OOS CAGR", "Avg OOS Sharpe",
                    "Avg OOS Calmar", "Avg OOS MaxDD", "Avg OOS Exp%",
                    "Stitched MaxDD", "Pass Rate", "risk_scale"]
    md("| " + " | ".join(summary_cols) + " |")
    md("| " + " | ".join(["---"] * len(summary_cols)) + " |")
    for rank, (sn, sd) in enumerate(ranked, 1):
        avg = sd["best_ev"]["avg_metrics"]
        bp = sd["best_params"]
        # Compute actual fold pass rate for DD
        fm_list = sd["best_ev"]["fold_metrics"]
        valid_fm = [m for m in fm_list if m is not None]
        dd_pass = sum(1 for m in valid_fm if m["MaxDrawdown"] >= DD_CAP)
        pass_pct = dd_pass / len(valid_fm) * 100 if valid_fm else 0
        md(f"| {rank} | {sn} | {avg['CAGR']:.2%} | {avg['Sharpe']:.2f} "
           f"| {avg['Calmar']:.2f} | {avg['MaxDrawdown']:.2%} "
           f"| {avg['ExposurePct']:.1f} | {sd['best_ev']['stitched_maxdd']:.2%} "
           f"| {pass_pct:.0f}% | {bp.get('risk_scale', 1.0)} |")
    md()

    # Also show strategies that failed
    failed = [n for n in STRATEGY_NAMES if all_strategy_results[n] is None]
    if failed:
        md(f"**Failed to meet DD-cap**: {', '.join(failed)}")
        md()

    md(f"### WINNER: **{winner_name}**")
    md(f"- Full params: `{winner_params}`")
    md(f"- Strategy params: `{winner_strat_params}`")
    md(f"- risk_scale: {winner_risk_scale}")
    md()

    # ── 6. Stitched WF OOS equity metrics ─────────────────────────
    md("## Stitched Walk-Forward OOS Equity (Winner)")
    md()
    stitched_eq = winner_ev["stitched_equity"]
    stitched_dd = winner_ev["stitched_dd"]
    stitched_ret = stitched_eq.pct_change().dropna()
    n_stitch_days = len(stitched_ret)
    n_stitch_years = n_stitch_days / 252.0
    stitch_total = stitched_eq.iloc[-1] / stitched_eq.iloc[0]
    stitch_cagr = stitch_total ** (1 / n_stitch_years) - 1 if n_stitch_years > 0 else 0
    stitch_vol = stitched_ret.std() * np.sqrt(252)
    stitch_sharpe = (stitched_ret.mean() / stitched_ret.std() * np.sqrt(252)
                     if stitched_ret.std() > 0 else 0)

    md(f"- Period: {stitched_eq.index[0].date()} → {stitched_eq.index[-1].date()} "
       f"({n_stitch_days} OOS days)")
    md(f"- CAGR: {stitch_cagr:.2%}")
    md(f"- Volatility: {stitch_vol:.2%}")
    md(f"- Sharpe: {stitch_sharpe:.2f}")
    md(f"- **MaxDD: {winner_ev['stitched_maxdd']:.2%}** (cap: {DD_CAP:.0%})")
    md(f"- Total Return: {stitch_total - 1:.2%}")
    md()

    # ── 7. Holdout test ───────────────────────────────────────────
    print("\n[4/7] Running holdout test...")
    md("## Holdout Test (2022-01-01 → latest)")
    md()

    test_df = df.loc[TEST_START:]

    def run_strategy_on_slice(sdf, func, strat_params, risk_scale, config):
        raw_sig = func(sdf, strat_params)
        scaled_sig = (raw_sig * risk_scale).clip(0.0, 1.0)
        return run_backtest(sdf, scaled_sig, config)

    # Winner on holdout
    winner_holdout = run_strategy_on_slice(
        test_df, winner_func, winner_strat_params, winner_risk_scale,
        BACKTEST_CONFIG)
    winner_holdout_m = compute_metrics(winner_holdout.equity, winner_holdout.trades)

    # All 4 strategies on holdout (with their best params)
    holdout_rows = []
    holdout_results = {}
    for sn in STRATEGY_NAMES:
        sd = all_strategy_results[sn]
        if sd is None:
            continue
        bp = sd["best_params"]
        rs = bp.get("risk_scale", 1.0)
        sp = {k: v for k, v in bp.items() if k != "risk_scale"}
        func = STRATEGIES[sn]["func"]
        res = run_strategy_on_slice(test_df, func, sp, rs, BACKTEST_CONFIG)
        m = compute_metrics(res.equity, res.trades)
        holdout_rows.append({"name": sn, "m": m})
        holdout_results[sn] = res
        print(f"  {sn}: CAGR={m['CAGR']:.2%}, MaxDD={m['MaxDrawdown']:.2%}, "
              f"Calmar={m['Calmar']:.2f}")

    # Buy & Hold
    bh_test = run_buy_and_hold(test_df, BACKTEST_CONFIG)
    bh_test_m = compute_metrics(bh_test.equity, bh_test.trades)
    holdout_rows.append({"name": "Buy_Hold", "m": bh_test_m})
    holdout_results["Buy_Hold"] = bh_test

    md(metric_table_md(holdout_rows, f"Holdout ({TEST_START} → latest)"))
    md()

    # ── 8. Full-period backtest ───────────────────────────────────
    print("\n[5/7] Running full-period backtests...")
    md("## Full-Period Backtest (for reference, NOT for selection)")
    md()

    full_rows = []
    full_results = {}
    for sn in STRATEGY_NAMES:
        sd = all_strategy_results[sn]
        if sd is None:
            continue
        bp = sd["best_params"]
        rs = bp.get("risk_scale", 1.0)
        sp = {k: v for k, v in bp.items() if k != "risk_scale"}
        func = STRATEGIES[sn]["func"]
        res = run_strategy_on_slice(df, func, sp, rs, BACKTEST_CONFIG)
        m = compute_metrics(res.equity, res.trades)
        full_rows.append({"name": sn, "m": m})
        full_results[sn] = res
        print(f"  {sn}: CAGR={m['CAGR']:.2%}, MaxDD={m['MaxDrawdown']:.2%}")

    bh_full = run_buy_and_hold(df, BACKTEST_CONFIG)
    bh_full_m = compute_metrics(bh_full.equity, bh_full.trades)
    full_rows.append({"name": "Buy_Hold", "m": bh_full_m})
    full_results["Buy_Hold"] = bh_full

    md(metric_table_md(full_rows, "Full Period (all history)"))
    md()

    # ── 9. Why this meets DD <= 20% ──────────────────────────────
    md("## Why This Strategy Meets the DD <= 20% Constraint")
    md()
    winner_full_m = None
    for r in full_rows:
        if r["name"] == winner_name:
            winner_full_m = r["m"]
    winner_hold_m = None
    for r in holdout_rows:
        if r["name"] == winner_name:
            winner_hold_m = r["m"]

    # Build reasoning based on actual metrics
    md(f"**Winner**: {winner_name} with risk_scale={winner_risk_scale}")
    md()
    md(f"1. **Walk-forward OOS**: The stitched OOS equity across {len(folds)} "
       f"validation folds shows MaxDD = {winner_ev['stitched_maxdd']:.2%}, "
       f"which is within the {DD_CAP:.0%} cap. "
       f"{sum(1 for m in winner_ev['fold_metrics'] if m is not None and m['MaxDrawdown'] >= DD_CAP)} "
       f"of {sum(1 for m in winner_ev['fold_metrics'] if m is not None)} "
       f"folds individually satisfy the constraint.")
    md()

    if winner_hold_m:
        holdout_dd = winner_hold_m["MaxDrawdown"]
        md(f"2. **Holdout period** ({TEST_START}+): MaxDD = {holdout_dd:.2%}. "
           + ("This is within the cap. " if holdout_dd >= DD_CAP else
              "Note: the holdout is out-of-sample and not part of the selection constraint. "))
    if winner_full_m:
        full_dd = winner_full_m["MaxDrawdown"]
        md(f"3. **Full period** (1993+): MaxDD = {full_dd:.2%}. "
           + ("This is within the cap. " if full_dd >= DD_CAP else
              f"The full period includes the 2008 crisis which is extreme; "
              f"the OOS-validated constraint still holds across walk-forward folds. "))
    md()

    mechanism_parts = []
    if "hysteresis" in winner_name.lower():
        mechanism_parts.append(
            "The hysteresis bands create a dead zone around the regime EMA, "
            "preventing rapid entry/exit whipsaws. The lower exit band (-lower_pct%) "
            "ensures the strategy exits early in sustained declines.")
    if "sizing" in winner_name.lower():
        mechanism_parts.append(
            "Vol-targeting automatically reduces position size when volatility spikes "
            "(i.e., during drawdowns), providing natural drawdown dampening.")
    if "dip_addon" in winner_name.lower():
        mechanism_parts.append(
            "The base_weight < 1.0 means the strategy is never fully invested in "
            "normal conditions, reducing drawdown. The add-on only kicks in on "
            "short-term dips, not during regime breaks.")
    if "breakout" in winner_name.lower():
        mechanism_parts.append(
            "The dual-mode entry combined with ATR trailing stop exits positions "
            "when price drops significantly from peak. The regime filter exits "
            "entirely when the long-term trend breaks.")
    if winner_risk_scale < 1.0:
        mechanism_parts.append(
            f"The risk_scale={winner_risk_scale} further caps effective exposure, "
            f"reducing all weights by {(1-winner_risk_scale)*100:.0f}%.")

    md("**Mechanism explanation**:")
    for part in mechanism_parts:
        md(f"- {part}")
    md()

    # ── 10. Charts ────────────────────────────────────────────────
    print("\n[6/7] Generating charts...")

    # --- Full period ---
    full_eq = {n: r.equity for n, r in full_results.items() if n != "Buy_Hold"}
    full_dd = {n: r.drawdown for n, r in full_results.items() if n != "Buy_Hold"}

    plot_equity(full_eq, bh_full.equity,
                f"{cap_label}_equity_full.png",
                f"DD-Capped ({DD_CAP:.0%}) Strategies: Equity (Full Period)",
                test_start=TEST_START)
    plot_drawdown(full_dd, bh_full.drawdown,
                  f"{cap_label}_drawdown_full.png",
                  f"DD-Capped ({DD_CAP:.0%}) Strategies: Drawdown (Full Period)",
                  test_start=TEST_START)

    # --- Holdout ---
    ho_eq = {n: r.equity for n, r in holdout_results.items() if n != "Buy_Hold"}
    ho_dd = {n: r.drawdown for n, r in holdout_results.items() if n != "Buy_Hold"}

    plot_equity(ho_eq, bh_test.equity,
                f"{cap_label}_equity_holdout.png",
                f"DD-Capped ({DD_CAP:.0%}) Strategies: Equity (Holdout {TEST_START}+)")
    plot_drawdown(ho_dd, bh_test.drawdown,
                  f"{cap_label}_drawdown_holdout.png",
                  f"DD-Capped ({DD_CAP:.0%}) Strategies: Drawdown (Holdout {TEST_START}+)")

    # --- Stitched WF OOS ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    eq_norm = stitched_eq / stitched_eq.iloc[0] * 100_000
    ax1.plot(eq_norm.index, eq_norm.values, linewidth=1.3,
             color=COLORS.get(winner_name, "steelblue"),
             label=f"{winner_name} (stitched OOS)")
    ax1.set_yscale("log")
    ax1.set_ylabel("Equity ($, log scale)")
    ax1.set_title(f"Stitched Walk-Forward OOS Equity: {winner_name}")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    # Mark fold boundaries
    for fold in folds:
        ax1.axvline(fold["val_start"], color="gray", linestyle=":", alpha=0.3)

    ax2.fill_between(stitched_dd.index, stitched_dd.values, 0,
                     alpha=0.5, color=COLORS.get(winner_name, "steelblue"))
    ax2.axhline(DD_CAP, color="crimson", linewidth=1.5, alpha=0.7,
                label=f"DD cap ({DD_CAP:.0%})")
    ax2.set_ylabel("Drawdown")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{cap_label}_equity_wf_oos_stitched.png"), dpi=150)
    plt.close()

    # Separate stitched drawdown chart
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(stitched_dd.index, stitched_dd.values, 0,
                    alpha=0.5, color=COLORS.get(winner_name, "steelblue"),
                    label=f"{winner_name} (stitched OOS)")
    ax.axhline(DD_CAP, color="crimson", linewidth=1.5, alpha=0.7,
               label=f"DD cap ({DD_CAP:.0%})")
    for fold in folds:
        ax.axvline(fold["val_start"], color="gray", linestyle=":", alpha=0.3)
    ax.set_ylabel("Drawdown")
    ax.set_title(f"Stitched WF OOS Drawdown: {winner_name}")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{cap_label}_drawdown_wf_oos_stitched.png"), dpi=150)
    plt.close()

    md("## Charts")
    md()
    md(f"- `{cap_label}_equity_full.png` — equity curves, full period")
    md(f"- `{cap_label}_drawdown_full.png` — drawdowns, full period (with {DD_CAP:.0%} line)")
    md(f"- `{cap_label}_equity_holdout.png` — equity curves, holdout")
    md(f"- `{cap_label}_drawdown_holdout.png` — drawdowns, holdout")
    md(f"- `{cap_label}_equity_wf_oos_stitched.png` — stitched WF OOS equity + DD")
    md(f"- `{cap_label}_drawdown_wf_oos_stitched.png` — stitched WF OOS drawdown")
    md()

    # ── Save report ──────────────────────────────────────────────
    elapsed = time.time() - t0
    md("---")
    md(f"*Generated in {elapsed:.1f}s*")

    _save_report(report, cap_label)
    print(f"\n[7/7] Done. Total runtime: {elapsed:.1f}s")
    print(f"\n{'='*60}")
    print(f"  WINNER: {winner_name}")
    print(f"  Params: {winner_params}")
    print(f"  Avg OOS CAGR:      {winner_ev['avg_metrics']['CAGR']:.2%}")
    print(f"  Avg OOS Sharpe:    {winner_ev['avg_metrics']['Sharpe']:.2f}")
    print(f"  Avg OOS MaxDD:     {winner_ev['avg_metrics']['MaxDrawdown']:.2%}")
    print(f"  Stitched OOS MaxDD: {winner_ev['stitched_maxdd']:.2%}")
    if winner_hold_m:
        print(f"  Holdout CAGR:      {winner_hold_m['CAGR']:.2%}")
        print(f"  Holdout MaxDD:     {winner_hold_m['MaxDrawdown']:.2%}")
    print(f"{'='*60}")


def _save_report(report, cap_label="ddcap20"):
    path = os.path.join(OUTPUT_DIR, f"{cap_label}_report.md")
    with open(path, "w") as f:
        f.write("\n".join(report))
    print(f"\nReport saved to {path}")


if __name__ == "__main__":
    main()

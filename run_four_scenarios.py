#!/usr/bin/env python3
"""
run_four_scenarios.py – Apples-to-apples comparison of four strategy scenarios.

Strategies:
  F) Hysteresis Regime   – Regime filter with hysteresis bands
  G) Sizing Regime       – Vol-scaled fractional sizing inside regime
  H) ATR Dip Add-On     – Base regime + ATR dip add-on (fractional)
  I) Breakout or Dip    – Dual-mode entry: breakout OR dip + ATR stop

Pipeline:
  1. Walk-forward optimization (8yr train, 2yr val, step 2yr)
  2. Consensus params selection
  3. Holdout test (2022-01-01 → latest)
  4. Full-period backtest (for reference)
  5. Report + charts

Usage:
    python run_four_scenarios.py
    python run_four_scenarios.py --strategies F_hysteresis_regime G_sizing_regime
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
from backtest import run_backtest, run_buy_and_hold, BacktestConfig
from metrics import compute_metrics, drawdown_series, format_metrics
from strategies import STRATEGIES
from optimizer import (walk_forward_optimize, final_test,
                       sensitivity_analysis)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

DEFAULT_STRATEGIES = [
    "F_hysteresis_regime",
    "G_sizing_regime",
    "H_atr_dip_addon",
    "I_breakout_or_dip",
]

# Colors for consistent chart styling
COLORS = {
    "F_hysteresis_regime": "#1f77b4",  # blue
    "G_sizing_regime":     "#ff7f0e",  # orange
    "H_atr_dip_addon":     "#2ca02c",  # green
    "I_breakout_or_dip":   "#d62728",  # red
    "Buy_Hold":            "#7f7f7f",  # gray
}


def parse_args():
    parser = argparse.ArgumentParser(description="Four Scenarios Backtest Comparison")
    parser.add_argument("--strategies", nargs="+", default=DEFAULT_STRATEGIES,
                        help="Strategy names to compare")
    return parser.parse_args()


def metric_table_md(rows: list[dict], title: str) -> str:
    """Format a list of metric dicts as a markdown table."""
    if not rows:
        return ""
    cols = ["Strategy", "CAGR", "Volatility", "Sharpe", "Sortino", "MaxDD",
            "Calmar", "WinRate", "ProfitFactor", "Exposure%", "AvgTradeDays",
            "Trades/Yr", "TotalReturn"]
    lines = [f"### {title}\n"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for r in rows:
        vals = [
            r["name"],
            f"{r['m']['CAGR']:.2%}",
            f"{r['m']['Volatility']:.2%}",
            f"{r['m']['Sharpe']:.2f}",
            f"{r['m']['Sortino']:.2f}",
            f"{r['m']['MaxDrawdown']:.2%}",
            f"{r['m']['Calmar']:.2f}",
            f"{r['m']['WinRate']:.1%}",
            f"{r['m']['ProfitFactor']:.2f}",
            f"{r['m']['ExposurePct']:.1f}",
            f"{r['m']['AvgTradeDuration']:.1f}",
            f"{r['m']['TradesPerYear']:.1f}",
            f"{r['m']['TotalReturn']:.2%}",
        ]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def fold_table_md(fold_results: list[dict], name: str) -> str:
    """Format fold-by-fold results as markdown table."""
    if not fold_results:
        return f"*No valid folds for {name}*\n"
    cols = ["Fold", "Train", "Val", "IS Calmar", "OOS Calmar", "OOS CAGR",
            "OOS MaxDD", "OOS Sharpe", "Best Params"]
    lines = [f"#### {name} — Fold-by-Fold\n"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for fr in fold_results:
        om = fr["oos_metrics"]
        # Abbreviate params
        p_str = ", ".join(f"{k}={v}" for k, v in fr["best_params"].items())
        if len(p_str) > 60:
            p_str = p_str[:57] + "..."
        vals = [
            str(fr["fold"]),
            fr["train_period"].replace(" to ", "→"),
            fr["val_period"].replace(" to ", "→"),
            f"{fr['is_score']:.2f}",
            f"{om['Calmar']:.2f}",
            f"{om['CAGR']:.2%}",
            f"{om['MaxDrawdown']:.2%}",
            f"{om['Sharpe']:.2f}",
            p_str,
        ]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def sensitivity_table_md(sa_df: pd.DataFrame, param_name: str,
                          base_val) -> str:
    """Format sensitivity analysis as markdown."""
    if sa_df.empty:
        return ""
    lines = [f"**{param_name}** (base={base_val}):\n"]
    lines.append("| " + " | ".join(sa_df.columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(sa_df.columns)) + " |")
    for _, row in sa_df.iterrows():
        vals = []
        for c in sa_df.columns:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def describe_strategy(name: str) -> str:
    """Plain-English description of each strategy."""
    descs = {
        "F_hysteresis_regime": (
            "**F: Hysteresis Regime Filter**\n"
            "- Go LONG when Close crosses above EMA(regime_len) * (1 + upper_pct%).\n"
            "- Go to CASH when Close crosses below EMA(regime_len) * (1 - lower_pct%).\n"
            "- Between the bands, hold the previous state (hysteresis prevents whipsaws).\n"
            "- Optional: require EMA slope > 0 over slope_window days for entry.\n"
            "- Binary signal (0 or 1). Signals on Close, executed next day."
        ),
        "G_sizing_regime": (
            "**G: Volatility-Scaled Regime Sizing**\n"
            "- When Close > EMA(regime_len) [with optional slope filter], allocate to SPY.\n"
            "- Position size = clamp(target_vol / realized_vol, 0, 1).\n"
            "- Allocates MORE in calm uptrends, LESS in choppy uptrends, 0 out of regime.\n"
            "- Fractional signal in [0, 1]. Signals on Close, executed next day."
        ),
        "H_atr_dip_addon": (
            "**H: Regime + ATR Dip Add-On**\n"
            "- Base: When Close > EMA(regime_len), hold base_weight (e.g., 50%).\n"
            "- Add-on: When Close dips below EMA(dip_ema) by dip_atr_mult * ATR,\n"
            "  increase weight to min(1.0, base + addon).\n"
            "- Add-on drops when price recovers above EMA(dip_ema). Exit all on regime break.\n"
            "- Fractional signal in [0, 1]. Signals on Close, executed next day."
        ),
        "I_breakout_or_dip": (
            "**I: Breakout OR Dip (Dual-Mode Entry)**\n"
            "- Regime: Close > EMA(regime_len).\n"
            "- Entry Mode 1: Close >= highest high of last breakout_len bars (breakout).\n"
            "- Entry Mode 2: Close <= EMA(dip_ema) * (1 + dip_pct%) (dip buy).\n"
            "- Either trigger starts a trade. Exit: ATR trailing stop OR regime break.\n"
            "- Binary signal (0 or 1). Signals on Close, executed next day."
        ),
    }
    return descs.get(name, f"Strategy: {name}")


def plot_equities(equities: dict, bh_eq: pd.Series, filename: str,
                  title: str, test_start: str = None):
    """Plot equity curves for all strategies + buy-and-hold."""
    fig, ax = plt.subplots(figsize=(14, 7))
    for name, eq in equities.items():
        color = COLORS.get(name, None)
        # Normalize to 100k start
        eq_norm = eq / eq.iloc[0] * 100_000
        ax.plot(eq_norm.index, eq_norm.values, label=name, linewidth=1.2,
                color=color)
    # Buy & hold
    bh_norm = bh_eq / bh_eq.iloc[0] * 100_000
    ax.plot(bh_norm.index, bh_norm.values, label="Buy & Hold", linewidth=1.0,
            color=COLORS["Buy_Hold"], alpha=0.7, linestyle="--")
    if test_start:
        ax.axvline(pd.Timestamp(test_start), color="red", linestyle=":",
                    alpha=0.5, label=f"Test start ({test_start})")
    ax.set_yscale("log")
    ax.set_ylabel("Equity ($, log scale)")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_drawdowns(dd_dict: dict, bh_dd: pd.Series, filename: str,
                   title: str, test_start: str = None):
    """Plot drawdown curves for all strategies + buy-and-hold."""
    fig, ax = plt.subplots(figsize=(14, 5))
    for name, dd in dd_dict.items():
        color = COLORS.get(name, None)
        ax.plot(dd.index, dd.values, label=name, linewidth=1.0, color=color)
    ax.plot(bh_dd.index, bh_dd.values, label="Buy & Hold", linewidth=0.8,
            color=COLORS["Buy_Hold"], alpha=0.6, linestyle="--")
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


def main():
    args = parse_args()
    strategy_names = args.strategies
    t0 = time.time()

    # Validate strategy names
    for name in strategy_names:
        if name not in STRATEGIES:
            print(f"ERROR: Unknown strategy '{name}'. Available: {list(STRATEGIES.keys())}")
            sys.exit(1)

    report = []

    def md(line=""):
        report.append(line)

    md("# Four Scenarios: Strategy Comparison Report")
    md()
    md(f"**Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    md(f"**Instrument**: SPY (long-only + cash)")
    md(f"**Costs**: {BACKTEST_CONFIG.commission_bps} bps commission + "
       f"{BACKTEST_CONFIG.slippage_bps} bps slippage per side")
    md(f"**Walk-forward**: {TRAIN_YEARS}yr train, {VAL_YEARS}yr val, "
       f"{STEP_YEARS}yr step")
    md(f"**Holdout test**: {TEST_START} → latest")
    md(f"**Objective**: maximize avg OOS Calmar ratio")
    md()

    # ── 1. Load data ─────────────────────────────────────────────────
    print("=" * 60)
    print("  FOUR SCENARIOS COMPARISON")
    print("=" * 60)
    print()

    print("[1/6] Loading data...")
    df = download_spy()
    df = add_indicators(df)
    md("## 1. Data")
    md(f"- Range: {df.index[0].date()} to {df.index[-1].date()} "
       f"({len(df)} trading days, {len(df)/252:.1f} years)")
    md()

    # ── 2. Strategy descriptions ─────────────────────────────────────
    md("## 2. Strategy Descriptions")
    md()
    for name in strategy_names:
        md(describe_strategy(name))
        spec = STRATEGIES[name]
        grid = spec["grid"]()
        md(f"- **Parameter grid size**: {len(grid)} combinations")
        md()

    # ── 3. Walk-forward optimization ─────────────────────────────────
    md("## 3. Walk-Forward Optimization")
    md()

    print("[2/6] Running walk-forward optimization...")
    wf_results = {}  # name -> wf dict
    consensus_params = {}  # name -> best params

    for name in strategy_names:
        spec = STRATEGIES[name]
        func = spec["func"]
        grid = spec["grid"]()
        print(f"\n--- {name} ({len(grid)} param combos) ---")

        wf = walk_forward_optimize(
            df=df,
            strategy_func=func,
            param_grid=grid,
            train_years=TRAIN_YEARS,
            val_years=VAL_YEARS,
            step_years=STEP_YEARS,
            test_start_date=TEST_START,
            config=BACKTEST_CONFIG,
            objective="Calmar",
            verbose=True,
        )

        wf_results[name] = wf
        consensus_params[name] = wf["best_params"]

        print(f"  Consensus params: {wf['best_params']}")
        print(f"  Avg OOS Calmar: {wf['oos_metrics_avg'].get('Calmar', 0):.2f}")

    # Write fold-by-fold tables
    for name in strategy_names:
        wf = wf_results[name]
        md(fold_table_md(wf["fold_results"], name))
        md()
        avg = wf["oos_metrics_avg"]
        md(f"**{name} Averages**: OOS Calmar={avg.get('Calmar', 0):.2f}, "
           f"OOS CAGR={avg.get('CAGR', 0):.2%}, "
           f"OOS MaxDD={avg.get('MaxDrawdown', 0):.2%}, "
           f"OOS Sharpe={avg.get('Sharpe', 0):.2f}, "
           f"OOS Exposure={avg.get('ExposurePct', 0):.1f}%, "
           f"OOS Trades/Yr={avg.get('TradesPerYear', 0):.1f}")
        md()

    # Consensus params summary
    md("### Consensus Parameters")
    md()
    for name in strategy_names:
        md(f"- **{name}**: `{consensus_params[name]}`")
    md()

    # ── 4. Holdout test ──────────────────────────────────────────────
    md("## 4. Holdout Test (OOS)")
    md()
    print("\n[3/6] Running holdout tests...")

    holdout_rows = []
    holdout_results = {}  # name -> BacktestResult

    for name in strategy_names:
        spec = STRATEGIES[name]
        func = spec["func"]
        params = consensus_params[name]

        tout = final_test(df, func, params, TEST_START, BACKTEST_CONFIG,
                          verbose=True)
        holdout_results[name] = tout["result"]
        holdout_rows.append({"name": name, "m": tout["metrics"]})

    # Buy & hold on holdout
    test_df = df.loc[TEST_START:]
    bh_test_result = run_buy_and_hold(test_df, BACKTEST_CONFIG)
    bh_test_m = compute_metrics(bh_test_result.equity, bh_test_result.trades)
    holdout_rows.append({"name": "Buy_Hold", "m": bh_test_m})
    holdout_results["Buy_Hold"] = bh_test_result

    md(metric_table_md(holdout_rows, f"Holdout Period ({TEST_START} → latest)"))
    md()

    # ── 5. Full-period backtest ──────────────────────────────────────
    md("## 5. Full-Period Backtest (for reference, NOT for selection)")
    md()
    print("\n[4/6] Running full-period backtests...")

    full_rows = []
    full_results = {}  # name -> BacktestResult

    for name in strategy_names:
        spec = STRATEGIES[name]
        func = spec["func"]
        params = consensus_params[name]

        sig = func(df, params)
        result = run_backtest(df, sig, BACKTEST_CONFIG)
        m = compute_metrics(result.equity, result.trades)

        full_results[name] = result
        full_rows.append({"name": name, "m": m})

        print(f"  {name}: CAGR={m['CAGR']:.2%}, MaxDD={m['MaxDrawdown']:.2%}, "
              f"Calmar={m['Calmar']:.2f}")

    # Buy & hold full
    bh_full = run_buy_and_hold(df, BACKTEST_CONFIG)
    bh_full_m = compute_metrics(bh_full.equity, bh_full.trades)
    full_rows.append({"name": "Buy_Hold", "m": bh_full_m})
    full_results["Buy_Hold"] = bh_full

    md(metric_table_md(full_rows, "Full Period (all history)"))
    md()

    # ── 6. Rankings ──────────────────────────────────────────────────
    md("## 6. Rankings")
    md()

    # Rank by Avg OOS Calmar
    oos_ranking = []
    for name in strategy_names:
        avg_cal = wf_results[name]["oos_metrics_avg"].get("Calmar", 0)
        oos_ranking.append((name, avg_cal))
    oos_ranking.sort(key=lambda x: x[1], reverse=True)

    md("### Ranking by Avg OOS Calmar (walk-forward)")
    md()
    for i, (name, cal) in enumerate(oos_ranking):
        md(f"{i+1}. **{name}**: {cal:.2f}")
    md()

    # Rank by Holdout Calmar
    holdout_ranking = []
    for r in holdout_rows:
        if r["name"] != "Buy_Hold":
            holdout_ranking.append((r["name"], r["m"]["Calmar"]))
    holdout_ranking.sort(key=lambda x: x[1], reverse=True)

    md("### Ranking by Holdout Calmar")
    md()
    for i, (name, cal) in enumerate(holdout_ranking):
        md(f"{i+1}. **{name}**: {cal:.2f}")
    md()

    # ── 7. Sensitivity / Robustness ────────────────────────────────
    md("## 7. Robustness: Sensitivity Around Consensus Params")
    md()
    md("For each strategy, key parameters are varied +/- 1 step from consensus "
       "to check stability. Evaluated on pre-test data only.")
    md()
    print("\n[5/6] Running sensitivity analysis...")

    pre_test_df = df.loc[:TEST_START]

    for name in strategy_names:
        spec = STRATEGIES[name]
        func = spec["func"]
        bp = consensus_params[name]
        md(f"### {name}")
        md()

        for param_name, base_val in bp.items():
            if isinstance(base_val, int):
                step = max(5, base_val // 5)
                vals = sorted(set([
                    max(2, base_val - step),
                    base_val,
                    base_val + step,
                ]))
            elif isinstance(base_val, float):
                step = max(0.25, abs(base_val) * 0.2)
                vals = sorted(set([
                    round(max(0.0, base_val - step), 4),
                    round(base_val, 4),
                    round(base_val + step, 4),
                ]))
            else:
                continue

            sa = sensitivity_analysis(pre_test_df, func, bp,
                                       param_name, vals, BACKTEST_CONFIG)
            if len(sa) > 0:
                md(sensitivity_table_md(sa, param_name, base_val))
                md()

    # ── 8. Charts ────────────────────────────────────────────────────
    print("\n[6/6] Generating charts...")

    # Full period equity
    full_eq = {n: r.equity for n, r in full_results.items() if n != "Buy_Hold"}
    full_dd = {n: r.drawdown for n, r in full_results.items() if n != "Buy_Hold"}
    plot_equities(full_eq, bh_full.equity,
                  "four_scenarios_equity_full.png",
                  "Four Scenarios: Equity Curves (Full Period)",
                  test_start=TEST_START)
    plot_drawdowns(full_dd, bh_full.drawdown,
                   "four_scenarios_drawdown_full.png",
                   "Four Scenarios: Drawdowns (Full Period)",
                   test_start=TEST_START)

    # Holdout period equity
    ho_eq = {n: r.equity for n, r in holdout_results.items() if n != "Buy_Hold"}
    ho_dd = {n: r.drawdown for n, r in holdout_results.items() if n != "Buy_Hold"}
    plot_equities(ho_eq, bh_test_result.equity,
                  "four_scenarios_equity_holdout.png",
                  f"Four Scenarios: Equity Curves (Holdout {TEST_START}+)")
    plot_drawdowns(ho_dd, bh_test_result.drawdown,
                   "four_scenarios_drawdown_holdout.png",
                   f"Four Scenarios: Drawdowns (Holdout {TEST_START}+)")

    md("## 8. Charts")
    md()
    md("- `four_scenarios_equity_full.png` — equity curves, full period")
    md("- `four_scenarios_drawdown_full.png` — drawdowns, full period")
    md("- `four_scenarios_equity_holdout.png` — equity curves, holdout")
    md("- `four_scenarios_drawdown_holdout.png` — drawdowns, holdout")
    md()

    # ── Save report ──────────────────────────────────────────────────
    elapsed = time.time() - t0
    md("---")
    md(f"*Generated in {elapsed:.1f}s*")

    report_path = os.path.join(OUTPUT_DIR, "four_scenarios_report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report))
    print(f"\nReport saved to {report_path}")
    print(f"Total runtime: {elapsed:.1f}s")


if __name__ == "__main__":
    main()

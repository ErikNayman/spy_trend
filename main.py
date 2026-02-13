#!/usr/bin/env python3
"""
main.py – SPY Trend-Following Strategy Research

Downloads SPY data, runs walk-forward optimization across 5 EMA-centric
strategy candidates, performs robustness checks, and generates a full
research report with charts.

Usage:
    python main.py

Outputs saved to ./output/
"""
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
import matplotlib.dates as mdates

from data import download_spy, add_indicators
from backtest import run_backtest, run_buy_and_hold, BacktestConfig
from metrics import (compute_metrics, drawdown_series, monthly_returns_table,
                     format_metrics)
from strategies import STRATEGIES
from optimizer import (walk_forward_optimize, final_test,
                       sensitivity_analysis, subperiod_analysis)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Configuration ───────────────────────────────────────────────────
BACKTEST_CONFIG = BacktestConfig(
    commission_bps=1.0,
    slippage_bps=2.0,
    initial_capital=100_000.0,
)

# Walk-forward settings
TRAIN_YEARS = 8
VAL_YEARS = 2
STEP_YEARS = 2
TEST_START = "2022-01-01"   # ~3 years holdout

# Subperiods for robustness
SUBPERIODS = [
    ("1993-02-01", "2002-12-31"),
    ("2003-01-01", "2012-12-31"),
    ("2013-01-01", "2019-12-31"),
    ("2020-01-01", "2025-12-31"),
]


def main():
    t0 = time.time()
    report_lines = []

    def log(msg=""):
        print(msg)
        report_lines.append(msg)

    log("=" * 70)
    log("  SPY TREND-FOLLOWING STRATEGY RESEARCH")
    log("=" * 70)
    log()

    # ── 1. Download data ────────────────────────────────────────────
    log("## 1. Data Download")
    df = download_spy()
    df = add_indicators(df)
    log(f"Data range: {df.index[0].date()} to {df.index[-1].date()} "
        f"({len(df)} trading days, {len(df)/252:.1f} years)")
    log()

    # ── 2. Buy-and-hold benchmark ──────────────────────────────────
    log("## 2. Buy-and-Hold Benchmark")
    bh_result = run_buy_and_hold(df, BACKTEST_CONFIG)
    bh_metrics = compute_metrics(bh_result.equity, bh_result.trades)
    log(format_metrics(bh_metrics))
    log()

    # ── 3. Walk-forward optimization for each strategy ──────────────
    log("## 3. Strategy Search (Walk-Forward Optimization)")
    log(f"   Train: {TRAIN_YEARS}yr, Val: {VAL_YEARS}yr, Step: {STEP_YEARS}yr")
    log(f"   Test holdout: {TEST_START} onward")
    log(f"   Objective: Calmar ratio")
    log()

    strategy_results = {}
    for name, spec in STRATEGIES.items():
        log(f"--- {name}: {spec['description']} ---")
        grid = spec["grid"]()
        log(f"  Parameter grid size: {len(grid)}")

        wf = walk_forward_optimize(
            df=df,
            strategy_func=spec["func"],
            param_grid=grid,
            train_years=TRAIN_YEARS,
            val_years=VAL_YEARS,
            step_years=STEP_YEARS,
            test_start_date=TEST_START,
            config=BACKTEST_CONFIG,
            objective="Calmar",
            verbose=True,
        )

        if wf["n_folds"] == 0:
            log(f"  No valid folds. Skipping.")
            log()
            continue

        log(f"  Consensus params: {wf['best_params']}")
        log(f"  Avg OOS Calmar: {wf['oos_metrics_avg'].get('Calmar', 0):.2f}")
        log(f"  Avg IS  Calmar: {wf['is_metrics_avg'].get('Calmar', 0):.2f}")
        log()

        strategy_results[name] = {
            "spec": spec,
            "wf": wf,
        }

    if not strategy_results:
        log("ERROR: No strategies produced valid results.")
        sys.exit(1)

    # ── 4. Select best strategy by OOS Calmar ────────────────────────
    log("## 4. Strategy Ranking (by avg OOS Calmar)")
    ranking = []
    for name, sr in strategy_results.items():
        oos_calmar = sr["wf"]["oos_metrics_avg"].get("Calmar", 0)
        oos_cagr = sr["wf"]["oos_metrics_avg"].get("CAGR", 0)
        oos_dd = sr["wf"]["oos_metrics_avg"].get("MaxDrawdown", 0)
        ranking.append({
            "Strategy": name,
            "OOS_Calmar": oos_calmar,
            "OOS_CAGR": oos_cagr,
            "OOS_MaxDD": oos_dd,
            "Params": sr["wf"]["best_params"],
        })

    ranking.sort(key=lambda x: x["OOS_Calmar"], reverse=True)
    for i, r in enumerate(ranking):
        log(f"  {i+1}. {r['Strategy']}: OOS Calmar={r['OOS_Calmar']:.2f}, "
            f"CAGR={r['OOS_CAGR']:.2%}, MaxDD={r['OOS_MaxDD']:.2%}")
    log()

    best_name = ranking[0]["Strategy"]
    best_sr = strategy_results[best_name]
    best_params = best_sr["wf"]["best_params"]
    best_func = best_sr["spec"]["func"]

    log(f"**WINNER: {best_name}**")
    log(f"  Params: {best_params}")
    log()

    # ── 5. Final test on holdout period ──────────────────────────────
    log("## 5. Final Out-of-Sample Test")
    test_out = final_test(df, best_func, best_params, TEST_START,
                          BACKTEST_CONFIG, verbose=True)
    log(f"\n  Test Period Metrics (HOLDOUT):")
    log(format_metrics(test_out["metrics"]))
    log()

    # Also run full-period backtest for charts
    full_sig = best_func(df, best_params)
    full_result = run_backtest(df, full_sig, BACKTEST_CONFIG)
    full_metrics = compute_metrics(full_result.equity, full_result.trades)

    log("## 5b. Full-Period Backtest (for reference, NOT for selection)")
    log(format_metrics(full_metrics))
    log()

    # Test-period buy-and-hold for comparison
    test_df = df.loc[TEST_START:]
    bh_test = run_buy_and_hold(test_df, BACKTEST_CONFIG)
    bh_test_m = compute_metrics(bh_test.equity, bh_test.trades)
    log("  Buy-and-Hold during test period:")
    log(format_metrics(bh_test_m))
    log()

    # ── 6. Robustness: Sensitivity Analysis ──────────────────────────
    log("## 6. Sensitivity Analysis")
    for param_name in best_params:
        base_val = best_params[param_name]
        if isinstance(base_val, int):
            vals = sorted(set([
                max(2, base_val - 50), max(2, base_val - 20),
                max(2, base_val - 10), base_val,
                base_val + 10, base_val + 20, base_val + 50
            ]))
        elif isinstance(base_val, float):
            vals = sorted(set([
                max(0.0, base_val - 2.0), max(0.0, base_val - 1.0),
                max(0.0, base_val - 0.5), base_val,
                base_val + 0.5, base_val + 1.0, base_val + 2.0
            ]))
        else:
            continue

        sa = sensitivity_analysis(df.loc[:TEST_START], best_func,
                                  best_params, param_name, vals,
                                  BACKTEST_CONFIG)
        if len(sa) > 0:
            log(f"\n  Sensitivity: {param_name} (base={base_val})")
            log(sa.to_string(index=False))

    log()

    # ── 7. Subperiod Analysis ────────────────────────────────────────
    log("## 7. Subperiod Stability")
    sp = subperiod_analysis(df, best_func, best_params, SUBPERIODS,
                            BACKTEST_CONFIG)
    if len(sp) > 0:
        log(sp.to_string(index=False))

    # Also do subperiod for buy-and-hold
    log("\n  Buy-and-Hold subperiods:")
    bh_sp_rows = []
    for start, end in SUBPERIODS:
        sub_df = df.loc[start:end]
        if len(sub_df) < 50:
            continue
        bh_r = run_buy_and_hold(sub_df, BACKTEST_CONFIG)
        bh_m = compute_metrics(bh_r.equity, bh_r.trades)
        bh_sp_rows.append({
            "Period": f"{start} to {end}",
            "CAGR": bh_m["CAGR"],
            "MaxDD": bh_m["MaxDrawdown"],
            "Calmar": bh_m["Calmar"],
            "Sharpe": bh_m["Sharpe"],
        })
    bh_sp = pd.DataFrame(bh_sp_rows)
    if len(bh_sp) > 0:
        log(bh_sp.to_string(index=False))
    log()

    # ── 8. Monthly Returns ───────────────────────────────────────────
    log("## 8. Monthly Returns (Test Period)")
    test_monthly = monthly_returns_table(test_out["result"].equity)
    log(test_monthly.to_string(float_format=lambda x: f"{x:.2%}" if not pd.isna(x) else ""))
    log()

    # ── 9. Charts ────────────────────────────────────────────────────
    log("## 9. Charts")
    _plot_equity_and_drawdown(
        full_result.equity, bh_result.equity,
        full_result.drawdown, bh_result.drawdown,
        best_name, best_params, TEST_START
    )
    log(f"  Saved: {OUTPUT_DIR}/equity_curve.png")
    log(f"  Saved: {OUTPUT_DIR}/drawdown.png")

    _plot_test_period(
        test_out["result"].equity, bh_test.equity,
        test_out["result"].drawdown,
        best_name
    )
    log(f"  Saved: {OUTPUT_DIR}/test_equity.png")
    log()

    # ── 10. Summary ──────────────────────────────────────────────────
    log("=" * 70)
    log("  FINAL RECOMMENDATION (based on OUT-OF-SAMPLE results)")
    log("=" * 70)
    log()
    log(f"Strategy: {best_name}")
    log(f"Description: {best_sr['spec']['description']}")
    log(f"Parameters: {best_params}")
    log()
    log("Rules (plain English):")
    log(_describe_strategy(best_name, best_params))
    log()
    log("Test Period Performance:")
    log(format_metrics(test_out["metrics"]))
    log()
    log("Buy-and-Hold Test Period:")
    log(format_metrics(bh_test_m))
    log()
    log("Why this strategy reduces drawdowns:")
    log("  This is a trend-following system that stays long during confirmed")
    log("  uptrends (price above long-term EMA) and exits to cash when the")
    log("  trend breaks. The ATR-based trailing stop (if present) provides an")
    log("  additional layer of protection by exiting when price drops")
    log("  significantly from its peak. By avoiding sustained bear markets,")
    log("  the strategy sacrifices some upside during whipsaws but dramatically")
    log("  reduces maximum drawdown compared to buy-and-hold.")
    log()

    elapsed = time.time() - t0
    log(f"Total runtime: {elapsed:.1f} seconds")

    # Save report
    report_path = os.path.join(OUTPUT_DIR, "report.md")
    with open(report_path, "w") as f:
        f.write("# SPY Trend-Following Strategy Research Report\n\n")
        f.write("```\n")
        f.write("\n".join(report_lines))
        f.write("\n```\n")
    print(f"\nReport saved to {report_path}")


def _describe_strategy(name: str, params: dict) -> str:
    """Generate plain-English description of the winning strategy."""
    if "crossover" in name.lower():
        return (
            f"  Go LONG when EMA({params['fast']}) crosses above EMA({params['slow']}).\n"
            f"  Go to CASH when EMA({params['fast']}) crosses below EMA({params['slow']}).\n"
            f"  Signals generated on Close, executed next day."
        )
    elif "regime" in name.lower():
        desc = f"  Go LONG when Close > EMA({params['regime_len']})"
        if params.get("slope_window", 0) > 0:
            desc += f" AND EMA({params['regime_len']}) slope over {params['slope_window']} days is positive"
        desc += ".\n  Go to CASH when either condition breaks.\n"
        desc += "  Signals generated on Close, executed next day."
        return desc
    elif "dip" in name.lower():
        return (
            f"  REGIME: Close > EMA({params['regime_len']}).\n"
            f"  ENTRY: When in regime AND Close pulls back within {params['dip_pct']}% "
            f"of EMA({params['dip_ema']}).\n"
            f"  EXIT: When Close < EMA({params['regime_len']}) (regime break).\n"
            f"  Stay in trade once entered until regime breaks.\n"
            f"  Signals generated on Close, executed next day."
        )
    elif "atr_stop" in name.lower() and "composite" not in name.lower():
        return (
            f"  ENTRY: EMA({params['fast']}) > EMA({params['slow']}) (bullish crossover).\n"
            f"  EXIT: Close drops below trailing stop = "
            f"highest_close - {params['atr_mult']} x ATR({params['atr_len']}),\n"
            f"        OR EMA crossover turns bearish.\n"
            f"  Re-enter when crossover fires bullish again.\n"
            f"  Signals generated on Close, executed next day."
        )
    elif "composite" in name.lower():
        desc = f"  REGIME: Close > EMA({params['regime_len']})"
        if params.get("slope_window", 0) > 0:
            desc += f" AND EMA slope > 0 over {params['slope_window']} days"
        desc += (
            f".\n  ENTRY: In regime AND Close <= EMA({params['entry_ema']}) "
            f"x (1 + {params['entry_band_pct']}%).\n"
            f"  EXIT: Trailing stop = highest_close - {params['atr_mult']} x "
            f"ATR({params['atr_len']}), OR regime break.\n"
            f"  Signals generated on Close, executed next day."
        )
        return desc
    return f"  Parameters: {params}"


def _plot_equity_and_drawdown(strat_eq, bh_eq, strat_dd, bh_dd,
                               strat_name, params, test_start):
    """Plot full-period equity curve and drawdown."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(strat_eq.index, strat_eq.values, label=f"Strategy: {strat_name}",
             linewidth=1.2, color="steelblue")
    ax1.plot(bh_eq.index, bh_eq.values, label="Buy & Hold SPY",
             linewidth=1.0, color="gray", alpha=0.7)
    ax1.axvline(pd.Timestamp(test_start), color="red", linestyle="--",
                alpha=0.5, label=f"Test start ({test_start})")
    ax1.set_yscale("log")
    ax1.set_ylabel("Equity ($, log scale)")
    ax1.set_title(f"SPY Trend Strategy: {strat_name}\nParams: {params}")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(strat_dd.index, strat_dd.values, 0,
                     alpha=0.5, color="steelblue", label="Strategy DD")
    ax2.fill_between(bh_dd.index, bh_dd.values, 0,
                     alpha=0.3, color="gray", label="B&H DD")
    ax2.axvline(pd.Timestamp(test_start), color="red", linestyle="--", alpha=0.5)
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel("Date")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "equity_curve.png"), dpi=150)
    plt.close()

    # Separate drawdown chart
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(strat_dd.index, strat_dd.values, 0,
                    alpha=0.6, color="steelblue", label="Strategy")
    ax.fill_between(bh_dd.index, bh_dd.values, 0,
                    alpha=0.3, color="gray", label="Buy & Hold")
    ax.axvline(pd.Timestamp(test_start), color="red", linestyle="--", alpha=0.5)
    ax.set_title("Drawdown Comparison")
    ax.set_ylabel("Drawdown")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "drawdown.png"), dpi=150)
    plt.close()


def _plot_test_period(strat_eq, bh_eq, strat_dd, strat_name):
    """Plot test-period equity and drawdown."""
    # Normalize to start at same value
    bh_norm = bh_eq / bh_eq.iloc[0] * strat_eq.iloc[0]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(strat_eq.index, strat_eq.values, label=f"Strategy", linewidth=1.2,
             color="steelblue")
    ax1.plot(bh_norm.index, bh_norm.values, label="Buy & Hold", linewidth=1.0,
             color="gray", alpha=0.7)
    ax1.set_ylabel("Equity ($)")
    ax1.set_title(f"Test Period: {strat_name}")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(strat_dd.index, strat_dd.values, 0,
                     alpha=0.5, color="steelblue")
    ax2.set_ylabel("Drawdown")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "test_equity.png"), dpi=150)
    plt.close()


if __name__ == "__main__":
    main()

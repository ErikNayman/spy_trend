#!/usr/bin/env python3
"""
run_ddcap_sweep.py – Multi-DD-Cap Sweep.

Run the DD-capped selection pipeline across multiple drawdown caps in one go.

Usage:
    python run_ddcap_sweep.py --dd-caps -10 -15 -20 -25
    python run_ddcap_sweep.py --dd-caps -10 -15 -20 -25 --risk-scales 0.5 0.6 0.7 0.8 0.9 1.0
    python run_ddcap_sweep.py --dd-caps -10 -20 --strategies F_hysteresis_regime G_sizing_regime
"""
import argparse
import json
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
from metrics import compute_metrics, drawdown_series
from strategies import STRATEGIES
from ddcap import (
    build_folds,
    expand_grid_with_risk_scale,
    evaluate_params_across_folds,
    passes_constraints,
    score_for_selection,
    run_strategy_on_slice,
    describe_strategy,
    metric_table_md,
    generate_tldr,
)

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
FOLD_PASS_RATE = 0.80
MIN_AVG_EXPOSURE = 60.0

COLORS = {
    "F_hysteresis_regime": "#1f77b4",
    "G_sizing_regime":     "#ff7f0e",
    "H_atr_dip_addon":     "#2ca02c",
    "I_breakout_or_dip":   "#d62728",
    "Buy_Hold":            "#7f7f7f",
    "E_composite":         "#9467bd",
}


def parse_args():
    p = argparse.ArgumentParser(description="Multi-DD-Cap Sweep")
    p.add_argument("--dd-caps", type=float, nargs="+", required=True,
                   help="DD cap values in %% (e.g., -10 -15 -20 -25)")
    p.add_argument("--risk-scales", type=float, nargs="+",
                   default=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                   help="risk_scale values. Default: 0.5..1.0")
    p.add_argument("--strategies", type=str, nargs="+",
                   default=["F_hysteresis_regime", "G_sizing_regime",
                            "H_atr_dip_addon", "I_breakout_or_dip"],
                   help="Strategy names. Default: F, G, H, I")
    return p.parse_args()


# ── Plotting helpers (same as run_ddcap20.py) ─────────────────────
def plot_equity(equities, bh_eq, filename, title, dd_cap, test_start=None):
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
    ax.set_yscale("log")
    ax.set_ylabel("Equity ($, log scale)")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_drawdown(dd_dict, bh_dd, filename, title, dd_cap, test_start=None):
    fig, ax = plt.subplots(figsize=(14, 5))
    for name, dd in dd_dict.items():
        color = COLORS.get(name, None)
        ax.plot(dd.index, dd.values, label=name, linewidth=1.0, color=color)
    ax.plot(bh_dd.index, bh_dd.values, label="Buy & Hold", linewidth=0.8,
            color=COLORS["Buy_Hold"], alpha=0.6, linestyle="--")
    ax.axhline(dd_cap, color="crimson", linestyle="-", linewidth=1.5,
               alpha=0.7, label=f"DD cap ({dd_cap:.0%})")
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


# ── Core: run one DD cap ──────────────────────────────────────────
def run_single_ddcap(df, folds, dd_cap, risk_scales, strategy_names,
                     config, fold_pass_rate, min_avg_exposure, cap_label,
                     test_start, verbose=True):
    """Run DD-capped selection for one cap value. Returns summary dict."""
    report = []

    def md(line=""):
        report.append(line)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  DD-CAP = {dd_cap:.0%}  ({cap_label})")
        print(f"{'='*60}")

    # Report header
    md("# Drawdown-Capped Strategy Selection Report")
    md()
    md(f"**Hard constraint**: MaxDD >= {dd_cap:.0%} (no worse than {abs(dd_cap):.0%})")
    md(f"**Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    md(f"**Data**: SPY {df.index[0].date()} → {df.index[-1].date()} ({len(df)} days)")
    md(f"**Costs**: {config.commission_bps} bps commission + "
       f"{config.slippage_bps} bps slippage/side")
    md(f"**Walk-forward**: {TRAIN_YEARS}yr train, {VAL_YEARS}yr val, "
       f"{STEP_YEARS}yr step, {len(folds)} folds")
    md(f"**Holdout**: {test_start} → latest")
    md(f"**risk_scale grid**: {risk_scales}")
    md(f"**Fold-pass rate required**: {fold_pass_rate:.0%}")
    md(f"**Min avg OOS exposure**: {min_avg_exposure}%")
    md()

    md("## Strategy Descriptions")
    md()
    for name in strategy_names:
        md(f"- {describe_strategy(name)}")
    md()

    # ── Optimization ──
    md("## Walk-Forward Optimization (DD-Capped)")
    md()

    all_strategy_results = {}

    for sname in strategy_names:
        spec = STRATEGIES[sname]
        func = spec["func"]
        base_grid = spec["grid"]()
        grid = expand_grid_with_risk_scale(base_grid, risk_scales)

        if verbose:
            print(f"  {sname}: {len(grid)} combos...", end=" ")

        passing = []
        n_evaluated = 0
        n_error = 0

        for params in grid:
            ev = evaluate_params_across_folds(df, folds, func, params, config)
            if ev is None:
                n_error += 1
                continue
            n_evaluated += 1
            if passes_constraints(ev, dd_cap, fold_pass_rate, min_avg_exposure):
                passing.append((params, ev))

        if verbose:
            print(f"{n_evaluated} evaluated, {len(passing)} passed")

        md(f"### {sname}")
        md(f"- Base grid: {len(base_grid)}, Expanded: {len(grid)}")
        md(f"- Evaluated: {n_evaluated}, Passed: **{len(passing)}** "
           f"({len(passing)/max(n_evaluated,1)*100:.1f}%)")

        if passing:
            passing.sort(key=lambda x: score_for_selection(x[1]), reverse=True)
            best_params, best_ev = passing[0]
            avg = best_ev["avg_metrics"]
            md(f"- **Best params**: `{best_params}`")
            md(f"- Avg OOS CAGR: {avg['CAGR']:.2%}, Stitched MaxDD: {best_ev['stitched_maxdd']:.2%}")
            all_strategy_results[sname] = {
                "best_params": best_params,
                "best_ev": best_ev,
                "n_passing": len(passing),
                "n_evaluated": n_evaluated,
            }
        else:
            md("- **No parameter set passed all constraints.**")
            all_strategy_results[sname] = None
        md()

    # ── Select winner ──
    candidates = {k: v for k, v in all_strategy_results.items() if v is not None}

    if not candidates:
        if verbose:
            print(f"  NO WINNER for DD-cap {dd_cap:.0%}")
        md("\n## RESULT: No strategy passed constraints.")
        _save_report(report, cap_label)
        return {
            "dd_cap": dd_cap,
            "winner": None,
            "risk_scale": None,
            "stitched_maxdd": None,
            "avg_oos_cagr": None,
            "holdout_cagr": None,
            "holdout_maxdd": None,
            "exposure": None,
            "notes": "No strategy passed",
            "all_strategies": {sn: None for sn in strategy_names},
        }

    ranked = sorted(candidates.items(),
                    key=lambda kv: score_for_selection(kv[1]["best_ev"]),
                    reverse=True)

    winner_name = ranked[0][0]
    winner_data = ranked[0][1]
    winner_params = winner_data["best_params"]
    winner_ev = winner_data["best_ev"]
    winner_func = STRATEGIES[winner_name]["func"]
    winner_risk_scale = winner_params.get("risk_scale", 1.0)
    winner_strat_params = {k: v for k, v in winner_params.items() if k != "risk_scale"}

    if verbose:
        print(f"  WINNER: {winner_name} (risk_scale={winner_risk_scale})")
        print(f"  Avg OOS CAGR: {winner_ev['avg_metrics']['CAGR']:.2%}")

    # Ranking table
    md("## Overall Ranking")
    md()
    summary_cols = ["Rank", "Strategy", "Avg OOS CAGR", "Avg OOS Sharpe",
                    "Stitched MaxDD", "Avg Exp%", "risk_scale"]
    md("| " + " | ".join(summary_cols) + " |")
    md("| " + " | ".join(["---"] * len(summary_cols)) + " |")
    for rank, (sn, sd) in enumerate(ranked, 1):
        avg = sd["best_ev"]["avg_metrics"]
        bp = sd["best_params"]
        md(f"| {rank} | {sn} | {avg['CAGR']:.2%} | {avg['Sharpe']:.2f} "
           f"| {sd['best_ev']['stitched_maxdd']:.2%} | {avg['ExposurePct']:.1f} "
           f"| {bp.get('risk_scale', 1.0)} |")
    md()

    md(f"### WINNER: **{winner_name}**")
    md(f"- Params: `{winner_params}`")
    md()

    # ── Holdout test ──
    test_df = df.loc[test_start:]
    holdout_rows = []
    holdout_results = {}

    for sn in strategy_names:
        sd = all_strategy_results[sn]
        if sd is None:
            continue
        bp = sd["best_params"]
        rs = bp.get("risk_scale", 1.0)
        sp = {k: v for k, v in bp.items() if k != "risk_scale"}
        func = STRATEGIES[sn]["func"]
        res = run_strategy_on_slice(test_df, func, sp, rs, config)
        m = compute_metrics(res.equity, res.trades)
        holdout_rows.append({"name": sn, "m": m})
        holdout_results[sn] = res

    bh_test = run_buy_and_hold(test_df, config)
    bh_test_m = compute_metrics(bh_test.equity, bh_test.trades)
    holdout_rows.append({"name": "Buy_Hold", "m": bh_test_m})
    holdout_results["Buy_Hold"] = bh_test

    md(metric_table_md(holdout_rows, f"Holdout ({test_start} → latest)"))
    md()

    # Winner holdout metrics
    winner_hold_m = None
    for r in holdout_rows:
        if r["name"] == winner_name:
            winner_hold_m = r["m"]

    # ── Full-period backtest ──
    full_rows = []
    full_results = {}
    for sn in strategy_names:
        sd = all_strategy_results[sn]
        if sd is None:
            continue
        bp = sd["best_params"]
        rs = bp.get("risk_scale", 1.0)
        sp = {k: v for k, v in bp.items() if k != "risk_scale"}
        func = STRATEGIES[sn]["func"]
        res = run_strategy_on_slice(df, func, sp, rs, config)
        m = compute_metrics(res.equity, res.trades)
        full_rows.append({"name": sn, "m": m})
        full_results[sn] = res

    bh_full = run_buy_and_hold(df, config)
    bh_full_m = compute_metrics(bh_full.equity, bh_full.trades)
    full_rows.append({"name": "Buy_Hold", "m": bh_full_m})
    full_results["Buy_Hold"] = bh_full

    md(metric_table_md(full_rows, "Full Period (all history)"))
    md()

    # ── TL;DR ──
    tldr = generate_tldr(winner_name, winner_params, winner_ev,
                         winner_hold_m, dd_cap, folds)
    insert_idx = 2
    for i, line in enumerate(report):
        if line.startswith("## Strategy Descriptions"):
            insert_idx = i
            break
    report.insert(insert_idx, "")
    report.insert(insert_idx, tldr)

    # ── Charts ──
    # Full period
    full_eq = {n: r.equity for n, r in full_results.items() if n != "Buy_Hold"}
    full_dd = {n: r.drawdown for n, r in full_results.items() if n != "Buy_Hold"}
    plot_equity(full_eq, bh_full.equity,
                f"{cap_label}_equity_full.png",
                f"DD-Capped ({dd_cap:.0%}) Strategies: Equity (Full Period)",
                dd_cap, test_start=test_start)
    plot_drawdown(full_dd, bh_full.drawdown,
                  f"{cap_label}_drawdown_full.png",
                  f"DD-Capped ({dd_cap:.0%}) Strategies: Drawdown (Full Period)",
                  dd_cap, test_start=test_start)

    # Holdout
    ho_eq = {n: r.equity for n, r in holdout_results.items() if n != "Buy_Hold"}
    ho_dd = {n: r.drawdown for n, r in holdout_results.items() if n != "Buy_Hold"}
    plot_equity(ho_eq, bh_test.equity,
                f"{cap_label}_equity_holdout.png",
                f"DD-Capped ({dd_cap:.0%}) Strategies: Equity (Holdout)",
                dd_cap)
    plot_drawdown(ho_dd, bh_test.drawdown,
                  f"{cap_label}_drawdown_holdout.png",
                  f"DD-Capped ({dd_cap:.0%}) Strategies: Drawdown (Holdout)",
                  dd_cap)

    md("## Charts")
    md()
    md(f"- `{cap_label}_equity_full.png`")
    md(f"- `{cap_label}_drawdown_full.png`")
    md(f"- `{cap_label}_equity_holdout.png`")
    md(f"- `{cap_label}_drawdown_holdout.png`")
    md()

    # Save report
    md("---")
    _save_report(report, cap_label)

    # Fold pass rate for notes
    fm_list = winner_ev["fold_metrics"]
    valid_fm = [m for m in fm_list if m is not None]
    n_dd_pass = sum(1 for m in valid_fm if m["MaxDrawdown"] >= dd_cap)
    pass_pct = n_dd_pass / len(valid_fm) * 100 if valid_fm else 0

    # Per-strategy detail for JSON
    per_strat = {}
    for sn in strategy_names:
        sd = all_strategy_results[sn]
        if sd is None:
            per_strat[sn] = {"passed": False}
        else:
            avg = sd["best_ev"]["avg_metrics"]
            per_strat[sn] = {
                "passed": True,
                "best_params": sd["best_params"],
                "avg_oos_cagr": avg["CAGR"],
                "avg_oos_sharpe": avg["Sharpe"],
                "stitched_maxdd": sd["best_ev"]["stitched_maxdd"],
                "n_passing": sd["n_passing"],
                "n_evaluated": sd["n_evaluated"],
            }

    return {
        "dd_cap": dd_cap,
        "winner": winner_name,
        "risk_scale": winner_risk_scale,
        "stitched_maxdd": winner_ev["stitched_maxdd"],
        "avg_oos_cagr": winner_ev["avg_metrics"]["CAGR"],
        "holdout_cagr": winner_hold_m["CAGR"] if winner_hold_m else None,
        "holdout_maxdd": winner_hold_m["MaxDrawdown"] if winner_hold_m else None,
        "exposure": winner_ev["avg_metrics"].get("ExposurePct", 0),
        "notes": f"Pass rate {pass_pct:.0f}%",
        "all_strategies": per_strat,
    }


def _save_report(report, cap_label):
    path = os.path.join(OUTPUT_DIR, f"{cap_label}_report.md")
    with open(path, "w") as f:
        f.write("\n".join(report))
    print(f"  Report saved: {path}")


def main():
    args = parse_args()

    dd_caps_pct = sorted(args.dd_caps)  # e.g., [-25, -20, -15, -10]
    risk_scales = args.risk_scales
    strategy_names = args.strategies

    # Validate strategy names
    for sn in strategy_names:
        if sn not in STRATEGIES:
            print(f"ERROR: Unknown strategy '{sn}'. Available: {list(STRATEGIES.keys())}")
            sys.exit(1)

    t0 = time.time()

    print("=" * 60)
    print("  MULTI-DD-CAP SWEEP")
    print("=" * 60)
    print(f"  DD caps: {dd_caps_pct}")
    print(f"  Strategies: {strategy_names}")
    print(f"  risk_scales: {risk_scales}")
    print()

    # ── 1. Load data ONCE ──
    print("[1/3] Loading data...")
    df = download_spy()
    df = add_indicators(df)
    print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} days)")

    # ── 2. Build folds ONCE ──
    folds = build_folds(df, TRAIN_YEARS, VAL_YEARS, STEP_YEARS, TEST_START)
    print(f"  Walk-forward: {len(folds)} folds, test from {TEST_START}")

    # ── 3. Run each DD cap ──
    print(f"\n[2/3] Running {len(dd_caps_pct)} DD-cap configurations...")
    sweep_results = []

    for dd_cap_pct in dd_caps_pct:
        dd_cap = dd_cap_pct / 100.0
        cap_label = f"ddcap{abs(int(dd_cap_pct))}"

        result = run_single_ddcap(
            df=df,
            folds=folds,
            dd_cap=dd_cap,
            risk_scales=risk_scales,
            strategy_names=strategy_names,
            config=BACKTEST_CONFIG,
            fold_pass_rate=FOLD_PASS_RATE,
            min_avg_exposure=MIN_AVG_EXPOSURE,
            cap_label=cap_label,
            test_start=TEST_START,
            verbose=True,
        )
        sweep_results.append(result)

    # ── 4. Generate sweep summary ──
    print(f"\n[3/3] Generating sweep summary...")

    # Markdown summary
    summary_lines = [
        "# DD-Cap Sweep Summary",
        "",
        f"**Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Strategies**: {', '.join(strategy_names)}",
        f"**risk_scales**: {risk_scales}",
        "",
        "## Results",
        "",
    ]

    cols = ["DD Cap", "Winner", "risk_scale", "Stitched OOS MaxDD",
            "Avg OOS CAGR", "Holdout CAGR", "Holdout MaxDD", "Exposure", "Notes"]
    summary_lines.append("| " + " | ".join(cols) + " |")
    summary_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")

    for r in sweep_results:
        if r["winner"] is None:
            summary_lines.append(
                f"| {r['dd_cap']:.0%} | — | — | — | — | — | — | — | {r['notes']} |")
        else:
            summary_lines.append(
                f"| {r['dd_cap']:.0%} | {r['winner']} | {r['risk_scale']} "
                f"| {r['stitched_maxdd']:.2%} | {r['avg_oos_cagr']:.2%} "
                f"| {r['holdout_cagr']:.2%} | {r['holdout_maxdd']:.2%} "
                f"| {r['exposure']:.1f}% | {r['notes']} |")
    summary_lines.append("")

    summary_path = os.path.join(OUTPUT_DIR, "ddcap_sweep_summary.md")
    with open(summary_path, "w") as f:
        f.write("\n".join(summary_lines))
    print(f"  Markdown summary: {summary_path}")

    # JSON summary
    json_data = {
        "sweep_date": pd.Timestamp.now().isoformat(),
        "strategies": strategy_names,
        "risk_scales": risk_scales,
        "caps": [],
    }
    for r in sweep_results:
        cap_entry = {
            "dd_cap": r["dd_cap"],
            "winner": r["winner"],
            "risk_scale": r["risk_scale"],
            "stitched_maxdd": r["stitched_maxdd"],
            "avg_oos_cagr": r["avg_oos_cagr"],
            "holdout_cagr": r["holdout_cagr"],
            "holdout_maxdd": r["holdout_maxdd"],
            "exposure": r["exposure"],
            "notes": r["notes"],
            "all_strategies": r["all_strategies"],
        }
        json_data["caps"].append(cap_entry)

    json_path = os.path.join(OUTPUT_DIR, "ddcap_sweep_summary.json")
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"  JSON summary: {json_path}")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  SWEEP COMPLETE — {len(dd_caps_pct)} caps in {elapsed:.1f}s")
    print(f"{'='*60}")

    # Print summary table to console
    print()
    print(f"{'DD Cap':>8} | {'Winner':<24} | {'rs':>4} | {'OOS CAGR':>10} | "
          f"{'HO CAGR':>9} | {'HO MaxDD':>9}")
    print("-" * 80)
    for r in sweep_results:
        if r["winner"] is None:
            print(f"{r['dd_cap']:>7.0%} | {'(none)':<24} | {'—':>4} | "
                  f"{'—':>10} | {'—':>9} | {'—':>9}")
        else:
            print(f"{r['dd_cap']:>7.0%} | {r['winner']:<24} | {r['risk_scale']:>4} | "
                  f"{r['avg_oos_cagr']:>9.2%} | {r['holdout_cagr']:>8.2%} | "
                  f"{r['holdout_maxdd']:>8.2%}")


if __name__ == "__main__":
    main()

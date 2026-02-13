#!/usr/bin/env python3
"""
app.py – Streamlit UI for SPY Trend-Following Backtest Research.

Launch:
    streamlit run app.py
"""
import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    generate_tldr,
)

# ── Page config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="SPY Trend Backtest",
    page_icon="📈",
    layout="wide",
)

# ── Strategy metadata ────────────────────────────────────────────
STRATEGY_DESCRIPTIONS = {
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

COLORS = {
    "F_hysteresis_regime": "#1f77b4",
    "G_sizing_regime":     "#ff7f0e",
    "H_atr_dip_addon":     "#2ca02c",
    "I_breakout_or_dip":   "#d62728",
    "Buy_Hold":            "#7f7f7f",
}


# ── Data loading (cached) ───────────────────────────────────────
@st.cache_data(show_spinner="Loading SPY data...")
def load_data():
    df = download_spy()
    df = add_indicators(df)
    return df


# ── Plotting helpers (Plotly) ────────────────────────────────────
def plot_equity_plotly(equities, bh_eq, title, test_start=None):
    fig = go.Figure()
    for name, eq in equities.items():
        eq_norm = eq / eq.iloc[0] * 100_000
        fig.add_trace(go.Scatter(
            x=eq_norm.index, y=eq_norm.values,
            name=name, mode="lines",
            line=dict(color=COLORS.get(name), width=1.5),
        ))
    bh_norm = bh_eq / bh_eq.iloc[0] * 100_000
    fig.add_trace(go.Scatter(
        x=bh_norm.index, y=bh_norm.values,
        name="Buy & Hold", mode="lines",
        line=dict(color=COLORS["Buy_Hold"], width=1, dash="dash"),
        opacity=0.7,
    ))
    if test_start:
        fig.add_vline(x=test_start, line_dash="dot", line_color="red",
                       annotation_text="Holdout start", opacity=0.5)
    fig.update_layout(
        title=title, yaxis_title="Equity ($, log scale)",
        yaxis_type="log", template="plotly_white",
        height=500, legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
    )
    return fig


def plot_drawdown_plotly(dd_dict, bh_dd, title, dd_cap=None, test_start=None):
    fig = go.Figure()
    for name, dd in dd_dict.items():
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            name=name, mode="lines",
            line=dict(color=COLORS.get(name), width=1),
        ))
    fig.add_trace(go.Scatter(
        x=bh_dd.index, y=bh_dd.values,
        name="Buy & Hold", mode="lines",
        line=dict(color=COLORS["Buy_Hold"], width=0.8, dash="dash"),
        opacity=0.6,
    ))
    if dd_cap is not None:
        fig.add_hline(y=dd_cap, line_dash="solid", line_color="crimson",
                       line_width=2, annotation_text=f"DD cap ({dd_cap:.0%})",
                       opacity=0.7)
    if test_start:
        fig.add_vline(x=test_start, line_dash="dot", line_color="red", opacity=0.5)
    fig.update_layout(
        title=title, yaxis_title="Drawdown",
        yaxis_tickformat=".0%", template="plotly_white",
        height=350, legend=dict(x=0.01, y=0.01, yanchor="bottom"),
        hovermode="x unified",
    )
    return fig


def plot_stitched_wf(stitched_equity, stitched_dd, folds, winner_name, dd_cap):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.05,
        subplot_titles=[
            f"Stitched Walk-Forward OOS Equity: {winner_name}",
            "Stitched WF OOS Drawdown",
        ],
    )
    eq_norm = stitched_equity / stitched_equity.iloc[0] * 100_000
    color = COLORS.get(winner_name, "steelblue")

    fig.add_trace(go.Scatter(
        x=eq_norm.index, y=eq_norm.values,
        name=f"{winner_name} (OOS)", mode="lines",
        line=dict(color=color, width=1.5),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=stitched_dd.index, y=stitched_dd.values,
        name="Drawdown", mode="lines",
        fill="tozeroy", fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.3)",
        line=dict(color=color, width=1),
    ), row=2, col=1)

    fig.add_hline(y=dd_cap, line_dash="solid", line_color="crimson",
                   line_width=2, row=2, col=1)

    for fold in folds:
        fig.add_vline(x=fold["val_start"], line_dash="dot",
                       line_color="gray", opacity=0.3, row=1, col=1)
        fig.add_vline(x=fold["val_start"], line_dash="dot",
                       line_color="gray", opacity=0.3, row=2, col=1)

    fig.update_yaxes(type="log", title_text="Equity ($, log)", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", title_text="Drawdown", row=2, col=1)
    fig.update_layout(
        template="plotly_white", height=600,
        hovermode="x unified", showlegend=False,
    )
    return fig


# ── Format metrics as DataFrame ──────────────────────────────────
def metrics_to_df(rows):
    records = []
    for r in rows:
        m = r["m"]
        records.append({
            "Strategy": r["name"],
            "CAGR": f"{m['CAGR']:.2%}",
            "Vol": f"{m['Volatility']:.2%}",
            "Sharpe": f"{m['Sharpe']:.2f}",
            "Sortino": f"{m['Sortino']:.2f}",
            "MaxDD": f"{m['MaxDrawdown']:.2%}",
            "Calmar": f"{m['Calmar']:.2f}",
            "WinRate": f"{m['WinRate']:.1%}",
            "PF": f"{m['ProfitFactor']:.2f}",
            "Exp%": f"{m['ExposurePct']:.1f}",
            "AvgDays": f"{m['AvgTradeDuration']:.1f}",
            "Tr/Yr": f"{m['TradesPerYear']:.1f}",
            "TotRet": f"{m['TotalReturn']:.2%}",
        })
    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
st.sidebar.title("Configuration")

mode = st.sidebar.radio(
    "Mode",
    ["DD-Capped Optimization", "Single Strategy Backtest"],
    help="DD-Capped: full walk-forward optimization with drawdown constraints. "
         "Single: run one strategy with custom params.",
)

st.sidebar.markdown("---")

# Strategy selection
DDCAP_STRATEGIES = ["F_hysteresis_regime", "G_sizing_regime",
                    "H_atr_dip_addon", "I_breakout_or_dip"]
ALL_STRATEGIES = list(STRATEGIES.keys())

if mode == "DD-Capped Optimization":
    selected_strategies = st.sidebar.multiselect(
        "Strategies", DDCAP_STRATEGIES, default=DDCAP_STRATEGIES,
        help="Strategies to include in the DD-capped optimization.",
    )
    dd_cap_pct = st.sidebar.slider(
        "Max Drawdown Cap (%)", min_value=-30, max_value=-5,
        value=-20, step=1,
        help="Hard constraint: MaxDD must be no worse than this.",
    )
    dd_cap = dd_cap_pct / 100.0

    st.sidebar.markdown("**Risk Scale Grid**")
    rs_col1, rs_col2 = st.sidebar.columns(2)
    rs_min = rs_col1.number_input("Min", 0.3, 1.0, 0.5, 0.1)
    rs_max = rs_col2.number_input("Max", 0.3, 1.0, 1.0, 0.1)
    rs_step = st.sidebar.number_input("Step", 0.05, 0.5, 0.1, 0.05)
    risk_scales = list(np.arange(rs_min, rs_max + rs_step / 2, rs_step).round(2))

    fold_pass_rate = st.sidebar.slider(
        "Fold Pass Rate", 0.5, 1.0, 0.8, 0.05,
        help="Fraction of folds that must individually satisfy the DD cap.",
    )
    min_exposure = st.sidebar.slider(
        "Min Avg OOS Exposure (%)", 20.0, 90.0, 60.0, 5.0,
    )
else:
    single_strategy = st.sidebar.selectbox(
        "Strategy", ALL_STRATEGIES,
        index=ALL_STRATEGIES.index("G_sizing_regime"),
    )

st.sidebar.markdown("---")
st.sidebar.markdown("**Walk-Forward**")
train_years = st.sidebar.number_input("Train (years)", 4, 12, 8)
val_years = st.sidebar.number_input("Validation (years)", 1, 4, 2)
step_years = st.sidebar.number_input("Step (years)", 1, 4, 2)
test_start = st.sidebar.text_input("Holdout Start", "2022-01-01")

st.sidebar.markdown("---")
st.sidebar.markdown("**Costs**")
commission_bps = st.sidebar.number_input("Commission (bps/side)", 0.0, 10.0, 1.0, 0.5)
slippage_bps = st.sidebar.number_input("Slippage (bps/side)", 0.0, 10.0, 2.0, 0.5)


# ══════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════
st.title("SPY Trend-Following Backtest")

config = BacktestConfig(
    commission_bps=commission_bps,
    slippage_bps=slippage_bps,
)

# ── DD-CAPPED OPTIMIZATION MODE ─────────────────────────────────
if mode == "DD-Capped Optimization":
    st.markdown(
        f"**Hard constraint**: MaxDD >= {dd_cap:.0%} &nbsp;|&nbsp; "
        f"**Costs**: {commission_bps} + {slippage_bps} bps/side &nbsp;|&nbsp; "
        f"**WF**: {train_years}yr train, {val_years}yr val, {step_years}yr step &nbsp;|&nbsp; "
        f"**risk_scale**: {risk_scales}"
    )

    with st.expander("Strategy Descriptions", expanded=False):
        for sname in selected_strategies:
            desc = STRATEGY_DESCRIPTIONS.get(sname, sname)
            st.markdown(f"- {desc}")

    if not selected_strategies:
        st.warning("Select at least one strategy.")
        st.stop()

    run_button = st.button("Run DD-Capped Optimization", type="primary",
                            use_container_width=True)

    if run_button:
        df = load_data()
        st.info(f"Data: SPY {df.index[0].date()} to {df.index[-1].date()} "
                f"({len(df)} days)")

        folds = build_folds(df, train_years, val_years, step_years, test_start)
        st.write(f"Walk-forward folds: **{len(folds)}**")

        # ── Optimization ──
        all_strategy_results = {}
        progress = st.progress(0, text="Optimizing...")

        total_strategies = len(selected_strategies)
        for si, sname in enumerate(selected_strategies):
            spec = STRATEGIES[sname]
            func = spec["func"]
            base_grid = spec["grid"]()
            grid = expand_grid_with_risk_scale(base_grid, risk_scales)

            progress.progress(
                si / total_strategies,
                text=f"Optimizing {sname} ({len(grid)} param combos)...",
            )

            passing = []
            n_evaluated = 0

            for params in grid:
                ev = evaluate_params_across_folds(df, folds, func, params, config)
                if ev is None:
                    continue
                n_evaluated += 1
                if passes_constraints(ev, dd_cap, fold_pass_rate, min_exposure):
                    passing.append((params, ev))

            if passing:
                passing.sort(key=lambda x: score_for_selection(x[1]), reverse=True)
                best_params, best_ev = passing[0]
                all_strategy_results[sname] = {
                    "best_params": best_params,
                    "best_ev": best_ev,
                    "n_passing": len(passing),
                    "n_evaluated": n_evaluated,
                }
            else:
                all_strategy_results[sname] = None

        progress.progress(1.0, text="Optimization complete!")

        # ── Results ──
        candidates = {k: v for k, v in all_strategy_results.items() if v is not None}
        failed = [n for n in selected_strategies if all_strategy_results[n] is None]

        if failed:
            st.warning(f"Failed to meet DD-cap: **{', '.join(failed)}**")

        if not candidates:
            st.error("No strategy passed all constraints. Try a looser DD cap or "
                     "wider risk_scale range.")
            st.stop()

        # Rank
        ranked = sorted(candidates.items(),
                        key=lambda kv: score_for_selection(kv[1]["best_ev"]),
                        reverse=True)
        winner_name = ranked[0][0]
        winner_data = ranked[0][1]
        winner_params = winner_data["best_params"]
        winner_ev = winner_data["best_ev"]
        winner_risk_scale = winner_params.get("risk_scale", 1.0)
        winner_strat_params = {k: v for k, v in winner_params.items()
                               if k != "risk_scale"}
        winner_func = STRATEGIES[winner_name]["func"]

        # ── Winner banner ──
        st.success(f"**WINNER: {winner_name}** &nbsp;|&nbsp; "
                   f"risk_scale={winner_risk_scale} &nbsp;|&nbsp; "
                   f"Avg OOS CAGR={winner_ev['avg_metrics']['CAGR']:.2%} &nbsp;|&nbsp; "
                   f"Stitched OOS MaxDD={winner_ev['stitched_maxdd']:.2%}")

        st.markdown(f"**Best params**: `{winner_params}`")

        # ── Explain Like I'm Busy ──
        # Compute holdout metrics for TL;DR (quick run on winner only)
        test_df_tldr = df.loc[test_start:]
        winner_holdout_tldr = run_strategy_on_slice(
            test_df_tldr, winner_func, winner_strat_params,
            winner_risk_scale, config)
        holdout_m_tldr = compute_metrics(winner_holdout_tldr.equity,
                                         winner_holdout_tldr.trades)

        with st.expander("Explain Like I'm Busy (One-Click Recommendation)",
                         expanded=True):
            tldr_text = generate_tldr(winner_name, winner_params, winner_ev,
                                      holdout_m_tldr, dd_cap, folds)
            st.markdown(tldr_text)

            # Optional LLM explanation
            if os.environ.get("ANTHROPIC_API_KEY"):
                if st.button("Get AI Explanation"):
                    from llm_explain import explain_with_llm
                    context = {
                        "winner": winner_name,
                        "params": winner_params,
                        "avg_oos_cagr": winner_ev["avg_metrics"]["CAGR"],
                        "avg_oos_sharpe": winner_ev["avg_metrics"]["Sharpe"],
                        "avg_oos_maxdd": winner_ev["avg_metrics"]["MaxDrawdown"],
                        "stitched_maxdd": winner_ev["stitched_maxdd"],
                        "dd_cap": dd_cap,
                        "holdout_cagr": holdout_m_tldr["CAGR"],
                        "holdout_maxdd": holdout_m_tldr["MaxDrawdown"],
                        "holdout_sharpe": holdout_m_tldr["Sharpe"],
                        "n_folds": len(folds),
                    }
                    with st.spinner("Asking Claude..."):
                        explanation = explain_with_llm(context)
                    if explanation:
                        st.markdown(explanation)
                    else:
                        st.info("Could not generate AI explanation.")

        # ── Ranking table ──
        st.markdown("### Overall Ranking")
        rank_rows = []
        for rank, (sn, sd) in enumerate(ranked, 1):
            avg = sd["best_ev"]["avg_metrics"]
            bp = sd["best_params"]
            fm_list = sd["best_ev"]["fold_metrics"]
            valid_fm = [m for m in fm_list if m is not None]
            dd_pass = sum(1 for m in valid_fm if m["MaxDrawdown"] >= dd_cap)
            pass_pct = dd_pass / len(valid_fm) * 100 if valid_fm else 0
            rank_rows.append({
                "Rank": rank,
                "Strategy": sn,
                "Avg OOS CAGR": f"{avg['CAGR']:.2%}",
                "Avg OOS Sharpe": f"{avg['Sharpe']:.2f}",
                "Avg OOS Calmar": f"{avg['Calmar']:.2f}",
                "Avg OOS MaxDD": f"{avg['MaxDrawdown']:.2%}",
                "Avg Exp%": f"{avg['ExposurePct']:.1f}",
                "Stitched MaxDD": f"{sd['best_ev']['stitched_maxdd']:.2%}",
                "Fold Pass": f"{pass_pct:.0f}%",
                "risk_scale": bp.get("risk_scale", 1.0),
            })
        st.dataframe(pd.DataFrame(rank_rows), use_container_width=True,
                     hide_index=True)

        # ── Tabs ──
        tab_wf, tab_holdout, tab_full, tab_folds = st.tabs([
            "Stitched WF OOS", "Holdout", "Full Period", "Fold Details",
        ])

        # --- Stitched WF OOS ---
        with tab_wf:
            stitched_eq = winner_ev["stitched_equity"]
            stitched_dd = winner_ev["stitched_dd"]
            stitched_ret = stitched_eq.pct_change().dropna()
            n_days = len(stitched_ret)
            n_years = n_days / 252.0
            total = stitched_eq.iloc[-1] / stitched_eq.iloc[0]
            cagr = total ** (1 / n_years) - 1 if n_years > 0 else 0
            vol = stitched_ret.std() * np.sqrt(252)
            sharpe = (stitched_ret.mean() / stitched_ret.std() * np.sqrt(252)
                      if stitched_ret.std() > 0 else 0)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Period", f"{stitched_eq.index[0].date()} to "
                                f"{stitched_eq.index[-1].date()}")
            c2.metric("CAGR", f"{cagr:.2%}")
            c3.metric("Sharpe", f"{sharpe:.2f}")
            c4.metric("MaxDD", f"{winner_ev['stitched_maxdd']:.2%}")
            c5.metric("Total Return", f"{total - 1:.2%}")

            fig_wf = plot_stitched_wf(stitched_eq, stitched_dd, folds,
                                       winner_name, dd_cap)
            st.plotly_chart(fig_wf, use_container_width=True)

        # --- Holdout ---
        with tab_holdout:
            test_df = df.loc[test_start:]
            holdout_rows = []
            holdout_results = {}

            for sn in selected_strategies:
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

            st.markdown(f"### Holdout ({test_start} to latest)")
            st.dataframe(metrics_to_df(holdout_rows),
                         use_container_width=True, hide_index=True)

            ho_eq = {n: r.equity for n, r in holdout_results.items()
                     if n != "Buy_Hold"}
            ho_dd = {n: r.drawdown for n, r in holdout_results.items()
                     if n != "Buy_Hold"}

            st.plotly_chart(
                plot_equity_plotly(ho_eq, bh_test.equity,
                                   f"Equity — Holdout ({test_start}+)"),
                use_container_width=True,
            )
            st.plotly_chart(
                plot_drawdown_plotly(ho_dd, bh_test.drawdown,
                                     f"Drawdown — Holdout ({test_start}+)",
                                     dd_cap=dd_cap),
                use_container_width=True,
            )

        # --- Full period ---
        with tab_full:
            full_rows = []
            full_results = {}

            for sn in selected_strategies:
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

            st.markdown("### Full Period (for reference, NOT for selection)")
            st.dataframe(metrics_to_df(full_rows),
                         use_container_width=True, hide_index=True)

            full_eq = {n: r.equity for n, r in full_results.items()
                       if n != "Buy_Hold"}
            full_dd = {n: r.drawdown for n, r in full_results.items()
                       if n != "Buy_Hold"}

            st.plotly_chart(
                plot_equity_plotly(full_eq, bh_full.equity,
                                   "Equity — Full Period", test_start=test_start),
                use_container_width=True,
            )
            st.plotly_chart(
                plot_drawdown_plotly(full_dd, bh_full.drawdown,
                                     "Drawdown — Full Period",
                                     dd_cap=dd_cap, test_start=test_start),
                use_container_width=True,
            )

        # --- Fold details ---
        with tab_folds:
            for sn in selected_strategies:
                sd = all_strategy_results[sn]
                if sd is None:
                    st.markdown(f"#### {sn}: *Failed — no params passed constraints*")
                    continue

                st.markdown(f"#### {sn}")
                st.markdown(f"**Best params**: `{sd['best_params']}`  \n"
                            f"Passed: {sd['n_passing']}/{sd['n_evaluated']} "
                            f"({sd['n_passing']/max(sd['n_evaluated'],1)*100:.1f}%)")

                fold_rows = []
                for fi, fold in enumerate(folds):
                    fm = (sd["best_ev"]["fold_metrics"][fi]
                          if fi < len(sd["best_ev"]["fold_metrics"]) else None)
                    if fm is None:
                        fold_rows.append({
                            "Fold": fi,
                            "Val Period": f"{fold['val_start'].date()} to "
                                          f"{fold['val_end'].date()}",
                            "OOS CAGR": "—", "OOS MaxDD": "—",
                            "OOS Sharpe": "—", "OOS Calmar": "—",
                            "Exp%": "—", "DD Pass?": "—",
                        })
                    else:
                        dd_ok = "YES" if fm["MaxDrawdown"] >= dd_cap else "NO"
                        fold_rows.append({
                            "Fold": fi,
                            "Val Period": f"{fold['val_start'].date()} to "
                                          f"{fold['val_end'].date()}",
                            "OOS CAGR": f"{fm['CAGR']:.2%}",
                            "OOS MaxDD": f"{fm['MaxDrawdown']:.2%}",
                            "OOS Sharpe": f"{fm['Sharpe']:.2f}",
                            "OOS Calmar": f"{fm['Calmar']:.2f}",
                            "Exp%": f"{fm['ExposurePct']:.1f}",
                            "DD Pass?": dd_ok,
                        })
                st.dataframe(pd.DataFrame(fold_rows),
                             use_container_width=True, hide_index=True)


# ── SINGLE STRATEGY BACKTEST MODE ───────────────────────────────
else:
    spec = STRATEGIES[single_strategy]
    func = spec["func"]
    desc = STRATEGY_DESCRIPTIONS.get(single_strategy, spec.get("description", ""))

    st.markdown(f"**Strategy**: {single_strategy}")
    if desc:
        st.markdown(desc)

    # Parameter inputs
    st.markdown("### Parameters")
    base_grid = spec["grid"]()
    # Use first param set as defaults
    defaults = base_grid[0] if base_grid else {}

    params = {}
    cols = st.columns(min(len(defaults), 4)) if defaults else []
    for i, (k, v) in enumerate(defaults.items()):
        col = cols[i % len(cols)] if cols else st
        if isinstance(v, float):
            params[k] = col.number_input(k, value=v, step=0.01 if v < 1 else 0.5,
                                          format="%.2f")
        elif isinstance(v, int):
            params[k] = col.number_input(k, value=v, step=1)
        else:
            params[k] = col.text_input(k, str(v))

    risk_scale_single = st.slider("risk_scale", 0.1, 1.0, 1.0, 0.05)

    run_single = st.button("Run Backtest", type="primary",
                            use_container_width=True)

    if run_single:
        df = load_data()
        st.info(f"Data: SPY {df.index[0].date()} to {df.index[-1].date()} "
                f"({len(df)} days)")

        test_df = df.loc[test_start:]

        # Full period
        res_full = run_strategy_on_slice(df, func, params, risk_scale_single,
                                          config)
        m_full = compute_metrics(res_full.equity, res_full.trades)

        # Holdout
        res_hold = run_strategy_on_slice(test_df, func, params,
                                          risk_scale_single, config)
        m_hold = compute_metrics(res_hold.equity, res_hold.trades)

        # Buy & Hold
        bh_full = run_buy_and_hold(df, config)
        bh_hold = run_buy_and_hold(test_df, config)
        bh_full_m = compute_metrics(bh_full.equity, bh_full.trades)
        bh_hold_m = compute_metrics(bh_hold.equity, bh_hold.trades)

        # Metrics cards
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Full CAGR", f"{m_full['CAGR']:.2%}")
        c2.metric("Full Sharpe", f"{m_full['Sharpe']:.2f}")
        c3.metric("Full MaxDD", f"{m_full['MaxDrawdown']:.2%}")
        c4.metric("Holdout CAGR", f"{m_hold['CAGR']:.2%}")
        c5.metric("Holdout MaxDD", f"{m_hold['MaxDrawdown']:.2%}")

        tab_fp, tab_ho = st.tabs(["Full Period", "Holdout"])

        with tab_fp:
            st.dataframe(
                metrics_to_df([
                    {"name": single_strategy, "m": m_full},
                    {"name": "Buy_Hold", "m": bh_full_m},
                ]),
                use_container_width=True, hide_index=True,
            )
            eq_dict = {single_strategy: res_full.equity}
            dd_dict = {single_strategy: res_full.drawdown}

            st.plotly_chart(
                plot_equity_plotly(eq_dict, bh_full.equity,
                                   f"{single_strategy} — Full Period",
                                   test_start=test_start),
                use_container_width=True,
            )
            st.plotly_chart(
                plot_drawdown_plotly(dd_dict, bh_full.drawdown,
                                     f"{single_strategy} — Drawdown (Full Period)",
                                     test_start=test_start),
                use_container_width=True,
            )

        with tab_ho:
            st.dataframe(
                metrics_to_df([
                    {"name": single_strategy, "m": m_hold},
                    {"name": "Buy_Hold", "m": bh_hold_m},
                ]),
                use_container_width=True, hide_index=True,
            )
            eq_dict_h = {single_strategy: res_hold.equity}
            dd_dict_h = {single_strategy: res_hold.drawdown}

            st.plotly_chart(
                plot_equity_plotly(eq_dict_h, bh_hold.equity,
                                   f"{single_strategy} — Holdout ({test_start}+)"),
                use_container_width=True,
            )
            st.plotly_chart(
                plot_drawdown_plotly(dd_dict_h, bh_hold.drawdown,
                                     f"{single_strategy} — Drawdown (Holdout)",
                                     ),
                use_container_width=True,
            )

"""
optimizer.py – Walk-forward optimization framework.

Design:
  - Split data into rolling windows: train / validation.
  - On each window, grid-search parameters on the training set,
    pick best by Calmar ratio, then evaluate on validation set.
  - Aggregate out-of-sample (OOS) validation results to select the best strategy.
  - Final test on the holdout period.

Walk-forward scheme:
  SPY data roughly 1993–2025 (~32 years).
  - Train window: 8 years (rolling).
  - Validation window: 2 years.
  - Step: 2 years.
  - This gives ~12 folds: [1993-2001 train | 2001-2003 val],
    [1995-2003 train | 2003-2005 val], ...
  - Final test period: last 3 years (2023-2025 approx, reserved).
"""
import numpy as np
import pandas as pd
from typing import Callable
from backtest import run_backtest, BacktestConfig, BacktestResult
from metrics import compute_metrics


def walk_forward_optimize(
    df: pd.DataFrame,
    strategy_func: Callable,
    param_grid: list[dict],
    train_years: int = 8,
    val_years: int = 2,
    step_years: int = 2,
    test_start_date: str | None = None,
    config: BacktestConfig | None = None,
    objective: str = "Calmar",
    min_trades_per_year: float = 0.5,
    max_trades_per_year: float = 50.0,
    min_exposure_pct: float = 10.0,
    verbose: bool = True,
) -> dict:
    """
    Walk-forward optimization.

    Returns dict with:
      - best_params: dict
      - oos_equity: pd.Series (concatenated OOS equity)
      - oos_metrics: dict
      - is_metrics_avg: dict (average in-sample metrics)
      - fold_results: list of fold details
      - best_param_counts: dict tracking which params were selected per fold
    """
    if config is None:
        config = BacktestConfig()

    dates = df.index
    start = dates[0]
    end = dates[-1]

    # Reserve test period
    if test_start_date:
        test_start = pd.Timestamp(test_start_date)
    else:
        test_start = end - pd.DateOffset(years=3)

    # Walk-forward folds (only on data before test period)
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
        fold_start = fold_start + pd.DateOffset(years=step_years)

    if len(folds) == 0:
        # Fallback: single split
        mid = start + (test_start - start) * 0.75
        folds = [{
            "train_start": start,
            "train_end": mid,
            "val_start": mid,
            "val_end": test_start,
        }]

    if verbose:
        print(f"  Walk-forward: {len(folds)} folds, "
              f"test reserved from {test_start.date()}")

    fold_results = []
    oos_equities = []
    param_selections = []

    for fi, fold in enumerate(folds):
        train_df = df.loc[fold["train_start"]:fold["train_end"]]
        val_df = df.loc[fold["val_start"]:fold["val_end"]]

        if len(train_df) < 252 or len(val_df) < 100:
            continue

        # Grid search on training data
        best_score = -np.inf
        best_params = None
        best_is_metrics = None

        for params in param_grid:
            try:
                sig = strategy_func(train_df, params)
                result = run_backtest(train_df, sig, config)
                m = compute_metrics(result.equity, result.trades)

                # Constraints
                if m["TradesPerYear"] < min_trades_per_year:
                    continue
                if m["TradesPerYear"] > max_trades_per_year:
                    continue
                if m["ExposurePct"] < min_exposure_pct:
                    continue

                score = m.get(objective, 0.0)
                if np.isnan(score) or np.isinf(score):
                    score = 0.0

                if score > best_score:
                    best_score = score
                    best_params = params
                    best_is_metrics = m
            except Exception:
                continue

        if best_params is None:
            continue

        # Evaluate best params on validation data
        try:
            val_sig = strategy_func(val_df, best_params)
            val_result = run_backtest(val_df, val_sig, config)
            val_m = compute_metrics(val_result.equity, val_result.trades)
        except Exception:
            continue

        fold_results.append({
            "fold": fi,
            "train_period": f"{fold['train_start'].date()} to {fold['train_end'].date()}",
            "val_period": f"{fold['val_start'].date()} to {fold['val_end'].date()}",
            "best_params": best_params,
            "is_score": best_score,
            "is_metrics": best_is_metrics,
            "oos_metrics": val_m,
        })
        oos_equities.append(val_result.equity)
        param_selections.append(str(best_params))

        if verbose:
            print(f"    Fold {fi}: IS Calmar={best_score:.2f}, "
                  f"OOS Calmar={val_m['Calmar']:.2f}, params={best_params}")

    # Select the most commonly chosen parameter set across folds
    if param_selections:
        from collections import Counter
        param_counts = Counter(param_selections)
        most_common_params_str = param_counts.most_common(1)[0][0]
        # Find the actual dict
        for fr in fold_results:
            if str(fr["best_params"]) == most_common_params_str:
                consensus_params = fr["best_params"]
                break
    else:
        consensus_params = param_grid[0] if param_grid else {}

    # Aggregate OOS metrics
    if fold_results:
        avg_oos = {}
        keys = fold_results[0]["oos_metrics"].keys()
        for k in keys:
            vals = [fr["oos_metrics"][k] for fr in fold_results
                    if not np.isnan(fr["oos_metrics"].get(k, np.nan))
                    and not np.isinf(fr["oos_metrics"].get(k, np.nan))]
            avg_oos[k] = np.mean(vals) if vals else 0.0

        avg_is = {}
        for k in keys:
            vals = [fr["is_metrics"][k] for fr in fold_results
                    if fr["is_metrics"] and
                    not np.isnan(fr["is_metrics"].get(k, np.nan))
                    and not np.isinf(fr["is_metrics"].get(k, np.nan))]
            avg_is[k] = np.mean(vals) if vals else 0.0
    else:
        avg_oos = {}
        avg_is = {}

    return {
        "best_params": consensus_params,
        "fold_results": fold_results,
        "oos_metrics_avg": avg_oos,
        "is_metrics_avg": avg_is,
        "n_folds": len(fold_results),
    }


def final_test(df: pd.DataFrame, strategy_func: Callable, params: dict,
               test_start_date: str, config: BacktestConfig | None = None,
               verbose: bool = True) -> dict:
    """
    Run the final out-of-sample test on the holdout period.
    """
    if config is None:
        config = BacktestConfig()

    test_start = pd.Timestamp(test_start_date)
    test_df = df.loc[test_start:]

    if len(test_df) < 50:
        print(f"  [WARNING] Test period only has {len(test_df)} days")

    sig = strategy_func(test_df, params)
    result = run_backtest(test_df, sig, config)
    m = compute_metrics(result.equity, result.trades)

    if verbose:
        print(f"  Test period: {test_df.index[0].date()} to {test_df.index[-1].date()} "
              f"({len(test_df)} days)")
        print(f"  Test Calmar: {m['Calmar']:.2f}, CAGR: {m['CAGR']:.2%}, "
              f"MaxDD: {m['MaxDrawdown']:.2%}")

    return {
        "metrics": m,
        "result": result,
        "test_df": test_df,
    }


def sensitivity_analysis(df: pd.DataFrame, strategy_func: Callable,
                         base_params: dict, param_name: str,
                         values: list, config: BacktestConfig | None = None) -> pd.DataFrame:
    """
    Vary one parameter while keeping others fixed.
    Returns DataFrame with parameter value and key metrics.
    """
    if config is None:
        config = BacktestConfig()

    rows = []
    for v in values:
        p = dict(base_params)
        p[param_name] = v
        try:
            sig = strategy_func(df, p)
            result = run_backtest(df, sig, config)
            m = compute_metrics(result.equity, result.trades)
            rows.append({
                param_name: v,
                "CAGR": m["CAGR"],
                "MaxDD": m["MaxDrawdown"],
                "Calmar": m["Calmar"],
                "Sharpe": m["Sharpe"],
                "Exposure": m["ExposurePct"],
                "Trades/Yr": m["TradesPerYear"],
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def subperiod_analysis(df: pd.DataFrame, strategy_func: Callable,
                       params: dict, periods: list[tuple[str, str]],
                       config: BacktestConfig | None = None) -> pd.DataFrame:
    """
    Evaluate strategy across subperiods.
    periods: list of (start_date, end_date) tuples as strings.
    """
    if config is None:
        config = BacktestConfig()

    rows = []
    for start, end in periods:
        sub_df = df.loc[start:end]
        if len(sub_df) < 50:
            continue
        try:
            sig = strategy_func(sub_df, params)
            result = run_backtest(sub_df, sig, config)
            m = compute_metrics(result.equity, result.trades)
            rows.append({
                "Period": f"{start} to {end}",
                "CAGR": m["CAGR"],
                "MaxDD": m["MaxDrawdown"],
                "Calmar": m["Calmar"],
                "Sharpe": m["Sharpe"],
                "Exposure": m["ExposurePct"],
                "Trades/Yr": m["TradesPerYear"],
            })
        except Exception:
            continue

    return pd.DataFrame(rows)

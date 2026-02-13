"""Tests for ddcap.py constraint and selection logic."""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import pytest

from ddcap import (
    build_folds,
    expand_grid_with_risk_scale,
    passes_constraints,
    score_for_selection,
)


# ── Helpers ───────────────────────────────────────────────────────
def _make_eval_result(fold_maxdds, stitched_maxdd, avg_cagr=0.08,
                      avg_sharpe=1.0, avg_calmar=0.5, avg_exposure=70.0):
    """Create a synthetic eval_result dict for testing."""
    fold_metrics = []
    for dd in fold_maxdds:
        fold_metrics.append({
            "CAGR": avg_cagr,
            "Volatility": 0.15,
            "Sharpe": avg_sharpe,
            "Sortino": 1.5,
            "MaxDrawdown": dd,
            "Calmar": avg_calmar,
            "WinRate": 0.55,
            "ProfitFactor": 1.5,
            "ExposurePct": avg_exposure,
            "AvgTradeDuration": 10.0,
            "TradesPerYear": 5.0,
            "TotalTrades": 50,
            "TotalReturn": 1.0,
            "NumYears": 2.0,
        })
    return {
        "fold_metrics": fold_metrics,
        "fold_daily_returns": [],
        "stitched_equity": pd.Series([100_000, 110_000]),
        "stitched_dd": pd.Series([0.0, -0.05]),
        "stitched_maxdd": stitched_maxdd,
        "avg_metrics": {
            "CAGR": avg_cagr,
            "Volatility": 0.15,
            "Sharpe": avg_sharpe,
            "Sortino": 1.5,
            "MaxDrawdown": min(fold_maxdds),
            "Calmar": avg_calmar,
            "WinRate": 0.55,
            "ProfitFactor": 1.5,
            "ExposurePct": avg_exposure,
            "AvgTradeDuration": 10.0,
            "TradesPerYear": 5.0,
        },
        "n_valid_folds": len(fold_metrics),
    }


# ── passes_constraints tests ─────────────────────────────────────
class TestPassesConstraints:

    def test_none_eval_result(self):
        """None eval_result → False."""
        assert passes_constraints(None, -0.20, 0.80, 60.0) is False

    def test_too_few_valid_folds(self):
        """Fewer than 3 valid folds → False."""
        ev = _make_eval_result([-0.05, -0.08], -0.10)
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is False

    def test_low_exposure(self):
        """ExposurePct < min_exposure → False."""
        ev = _make_eval_result(
            [-0.05, -0.08, -0.10, -0.12, -0.06],
            stitched_maxdd=-0.12,
            avg_exposure=40.0,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is False

    def test_bad_stitched_maxdd(self):
        """stitched_maxdd < dd_cap → False."""
        ev = _make_eval_result(
            [-0.05, -0.08, -0.10, -0.12, -0.06],
            stitched_maxdd=-0.25,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is False

    def test_low_fold_pass_rate(self):
        """Too many folds exceed DD cap → False."""
        # Only 2 of 5 folds within -20% cap (40% < 80%)
        ev = _make_eval_result(
            [-0.05, -0.25, -0.30, -0.22, -0.08],
            stitched_maxdd=-0.15,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is False

    def test_all_constraints_pass(self):
        """Synthetic passing example → True."""
        ev = _make_eval_result(
            [-0.05, -0.08, -0.10, -0.12, -0.06],
            stitched_maxdd=-0.12,
            avg_exposure=70.0,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is True

    def test_borderline_fold_pass_rate(self):
        """Exactly 80% fold pass rate → True."""
        # 4 of 5 folds pass (80%)
        ev = _make_eval_result(
            [-0.10, -0.15, -0.18, -0.25, -0.05],
            stitched_maxdd=-0.18,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is True

    def test_borderline_stitched_maxdd(self):
        """stitched_maxdd exactly at dd_cap → True (>= check)."""
        ev = _make_eval_result(
            [-0.10, -0.15, -0.18, -0.12, -0.05],
            stitched_maxdd=-0.20,
        )
        assert passes_constraints(ev, -0.20, 0.80, 60.0) is True


# ── score_for_selection tests ─────────────────────────────────────
class TestScoreForSelection:

    def test_higher_cagr_ranks_first(self):
        """Higher CAGR → higher score."""
        ev_high = _make_eval_result([-0.05] * 5, -0.10, avg_cagr=0.12)
        ev_low = _make_eval_result([-0.05] * 5, -0.10, avg_cagr=0.06)
        assert score_for_selection(ev_high) > score_for_selection(ev_low)

    def test_same_cagr_sharpe_tiebreak(self):
        """Same CAGR, higher Sharpe → higher score."""
        ev_high = _make_eval_result([-0.05] * 5, -0.10,
                                    avg_cagr=0.10, avg_sharpe=1.5)
        ev_low = _make_eval_result([-0.05] * 5, -0.10,
                                   avg_cagr=0.10, avg_sharpe=0.8)
        assert score_for_selection(ev_high) > score_for_selection(ev_low)

    def test_returns_tuple(self):
        """score_for_selection returns a 3-tuple."""
        ev = _make_eval_result([-0.05] * 5, -0.10)
        result = score_for_selection(ev)
        assert isinstance(result, tuple)
        assert len(result) == 3


# ── build_folds tests ────────────────────────────────────────────
class TestBuildFolds:

    def test_basic_fold_count(self):
        """Correct number of folds for known date range."""
        dates = pd.date_range("1993-01-29", "2025-12-31", freq="B")
        df = pd.DataFrame({"Close": range(len(dates))}, index=dates)
        folds = build_folds(df, train_years=8, val_years=2,
                           step_years=2, test_start_date="2022-01-01")
        # From 1993, 8+2=10yr first fold ends 2003
        # Then 2yr steps: 1995→2005, 1997→2007, 1999→2009, 2001→2011,
        # 2003→2013, 2005→2015, 2007→2017, 2009→2019, 2011→2021
        # 2013→2023 would exceed 2022-01-01, so stops.
        assert len(folds) >= 5  # sanity check: at least 5 folds
        assert len(folds) <= 15  # not too many

    def test_fold_structure(self):
        """Each fold has required keys."""
        dates = pd.date_range("1993-01-29", "2025-12-31", freq="B")
        df = pd.DataFrame({"Close": range(len(dates))}, index=dates)
        folds = build_folds(df, 8, 2, 2, "2022-01-01")
        for fold in folds:
            assert "train_start" in fold
            assert "train_end" in fold
            assert "val_start" in fold
            assert "val_end" in fold
            assert fold["train_end"] == fold["val_start"]
            assert fold["val_end"] <= pd.Timestamp("2022-01-01")

    def test_no_folds_short_data(self):
        """Very short data → 0 folds."""
        dates = pd.date_range("2020-01-01", "2021-12-31", freq="B")
        df = pd.DataFrame({"Close": range(len(dates))}, index=dates)
        folds = build_folds(df, 8, 2, 2, "2022-01-01")
        assert len(folds) == 0


# ── expand_grid_with_risk_scale tests ────────────────────────────
class TestExpandGrid:

    def test_expansion_count(self):
        """Grid size = base × risk_scales."""
        base = [{"a": 1}, {"a": 2}]
        expanded = expand_grid_with_risk_scale(base, [0.5, 1.0])
        assert len(expanded) == 4

    def test_risk_scale_added(self):
        """Each expanded dict has risk_scale key."""
        base = [{"regime_len": 200}]
        expanded = expand_grid_with_risk_scale(base, [0.5, 0.8, 1.0])
        assert len(expanded) == 3
        for ep in expanded:
            assert "risk_scale" in ep
            assert "regime_len" in ep

    def test_no_mutation_of_base(self):
        """Expanding doesn't modify the original base grid."""
        base = [{"a": 1}]
        original_a = base[0].copy()
        expand_grid_with_risk_scale(base, [0.5, 1.0])
        assert base[0] == original_a
        assert "risk_scale" not in base[0]

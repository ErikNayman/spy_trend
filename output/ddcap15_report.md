# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -15% (no worse than 15%)
**Date**: 2026-02-13 23:04
**Data**: SPY 1993-01-29 → 2026-02-11 (8316 days)
**Costs**: 1.0 bps commission + 2.0 bps slippage/side
**Walk-forward**: 8yr train, 2yr val, 2yr step, 10 folds
**Holdout**: 2022-01-01 → latest
**risk_scale grid**: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
**Fold-pass rate required**: 80%
**Min avg OOS exposure**: 60.0%

## TL;DR (Recommendation)

- **Recommended strategy**: G_sizing_regime (risk_scale=0.9)
- **Why**:
  - Highest average OOS CAGR (5.45%) among DD-cap passing strategies
  - Stitched walk-forward MaxDD (-14.21%) stays within -15% cap
  - Passed DD constraint in 10 of 10 validation folds (100%)
- **What to watch**:
  - Volatility spikes may reduce position size below target
  - risk_scale=0.9 caps max exposure at 90%, limiting upside capture in strong trends
- **Risk**: MaxDD cap -15%, stitched OOS MaxDD -14.21%, holdout MaxDD -12.52%

> *Not financial advice. Past performance does not guarantee future results.*

## Strategy Descriptions

- **F: Hysteresis Regime Filter** — Go LONG when Close crosses above EMA(regime_len) * (1+upper_pct%), go CASH when below EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). Optional slope filter. Binary (0/1), risk_scale applied post-signal.
- **G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, less in choppy ones. Fractional [0,1], risk_scale applied post-signal.
- **H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. Fractional [0,1], risk_scale applied post-signal.
- **I: Breakout OR Dip** — In regime: enter on N-day high breakout OR dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. Binary (0/1), risk_scale applied post-signal.

## Walk-Forward Optimization (DD-Capped)

### F_hysteresis_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **57** (17.6%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 0.7}`
- Avg OOS CAGR: 4.69%, Stitched MaxDD: -14.02%

### G_sizing_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **160** (49.4%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.9}`
- Avg OOS CAGR: 5.45%, Stitched MaxDD: -14.21%

### H_atr_dip_addon
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **335** (58.2%)
- **Best params**: `{'regime_len': 150, 'dip_ema': 20, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.5, 'addon_weight': 0.5, 'risk_scale': 0.9}`
- Avg OOS CAGR: 3.18%, Stitched MaxDD: -14.71%

### I_breakout_or_dip
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **182** (31.6%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 14, 'atr_mult': 5.0, 'risk_scale': 0.7}`
- Avg OOS CAGR: 4.52%, Stitched MaxDD: -14.50%

## Overall Ranking

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Stitched MaxDD | Avg Exp% | risk_scale |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | G_sizing_regime | 5.45% | 0.54 | -14.21% | 67.3 | 0.9 |
| 2 | F_hysteresis_regime | 4.69% | 0.54 | -14.02% | 66.4 | 0.7 |
| 3 | I_breakout_or_dip | 4.52% | 0.43 | -14.50% | 67.5 | 0.7 |
| 4 | H_atr_dip_addon | 3.18% | 0.32 | -14.71% | 72.8 | 0.9 |

### WINNER: **G_sizing_regime**
- Params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.9}`

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 7.44% | 6.91% | 1.07 | 1.20 | -7.75% | 0.96 | 75.0% | 11.02 | 65.5 | 168.8 | 1.0 | 34.07% |
| G_sizing_regime | 8.08% | 8.74% | 0.93 | 1.04 | -12.52% | 0.65 | 30.0% | 4.81 | 65.5 | 67.5 | 2.4 | 37.40% |
| H_atr_dip_addon | 5.76% | 5.99% | 0.97 | 1.08 | -9.28% | 0.62 | 14.3% | 2.92 | 70.1 | 34.4 | 5.1 | 25.72% |
| I_breakout_or_dip | 6.06% | 6.79% | 0.90 | 0.97 | -7.26% | 0.84 | 23.1% | 3.31 | 61.5 | 48.7 | 3.2 | 27.19% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 5.39% | 8.30% | 0.67 | 0.76 | -18.26% | 0.30 | 48.8% | 4.35 | 75.2 | 152.4 | 1.2 | 464.98% |
| G_sizing_regime | 6.27% | 9.63% | 0.68 | 0.77 | -21.24% | 0.30 | 27.5% | 3.72 | 75.7 | 69.2 | 2.8 | 643.55% |
| H_atr_dip_addon | 4.18% | 6.90% | 0.63 | 0.67 | -18.06% | 0.23 | 23.9% | 2.62 | 77.4 | 39.5 | 4.9 | 286.77% |
| I_breakout_or_dip | 4.94% | 7.97% | 0.65 | 0.71 | -18.86% | 0.26 | 27.8% | 2.77 | 72.5 | 45.3 | 4.0 | 391.07% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Charts

- `ddcap15_equity_full.png`
- `ddcap15_drawdown_full.png`
- `ddcap15_equity_holdout.png`
- `ddcap15_drawdown_holdout.png`

---
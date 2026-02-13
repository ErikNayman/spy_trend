# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -15% (no worse than 15%)
**Date**: 2026-02-13 20:38
**Data**: SPY 1993-01-29 → 2026-02-11 (8316 days)
**Costs**: 1.0 bps commission + 2.0 bps slippage/side
**Walk-forward**: 8yr train, 2yr val, 2yr step, 10 folds
**Holdout**: 2022-01-01 → latest
**risk_scale grid**: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
**Fold-pass rate required**: 80%
**Min avg OOS exposure**: 60.0%

## Strategy Descriptions

- **F: Hysteresis Regime Filter** — Go LONG when Close crosses above EMA(regime_len) * (1+upper_pct%), go CASH when below EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). Optional slope filter. Binary (0/1), risk_scale applied post-signal.
- **G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, less in choppy ones. Fractional [0,1], risk_scale applied post-signal.
- **H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. Fractional [0,1], risk_scale applied post-signal.
- **I: Breakout OR Dip** — In regime: enter on N-day high breakout OR dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. Binary (0/1), risk_scale applied post-signal.

## Walk-Forward Optimization (DD-Capped)

### F_hysteresis_regime
- Base grid: 54 combos
- Expanded grid (× risk_scale): 324 combos

- Evaluated: 324, Passed DD-cap: **57** (17.6%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 0.7}`
- Avg OOS CAGR: 4.69%
- Avg OOS Sharpe: 0.54
- Avg OOS Calmar: 0.64
- Avg OOS MaxDD: -8.03%
- Avg OOS Exposure: 66.4%
- Stitched OOS MaxDD: -14.02%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 10.45% | -5.96% | 1.28 | 1.75 | 88.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.44% | -5.14% | 0.65 | 0.67 | 75.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -4.26% | -12.71% | -0.82 | -0.34 | 24.2 | YES |
| 4 | 2009-01-29→2011-01-29 | 11.32% | -13.76% | 1.06 | 0.82 | 77.4 | YES |
| 5 | 2011-01-29→2013-01-29 | 1.79% | -8.23% | 0.29 | 0.22 | 63.5 | YES |
| 6 | 2013-01-29→2015-01-29 | 9.96% | -5.58% | 1.27 | 1.78 | 94.4 | YES |
| 7 | 2015-01-29→2017-01-29 | -0.19% | -9.22% | 0.00 | -0.02 | 73.6 | YES |
| 8 | 2017-01-29→2019-01-29 | 5.42% | -7.14% | 0.75 | 0.76 | 83.3 | YES |
| 9 | 2019-01-29→2021-01-29 | 8.94% | -12.51% | 0.89 | 0.71 | 83.8 | YES |

### G_sizing_regime
- Base grid: 54 combos
- Expanded grid (× risk_scale): 324 combos

- Evaluated: 324, Passed DD-cap: **160** (49.4%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.9}`
- Avg OOS CAGR: 5.45%
- Avg OOS Sharpe: 0.54
- Avg OOS Calmar: 0.67
- Avg OOS MaxDD: -9.45%
- Avg OOS Exposure: 67.3%
- Stitched OOS MaxDD: -14.21%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 12.83% | -6.60% | 1.27 | 1.94 | 88.5 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.16% | -8.87% | 0.47 | 0.36 | 76.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -3.83% | -13.57% | -0.57 | -0.28 | 25.5 | YES |
| 4 | 2009-01-29→2011-01-29 | 11.01% | -13.65% | 1.00 | 0.81 | 78.4 | YES |
| 5 | 2011-01-29→2013-01-29 | 3.70% | -9.78% | 0.45 | 0.38 | 68.3 | YES |
| 6 | 2013-01-29→2015-01-29 | 14.10% | -5.97% | 1.40 | 2.36 | 95.0 | YES |
| 7 | 2015-01-29→2017-01-29 | -1.90% | -13.06% | -0.19 | -0.15 | 73.6 | YES |
| 8 | 2017-01-29→2019-01-29 | 6.07% | -10.26% | 0.75 | 0.59 | 82.9 | YES |
| 9 | 2019-01-29→2021-01-29 | 9.39% | -12.69% | 0.86 | 0.74 | 83.8 | YES |

### H_atr_dip_addon
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **335** (58.2%)
- **Best params**: `{'regime_len': 150, 'dip_ema': 20, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.5, 'addon_weight': 0.5, 'risk_scale': 0.9}`
- Avg OOS CAGR: 3.18%
- Avg OOS Sharpe: 0.32
- Avg OOS Calmar: 0.55
- Avg OOS MaxDD: -8.20%
- Avg OOS Exposure: 72.8%
- Stitched OOS MaxDD: -14.71%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -3.98% | -7.77% | -1.96 | -0.51 | 11.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 6.82% | -6.12% | 1.06 | 1.12 | 88.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 4.61% | -4.83% | 1.09 | 0.95 | 82.4 | YES |
| 3 | 2007-01-29→2009-01-29 | -3.41% | -10.87% | -0.68 | -0.31 | 37.4 | YES |
| 4 | 2009-01-29→2011-01-29 | 8.23% | -10.28% | 0.88 | 0.80 | 81.7 | YES |
| 5 | 2011-01-29→2013-01-29 | 1.56% | -7.53% | 0.29 | 0.21 | 75.4 | YES |
| 6 | 2013-01-29→2015-01-29 | 9.24% | -4.01% | 1.32 | 2.31 | 97.2 | YES |
| 7 | 2015-01-29→2017-01-29 | 2.20% | -6.17% | 0.44 | 0.36 | 80.7 | YES |
| 8 | 2017-01-29→2019-01-29 | 0.07% | -12.42% | 0.04 | 0.01 | 84.7 | YES |
| 9 | 2019-01-29→2021-01-29 | 6.43% | -12.01% | 0.74 | 0.54 | 88.7 | YES |

### I_breakout_or_dip
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **182** (31.6%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 14, 'atr_mult': 5.0, 'risk_scale': 0.7}`
- Avg OOS CAGR: 4.52%
- Avg OOS Sharpe: 0.43
- Avg OOS Calmar: 0.70
- Avg OOS MaxDD: -8.71%
- Avg OOS Exposure: 67.5%
- Stitched OOS MaxDD: -14.50%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -2.60% | -5.14% | -1.32 | -0.51 | 4.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 10.14% | -6.72% | 1.26 | 1.51 | 85.9 | YES |
| 2 | 2005-01-29→2007-01-29 | 5.09% | -5.27% | 0.91 | 0.96 | 80.0 | YES |
| 3 | 2007-01-29→2009-01-29 | -4.88% | -13.44% | -0.79 | -0.36 | 33.5 | YES |
| 4 | 2009-01-29→2011-01-29 | 14.33% | -8.30% | 1.33 | 1.73 | 71.0 | YES |
| 5 | 2011-01-29→2013-01-29 | 2.99% | -8.58% | 0.44 | 0.35 | 66.7 | YES |
| 6 | 2013-01-29→2015-01-29 | 10.00% | -4.13% | 1.26 | 2.42 | 97.2 | YES |
| 7 | 2015-01-29→2017-01-29 | -0.39% | -11.53% | -0.03 | -0.03 | 72.8 | YES |
| 8 | 2017-01-29→2019-01-29 | 1.65% | -13.28% | 0.27 | 0.12 | 83.7 | YES |
| 9 | 2019-01-29→2021-01-29 | 8.84% | -10.75% | 0.94 | 0.82 | 80.0 | YES |

## Overall Ranking (by avg OOS CAGR among DD-cap passing)

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Avg OOS Calmar | Avg OOS MaxDD | Avg OOS Exp% | Stitched MaxDD | Pass Rate | risk_scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | G_sizing_regime | 5.45% | 0.54 | 0.67 | -9.45% | 67.3 | -14.21% | 100% | 0.9 |
| 2 | F_hysteresis_regime | 4.69% | 0.54 | 0.64 | -8.03% | 66.4 | -14.02% | 100% | 0.7 |
| 3 | I_breakout_or_dip | 4.52% | 0.43 | 0.70 | -8.71% | 67.5 | -14.50% | 100% | 0.7 |
| 4 | H_atr_dip_addon | 3.18% | 0.32 | 0.55 | -8.20% | 72.8 | -14.71% | 100% | 0.9 |

### WINNER: **G_sizing_regime**
- Full params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.9}`
- Strategy params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15}`
- risk_scale: 0.9

## Stitched Walk-Forward OOS Equity (Winner)

- Period: 2001-01-29 → 2021-01-29 (5032 OOS days)
- CAGR: 5.29%
- Volatility: 8.69%
- Sharpe: 0.64
- **MaxDD: -14.21%** (cap: -15%)
- Total Return: 179.84%

## Holdout Test (2022-01-01 → latest)

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 7.44% | 6.91% | 1.07 | 1.20 | -7.75% | 0.96 | 75.0% | 11.02 | 65.5 | 168.8 | 1.0 | 34.07% |
| G_sizing_regime | 8.08% | 8.74% | 0.93 | 1.04 | -12.52% | 0.65 | 30.0% | 4.81 | 65.5 | 67.5 | 2.4 | 37.40% |
| H_atr_dip_addon | 5.76% | 5.99% | 0.97 | 1.08 | -9.28% | 0.62 | 14.3% | 2.92 | 70.1 | 34.4 | 5.1 | 25.72% |
| I_breakout_or_dip | 6.06% | 6.79% | 0.90 | 0.97 | -7.26% | 0.84 | 23.1% | 3.31 | 61.5 | 48.7 | 3.2 | 27.19% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

## Full-Period Backtest (for reference, NOT for selection)

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 5.39% | 8.30% | 0.67 | 0.76 | -18.26% | 0.30 | 48.8% | 4.35 | 75.2 | 152.4 | 1.2 | 464.98% |
| G_sizing_regime | 6.27% | 9.63% | 0.68 | 0.77 | -21.24% | 0.30 | 27.5% | 3.72 | 75.7 | 69.2 | 2.8 | 643.55% |
| H_atr_dip_addon | 4.18% | 6.90% | 0.63 | 0.67 | -18.06% | 0.23 | 23.9% | 2.62 | 77.4 | 39.5 | 4.9 | 286.77% |
| I_breakout_or_dip | 4.94% | 7.97% | 0.65 | 0.71 | -18.86% | 0.26 | 27.8% | 2.77 | 72.5 | 45.3 | 4.0 | 391.07% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Why This Strategy Meets the DD <= 20% Constraint

**Winner**: G_sizing_regime with risk_scale=0.9

1. **Walk-forward OOS**: The stitched OOS equity across 10 validation folds shows MaxDD = -14.21%, which is within the -15% cap. 10 of 10 folds individually satisfy the constraint.

2. **Holdout period** (2022-01-01+): MaxDD = -12.52%. This is within the cap. 
3. **Full period** (1993+): MaxDD = -21.24%. The full period includes the 2008 crisis which is extreme; the OOS-validated constraint still holds across walk-forward folds. 

**Mechanism explanation**:
- Vol-targeting automatically reduces position size when volatility spikes (i.e., during drawdowns), providing natural drawdown dampening.
- The risk_scale=0.9 further caps effective exposure, reducing all weights by 10%.

## Charts

- `ddcap15_equity_full.png` — equity curves, full period
- `ddcap15_drawdown_full.png` — drawdowns, full period (with -15% line)
- `ddcap15_equity_holdout.png` — equity curves, holdout
- `ddcap15_drawdown_holdout.png` — drawdowns, holdout
- `ddcap15_equity_wf_oos_stitched.png` — stitched WF OOS equity + DD
- `ddcap15_drawdown_wf_oos_stitched.png` — stitched WF OOS drawdown

---
*Generated in 163.2s*
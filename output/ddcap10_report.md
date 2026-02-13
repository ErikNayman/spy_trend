# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -10% (no worse than 10%)
**Date**: 2026-02-13 20:48
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

- Evaluated: 324, Passed DD-cap: **0** (0.0%)
- **No parameter set passed all constraints.**

### G_sizing_regime
- Base grid: 54 combos
- Expanded grid (× risk_scale): 324 combos

- Evaluated: 324, Passed DD-cap: **30** (9.3%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.6}`
- Avg OOS CAGR: 3.66%
- Avg OOS Sharpe: 0.54
- Avg OOS Calmar: 0.67
- Avg OOS MaxDD: -6.38%
- Avg OOS Exposure: 67.3%
- Stitched OOS MaxDD: -9.65%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 8.50% | -4.40% | 1.27 | 1.93 | 88.5 | YES |
| 2 | 2005-01-29→2007-01-29 | 2.16% | -5.98% | 0.47 | 0.36 | 76.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -2.52% | -9.21% | -0.57 | -0.27 | 25.5 | YES |
| 4 | 2009-01-29→2011-01-29 | 7.36% | -9.27% | 1.00 | 0.79 | 78.4 | YES |
| 5 | 2011-01-29→2013-01-29 | 2.54% | -6.60% | 0.45 | 0.38 | 68.3 | YES |
| 6 | 2013-01-29→2015-01-29 | 9.31% | -4.01% | 1.40 | 2.32 | 95.0 | YES |
| 7 | 2015-01-29→2017-01-29 | -1.19% | -8.82% | -0.19 | -0.14 | 73.6 | YES |
| 8 | 2017-01-29→2019-01-29 | 4.09% | -6.91% | 0.75 | 0.59 | 82.9 | YES |
| 9 | 2019-01-29→2021-01-29 | 6.31% | -8.60% | 0.86 | 0.73 | 83.8 | YES |

### H_atr_dip_addon
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **80** (13.9%)
- **Best params**: `{'regime_len': 150, 'dip_ema': 20, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.5, 'addon_weight': 0.5, 'risk_scale': 0.6}`
- Avg OOS CAGR: 2.13%
- Avg OOS Sharpe: 0.32
- Avg OOS Calmar: 0.54
- Avg OOS MaxDD: -5.53%
- Avg OOS Exposure: 72.8%
- Stitched OOS MaxDD: -9.95%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -2.67% | -5.24% | -1.96 | -0.51 | 11.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 4.55% | -4.10% | 1.06 | 1.11 | 88.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.07% | -3.24% | 1.09 | 0.95 | 82.4 | YES |
| 3 | 2007-01-29→2009-01-29 | -2.26% | -7.35% | -0.68 | -0.31 | 37.4 | YES |
| 4 | 2009-01-29→2011-01-29 | 5.52% | -6.92% | 0.88 | 0.80 | 81.7 | YES |
| 5 | 2011-01-29→2013-01-29 | 1.08% | -5.08% | 0.29 | 0.21 | 75.4 | YES |
| 6 | 2013-01-29→2015-01-29 | 6.13% | -2.68% | 1.32 | 2.29 | 97.2 | YES |
| 7 | 2015-01-29→2017-01-29 | 1.49% | -4.12% | 0.44 | 0.36 | 80.7 | YES |
| 8 | 2017-01-29→2019-01-29 | 0.09% | -8.39% | 0.04 | 0.01 | 84.7 | YES |
| 9 | 2019-01-29→2021-01-29 | 4.34% | -8.14% | 0.74 | 0.53 | 88.7 | YES |

### I_breakout_or_dip
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **6** (1.0%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 14, 'atr_mult': 3.0, 'risk_scale': 0.5}`
- Avg OOS CAGR: 3.06%
- Avg OOS Sharpe: 0.43
- Avg OOS Calmar: 0.64
- Avg OOS MaxDD: -5.93%
- Avg OOS Exposure: 66.7%
- Stitched OOS MaxDD: -9.75%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -1.86% | -3.69% | -1.32 | -0.50 | 4.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 6.60% | -5.13% | 1.16 | 1.29 | 84.9 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.21% | -3.79% | 0.81 | 0.85 | 79.4 | YES |
| 3 | 2007-01-29→2009-01-29 | -3.33% | -8.97% | -0.77 | -0.37 | 33.1 | YES |
| 4 | 2009-01-29→2011-01-29 | 7.79% | -8.02% | 1.07 | 0.97 | 70.0 | YES |
| 5 | 2011-01-29→2013-01-29 | 2.10% | -6.26% | 0.43 | 0.34 | 66.1 | YES |
| 6 | 2013-01-29→2015-01-29 | 7.13% | -3.00% | 1.28 | 2.38 | 95.4 | YES |
| 7 | 2015-01-29→2017-01-29 | -0.41% | -8.35% | -0.06 | -0.05 | 72.0 | YES |
| 8 | 2017-01-29→2019-01-29 | 3.53% | -5.69% | 0.78 | 0.62 | 82.9 | YES |
| 9 | 2019-01-29→2021-01-29 | 5.82% | -6.39% | 0.89 | 0.91 | 79.0 | YES |

## Overall Ranking (by avg OOS CAGR among DD-cap passing)

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Avg OOS Calmar | Avg OOS MaxDD | Avg OOS Exp% | Stitched MaxDD | Pass Rate | risk_scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | G_sizing_regime | 3.66% | 0.54 | 0.67 | -6.38% | 67.3 | -9.65% | 100% | 0.6 |
| 2 | I_breakout_or_dip | 3.06% | 0.43 | 0.64 | -5.93% | 66.7 | -9.75% | 100% | 0.5 |
| 3 | H_atr_dip_addon | 2.13% | 0.32 | 0.54 | -5.53% | 72.8 | -9.95% | 100% | 0.6 |

**Failed to meet DD-cap**: F_hysteresis_regime

### WINNER: **G_sizing_regime**
- Full params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.6}`
- Strategy params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15}`
- risk_scale: 0.6

## Stitched Walk-Forward OOS Equity (Winner)

- Period: 2001-01-29 → 2021-01-29 (5032 OOS days)
- CAGR: 3.58%
- Volatility: 5.79%
- Sharpe: 0.64
- **MaxDD: -9.65%** (cap: -10%)
- Total Return: 101.95%

## Holdout Test (2022-01-01 → latest)

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G_sizing_regime | 5.41% | 5.83% | 0.93 | 1.04 | -8.51% | 0.64 | 30.0% | 4.81 | 65.5 | 67.5 | 2.4 | 24.03% |
| H_atr_dip_addon | 3.85% | 3.99% | 0.97 | 1.08 | -6.27% | 0.61 | 14.3% | 2.92 | 70.1 | 34.4 | 5.1 | 16.68% |
| I_breakout_or_dip | 4.29% | 4.83% | 0.89 | 0.95 | -5.25% | 0.82 | 36.8% | 2.79 | 60.9 | 33.0 | 4.6 | 18.73% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

## Full-Period Backtest (for reference, NOT for selection)

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G_sizing_regime | 4.24% | 6.42% | 0.68 | 0.77 | -14.65% | 0.29 | 27.5% | 3.72 | 75.7 | 69.2 | 2.8 | 294.21% |
| H_atr_dip_addon | 2.83% | 4.60% | 0.63 | 0.67 | -12.34% | 0.23 | 23.9% | 2.62 | 77.4 | 39.5 | 4.9 | 150.75% |
| I_breakout_or_dip | 3.33% | 5.60% | 0.61 | 0.67 | -14.33% | 0.23 | 37.7% | 2.10 | 71.6 | 29.9 | 6.0 | 194.44% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Why This Strategy Meets the DD <= 20% Constraint

**Winner**: G_sizing_regime with risk_scale=0.6

1. **Walk-forward OOS**: The stitched OOS equity across 10 validation folds shows MaxDD = -9.65%, which is within the -10% cap. 10 of 10 folds individually satisfy the constraint.

2. **Holdout period** (2022-01-01+): MaxDD = -8.51%. This is within the cap. 
3. **Full period** (1993+): MaxDD = -14.65%. The full period includes the 2008 crisis which is extreme; the OOS-validated constraint still holds across walk-forward folds. 

**Mechanism explanation**:
- Vol-targeting automatically reduces position size when volatility spikes (i.e., during drawdowns), providing natural drawdown dampening.
- The risk_scale=0.6 further caps effective exposure, reducing all weights by 40%.

## Charts

- `ddcap10_equity_full.png` — equity curves, full period
- `ddcap10_drawdown_full.png` — drawdowns, full period (with -10% line)
- `ddcap10_equity_holdout.png` — equity curves, holdout
- `ddcap10_drawdown_holdout.png` — drawdowns, holdout
- `ddcap10_equity_wf_oos_stitched.png` — stitched WF OOS equity + DD
- `ddcap10_drawdown_wf_oos_stitched.png` — stitched WF OOS drawdown

---
*Generated in 160.9s*
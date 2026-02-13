# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -25% (no worse than 25%)
**Date**: 2026-02-13 20:53
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

- Evaluated: 324, Passed DD-cap: **255** (78.7%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 3.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Avg OOS CAGR: 7.21%
- Avg OOS Sharpe: 0.59
- Avg OOS Calmar: 0.77
- Avg OOS MaxDD: -12.31%
- Avg OOS Exposure: 70.6%
- Stitched OOS MaxDD: -24.73%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 17.51% | -7.53% | 1.45 | 2.33 | 91.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 7.26% | -8.35% | 0.80 | 0.87 | 89.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -7.76% | -20.61% | -0.87 | -0.38 | 29.3 | YES |
| 4 | 2009-01-29→2011-01-29 | 12.08% | -24.73% | 0.79 | 0.49 | 81.0 | YES |
| 5 | 2011-01-29→2013-01-29 | 7.49% | -9.69% | 0.69 | 0.77 | 75.2 | YES |
| 6 | 2013-01-29→2015-01-29 | 16.67% | -7.27% | 1.44 | 2.29 | 95.2 | YES |
| 7 | 2015-01-29→2017-01-29 | 0.29% | -14.83% | 0.08 | 0.02 | 76.5 | YES |
| 8 | 2017-01-29→2019-01-29 | 7.65% | -10.10% | 0.75 | 0.76 | 83.3 | YES |
| 9 | 2019-01-29→2021-01-29 | 10.95% | -19.98% | 0.72 | 0.55 | 84.8 | YES |

### G_sizing_regime
- Base grid: 54 combos
- Expanded grid (× risk_scale): 324 combos

- Evaluated: 324, Passed DD-cap: **313** (96.6%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.2, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.64%
- Avg OOS Sharpe: 0.56
- Avg OOS Calmar: 0.71
- Avg OOS MaxDD: -11.15%
- Avg OOS Exposure: 67.3%
- Stitched OOS MaxDD: -17.89%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 15.49% | -7.23% | 1.33 | 2.14 | 88.5 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.43% | -9.90% | 0.46 | 0.35 | 76.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -4.92% | -16.15% | -0.63 | -0.30 | 25.5 | YES |
| 4 | 2009-01-29→2011-01-29 | 14.50% | -17.89% | 1.03 | 0.81 | 78.4 | YES |
| 5 | 2011-01-29→2013-01-29 | 4.70% | -10.89% | 0.50 | 0.43 | 68.3 | YES |
| 6 | 2013-01-29→2015-01-29 | 16.65% | -6.73% | 1.45 | 2.47 | 95.0 | YES |
| 7 | 2015-01-29→2017-01-29 | -1.76% | -14.92% | -0.14 | -0.12 | 73.6 | YES |
| 8 | 2017-01-29→2019-01-29 | 6.81% | -11.14% | 0.71 | 0.61 | 82.9 | YES |
| 9 | 2019-01-29→2021-01-29 | 11.47% | -16.62% | 0.85 | 0.69 | 83.8 | YES |

### H_atr_dip_addon
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **576** (100.0%)
- **Best params**: `{'regime_len': 200, 'dip_ema': 50, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.7, 'addon_weight': 0.3, 'risk_scale': 1.0}`
- Avg OOS CAGR: 4.57%
- Avg OOS Sharpe: 0.41
- Avg OOS Calmar: 0.57
- Avg OOS MaxDD: -10.84%
- Avg OOS Exposure: 73.7%
- Stitched OOS MaxDD: -21.71%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -1.77% | -3.53% | -0.78 | -0.50 | 4.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 11.27% | -5.71% | 1.24 | 1.98 | 91.3 | YES |
| 2 | 2005-01-29→2007-01-29 | 4.00% | -7.03% | 0.66 | 0.57 | 85.0 | YES |
| 3 | 2007-01-29→2009-01-29 | -7.10% | -17.27% | -1.04 | -0.41 | 37.8 | YES |
| 4 | 2009-01-29→2011-01-29 | 7.02% | -20.04% | 0.59 | 0.35 | 84.7 | YES |
| 5 | 2011-01-29→2013-01-29 | -0.32% | -13.03% | 0.01 | -0.02 | 77.2 | YES |
| 6 | 2013-01-29→2015-01-29 | 13.04% | -5.81% | 1.42 | 2.25 | 97.6 | YES |
| 7 | 2015-01-29→2017-01-29 | 1.58% | -9.08% | 0.25 | 0.17 | 80.7 | YES |
| 8 | 2017-01-29→2019-01-29 | 5.18% | -9.79% | 0.62 | 0.53 | 88.2 | YES |
| 9 | 2019-01-29→2021-01-29 | 12.79% | -17.09% | 1.11 | 0.75 | 89.7 | YES |

### I_breakout_or_dip
- Base grid: 96 combos
- Expanded grid (× risk_scale): 576 combos

- Evaluated: 576, Passed DD-cap: **562** (97.6%)
- **Best params**: `{'regime_len': 200, 'breakout_len': 20, 'dip_ema': 50, 'dip_pct': 3.0, 'atr_len': 14, 'atr_mult': 5.0, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.87%
- Avg OOS Sharpe: 0.51
- Avg OOS Calmar: 0.62
- Avg OOS MaxDD: -12.75%
- Avg OOS Exposure: 73.0%
- Stitched OOS MaxDD: -24.42%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -1.17% | -2.37% | -0.44 | -0.49 | 3.2 | YES |
| 1 | 2003-01-29→2005-01-29 | 15.30% | -8.48% | 1.25 | 1.80 | 91.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 5.40% | -9.80% | 0.66 | 0.55 | 85.0 | YES |
| 3 | 2007-01-29→2009-01-29 | -9.11% | -22.17% | -0.96 | -0.41 | 37.8 | YES |
| 4 | 2009-01-29→2011-01-29 | 14.14% | -24.42% | 0.90 | 0.58 | 82.3 | YES |
| 5 | 2011-01-29→2013-01-29 | 5.38% | -10.60% | 0.54 | 0.51 | 75.2 | YES |
| 6 | 2013-01-29→2015-01-29 | 14.54% | -6.73% | 1.26 | 2.16 | 97.6 | YES |
| 7 | 2015-01-29→2017-01-29 | 1.32% | -12.98% | 0.18 | 0.10 | 80.7 | YES |
| 8 | 2017-01-29→2019-01-29 | 6.06% | -12.37% | 0.60 | 0.49 | 88.0 | YES |
| 9 | 2019-01-29→2021-01-29 | 16.81% | -17.55% | 1.12 | 0.96 | 88.7 | YES |

## Overall Ranking (by avg OOS CAGR among DD-cap passing)

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Avg OOS Calmar | Avg OOS MaxDD | Avg OOS Exp% | Stitched MaxDD | Pass Rate | risk_scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | F_hysteresis_regime | 7.21% | 0.59 | 0.77 | -12.31% | 70.6 | -24.73% | 100% | 1.0 |
| 2 | I_breakout_or_dip | 6.87% | 0.51 | 0.62 | -12.75% | 73.0 | -24.42% | 100% | 1.0 |
| 3 | G_sizing_regime | 6.64% | 0.56 | 0.71 | -11.15% | 67.3 | -17.89% | 100% | 1.0 |
| 4 | H_atr_dip_addon | 4.57% | 0.41 | 0.57 | -10.84% | 73.7 | -21.71% | 100% | 1.0 |

### WINNER: **F_hysteresis_regime**
- Full params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 3.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Strategy params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 3.0, 'slope_window': 20}`
- risk_scale: 1.0

## Stitched Walk-Forward OOS Equity (Winner)

- Period: 2001-01-29 → 2021-01-29 (5032 OOS days)
- CAGR: 6.95%
- Volatility: 11.39%
- Sharpe: 0.65
- **MaxDD: -24.73%** (cap: -25%)
- Total Return: 282.29%

## Holdout Test (2022-01-01 → latest)

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.49% | 10.56% | 0.82 | 0.89 | -14.46% | 0.59 | 75.0% | 6.46 | 68.2 | 175.5 | 1.0 | 39.52% |
| G_sizing_regime | 9.12% | 9.94% | 0.93 | 1.03 | -14.95% | 0.61 | 30.0% | 4.40 | 65.5 | 67.5 | 2.4 | 42.84% |
| H_atr_dip_addon | 7.02% | 7.79% | 0.91 | 1.01 | -12.30% | 0.57 | 18.8% | 3.52 | 69.0 | 44.4 | 3.9 | 31.97% |
| I_breakout_or_dip | 10.59% | 10.34% | 1.03 | 1.18 | -14.14% | 0.75 | 20.0% | 3.75 | 68.3 | 46.9 | 3.7 | 50.87% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

## Full-Period Backtest (for reference, NOT for selection)

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.75% | 12.50% | 0.73 | 0.83 | -26.22% | 0.33 | 57.1% | 5.62 | 78.8 | 311.9 | 0.6 | 1493.58% |
| G_sizing_regime | 7.51% | 11.54% | 0.69 | 0.78 | -25.48% | 0.29 | 28.6% | 3.59 | 75.7 | 69.2 | 2.8 | 991.47% |
| H_atr_dip_addon | 5.98% | 9.36% | 0.67 | 0.75 | -20.68% | 0.29 | 27.4% | 2.99 | 79.0 | 53.0 | 3.8 | 578.98% |
| I_breakout_or_dip | 7.65% | 12.13% | 0.67 | 0.76 | -25.88% | 0.30 | 24.2% | 2.94 | 77.9 | 52.2 | 3.8 | 1038.20% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Why This Strategy Meets the DD <= 20% Constraint

**Winner**: F_hysteresis_regime with risk_scale=1.0

1. **Walk-forward OOS**: The stitched OOS equity across 10 validation folds shows MaxDD = -24.73%, which is within the -25% cap. 10 of 10 folds individually satisfy the constraint.

2. **Holdout period** (2022-01-01+): MaxDD = -14.46%. This is within the cap. 
3. **Full period** (1993+): MaxDD = -26.22%. The full period includes the 2008 crisis which is extreme; the OOS-validated constraint still holds across walk-forward folds. 

**Mechanism explanation**:
- The hysteresis bands create a dead zone around the regime EMA, preventing rapid entry/exit whipsaws. The lower exit band (-lower_pct%) ensures the strategy exits early in sustained declines.

## Charts

- `ddcap25_equity_full.png` — equity curves, full period
- `ddcap25_drawdown_full.png` — drawdowns, full period (with -25% line)
- `ddcap25_equity_holdout.png` — equity curves, holdout
- `ddcap25_drawdown_holdout.png` — drawdowns, holdout
- `ddcap25_equity_wf_oos_stitched.png` — stitched WF OOS equity + DD
- `ddcap25_drawdown_wf_oos_stitched.png` — stitched WF OOS drawdown

---
*Generated in 160.7s*
# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -20% (no worse than 20%)
**Date**: 2026-02-12 21:07
**Data**: SPY 1993-01-29 → 2026-02-11 (8316 days)
**Costs**: 1.0 bps commission + 2.0 bps slippage/side
**Walk-forward**: 8yr train, 2yr val, 2yr step, 10 folds
**Holdout**: 2022-01-01 → latest
**risk_scale grid**: [0.7, 0.8, 0.9, 1.0]
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
- Expanded grid (× risk_scale): 216 combos

- Evaluated: 216, Passed DD-cap: **61** (28.2%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.65%
- Avg OOS Sharpe: 0.54
- Avg OOS Calmar: 0.64
- Avg OOS MaxDD: -11.29%
- Avg OOS Exposure: 66.4%
- Stitched OOS MaxDD: -19.53%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | 0.00% | 0.00% | 0.00 | 0.00 | 0.0 | YES |
| 1 | 2003-01-29→2005-01-29 | 15.03% | -8.53% | 1.28 | 1.76 | 88.1 | YES |
| 2 | 2005-01-29→2007-01-29 | 4.85% | -7.29% | 0.65 | 0.67 | 75.6 | YES |
| 3 | 2007-01-29→2009-01-29 | -6.11% | -17.75% | -0.82 | -0.34 | 24.2 | YES |
| 4 | 2009-01-29→2011-01-29 | 16.15% | -19.18% | 1.06 | 0.84 | 77.4 | YES |
| 5 | 2011-01-29→2013-01-29 | 2.42% | -11.60% | 0.29 | 0.21 | 63.5 | YES |
| 6 | 2013-01-29→2015-01-29 | 14.32% | -7.91% | 1.27 | 1.81 | 94.4 | YES |
| 7 | 2015-01-29→2017-01-29 | -0.41% | -13.02% | 0.00 | -0.03 | 73.6 | YES |
| 8 | 2017-01-29→2019-01-29 | 7.65% | -10.10% | 0.75 | 0.76 | 83.3 | YES |
| 9 | 2019-01-29→2021-01-29 | 12.64% | -17.52% | 0.89 | 0.72 | 83.8 | YES |

### G_sizing_regime
- Base grid: 54 combos
- Expanded grid (× risk_scale): 216 combos

- Evaluated: 216, Passed DD-cap: **156** (72.2%)
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
- Expanded grid (× risk_scale): 384 combos

- Evaluated: 384, Passed DD-cap: **332** (86.5%)
- **Best params**: `{'regime_len': 200, 'dip_ema': 50, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.7, 'addon_weight': 0.3, 'risk_scale': 0.9}`
- Avg OOS CAGR: 4.12%
- Avg OOS Sharpe: 0.41
- Avg OOS Calmar: 0.56
- Avg OOS MaxDD: -9.81%
- Avg OOS Exposure: 73.7%
- Stitched OOS MaxDD: -19.74%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -1.60% | -3.18% | -0.78 | -0.50 | 4.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 10.13% | -5.14% | 1.24 | 1.97 | 91.3 | YES |
| 2 | 2005-01-29→2007-01-29 | 3.61% | -6.35% | 0.66 | 0.57 | 85.0 | YES |
| 3 | 2007-01-29→2009-01-29 | -6.40% | -15.66% | -1.04 | -0.41 | 37.8 | YES |
| 4 | 2009-01-29→2011-01-29 | 6.38% | -18.20% | 0.59 | 0.35 | 84.7 | YES |
| 5 | 2011-01-29→2013-01-29 | -0.26% | -11.77% | 0.01 | -0.02 | 77.2 | YES |
| 6 | 2013-01-29→2015-01-29 | 11.70% | -5.23% | 1.42 | 2.24 | 97.6 | YES |
| 7 | 2015-01-29→2017-01-29 | 1.44% | -8.20% | 0.25 | 0.18 | 80.7 | YES |
| 8 | 2017-01-29→2019-01-29 | 4.68% | -8.84% | 0.62 | 0.53 | 88.2 | YES |
| 9 | 2019-01-29→2021-01-29 | 11.51% | -15.50% | 1.11 | 0.74 | 89.7 | YES |

### I_breakout_or_dip
- Base grid: 96 combos
- Expanded grid (× risk_scale): 384 combos

- Evaluated: 384, Passed DD-cap: **212** (55.2%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 20, 'atr_mult': 3.0, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.32%
- Avg OOS Sharpe: 0.44
- Avg OOS Calmar: 0.70
- Avg OOS MaxDD: -11.18%
- Avg OOS Exposure: 66.6%
- Stitched OOS MaxDD: -19.37%

| Fold | Val Period | OOS CAGR | OOS MaxDD | OOS Sharpe | OOS Calmar | OOS Exp% | DD Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2001-01-29→2003-01-29 | -3.71% | -7.29% | -1.32 | -0.51 | 4.4 | YES |
| 1 | 2003-01-29→2005-01-29 | 13.81% | -9.33% | 1.21 | 1.48 | 84.9 | YES |
| 2 | 2005-01-29→2007-01-29 | 6.35% | -7.47% | 0.81 | 0.85 | 79.4 | YES |
| 3 | 2007-01-29→2009-01-29 | -7.01% | -17.90% | -0.80 | -0.39 | 32.9 | YES |
| 4 | 2009-01-29→2011-01-29 | 18.98% | -10.46% | 1.25 | 1.81 | 70.0 | YES |
| 5 | 2011-01-29→2013-01-29 | 3.28% | -13.35% | 0.37 | 0.25 | 66.1 | YES |
| 6 | 2013-01-29→2015-01-29 | 12.42% | -6.48% | 1.12 | 1.92 | 95.2 | YES |
| 7 | 2015-01-29→2017-01-29 | -0.76% | -15.83% | -0.04 | -0.05 | 71.8 | YES |
| 8 | 2017-01-29→2019-01-29 | 7.23% | -11.19% | 0.81 | 0.65 | 82.7 | YES |
| 9 | 2019-01-29→2021-01-29 | 12.57% | -12.47% | 0.97 | 1.01 | 78.6 | YES |

## Overall Ranking (by avg OOS CAGR among DD-cap passing)

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Avg OOS Calmar | Avg OOS MaxDD | Avg OOS Exp% | Stitched MaxDD | Pass Rate | risk_scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | F_hysteresis_regime | 6.65% | 0.54 | 0.64 | -11.29% | 66.4 | -19.53% | 100% | 1.0 |
| 2 | G_sizing_regime | 6.64% | 0.56 | 0.71 | -11.15% | 67.3 | -17.89% | 100% | 1.0 |
| 3 | I_breakout_or_dip | 6.32% | 0.44 | 0.70 | -11.18% | 66.6 | -19.37% | 100% | 1.0 |
| 4 | H_atr_dip_addon | 4.12% | 0.41 | 0.56 | -9.81% | 73.7 | -19.74% | 100% | 0.9 |

### WINNER: **F_hysteresis_regime**
- Full params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Strategy params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20}`
- risk_scale: 1.0

## Stitched Walk-Forward OOS Equity (Winner)

- Period: 2001-01-29 → 2021-01-29 (5032 OOS days)
- CAGR: 6.40%
- Volatility: 10.54%
- Sharpe: 0.64
- **MaxDD: -19.53%** (cap: -20%)
- Total Return: 245.37%

## Holdout Test (2022-01-01 → latest)

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 10.63% | 9.87% | 1.07 | 1.20 | -10.92% | 0.97 | 75.0% | 11.02 | 65.5 | 168.8 | 1.0 | 51.10% |
| G_sizing_regime | 9.12% | 9.94% | 0.93 | 1.03 | -14.95% | 0.61 | 30.0% | 4.40 | 65.5 | 67.5 | 2.4 | 42.84% |
| H_atr_dip_addon | 6.33% | 7.01% | 0.91 | 1.01 | -11.13% | 0.57 | 18.8% | 3.52 | 69.0 | 44.4 | 3.9 | 28.50% |
| I_breakout_or_dip | 7.72% | 9.62% | 0.82 | 0.87 | -10.25% | 0.75 | 33.3% | 2.35 | 60.7 | 29.8 | 5.1 | 35.53% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

## Full-Period Backtest (for reference, NOT for selection)

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 7.56% | 11.86% | 0.67 | 0.76 | -25.15% | 0.30 | 48.8% | 4.35 | 75.2 | 152.4 | 1.2 | 1006.45% |
| G_sizing_regime | 7.51% | 11.54% | 0.69 | 0.78 | -25.48% | 0.29 | 28.6% | 3.59 | 75.7 | 69.2 | 2.8 | 991.47% |
| H_atr_dip_addon | 5.41% | 8.42% | 0.67 | 0.75 | -18.78% | 0.29 | 27.4% | 2.99 | 79.0 | 53.0 | 3.8 | 467.99% |
| I_breakout_or_dip | 6.50% | 11.21% | 0.62 | 0.68 | -23.87% | 0.27 | 37.9% | 2.06 | 71.5 | 28.9 | 6.2 | 697.62% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Why This Strategy Meets the DD <= 20% Constraint

**Winner**: F_hysteresis_regime with risk_scale=1.0

1. **Walk-forward OOS**: The stitched OOS equity across 10 validation folds shows MaxDD = -19.53%, which is within the -20% cap. 10 of 10 folds individually satisfy the constraint.

2. **Holdout period** (2022-01-01+): MaxDD = -10.92%. This is within the cap. 
3. **Full period** (1993+): MaxDD = -25.15%. The full period includes the 2008 crisis which is extreme; the OOS-validated constraint still holds across walk-forward folds. 

**Mechanism explanation**:
- The hysteresis bands create a dead zone around the regime EMA, preventing rapid entry/exit whipsaws. The lower exit band (-lower_pct%) ensures the strategy exits early in sustained declines.

## Charts

- `ddcap20_equity_full.png` — equity curves, full period
- `ddcap20_drawdown_full.png` — drawdowns, full period (with -20% line)
- `ddcap20_equity_holdout.png` — equity curves, holdout
- `ddcap20_drawdown_holdout.png` — drawdowns, holdout
- `ddcap20_equity_wf_oos_stitched.png` — stitched WF OOS equity + DD
- `ddcap20_drawdown_wf_oos_stitched.png` — stitched WF OOS drawdown

---
*Generated in 107.5s*
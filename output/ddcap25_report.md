# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -25% (no worse than 25%)
**Date**: 2026-02-13 22:44
**Data**: SPY 1993-01-29 → 2026-02-11 (8316 days)
**Costs**: 1.0 bps commission + 2.0 bps slippage/side
**Walk-forward**: 8yr train, 2yr val, 2yr step, 10 folds
**Holdout**: 2022-01-01 → latest
**risk_scale grid**: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
**Fold-pass rate required**: 80%
**Min avg OOS exposure**: 60.0%

## TL;DR (Recommendation)

- **Recommended strategy**: F_hysteresis_regime (risk_scale=1.0)
- **Why**:
  - Highest average OOS CAGR (7.21%) among DD-cap passing strategies
  - Stitched walk-forward MaxDD (-24.73%) stays within -25% cap
  - Passed DD constraint in 10 of 10 validation folds (100%)
- **What to watch**:
  - Regime EMA breakdown: strategy goes to cash (no protection if EMA whipsaws)
- **Risk**: MaxDD cap -25%, stitched OOS MaxDD -24.73%, holdout MaxDD -14.46%

> *Not financial advice. Past performance does not guarantee future results.*

## Strategy Descriptions

- **F: Hysteresis Regime Filter** — Go LONG when Close crosses above EMA(regime_len) * (1+upper_pct%), go CASH when below EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). Optional slope filter. Binary (0/1), risk_scale applied post-signal.
- **G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, less in choppy ones. Fractional [0,1], risk_scale applied post-signal.
- **H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. Fractional [0,1], risk_scale applied post-signal.
- **I: Breakout OR Dip** — In regime: enter on N-day high breakout OR dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. Binary (0/1), risk_scale applied post-signal.

## Walk-Forward Optimization (DD-Capped)

### F_hysteresis_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **255** (78.7%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 3.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Avg OOS CAGR: 7.21%, Stitched MaxDD: -24.73%

### G_sizing_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **313** (96.6%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.2, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.64%, Stitched MaxDD: -17.89%

### H_atr_dip_addon
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **576** (100.0%)
- **Best params**: `{'regime_len': 200, 'dip_ema': 50, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.7, 'addon_weight': 0.3, 'risk_scale': 1.0}`
- Avg OOS CAGR: 4.57%, Stitched MaxDD: -21.71%

### I_breakout_or_dip
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **562** (97.6%)
- **Best params**: `{'regime_len': 200, 'breakout_len': 20, 'dip_ema': 50, 'dip_pct': 3.0, 'atr_len': 14, 'atr_mult': 5.0, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.87%, Stitched MaxDD: -24.42%

## Overall Ranking

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Stitched MaxDD | Avg Exp% | risk_scale |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | F_hysteresis_regime | 7.21% | 0.59 | -24.73% | 70.6 | 1.0 |
| 2 | I_breakout_or_dip | 6.87% | 0.51 | -24.42% | 73.0 | 1.0 |
| 3 | G_sizing_regime | 6.64% | 0.56 | -17.89% | 67.3 | 1.0 |
| 4 | H_atr_dip_addon | 4.57% | 0.41 | -21.71% | 73.7 | 1.0 |

### WINNER: **F_hysteresis_regime**
- Params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 3.0, 'slope_window': 20, 'risk_scale': 1.0}`

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.49% | 10.56% | 0.82 | 0.89 | -14.46% | 0.59 | 75.0% | 6.46 | 68.2 | 175.5 | 1.0 | 39.52% |
| G_sizing_regime | 9.12% | 9.94% | 0.93 | 1.03 | -14.95% | 0.61 | 30.0% | 4.40 | 65.5 | 67.5 | 2.4 | 42.84% |
| H_atr_dip_addon | 7.02% | 7.79% | 0.91 | 1.01 | -12.30% | 0.57 | 18.8% | 3.52 | 69.0 | 44.4 | 3.9 | 31.97% |
| I_breakout_or_dip | 10.59% | 10.34% | 1.03 | 1.18 | -14.14% | 0.75 | 20.0% | 3.75 | 68.3 | 46.9 | 3.7 | 50.87% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.75% | 12.50% | 0.73 | 0.83 | -26.22% | 0.33 | 57.1% | 5.62 | 78.8 | 311.9 | 0.6 | 1493.58% |
| G_sizing_regime | 7.51% | 11.54% | 0.69 | 0.78 | -25.48% | 0.29 | 28.6% | 3.59 | 75.7 | 69.2 | 2.8 | 991.47% |
| H_atr_dip_addon | 5.98% | 9.36% | 0.67 | 0.75 | -20.68% | 0.29 | 27.4% | 2.99 | 79.0 | 53.0 | 3.8 | 578.98% |
| I_breakout_or_dip | 7.65% | 12.13% | 0.67 | 0.76 | -25.88% | 0.30 | 24.2% | 2.94 | 77.9 | 52.2 | 3.8 | 1038.20% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Charts

- `ddcap25_equity_full.png`
- `ddcap25_drawdown_full.png`
- `ddcap25_equity_holdout.png`
- `ddcap25_drawdown_holdout.png`

---
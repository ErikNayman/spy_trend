# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -20% (no worse than 20%)
**Date**: 2026-02-13 23:01
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
  - Highest average OOS CAGR (6.65%) among DD-cap passing strategies
  - Stitched walk-forward MaxDD (-19.53%) stays within -20% cap
  - Passed DD constraint in 10 of 10 validation folds (100%)
- **What to watch**:
  - Regime EMA breakdown: strategy goes to cash (no protection if EMA whipsaws)
- **Risk**: MaxDD cap -20%, stitched OOS MaxDD -19.53%, holdout MaxDD -10.92%

> *Not financial advice. Past performance does not guarantee future results.*

## Strategy Descriptions

- **F: Hysteresis Regime Filter** — Go LONG when Close crosses above EMA(regime_len) * (1+upper_pct%), go CASH when below EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). Optional slope filter. Binary (0/1), risk_scale applied post-signal.
- **G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, less in choppy ones. Fractional [0,1], risk_scale applied post-signal.
- **H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. Fractional [0,1], risk_scale applied post-signal.
- **I: Breakout OR Dip** — In regime: enter on N-day high breakout OR dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. Binary (0/1), risk_scale applied post-signal.

## Walk-Forward Optimization (DD-Capped)

### F_hysteresis_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **160** (49.4%)
- **Best params**: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.65%, Stitched MaxDD: -19.53%

### G_sizing_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **264** (81.5%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.2, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.64%, Stitched MaxDD: -17.89%

### H_atr_dip_addon
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **524** (91.0%)
- **Best params**: `{'regime_len': 200, 'dip_ema': 50, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.7, 'addon_weight': 0.3, 'risk_scale': 0.9}`
- Avg OOS CAGR: 4.12%, Stitched MaxDD: -19.74%

### I_breakout_or_dip
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **404** (70.1%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 20, 'atr_mult': 3.0, 'risk_scale': 1.0}`
- Avg OOS CAGR: 6.32%, Stitched MaxDD: -19.37%

## Overall Ranking

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Stitched MaxDD | Avg Exp% | risk_scale |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | F_hysteresis_regime | 6.65% | 0.54 | -19.53% | 66.4 | 1.0 |
| 2 | G_sizing_regime | 6.64% | 0.56 | -17.89% | 67.3 | 1.0 |
| 3 | I_breakout_or_dip | 6.32% | 0.44 | -19.37% | 66.6 | 1.0 |
| 4 | H_atr_dip_addon | 4.12% | 0.41 | -19.74% | 73.7 | 0.9 |

### WINNER: **F_hysteresis_regime**
- Params: `{'regime_len': 200, 'upper_pct': 2.0, 'lower_pct': 1.0, 'slope_window': 20, 'risk_scale': 1.0}`

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 10.63% | 9.87% | 1.07 | 1.20 | -10.92% | 0.97 | 75.0% | 11.02 | 65.5 | 168.8 | 1.0 | 51.10% |
| G_sizing_regime | 9.12% | 9.94% | 0.93 | 1.03 | -14.95% | 0.61 | 30.0% | 4.40 | 65.5 | 67.5 | 2.4 | 42.84% |
| H_atr_dip_addon | 6.33% | 7.01% | 0.91 | 1.01 | -11.13% | 0.57 | 18.8% | 3.52 | 69.0 | 44.4 | 3.9 | 28.50% |
| I_breakout_or_dip | 7.72% | 9.62% | 0.82 | 0.87 | -10.25% | 0.75 | 33.3% | 2.35 | 60.7 | 29.8 | 5.1 | 35.53% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 7.56% | 11.86% | 0.67 | 0.76 | -25.15% | 0.30 | 48.8% | 4.35 | 75.2 | 152.4 | 1.2 | 1006.45% |
| G_sizing_regime | 7.51% | 11.54% | 0.69 | 0.78 | -25.48% | 0.29 | 28.6% | 3.59 | 75.7 | 69.2 | 2.8 | 991.47% |
| H_atr_dip_addon | 5.41% | 8.42% | 0.67 | 0.75 | -18.78% | 0.29 | 27.4% | 2.99 | 79.0 | 53.0 | 3.8 | 467.99% |
| I_breakout_or_dip | 6.50% | 11.21% | 0.62 | 0.68 | -23.87% | 0.27 | 37.9% | 2.06 | 71.5 | 28.9 | 6.2 | 697.62% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Charts

- `ddcap20_equity_full.png`
- `ddcap20_drawdown_full.png`
- `ddcap20_equity_holdout.png`
- `ddcap20_drawdown_holdout.png`

---
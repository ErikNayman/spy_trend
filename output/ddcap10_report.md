# Drawdown-Capped Strategy Selection Report

**Hard constraint**: MaxDD >= -10% (no worse than 10%)
**Date**: 2026-02-13 23:07
**Data**: SPY 1993-01-29 → 2026-02-11 (8316 days)
**Costs**: 1.0 bps commission + 2.0 bps slippage/side
**Walk-forward**: 8yr train, 2yr val, 2yr step, 10 folds
**Holdout**: 2022-01-01 → latest
**risk_scale grid**: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
**Fold-pass rate required**: 80%
**Min avg OOS exposure**: 60.0%

## TL;DR (Recommendation)

- **Recommended strategy**: G_sizing_regime (risk_scale=0.6)
- **Why**:
  - Highest average OOS CAGR (3.66%) among DD-cap passing strategies
  - Stitched walk-forward MaxDD (-9.65%) stays within -10% cap
  - Passed DD constraint in 10 of 10 validation folds (100%)
- **What to watch**:
  - Volatility spikes may reduce position size below target
  - risk_scale=0.6 caps max exposure at 60%, limiting upside capture in strong trends
- **Risk**: MaxDD cap -10%, stitched OOS MaxDD -9.65%, holdout MaxDD -8.51%

> *Not financial advice. Past performance does not guarantee future results.*

## Strategy Descriptions

- **F: Hysteresis Regime Filter** — Go LONG when Close crosses above EMA(regime_len) * (1+upper_pct%), go CASH when below EMA*(1-lower_pct%). Between bands: hold previous state (hysteresis). Optional slope filter. Binary (0/1), risk_scale applied post-signal.
- **G: Vol-Scaled Regime Sizing** — In regime (Close>EMA), allocate weight = clamp(target_vol / realized_vol, 0, 1). More in calm uptrends, less in choppy ones. Fractional [0,1], risk_scale applied post-signal.
- **H: Regime + ATR Dip Add-On** — Base weight in regime, add-on when Close dips below EMA(dip_ema) by dip_atr_mult*ATR. Total capped at 1. Fractional [0,1], risk_scale applied post-signal.
- **I: Breakout OR Dip** — In regime: enter on N-day high breakout OR dip near EMA(dip_ema). Exit: ATR trailing stop or regime break. Binary (0/1), risk_scale applied post-signal.

## Walk-Forward Optimization (DD-Capped)

### F_hysteresis_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **0** (0.0%)
- **No parameter set passed all constraints.**

### G_sizing_regime
- Base grid: 54, Expanded: 324
- Evaluated: 324, Passed: **30** (9.3%)
- **Best params**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.6}`
- Avg OOS CAGR: 3.66%, Stitched MaxDD: -9.65%

### H_atr_dip_addon
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **80** (13.9%)
- **Best params**: `{'regime_len': 150, 'dip_ema': 20, 'atr_len': 20, 'dip_atr_mult': 1.0, 'base_weight': 0.5, 'addon_weight': 0.5, 'risk_scale': 0.6}`
- Avg OOS CAGR: 2.13%, Stitched MaxDD: -9.95%

### I_breakout_or_dip
- Base grid: 96, Expanded: 576
- Evaluated: 576, Passed: **6** (1.0%)
- **Best params**: `{'regime_len': 150, 'breakout_len': 50, 'dip_ema': 20, 'dip_pct': 1.0, 'atr_len': 14, 'atr_mult': 3.0, 'risk_scale': 0.5}`
- Avg OOS CAGR: 3.06%, Stitched MaxDD: -9.75%

## Overall Ranking

| Rank | Strategy | Avg OOS CAGR | Avg OOS Sharpe | Stitched MaxDD | Avg Exp% | risk_scale |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | G_sizing_regime | 3.66% | 0.54 | -9.65% | 67.3 | 0.6 |
| 2 | I_breakout_or_dip | 3.06% | 0.43 | -9.75% | 66.7 | 0.5 |
| 3 | H_atr_dip_addon | 2.13% | 0.32 | -9.95% | 72.8 | 0.6 |

### WINNER: **G_sizing_regime**
- Params: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 20, 'target_vol': 0.15, 'risk_scale': 0.6}`

### Holdout (2022-01-01 → latest)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G_sizing_regime | 5.41% | 5.83% | 0.93 | 1.04 | -8.51% | 0.64 | 30.0% | 4.81 | 65.5 | 67.5 | 2.4 | 24.03% |
| H_atr_dip_addon | 3.85% | 3.99% | 0.97 | 1.08 | -6.27% | 0.61 | 14.3% | 2.92 | 70.1 | 34.4 | 5.1 | 16.68% |
| I_breakout_or_dip | 4.29% | 4.83% | 0.89 | 0.95 | -5.25% | 0.82 | 36.8% | 2.79 | 60.9 | 33.0 | 4.6 | 18.73% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

### Full Period (all history)

| Strategy | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | WinRate | PF | Exp% | AvgDays | Tr/Yr | TotRet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G_sizing_regime | 4.24% | 6.42% | 0.68 | 0.77 | -14.65% | 0.29 | 27.5% | 3.72 | 75.7 | 69.2 | 2.8 | 294.21% |
| H_atr_dip_addon | 2.83% | 4.60% | 0.63 | 0.67 | -12.34% | 0.23 | 23.9% | 2.62 | 77.4 | 39.5 | 4.9 | 150.75% |
| I_breakout_or_dip | 3.33% | 5.60% | 0.61 | 0.67 | -14.33% | 0.23 | 37.7% | 2.10 | 71.6 | 29.9 | 6.0 | 194.44% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## Charts

- `ddcap10_equity_full.png`
- `ddcap10_drawdown_full.png`
- `ddcap10_equity_holdout.png`
- `ddcap10_drawdown_holdout.png`

---
# Four Scenarios: Strategy Comparison Report

**Date**: 2026-02-12 19:21
**Instrument**: SPY (long-only + cash)
**Costs**: 1.0 bps commission + 2.0 bps slippage per side
**Walk-forward**: 8yr train, 2yr val, 2yr step
**Holdout test**: 2022-01-01 → latest
**Objective**: maximize avg OOS Calmar ratio

## 1. Data
- Range: 1993-01-29 to 2026-02-11 (8316 trading days, 33.0 years)

## 2. Strategy Descriptions

**F: Hysteresis Regime Filter**
- Go LONG when Close crosses above EMA(regime_len) * (1 + upper_pct%).
- Go to CASH when Close crosses below EMA(regime_len) * (1 - lower_pct%).
- Between the bands, hold the previous state (hysteresis prevents whipsaws).
- Optional: require EMA slope > 0 over slope_window days for entry.
- Binary signal (0 or 1). Signals on Close, executed next day.
- **Parameter grid size**: 54 combinations

**G: Volatility-Scaled Regime Sizing**
- When Close > EMA(regime_len) [with optional slope filter], allocate to SPY.
- Position size = clamp(target_vol / realized_vol, 0, 1).
- Allocates MORE in calm uptrends, LESS in choppy uptrends, 0 out of regime.
- Fractional signal in [0, 1]. Signals on Close, executed next day.
- **Parameter grid size**: 54 combinations

**H: Regime + ATR Dip Add-On**
- Base: When Close > EMA(regime_len), hold base_weight (e.g., 50%).
- Add-on: When Close dips below EMA(dip_ema) by dip_atr_mult * ATR,
  increase weight to min(1.0, base + addon).
- Add-on drops when price recovers above EMA(dip_ema). Exit all on regime break.
- Fractional signal in [0, 1]. Signals on Close, executed next day.
- **Parameter grid size**: 96 combinations

**I: Breakout OR Dip (Dual-Mode Entry)**
- Regime: Close > EMA(regime_len).
- Entry Mode 1: Close >= highest high of last breakout_len bars (breakout).
- Entry Mode 2: Close <= EMA(dip_ema) * (1 + dip_pct%) (dip buy).
- Either trigger starts a trade. Exit: ATR trailing stop OR regime break.
- Binary signal (0 or 1). Signals on Close, executed next day.
- **Parameter grid size**: 96 combinations

## 3. Walk-Forward Optimization

#### F_hysteresis_regime — Fold-by-Fold

| Fold | Train | Val | IS Calmar | OOS Calmar | OOS CAGR | OOS MaxDD | OOS Sharpe | Best Params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1993-01-29→2001-01-29 | 2001-01-29→2003-01-29 | 1.09 | 0.00 | 0.00% | 0.00% | 0.00 | regime_len=200, upper_pct=0.0, lower_pct=2.0, slope_windo... |
| 1 | 1995-01-29→2003-01-29 | 2003-01-29→2005-01-29 | 0.89 | 1.99 | 15.53% | -7.82% | 1.32 | regime_len=200, upper_pct=0.0, lower_pct=1.0, slope_windo... |
| 2 | 1997-01-29→2005-01-29 | 2005-01-29→2007-01-29 | 0.59 | 0.71 | 6.55% | -9.29% | 0.74 | regime_len=200, upper_pct=0.0, lower_pct=2.0, slope_windo... |
| 3 | 1999-01-29→2007-01-29 | 2007-01-29→2009-01-29 | 0.30 | -0.38 | -8.23% | -21.89% | -0.93 | regime_len=200, upper_pct=0.0, lower_pct=2.0, slope_windo... |
| 4 | 2001-01-29→2009-01-29 | 2009-01-29→2011-01-29 | 0.23 | 0.33 | 7.66% | -23.32% | 0.50 | regime_len=200, upper_pct=1.0, lower_pct=3.0, slope_window=0 |
| 5 | 2003-01-29→2011-01-29 | 2011-01-29→2013-01-29 | 0.48 | 0.07 | 0.90% | -13.12% | 0.14 | regime_len=100, upper_pct=1.0, lower_pct=1.0, slope_windo... |
| 6 | 2005-01-29→2013-01-29 | 2013-01-29→2015-01-29 | 0.30 | 2.12 | 15.77% | -7.43% | 1.36 | regime_len=150, upper_pct=0.0, lower_pct=2.0, slope_window=0 |
| 7 | 2007-01-29→2015-01-29 | 2015-01-29→2017-01-29 | 0.41 | -0.21 | -3.22% | -15.14% | -0.31 | regime_len=100, upper_pct=1.0, lower_pct=1.0, slope_windo... |
| 8 | 2009-01-29→2017-01-29 | 2017-01-29→2019-01-29 | 0.79 | 0.30 | 4.51% | -14.90% | 0.51 | regime_len=100, upper_pct=0.0, lower_pct=1.0, slope_window=0 |
| 9 | 2011-01-29→2019-01-29 | 2019-01-29→2021-01-29 | 0.57 | 0.55 | 10.95% | -19.98% | 0.72 | regime_len=200, upper_pct=2.0, lower_pct=3.0, slope_windo... |

**F_hysteresis_regime Averages**: OOS Calmar=0.55, OOS CAGR=5.04%, OOS MaxDD=-13.29%, OOS Sharpe=0.41, OOS Exposure=69.8%, OOS Trades/Yr=2.2

#### G_sizing_regime — Fold-by-Fold

| Fold | Train | Val | IS Calmar | OOS Calmar | OOS CAGR | OOS MaxDD | OOS Sharpe | Best Params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1993-01-29→2001-01-29 | 2001-01-29→2003-01-29 | 0.69 | 0.00 | 0.00% | 0.00% | 0.00 | regime_len=200, slope_window=20, vol_window=40, target_vo... |
| 1 | 1995-01-29→2003-01-29 | 2003-01-29→2005-01-29 | 0.62 | 1.52 | 11.01% | -7.25% | 1.18 | regime_len=200, slope_window=20, vol_window=60, target_vo... |
| 2 | 1997-01-29→2005-01-29 | 2005-01-29→2007-01-29 | 0.26 | 0.35 | 3.43% | -9.90% | 0.46 | regime_len=200, slope_window=20, vol_window=40, target_vo... |
| 3 | 1999-01-29→2007-01-29 | 2007-01-29→2009-01-29 | 0.04 | -0.23 | -2.64% | -11.33% | -0.45 | regime_len=200, slope_window=20, vol_window=60, target_vo... |
| 4 | 2001-01-29→2009-01-29 | 2009-01-29→2011-01-29 | 0.15 | 0.95 | 9.75% | -10.29% | 1.06 | regime_len=150, slope_window=20, vol_window=60, target_vo... |
| 5 | 2003-01-29→2011-01-29 | 2011-01-29→2013-01-29 | 0.45 | 0.52 | 3.90% | -7.46% | 0.50 | regime_len=100, slope_window=0, vol_window=20, target_vol... |
| 6 | 2005-01-29→2013-01-29 | 2013-01-29→2015-01-29 | 0.39 | 0.61 | 4.53% | -7.41% | 0.52 | regime_len=100, slope_window=0, vol_window=20, target_vol... |
| 7 | 2007-01-29→2015-01-29 | 2015-01-29→2017-01-29 | 0.38 | -0.15 | -2.15% | -14.45% | -0.19 | regime_len=200, slope_window=20, vol_window=20, target_vo... |
| 8 | 2009-01-29→2017-01-29 | 2017-01-29→2019-01-29 | 0.74 | 0.07 | 1.34% | -19.97% | 0.18 | regime_len=150, slope_window=0, vol_window=20, target_vol... |
| 9 | 2011-01-29→2019-01-29 | 2019-01-29→2021-01-29 | 0.67 | 0.55 | 10.34% | -18.68% | 0.79 | regime_len=200, slope_window=20, vol_window=60, target_vo... |

**G_sizing_regime Averages**: OOS Calmar=0.42, OOS CAGR=3.95%, OOS MaxDD=-10.67%, OOS Sharpe=0.41, OOS Exposure=67.4%, OOS Trades/Yr=4.0

#### H_atr_dip_addon — Fold-by-Fold

| Fold | Train | Val | IS Calmar | OOS Calmar | OOS CAGR | OOS MaxDD | OOS Sharpe | Best Params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1993-01-29→2001-01-29 | 2001-01-29→2003-01-29 | 0.76 | -0.50 | -1.27% | -2.53% | -0.78 | regime_len=200, dip_ema=20, atr_len=14, dip_atr_mult=1.0,... |
| 1 | 1995-01-29→2003-01-29 | 2003-01-29→2005-01-29 | 0.61 | 1.98 | 9.34% | -4.73% | 1.23 | regime_len=200, dip_ema=20, atr_len=14, dip_atr_mult=1.0,... |
| 2 | 1997-01-29→2005-01-29 | 2005-01-29→2007-01-29 | 0.37 | 0.78 | 4.41% | -5.63% | 0.86 | regime_len=200, dip_ema=20, atr_len=14, dip_atr_mult=1.0,... |
| 3 | 1999-01-29→2007-01-29 | 2007-01-29→2009-01-29 | 0.02 | -0.33 | -4.21% | -12.78% | -0.75 | regime_len=200, dip_ema=20, atr_len=20, dip_atr_mult=1.5,... |
| 4 | 2001-01-29→2009-01-29 | 2009-01-29→2011-01-29 | 0.13 | 0.32 | 5.48% | -17.34% | 0.55 | regime_len=200, dip_ema=20, atr_len=20, dip_atr_mult=1.0,... |
| 5 | 2003-01-29→2011-01-29 | 2011-01-29→2013-01-29 | 0.24 | -0.16 | -1.66% | -10.26% | -0.23 | regime_len=200, dip_ema=50, atr_len=14, dip_atr_mult=2.0,... |
| 6 | 2005-01-29→2013-01-29 | 2013-01-29→2015-01-29 | 0.14 | 1.54 | 7.57% | -4.91% | 1.17 | regime_len=200, dip_ema=50, atr_len=14, dip_atr_mult=1.5,... |
| 7 | 2007-01-29→2015-01-29 | 2015-01-29→2017-01-29 | 0.23 | 0.15 | 1.08% | -7.27% | 0.23 | regime_len=150, dip_ema=20, atr_len=20, dip_atr_mult=1.5,... |
| 8 | 2009-01-29→2017-01-29 | 2017-01-29→2019-01-29 | 0.72 | -0.06 | -0.84% | -13.24% | -0.11 | regime_len=150, dip_ema=20, atr_len=14, dip_atr_mult=2.0,... |
| 9 | 2011-01-29→2019-01-29 | 2019-01-29→2021-01-29 | 0.51 | 0.49 | 7.74% | -15.80% | 0.77 | regime_len=200, dip_ema=20, atr_len=20, dip_atr_mult=1.0,... |

**H_atr_dip_addon Averages**: OOS Calmar=0.42, OOS CAGR=2.76%, OOS MaxDD=-9.45%, OOS Sharpe=0.29, OOS Exposure=73.3%, OOS Trades/Yr=4.9

#### I_breakout_or_dip — Fold-by-Fold

| Fold | Train | Val | IS Calmar | OOS Calmar | OOS CAGR | OOS MaxDD | OOS Sharpe | Best Params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1993-01-29→2001-01-29 | 2001-01-29→2003-01-29 | 0.54 | -0.49 | -1.25% | -2.53% | -0.71 | regime_len=200, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 1 | 1995-01-29→2003-01-29 | 2003-01-29→2005-01-29 | 0.53 | 1.94 | 16.48% | -8.48% | 1.38 | regime_len=200, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 2 | 1997-01-29→2005-01-29 | 2005-01-29→2007-01-29 | 0.25 | 0.54 | 5.02% | -9.33% | 0.62 | regime_len=200, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 3 | 1999-01-29→2007-01-29 | 2007-01-29→2009-01-29 | 0.04 | -0.39 | -7.01% | -17.90% | -0.80 | regime_len=150, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 4 | 2001-01-29→2009-01-29 | 2009-01-29→2011-01-29 | 0.11 | 0.57 | 12.61% | -22.13% | 0.84 | regime_len=200, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 5 | 2003-01-29→2011-01-29 | 2011-01-29→2013-01-29 | 0.30 | 0.19 | 2.59% | -13.35% | 0.31 | regime_len=150, breakout_len=20, dip_ema=50, dip_pct=1.0,... |
| 6 | 2005-01-29→2013-01-29 | 2013-01-29→2015-01-29 | 0.23 | 2.15 | 12.76% | -5.95% | 1.15 | regime_len=150, breakout_len=20, dip_ema=50, dip_pct=1.0,... |
| 7 | 2007-01-29→2015-01-29 | 2015-01-29→2017-01-29 | 0.40 | -0.04 | -0.59% | -15.42% | -0.02 | regime_len=150, breakout_len=20, dip_ema=50, dip_pct=1.0,... |
| 8 | 2009-01-29→2017-01-29 | 2017-01-29→2019-01-29 | 0.81 | 0.12 | 2.22% | -18.59% | 0.27 | regime_len=150, breakout_len=20, dip_ema=20, dip_pct=1.0,... |
| 9 | 2011-01-29→2019-01-29 | 2019-01-29→2021-01-29 | 0.83 | 0.81 | 14.07% | -17.30% | 0.97 | regime_len=200, breakout_len=20, dip_ema=50, dip_pct=3.0,... |

**I_breakout_or_dip Averages**: OOS Calmar=0.54, OOS CAGR=5.69%, OOS MaxDD=-13.10%, OOS Sharpe=0.40, OOS Exposure=67.6%, OOS Trades/Yr=5.4

### Consensus Parameters

- **F_hysteresis_regime**: `{'regime_len': 200, 'upper_pct': 0.0, 'lower_pct': 2.0, 'slope_window': 20}`
- **G_sizing_regime**: `{'regime_len': 200, 'slope_window': 20, 'vol_window': 60, 'target_vol': 0.1}`
- **H_atr_dip_addon**: `{'regime_len': 200, 'dip_ema': 20, 'atr_len': 14, 'dip_atr_mult': 1.0, 'base_weight': 0.5, 'addon_weight': 0.5}`
- **I_breakout_or_dip**: `{'regime_len': 150, 'breakout_len': 20, 'dip_ema': 50, 'dip_pct': 1.0, 'atr_len': 20, 'atr_mult': 3.0}`

## 4. Holdout Test (OOS)

### Holdout Period (2022-01-01 → latest)

| Strategy | CAGR | Volatility | Sharpe | Sortino | MaxDD | Calmar | WinRate | ProfitFactor | Exposure% | AvgTradeDays | Trades/Yr | TotalReturn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.47% | 10.49% | 0.83 | 0.89 | -16.88% | 0.50 | 60.0% | 4.51 | 67.9 | 139.8 | 1.2 | 39.44% |
| G_sizing_regime | 6.72% | 8.12% | 0.84 | 0.90 | -9.77% | 0.69 | 30.0% | 5.15 | 65.5 | 67.5 | 2.4 | 30.47% |
| H_atr_dip_addon | 7.02% | 6.63% | 1.06 | 1.15 | -10.24% | 0.69 | 25.0% | 4.90 | 69.0 | 44.4 | 3.9 | 31.98% |
| I_breakout_or_dip | 8.04% | 9.30% | 0.88 | 0.92 | -12.05% | 0.67 | 35.0% | 2.59 | 57.8 | 29.8 | 4.9 | 37.17% |
| Buy_Hold | 10.98% | 17.87% | 0.67 | 0.93 | -24.52% | 0.45 | 100.0% | inf | 100.0 | 1030.0 | 0.2 | 53.08% |

## 5. Full-Period Backtest (for reference, NOT for selection)

### Full Period (all history)

| Strategy | CAGR | Volatility | Sharpe | Sortino | MaxDD | Calmar | WinRate | ProfitFactor | Exposure% | AvgTradeDays | Trades/Yr | TotalReturn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_hysteresis_regime | 8.52% | 12.36% | 0.72 | 0.83 | -30.06% | 0.28 | 54.5% | 5.16 | 78.3 | 197.4 | 1.0 | 1384.66% |
| G_sizing_regime | 5.52% | 8.62% | 0.67 | 0.76 | -15.40% | 0.36 | 27.5% | 3.84 | 75.7 | 69.2 | 2.8 | 489.31% |
| H_atr_dip_addon | 5.67% | 8.06% | 0.72 | 0.80 | -17.25% | 0.33 | 23.4% | 3.53 | 79.0 | 53.0 | 3.8 | 516.57% |
| I_breakout_or_dip | 6.33% | 11.05% | 0.61 | 0.67 | -29.61% | 0.21 | 37.4% | 2.06 | 70.0 | 28.7 | 6.2 | 658.29% |
| Buy_Hold | 10.69% | 18.61% | 0.64 | 0.81 | -55.19% | 0.19 | 100.0% | inf | 100.0 | 8315.0 | 0.0 | 2753.60% |

## 6. Rankings

### Ranking by Avg OOS Calmar (walk-forward)

1. **F_hysteresis_regime**: 0.55
2. **I_breakout_or_dip**: 0.54
3. **H_atr_dip_addon**: 0.42
4. **G_sizing_regime**: 0.42

### Ranking by Holdout Calmar

1. **G_sizing_regime**: 0.69
2. **H_atr_dip_addon**: 0.69
3. **I_breakout_or_dip**: 0.67
4. **F_hysteresis_regime**: 0.50

## 7. Robustness: Sensitivity Around Consensus Params

For each strategy, key parameters are varied +/- 1 step from consensus to check stability. Evaluated on pre-test data only.

### F_hysteresis_regime

**regime_len** (base=200):

| regime_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 160.0000 | 0.0902 | -0.2604 | 0.3463 | 0.7701 | 77.3751 | 1.0725 |
| 200.0000 | 0.0961 | -0.2087 | 0.4604 | 0.7996 | 78.9127 | 0.8649 |
| 240.0000 | 0.0973 | -0.2291 | 0.4247 | 0.7880 | 79.9835 | 0.6919 |

**upper_pct** (base=0.0):

| upper_pct | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 0.0961 | -0.2087 | 0.4604 | 0.7996 | 78.9127 | 0.8649 |
| 0.2500 | 0.0951 | -0.2087 | 0.4558 | 0.7930 | 78.8440 | 0.8649 |

**lower_pct** (base=2.0):

| lower_pct | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 1.6000 | 0.0947 | -0.2176 | 0.4354 | 0.7932 | 78.4734 | 0.9687 |
| 2.0000 | 0.0961 | -0.2087 | 0.4604 | 0.7996 | 78.9127 | 0.8649 |
| 2.4000 | 0.0992 | -0.1967 | 0.5044 | 0.8156 | 79.2559 | 0.6919 |

**slope_window** (base=20):

| slope_window | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 15.0000 | 0.0977 | -0.2371 | 0.4123 | 0.8107 | 79.1323 | 0.8995 |
| 20.0000 | 0.0961 | -0.2087 | 0.4604 | 0.7996 | 78.9127 | 0.8649 |
| 25.0000 | 0.0953 | -0.2415 | 0.3946 | 0.7944 | 78.7754 | 0.8995 |

### G_sizing_regime

**regime_len** (base=200):

| regime_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 160.0000 | 0.0528 | -0.1664 | 0.3170 | 0.6530 | 74.1076 | 3.4250 |
| 200.0000 | 0.0584 | -0.1382 | 0.4227 | 0.7009 | 76.3317 | 2.5947 |
| 240.0000 | 0.0632 | -0.1439 | 0.4394 | 0.7406 | 78.1027 | 2.1104 |

**slope_window** (base=20):

| slope_window | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 15.0000 | 0.0603 | -0.1378 | 0.4378 | 0.7214 | 76.6200 | 2.5255 |
| 20.0000 | 0.0584 | -0.1382 | 0.4227 | 0.7009 | 76.3317 | 2.5947 |
| 25.0000 | 0.0573 | -0.1390 | 0.4123 | 0.6893 | 76.1532 | 2.6985 |

**vol_window** (base=60):

| vol_window | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 48.0000 | 0.0592 | -0.1420 | 0.4169 | 0.7043 | 76.3317 | 2.5947 |
| 60.0000 | 0.0584 | -0.1382 | 0.4227 | 0.7009 | 76.3317 | 2.5947 |
| 72.0000 | 0.0583 | -0.1402 | 0.4156 | 0.7027 | 76.3317 | 2.5947 |

**target_vol** (base=0.1):

| target_vol | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 0.1000 | 0.0584 | -0.1382 | 0.4227 | 0.7009 | 76.3317 | 2.5947 |
| 0.3500 | 0.0817 | -0.2221 | 0.3678 | 0.7144 | 76.3317 | 2.5947 |

### H_atr_dip_addon

**regime_len** (base=200):

| regime_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 160.0000 | 0.0513 | -0.2093 | 0.2452 | 0.6843 | 78.1027 | 4.6013 |
| 200.0000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 240.0000 | 0.0673 | -0.1730 | 0.3890 | 0.8121 | 80.4366 | 2.7331 |

**dip_ema** (base=20):

| dip_ema | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 15.0000 | 0.0608 | -0.1681 | 0.3619 | 0.7525 | 79.3795 | 3.4596 |
| 20.0000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 25.0000 | 0.0569 | -0.1586 | 0.3589 | 0.7245 | 79.3795 | 3.4596 |

**atr_len** (base=14):

| atr_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 9.0000 | 0.0595 | -0.1586 | 0.3753 | 0.7556 | 79.3795 | 3.4596 |
| 14.0000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 19.0000 | 0.0598 | -0.1611 | 0.3709 | 0.7425 | 79.3795 | 3.4596 |

**dip_atr_mult** (base=1.0):

| dip_atr_mult | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.7500 | 0.0602 | -0.1930 | 0.3121 | 0.7274 | 79.3795 | 3.4596 |
| 1.0000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 1.2500 | 0.0583 | -0.1580 | 0.3691 | 0.7660 | 79.3795 | 3.4596 |

**base_weight** (base=0.5):

| base_weight | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.2500 | 0.0395 | -0.1070 | 0.3693 | 0.7545 | 79.3795 | 3.4596 |
| 0.5000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 0.7500 | 0.0722 | -0.2086 | 0.3459 | 0.7402 | 79.3795 | 3.4596 |

**addon_weight** (base=0.5):

| addon_weight | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.2500 | 0.0517 | -0.1442 | 0.3586 | 0.7496 | 79.3795 | 3.4596 |
| 0.5000 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |
| 0.7500 | 0.0605 | -0.1586 | 0.3814 | 0.7621 | 79.3795 | 3.4596 |

### I_breakout_or_dip

**regime_len** (base=150):

| regime_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 120.0000 | 0.0649 | -0.3348 | 0.1940 | 0.6363 | 68.9731 | 6.3311 |
| 150.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 180.0000 | 0.0686 | -0.2638 | 0.2599 | 0.6377 | 72.4190 | 5.9160 |

**breakout_len** (base=20):

| breakout_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 15.0000 | 0.0661 | -0.2961 | 0.2232 | 0.6275 | 71.1560 | 6.1582 |
| 20.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 25.0000 | 0.0669 | -0.2961 | 0.2260 | 0.6350 | 71.1285 | 6.1236 |

**dip_ema** (base=50):

| dip_ema | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 40.0000 | 0.0681 | -0.2851 | 0.2390 | 0.6430 | 71.9797 | 6.1928 |
| 50.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 60.0000 | 0.0608 | -0.2961 | 0.2053 | 0.5891 | 68.9594 | 6.0544 |

**dip_pct** (base=1.0):

| dip_pct | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 0.7500 | 0.0679 | -0.2757 | 0.2464 | 0.6474 | 69.9753 | 5.9852 |
| 1.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 1.2500 | 0.0657 | -0.3053 | 0.2154 | 0.6215 | 72.0621 | 6.2965 |

**atr_len** (base=20):

| atr_len | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 15.0000 | 0.0647 | -0.3079 | 0.2103 | 0.6184 | 71.2246 | 5.9160 |
| 20.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 25.0000 | 0.0648 | -0.3082 | 0.2102 | 0.6177 | 70.5107 | 6.1928 |

**atr_mult** (base=3.0):

| atr_mult | CAGR | MaxDD | Calmar | Sharpe | Exposure | Trades/Yr |
| --- | --- | --- | --- | --- | --- | --- |
| 2.4000 | 0.0575 | -0.2990 | 0.1923 | 0.5738 | 67.1060 | 7.8188 |
| 3.0000 | 0.0670 | -0.2961 | 0.2264 | 0.6358 | 71.1422 | 6.1236 |
| 3.6000 | 0.0688 | -0.3244 | 0.2121 | 0.6450 | 72.1032 | 4.9819 |

## 8. Charts

- `four_scenarios_equity_full.png` — equity curves, full period
- `four_scenarios_drawdown_full.png` — drawdowns, full period
- `four_scenarios_equity_holdout.png` — equity curves, holdout
- `four_scenarios_drawdown_holdout.png` — drawdowns, holdout

---
*Generated in 95.3s*
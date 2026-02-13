# SPY Trend-Following Strategy Research Report

```
======================================================================
  SPY TREND-FOLLOWING STRATEGY RESEARCH
======================================================================

## 1. Data Download
Data range: 1993-01-29 to 2026-02-11 (8316 trading days, 33.0 years)

## 2. Buy-and-Hold Benchmark
  CAGR:             10.69%
  Volatility:       18.61%
  Sharpe:           0.64
  Sortino:          0.81
  Max Drawdown:     -55.19%
  Calmar:           0.19
  Win Rate:         100.0%
  Profit Factor:    inf
  Exposure:         100.0%
  Avg Trade Days:   8315.0
  Trades/Year:      0.0
  Total Return:     2753.60%

## 3. Strategy Search (Walk-Forward Optimization)
   Train: 8yr, Val: 2yr, Step: 2yr
   Test holdout: 2022-01-01 onward
   Objective: Calmar ratio

--- A_ema_crossover: EMA fast/slow crossover ---
  Parameter grid size: 15
  Consensus params: {'fast': 10, 'slow': 50}
  Avg OOS Calmar: 0.54
  Avg IS  Calmar: 0.53

--- B_regime_filter: Regime filter (price > EMA + slope) ---
  Parameter grid size: 12
  Consensus params: {'regime_len': 200, 'slope_window': 10}
  Avg OOS Calmar: 0.47
  Avg IS  Calmar: 0.44

--- C_buy_dip_uptrend: Buy-the-dip inside bullish regime ---
  Parameter grid size: 16
  Consensus params: {'regime_len': 200, 'dip_ema': 20, 'dip_pct': 1.0}
  Avg OOS Calmar: 0.62
  Avg IS  Calmar: 0.39

--- D_ema_atr_stop: EMA crossover + ATR trailing stop ---
  Parameter grid size: 54
  Consensus params: {'fast': 20, 'slow': 100, 'atr_len': 20, 'atr_mult': 2.0}
  Avg OOS Calmar: 0.45
  Avg IS  Calmar: 0.57

--- E_composite: Composite: regime + dip entry + ATR stop ---
  Parameter grid size: 144
  Consensus params: {'regime_len': 200, 'slope_window': 20, 'entry_ema': 20, 'entry_band_pct': 5.0, 'atr_len': 14, 'atr_mult': 5.0}
  Avg OOS Calmar: 0.78
  Avg IS  Calmar: 0.42

## 4. Strategy Ranking (by avg OOS Calmar)
  1. E_composite: OOS Calmar=0.78, CAGR=7.13%, MaxDD=-10.83%
  2. C_buy_dip_uptrend: OOS Calmar=0.62, CAGR=6.07%, MaxDD=-13.05%
  3. A_ema_crossover: OOS Calmar=0.54, CAGR=5.08%, MaxDD=-14.54%
  4. B_regime_filter: OOS Calmar=0.47, CAGR=4.87%, MaxDD=-12.54%
  5. D_ema_atr_stop: OOS Calmar=0.45, CAGR=3.54%, MaxDD=-16.19%

**WINNER: E_composite**
  Params: {'regime_len': 200, 'slope_window': 20, 'entry_ema': 20, 'entry_band_pct': 5.0, 'atr_len': 14, 'atr_mult': 5.0}

## 5. Final Out-of-Sample Test

  Test Period Metrics (HOLDOUT):
  CAGR:             9.22%
  Volatility:       9.95%
  Sharpe:           0.94
  Sortino:          1.04
  Max Drawdown:     -15.11%
  Calmar:           0.61
  Win Rate:         27.3%
  Profit Factor:    3.86
  Exposure:         65.4%
  Avg Trade Days:   61.3
  Trades/Year:      2.7
  Total Return:     43.40%

## 5b. Full-Period Backtest (for reference, NOT for selection)
  CAGR:             7.31%
  Volatility:       11.90%
  Sharpe:           0.65
  Sortino:          0.74
  Max Drawdown:     -25.87%
  Calmar:           0.28
  Win Rate:         29.0%
  Profit Factor:    3.05
  Exposure:         75.6%
  Avg Trade Days:   62.9
  Trades/Year:      3.0
  Total Return:     926.67%

  Buy-and-Hold during test period:
  CAGR:             10.98%
  Volatility:       17.87%
  Sharpe:           0.67
  Sortino:          0.93
  Max Drawdown:     -24.52%
  Calmar:           0.45
  Win Rate:         100.0%
  Profit Factor:    inf
  Exposure:         100.0%
  Avg Trade Days:   1030.0
  Trades/Year:      0.2
  Total Return:     53.08%

## 6. Sensitivity Analysis

  Sensitivity: regime_len (base=200)
 regime_len     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
        150 0.070734 -0.247420 0.285888 0.646456 73.544756   3.528830
        180 0.070053 -0.247882 0.282604 0.628773 75.343218   3.321252
        190 0.076214 -0.212163 0.359224 0.675005 75.604064   3.009885
        200 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
        210 0.077510 -0.217860 0.355778 0.679551 76.565074   2.871499
        220 0.078157 -0.246054 0.317640 0.679180 77.086766   2.836903
        250 0.082933 -0.241125 0.343942 0.704492 78.130148   2.560132

  Sensitivity: slope_window (base=20)
 slope_window     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
            2 0.084772 -0.249727 0.339459 0.725758 78.528281   3.113674
           10 0.082150 -0.220412 0.372710 0.715524 76.935750   2.802306
           20 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
           30 0.075872 -0.237425 0.319562 0.670370 75.878638   2.871499
           40 0.080408 -0.223280 0.360120 0.707343 75.521691   2.836903
           70 0.073691 -0.254849 0.289158 0.661483 73.846787   2.975288

  Sensitivity: entry_ema (base=20)
 entry_ema     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
         2 0.078956 -0.222128 0.355454 0.693031 76.221856   2.871499
        10 0.078956 -0.222128 0.355454 0.693031 76.221856   2.871499
        20 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
        30 0.079133 -0.222128 0.356248 0.697797 76.002197   2.871499
        40 0.078802 -0.217935 0.361583 0.695807 75.851181   2.871499
        70 0.079757 -0.209754 0.380240 0.703922 75.768808   2.871499

  Sensitivity: entry_band_pct (base=5.0)
 entry_band_pct     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
            3.0 0.078823 -0.217935 0.361681 0.695972 75.837452   2.871499
            4.0 0.078583 -0.222128 0.353773 0.690432 76.139484   2.871499
            4.5 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
            5.0 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
            5.5 0.078956 -0.222128 0.355454 0.693031 76.221856   2.871499
            6.0 0.078956 -0.222128 0.355454 0.693031 76.221856   2.871499
            7.0 0.078956 -0.222128 0.355454 0.693031 76.221856   2.871499

  Sensitivity: atr_len (base=14)
 atr_len     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
       2 0.082525 -0.222128 0.371520 0.720975 76.057111   3.217463
       4 0.081698 -0.222128 0.367794 0.714036 76.194399   2.871499
      14 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
      24 0.077061 -0.222128 0.346921 0.681274 76.070840   3.148270
      34 0.077885 -0.222128 0.350632 0.687686 76.057111   3.148270
      64 0.076010 -0.259026 0.293445 0.676921 75.961010   3.425041

  Sensitivity: atr_mult (base=5.0)
 atr_mult     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
      3.0 0.068174 -0.252574 0.269918 0.621718 75.137287   5.500824
      4.0 0.072039 -0.227520 0.316628 0.643468 75.823723   3.771005
      4.5 0.078603 -0.222128 0.353863 0.690799 76.057111   3.182867
      5.0 0.079229 -0.222128 0.356680 0.695180 76.208127   2.871499
      5.5 0.083070 -0.222128 0.373973 0.724361 76.263042   2.698517
      6.0 0.081825 -0.222128 0.368367 0.714822 76.290500   2.629325
      7.0 0.082536 -0.222128 0.371570 0.719720 76.317957   2.594728

## 7. Subperiod Stability
                  Period     CAGR     MaxDD   Calmar   Sharpe  Exposure  Trades/Yr
1993-02-01 to 2002-12-31 0.086438 -0.209606 0.412382 0.697794 69.067627   2.722689
2003-01-01 to 2012-12-31 0.035394 -0.208587 0.169684 0.371360 71.899841   4.106518
2013-01-01 to 2019-12-31 0.099931 -0.120192 0.831427 0.949507 88.188529   2.146508
2020-01-01 to 2025-12-31 0.096055 -0.256334 0.374727 0.838361 73.722628   3.177173

  Buy-and-Hold subperiods:
                  Period     CAGR     MaxDD   Calmar   Sharpe
1993-02-01 to 2002-12-31 0.090734 -0.475158 0.190955 0.561089
2003-01-01 to 2012-12-31 0.066716 -0.551894 0.120886 0.415470
2013-01-01 to 2019-12-31 0.141960 -0.193489 0.733687 1.102688
2020-01-01 to 2025-12-31 0.148602 -0.337173 0.440731 0.771911

## 8. Monthly Returns (Test Period)
       Jan    Feb     Mar    Apr    May   Jun   Jul    Aug    Sep    Oct   Nov    Dec  Annual
Year                                                                                         
2022   NaN  0.00%   0.00%  0.00%  0.00% 0.00% 0.00%  0.00%  0.00%  0.00% 0.00%  0.00%     NaN
2023 0.00% -4.36%  -1.52%  1.51%  0.46% 6.48% 3.27% -1.63% -4.59% -2.27% 5.92%  4.57%   7.30%
2024 1.59%  5.22%   3.27% -4.03%  5.06% 3.53% 1.21%  2.34%  2.10% -0.89% 5.96% -2.41%  24.89%
2025 2.69% -1.27% -10.12%  0.00% -0.84% 5.14% 2.30%  2.05%  3.56%  2.38% 0.19%  0.08%   5.45%
2026 1.47% -0.00%     NaN    NaN    NaN   NaN   NaN    NaN    NaN    NaN   NaN    NaN   1.47%

## 9. Charts
  Saved: /Users/admin/Work/spy_trend/output/equity_curve.png
  Saved: /Users/admin/Work/spy_trend/output/drawdown.png
  Saved: /Users/admin/Work/spy_trend/output/test_equity.png

======================================================================
  FINAL RECOMMENDATION (based on OUT-OF-SAMPLE results)
======================================================================

Strategy: E_composite
Description: Composite: regime + dip entry + ATR stop
Parameters: {'regime_len': 200, 'slope_window': 20, 'entry_ema': 20, 'entry_band_pct': 5.0, 'atr_len': 14, 'atr_mult': 5.0}

Rules (plain English):
  REGIME: Close > EMA(200) AND EMA slope > 0 over 20 days.
  ENTRY: In regime AND Close <= EMA(20) x (1 + 5.0%).
  EXIT: Trailing stop = highest_close - 5.0 x ATR(14), OR regime break.
  Signals generated on Close, executed next day.

Test Period Performance:
  CAGR:             9.22%
  Volatility:       9.95%
  Sharpe:           0.94
  Sortino:          1.04
  Max Drawdown:     -15.11%
  Calmar:           0.61
  Win Rate:         27.3%
  Profit Factor:    3.86
  Exposure:         65.4%
  Avg Trade Days:   61.3
  Trades/Year:      2.7
  Total Return:     43.40%

Buy-and-Hold Test Period:
  CAGR:             10.98%
  Volatility:       17.87%
  Sharpe:           0.67
  Sortino:          0.93
  Max Drawdown:     -24.52%
  Calmar:           0.45
  Win Rate:         100.0%
  Profit Factor:    inf
  Exposure:         100.0%
  Avg Trade Days:   1030.0
  Trades/Year:      0.2
  Total Return:     53.08%

Why this strategy reduces drawdowns:
  This is a trend-following system that stays long during confirmed
  uptrends (price above long-term EMA) and exits to cash when the
  trend breaks. The ATR-based trailing stop (if present) provides an
  additional layer of protection by exiting when price drops
  significantly from its peak. By avoiding sustained bear markets,
  the strategy sacrifices some upside during whipsaws but dramatically
  reduces maximum drawdown compared to buy-and-hold.

Total runtime: 80.3 seconds
```

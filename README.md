# SPY Trend-Following Strategy Research

Quantitative research project implementing and evaluating long-only trend-following strategies on SPY (S&P 500 ETF) with daily rebalancing.

## Overview

This project builds, optimizes, and rigorously tests a series of EMA-based trend-following strategies for SPY. The goal is to capture equity uptrends while exiting to cash during sustained declines, reducing max drawdown compared to buy-and-hold.

**Key features:**
- Walk-forward optimization (8yr train / 2yr validation / 2yr step, ~10 folds)
- No look-ahead bias: signals on Close[t] executed at t+1
- Fractional position sizing support (weights in [0, 1])
- Transaction costs: 1 bps commission + 2 bps slippage per side
- Holdout test period: 2022-01-01 to present
- 33 years of data (1993-2026)

## Strategies

| ID | Name | Type | Description |
|----|------|------|-------------|
| A | EMA Crossover | Binary | Long when EMA(fast) > EMA(slow) |
| B | Regime Filter | Binary | Long when Close > EMA + positive slope |
| C | Buy Dip in Uptrend | Binary | Enter on pullbacks inside bullish regime |
| D | EMA + ATR Stop | Binary | EMA crossover entry + ATR trailing stop exit |
| E | Composite | Binary | Regime + dip entry + ATR stop |
| **F** | **Hysteresis Regime** | **Binary** | **Regime filter with hysteresis bands to reduce whipsaws** |
| **G** | **Vol-Scaled Sizing** | **Fractional** | **Regime filter with volatility-targeted position sizing** |
| **H** | **ATR Dip Add-On** | **Fractional** | **Base regime weight + ATR-scaled dip add-on** |
| **I** | **Breakout or Dip** | **Binary** | **Dual-mode entry: breakout OR dip, with ATR trailing stop** |

## Research Scenarios

### 1. Four Scenarios Comparison (`run_four_scenarios.py`)

Apples-to-apples walk-forward comparison of strategies F, G, H, I. Consensus parameters selected by most-frequent best params across folds. Ranked by average OOS Calmar ratio.

### 2. Drawdown-Capped Selection (`run_ddcap20.py`)

Hard constraint optimization: **MaxDD must be no worse than -20%**. Evaluates each parameter set (including a `risk_scale` lever) across all validation folds with fixed params. Constraints:
- 80%+ of folds must satisfy OOS MaxDD >= -20%
- Stitched walk-forward OOS equity MaxDD >= -20%
- Average OOS exposure >= 60%

**Winner: F_hysteresis_regime**

| Metric | F_hysteresis_regime | Buy & Hold |
|--------|-------------------|------------|
| Holdout CAGR | 10.63% | 10.98% |
| Holdout MaxDD | **-10.92%** | -24.52% |
| Holdout Calmar | **0.97** | 0.45 |
| Holdout Sharpe | **1.07** | 0.67 |

Parameters: `regime_len=200, upper_pct=2.0, lower_pct=1.0, slope_window=20`

The strategy nearly matches buy-and-hold on return while cutting max drawdown by more than half.

## Project Structure

```
spy_trend/
  backtest.py              # Vectorized backtester (fractional weights, turnover costs)
  data.py                  # SPY data download (yfinance) + CSV cache
  metrics.py               # Performance metrics (CAGR, Sharpe, Calmar, etc.)
  optimizer.py             # Walk-forward optimization framework
  strategies.py            # All 9 strategy implementations + parameter grids
  main.py                  # Original A-E research pipeline
  run_four_scenarios.py    # F/G/H/I comparison
  run_ddcap20.py           # Drawdown-capped selection
  output/                  # Reports (.md) and charts (.png)
```

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the interactive web UI
streamlit run app.py

# Run the four-scenarios comparison (CLI)
python run_four_scenarios.py

# Run the drawdown-capped selection (CLI)
python run_ddcap20.py               # default -20% cap
python run_ddcap20.py --dd-cap -15  # custom cap

# Run the original A-E research
python main.py
```

### Web UI (`app.py`)

The Streamlit app provides two modes:

1. **DD-Capped Optimization** — full walk-forward optimization with drawdown constraints, interactive Plotly charts, ranking table, fold-by-fold details.
2. **Single Strategy Backtest** — run any of the 9 strategies (A-I) with custom parameters and see equity/drawdown curves instantly.

Configuration is in the sidebar: DD cap, risk_scale grid, walk-forward settings, cost model.

Reports and charts are saved to `./output/`.

## Data

SPY daily OHLCV from yfinance (auto-adjusted for splits/dividends). Cached locally as `spy_daily.csv` after first download. Data range: 1993-01-29 to present (~8300 trading days).

# Investment Scenario Simulator

**"TheTradeSIM"**

> Investors are shown a single number — "expected return 7%". We show them the full range of what could actually happen, and explain it in plain language.

Built for the **Blackstone Challenge at ShellHacks 2026**.

---

## Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Solution](#our-solution)
- [Features](#features)
- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Methodology](#methodology)
- [Limitations & Disclaimer](#limitations--disclaimer)
- [Future Work](#future-work)
- [Team](#team)

---

## Overview

Investment Scenario Simulator is a web application that helps investors understand the **range of possible outcomes** of an investment plan instead of a single projected return. The user enters how they want to invest, how much, and for how long. The app runs thousands of simulations on real market data, visualizes the results as fan charts, computes advanced risk statistics, backtests the plan against real history, and uses AI to explain everything in plain language.

We do not predict the market. We make risk **visible and understandable**.

---

## The Problem

Retail investors have access to more information than ever — performance reports, filings, market data, economic trends, news — but almost no intuition for **risk**.

- Most tools show what *happened*, not what *could happen* to *your* money over *your* time horizon.
- Projections are usually a single number ("expected return 7%") that hides the uncertainty entirely.
- Concepts like volatility, drawdown, correlation, and diversification remain abstract for most people.

The result: investors either drown in raw data or make decisions based on oversimplified numbers.

---

## Our Solution

A simulator that turns an investment plan into a **distribution of outcomes**:

1. The user selects a strategy (preset or custom tickers), an amount, and a time horizon.
2. The app pulls historical market data from Yahoo Finance.
3. Two simulation engines generate thousands of possible future paths.
4. Results are shown as fan charts for the whole portfolio **and for each individual holding**.
5. Advanced statistics quantify the risk.
6. A real backtest shows what the same plan would have done in the past.
7. Claude explains the bad, typical, and good case in plain English.

Instead of *"you'll have $7,000"*, the user sees:

> *"In the worst 10% of cases you'd have $4,200, typically $6,900, and there's a 15% chance you end up below what you started with."*

---

## Features

| Feature | Description |
|---|---|
| **Plan input** | Budget, time horizon (1–20 years), preset strategies (Prudent / Balanced / Aggressive) or custom tickers |
| **Two simulation engines** | Correlated Monte Carlo (GBM with Cholesky decomposition) and historical bootstrap resampling |
| **Portfolio fan chart** | 10–90% and 25–75% outcome bands plus median path |
| **Per-asset fan charts** | The same analysis for every individual investment |
| **Advanced statistics** | Percentile outcomes, probability of loss, annualized return & volatility, Sharpe ratio, max drawdown |
| **Correlation matrix** | Shows how assets move together (real diversification, not assumed) |
| **Historical backtest** | "What if you had invested this amount N years ago?" using real prices |
| **AI explanation** | Claude translates the numbers into a plain-language narrative for each scenario |
| **No account required** | Zero friction: open the app and simulate |

---

## How It Works

```
User input (budget, horizon, strategy)
            │
            ▼
   Yahoo Finance (10y daily prices)
            │
            ▼
   Daily returns, mean, covariance
            │
    ┌───────┴────────┐
    ▼                ▼
Monte Carlo      Bootstrap
(GBM, correlated) (resampled history)
    └───────┬────────┘
            ▼
  N simulated paths (portfolio + per asset)
            │
    ┌───────┼──────────────┐
    ▼       ▼              ▼
Fan charts  Statistics   Backtest
            │
            ▼
   Claude API → plain-language explanation
```

---

## Tech Stack

- **Python 3.10+**
- **Streamlit** — web UI
- **yfinance** — market data (Yahoo Finance)
- **NumPy / Pandas** — simulation and statistics
- **Plotly** — interactive charts
- **Anthropic Claude API** — natural-language explanations

---

## Getting Started

### Prerequisites

- Python 3.10 or newer
- An Anthropic API key (optional — the app works without it, but the AI explanation will be disabled)

### Installation

```bash
git clone https://github.com/<your-username>/investment-scenario-simulator.git
cd investment-scenario-simulator

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

`requirements.txt`:

```
streamlit
yfinance
numpy
pandas
plotly
anthropic
```

### Configuration

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"     # Windows: set ANTHROPIC_API_KEY=your-key-here
```

### Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Usage

1. In the sidebar, enter the **amount** you want to invest.
2. Choose a **time horizon** in years.
3. Pick a **strategy**:
   - *Prudent* — 70% BND / 30% VTI
   - *Balanced* — 50% BND / 50% VTI
   - *Aggressive* — 60% VTI / 40% QQQ
   - *Custom* — type any tickers, comma separated (e.g. `AAPL, MSFT, VTI`)
4. Select the number of **simulations** and the **engine**.
5. Press **Simulate**.

You will see:

- Four headline metrics: pessimistic, median, optimistic outcome and probability of loss
- The portfolio fan chart
- A statistics table and a fan chart for each asset
- The correlation matrix and the historical backtest
- The AI-generated explanation

---

## Project Structure

```
investment-scenario-simulator/
├── app.py              # Streamlit application (UI, data, simulation, AI)
├── requirements.txt    # Python dependencies
└── README.md
```

---

## Methodology

### Monte Carlo (Geometric Brownian Motion)

Daily log-returns are modeled as a multivariate normal distribution with the historical mean vector and covariance matrix. Correlated shocks are generated with a **Cholesky decomposition** of the covariance matrix, so assets move together the way they actually do in the data. Each path compounds daily for `252 × years` trading days.

### Historical Bootstrap

Instead of assuming a distribution, random days are sampled (with replacement) from the real historical return series and compounded. This preserves fat tails, skew, and cross-asset correlation observed in reality, and offers a useful contrast with the parametric model.

### Statistics

- **Annualized return**: `(1 + mean daily return)^252 − 1`
- **Annualized volatility**: `std daily return × √252`
- **Sharpe ratio**: annualized return / annualized volatility (risk-free rate assumed 0 for simplicity)
- **Max drawdown**: largest peak-to-trough decline in the historical cumulative return
- **Probability of loss**: share of simulated paths ending below the initial investment

### Backtest

The selected weights are applied to real prices from `N` years ago and the portfolio value is tracked to today.

---

## Limitations & Disclaimer

This is an **educational tool**, not financial advice.

- Simulations are based on historical data; the future may differ.
- The GBM model assumes normally distributed log-returns, which underestimates extreme events.
- Transaction costs, taxes, dividends timing and rebalancing are not modeled.
- The Sharpe ratio uses a 0% risk-free rate.
- Data quality depends on Yahoo Finance availability.

Nothing in this application constitutes a recommendation to buy or sell any security.

---

## Future Work

- **News-driven scenarios**: use Claude to read today's headlines, propose plausible macro scenarios (rate cut, tariffs, earnings miss) and apply them as shocks to the simulation
- **Custom weights** with sliders and rebalancing options
- **Events watchlist**: upcoming earnings, unusual volume, fresh news for the assets in the plan
- **Portfolio upload** (CSV) and look-through of ETF holdings
- **User accounts** to save and compare plans
- **Additional models**: GARCH volatility, regime switching, Student-t shocks for fatter tails

---

## Team

Built at ShellHacks 2026 by *Joseph Carmona, Keniel Cruz Garcia, Daniele Vernaleone*.

---

## License

MIT

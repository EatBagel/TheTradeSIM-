# The Trade Sim



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

The Trade Sim is a web application that helps investors understand the **range of possible outcomes** of an investment plan instead of a single projected return. The user enters how they want to invest, how much, and for how long. The app runs thousands of simulations on real market data, visualizes the results as fan charts for the whole plan and for each investment, and computes risk statistics in plain terms.

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

1. The user picks their investments (or a preset), an amount, and a time horizon.
2. The app pulls historical market data from Yahoo Finance.
3. Two simulation engines generate thousands of possible future paths.
4. Results are shown as fan charts for the whole portfolio **and for each individual investment**, each in its own tab.
5. Statistics quantify the risk: bad, typical and good outcome, chance of loss, volatility, drawdown.

Instead of *"you'll have $7,000"*, the user sees:

> *"In the worst 10% of cases you'd have $4,200, typically $6,900, and there's a 15% chance you end up below what you started with."*

---

## Features

| Feature | Description |
|---|---|
| **Guided, jargon-free flow** | Three numbered steps on one page: money and time → where it goes → what could happen. Plain-language labels everywhere, tooltips on every statistic, a *Words explained* glossary |
| **Plan input** | Amount, years (1–20), an approach (Play it safe / Balanced / Aggressive) that seeds the goal and loss-limit lines, and your mix with sliders: stocks, ETFs, bonds (by country and type), crypto, commodities and real estate |
| **Risk level** | Low / Medium / High / Very high, from past yearly swings, with what it means in a few words |
| **Multi-currency** | Non-USD instruments (EUR, GBP, CHF, JPY, …) are converted to USD with daily FX rates |
| **Two simulation engines** | Correlated Monte Carlo (GBM with Cholesky decomposition) and historical bootstrap resampling |
| **Fan chart** | "Most scenarios" (10–90%) and "likely zone" (25–75%) bands, the middle outcome, and one example scenario |
| **Line → candlestick zoom** | Every time chart starts as a line. Zooming in switches to candlesticks whose unit follows the zoom (years → months, a month → days, a day → hours; never smaller than 1 hour), with nights and weekends hidden |
| **Goal & loss-limit lines** | Drag a green goal line and a red loss-limit line on any chart and set how long you'd stay invested; the bad, likely and good scenarios tell you which line is hit first and when, or what you have if neither is |
| **One tab per investment** | Each investment in the plan gets its own tab with the same outcomes, fan chart and statistics as the portfolio |
| **Statistics** | Bad / likely / good outcome, chance of ending with less, and the past: average growth per year, yearly swings (volatility), worst fall from a peak (max drawdown), growth per unit of risk (Sharpe) |
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
    ┌───────┴────────┐
    ▼                ▼
Fan charts       Statistics
(portfolio + one tab per investment)
```

---

## Tech Stack

- **Python 3.10+**
- **Streamlit** — web UI
- **yfinance** — market data (Yahoo Finance)
- **NumPy / Pandas** — simulation and statistics
- **Plotly** — interactive charts (with a small JavaScript hook for the line → candlestick zoom)

---

## Getting Started

### Prerequisites

- Python 3.10 or newer

### Installation

```bash
git clone https://github.com/<your-username>/the-trade-sim.git
cd the-trade-sim

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
```

### Configuration

No API keys are needed. The UI is pinned to a light theme in `.streamlit/config.toml` (with a soft blue background and white cards) so chart text stays readable inside the chart frames. The logo in `assets/logo.svg` is used in the header and as the browser tab icon.

### Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Usage

The page is a single top-to-bottom flow in three numbered steps. No sidebar, no jargon: every number comes with a plain-language label, and a *Words explained* section at the bottom covers the few technical terms.

### Step 1 · Your money and your time

Enter the **amount** you'd invest and slide the **years** you could leave it invested (1–20).

### Step 2 · How do you want to play it?

Choose an **approach**. It never changes what you invest in; it sets how much gain you aim for and how much loss you'd accept, and those become the starting positions of the goal and loss-limit lines on every chart:

| Approach | Goal | Loss limit |
|---|---|---|
| *Play it safe* | +15% | −5% |
| *Balanced* (default) | +40% | −15% |
| *Aggressive* | +100% | −30% |

The choice is remembered. On the results page, if the approach and the mix don't match (playing it safe with a high-risk mix, or aggressive with a low-risk one), a note says so.

### Step 3 · Where does it go?

The mix starts at 50% bonds / 50% US stock market. Shape it however you like:

- **Sliders:** one per investment, showing the share of your money that goes there. A bar underneath shows how much of your money is assigned; the button is disabled while the total is over 100%. Below 100%, the shares are scaled up so the whole amount is invested.
- **✕** removes an investment; **Split evenly** gives every investment the same share.
- **Add an investment:** choose the kind (each with a one-line explanation), then the investment itself; only bonds ask for a country first. For stocks, ETFs and crypto you can also type any Yahoo Finance ticker (press Enter after typing). The new investment takes the share you set and the others shrink proportionally to make room; a confirmation pops up.

**Advanced settings (optional)** hides the number of scenarios (250–2,000) and the method: *Statistical model* (Monte Carlo) or *Replay real history* (bootstrap), each explained in a sentence.

Press **Show me what could happen to my $…**.

> Everything above lives in `plan_form()` in `app.py`; it returns one `plan` dictionary. A different onboarding form only needs to return the same dictionary.

### Step 4 · What could happen

For the whole mix, and then in **one tab per investment**, you get the same block:

- **Risk level** chip (Low / Medium / High / Very high, from past yearly swings) with what it means in a few words.
- **Four cards:** *If things go badly* (only 1 in 10 scenarios ends worse), *Most likely* (the middle scenario), *If things go well* (only 1 in 10 ends better), and *Chance of ending with less* than you put in.
- **One sentence** that says the same thing in words.
- **How to read this chart**, a short expandable guide.
- **The chart** with the goal / loss-limit lines and the scenario panel (below).
- **What the past 10 years looked like:** average growth per year, yearly swings, worst fall from a peak, growth per unit of risk. Each has a tooltip explaining it.

### Goal and loss limit

Every chart has two lines you can drag up and down. Hover near a line until the cursor turns into ↕, then drag. Pressing anywhere else still zooms.

- **Green line (goal):** the gain you'd be happy with. It starts at your approach's goal and snaps to the nearest precomputed level.
- **Red line (loss limit):** the loss you couldn't accept. It starts at your approach's loss limit.

Under the chart, **If you keep it for** sets how long you plan to stay invested, in months or years. It starts at the full horizon and can't exceed it. Both lines run from today to that date, and a dotted vertical line marks it.

The panel updates while you drag and when you change the duration. A scenario ends as soon as it touches either line before the check date; otherwise its value on the check date is used.

- **Three cards**, *If things go badly* (10th percentile), *Most likely* (median) and *If things go well* (90th percentile), each saying one of:
  - *You hit your loss limit* after how long, and with how much
  - *You reach your goal* after how long, and with how much
  - *Neither happens*, and what you have on the check date
- **Summary line:** the share of scenarios that reach the goal first (with the typical time), that hit the loss limit first (with the typical time), and that do neither by the check date (with the range of values then, 10th–90th percentile).

Each chart (the mix and each investment tab) has its own lines and duration.

### Zooming the charts

All charts start as a **line**. Zoom in with any of these:

- drag across the chart
- scroll wheel
- the range slider under the chart

As soon as you zoom in, the example scenario turns into **candlesticks**, and the candle unit follows the zoom so there are always about 30 candles on screen:

| Visible period | Candle unit |
|---|---|
| several years | 3 months or 1 year |
| ~2 years | 1 month |
| ~6 months | 1 week |
| ~1 month | 1 day |
| ~1–2 weeks | 1–4 hours |
| 1 day (deepest zoom) | 1 hour |

- **Smallest unit:** 1 hour. You can't zoom in to less than one day.
- **No empty gaps:** nights, weekends and holidays are hidden, so candles sit side by side.
- **Price axis:** rescales to what's on screen, bands included.
- **Zooming back out:** zooming all the way out, or double-clicking, brings the line back.

A simulation produces one value per day, so the hourly candles inside each day are drawn as random-but-repeatable movement that exactly connects that day's start and end values (a "Brownian bridge"). They illustrate a plausible intraday path; they are not a forecast.

---

## Project Structure

```
the-trade-sim/
├── app.py                  # Streamlit application (UI, data, simulation, charts)
├── requirements.txt        # Python dependencies
├── assets/
│   └── logo.svg            # Logo (header and browser tab icon)
├── .streamlit/
│   └── config.toml         # Light theme and background colours
└── README.md
```

---

## Methodology

### Monte Carlo (Geometric Brownian Motion)

Daily log-returns are modeled as a multivariate normal distribution with the historical mean vector and covariance matrix. Correlated shocks are generated with a **Cholesky decomposition** of the covariance matrix, so assets move together the way they actually do in the data. Each path compounds daily for `P × years` steps, where `P` is the number of trading days per year observed in the data: about 252 when any exchange-traded asset is in the plan, about 365 for crypto-only plans, which trade every day.

### Data preparation

Prices are downloaded from Yahoo Finance (10 years of daily OHLC, adjusted for splits and dividends). Instruments quoted in another currency are converted to USD with the matching Yahoo FX rate (e.g. `EURUSD=X`); prices quoted in pence are divided by 100 first. All instruments are then aligned to the dates they have in common.

### Historical Bootstrap

Instead of assuming a distribution, random days are sampled (with replacement) from the real historical return series and compounded. This preserves fat tails, skew, and cross-asset correlation observed in reality, and offers a useful contrast with the parametric model.

### Statistics

- **Annualized return**: `(1 + mean daily return)^P − 1`
- **Annualized volatility**: `std daily return × √P`
- **Sharpe ratio**: annualized return / annualized volatility (risk-free rate assumed 0 for simplicity)
- **Max drawdown**: largest peak-to-trough decline in the historical cumulative return
- **Probability of loss**: share of simulated paths ending below the initial investment

The portfolio's historical statistics use a buy-and-hold portfolio built with the selected weights at the start of the common history.

### Simulated portfolio

Each simulated path grows every holding separately from its initial allocation (buy and hold, no rebalancing). The portfolio is the sum of the holdings, so the per-asset fan charts come from the same paths as the portfolio fan chart. The **typical path** is the single simulated path whose final value is closest to the median.

### Target and stop-loss

For each chart, the app takes 400 of the simulated paths and a grid of 60 target levels (from +1% up to the 99th percentile of the paths' highest values) and 60 stop-loss levels (from −1% down to the 1st percentile of their lowest values). For every path and level it records the first day the path touches that level, plus each path's value at the end of every month. The browser combines these for whatever lines and duration the user picks, so the results update instantly without re-running the simulation.

- **Exit rule:** for each path, the exit is whichever line it touches first before the check date. A target exit is valued at the target level, a stop-loss exit at the stop level, and a path that touches neither at its value on the check date (month-end granularity).
- **Scenarios:** paths are ranked from worst to best exit value. Among equal exits, an earlier stop-loss counts as worse and an earlier target as better. The pessimistic, most likely and optimistic scenarios are the paths at the 10th, 50th and 90th percentile of that ranking.
- **Gaps:** barriers are checked once per simulated day. A real stop-loss order can fill below its level if the price gaps down; that slippage is not modeled.

### Candlesticks

Candles are built from the typical path. Each simulated day is filled with random-but-repeatable hourly movement that exactly connects that day's start and end values (a "Brownian bridge"), using the path's own daily volatility. Longer candles (days, weeks, months) group those hours: first, highest, lowest and last value.

---

## Limitations & Disclaimer

This is an **educational tool**, not financial advice.

- Simulations are based on historical data; the future may differ.
- The GBM model assumes normally distributed log-returns, which underestimates extreme events.
- Transaction costs, taxes, dividends timing and rebalancing are not modeled.
- The Sharpe ratio uses a 0% risk-free rate.
- All investments are analyzed over their common history only. Adding a young asset (e.g. Solana, data since 2020) shortens the history for the whole plan.
- Crypto's past growth was extreme, and the simulation extrapolates it. Plans with crypto can show very large, unrealistic upside.
- Currency conversion uses the daily closing FX rate; currency-hedging costs are not modeled.
- Candlesticks come from one representative simulated path, not from the whole distribution.
- Data quality depends on Yahoo Finance availability.

Nothing in this application constitutes a recommendation to buy or sell any security.

---

## Future Work

- **Plain-language AI explanation**, **historical backtest** and **correlation view**: built in an earlier version and removed from the dashboard for now
- **News-driven scenarios**: use Claude to read today's headlines, propose plausible macro scenarios (rate cut, tariffs, earnings miss) and apply them as shocks to the simulation
- **Custom weights** with sliders and rebalancing options
- **Events watchlist**: upcoming earnings, unusual volume, fresh news for the assets in the plan
- **Portfolio upload** (CSV) and look-through of ETF holdings
- **User accounts** to save and compare plans
- **Additional models**: GARCH volatility, regime switching, Student-t shocks for fatter tails

---

## Team

Built at ShellHacks 2026 by *Joseph Carmona, Daniele Vernaleone, Keniel Cruz Garcia*.

---

## License

MIT

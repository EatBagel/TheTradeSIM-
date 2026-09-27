# The Trade Sim

<p><img src="assets/logo.svg" width="72" alt="The Trade Sim logo"></p>

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
- [How reliable is it?](#how-reliable-is-it)
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
| **Two simulation engines** | *Statistical model*: correlated Student-t shocks (fat tails) with calm/stressed volatility regimes fitted to the data. *Replay real history*: block bootstrap of whole real months, so crashes keep their size and duration |
| **Honest expected growth** | The drift is anchored to long-run averages (stocks 7%, bonds the current 10-year Treasury yield, crypto 8%) with the past decade weighing only 25%, so no asset extrapolates a lucky decade |
| **Real-world costs** | Yearly fees, inflation (results in today's money) and dividends paid out vs reinvested |
| **What-if events** | Inject a rate cut, tariffs, bad earnings, a recession, an inflation surprise or a crypto crackdown at a chosen time, with a chosen probability; marked on the charts |
| **Fan chart** | "Most scenarios" (10–90%) and "likely zone" (25–75%) bands, the middle outcome, and one example scenario |
| **Line → candlestick zoom** | Every time chart starts as a line. Zooming in switches to candlesticks whose unit follows the zoom (years → months, a month → days, a day → hours; never smaller than 1 hour), with nights and weekends hidden |
| **Goal & loss-limit lines** | Drag a green goal line and a red loss-limit line on any chart and set how long you'd stay invested; the bad, likely and good scenarios tell you which line is hit first and when, or what you have if neither is |
| **One tab per investment** | Each investment in the plan gets its own tab with the same outcomes, fan chart and statistics as the portfolio |
| **Statistics** | Bad / likely / good outcome, chance of ending with less, and the past: average growth per year, yearly swings (volatility), worst fall from a peak (max drawdown), growth per unit of risk (Sharpe) |
| **PDF report** | Generated by the app: plan overview with the mix table and pie on page 1, then a page per chart (the mix and each investment) with outcomes, the fan chart, goal / loss-limit results and past statistics, and a closing page on the growth rates used and how much to trust the numbers |
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
- **matplotlib + fpdf2** — the PDF report

---

## Getting Started

### Prerequisites

- Python 3.10 or newer

### Installation

```bash
git clone https://github.com/EatBagel/TheTradeSIM-.git
cd TheTradeSIM-

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
matplotlib
fpdf2
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

The app opens with a short welcome that explains the four steps, then walks you through them one page at a time (back and forward buttons, a breadcrumb at the top). Every page uses plain words and tooltips; a *Words explained* section at the bottom of the report covers the few technical terms. The wizard lives in `form.py`; everything it collects ends up in one `plan` dictionary in `st.session_state.plan`, which the dashboard in `app.py` reads.

### Step 1 · Your plan

An optional **plan name**, the **amount** you'd invest, the **years** you could leave it invested (1–20), and your **approach**.

The approach never changes what you invest in; it sizes the goal and loss-limit lines that every chart starts with, in proportion to that chart's own numbers: the goal is a share of the **expected gain over your horizon**, the loss limit a multiple of the **typical yearly swing**. So a 1-year plan gets a smaller goal than a 10-year one, and a crypto chart a wider loss limit than a bond chart.

| Approach | Goal | Loss limit |
|---|---|---|
| *Play it safe* | 70% of the expected gain | 0.75× the yearly swing |
| *Balanced* (default) | 100% of the expected gain | 1.25× the yearly swing |
| *Aggressive* | 160% of the expected gain | 2× the yearly swing |

The goal is kept between +5% and +500%, the loss limit between −3% and −60%. Each chart states the resulting numbers. Example, a 50/50 bonds/stocks mix over 10 years: Play it safe +31% / −9%, Balanced +44% / −15%, Aggressive +70% / −24%.

### Step 2 · Your mix

The mix starts at 50% bonds / 50% US stock market. **Add an investment**: choose the kind (each with a one-line explanation), then the investment itself; only bonds ask for a country first. For stocks, ETFs and crypto you can also type any Yahoo Finance ticker (press Enter after typing). Set its share and press *Add*; adding a ticker that's already there replaces it.

**Your mix so far** shows a table (click a share to change it, select a row and use the trash icon to delete it) next to a pie chart. Below it, a message says whether you're over, under or exactly at 100%, with two helpers: **Split evenly** and **Scale to 100%** (keeps the proportions). *Next* only unlocks at exactly 100%.

### Step 3 · Fine-tune (optional)

Sensible defaults are set; **Skip, use the defaults** goes straight to the review. Otherwise:

- the number of scenarios (250–2,000) and the method: *Statistical model* or *Replay real history*, each explained in a sentence
- **yearly fees** (default 0.3%), **inflation** (default 2.5%) with a switch to show results in today's money (on by default), and whether **dividends are reinvested** (on by default; off means they're paid out to you and the value shown leaves them out)
- **what-if events**: pick one or more (interest-rate cut, new tariffs, bad quarterly earnings, recession, inflation surprise, crypto crackdown), when they happen and the chance they happen. They're added to the scenarios and marked on the charts with a dashed line.

### Step 4 · Review

Everything in one place: the plan facts, a table of the investments with the dollar amount each gets, and the pie chart. *Edit plan / mix / settings* jump back to the right step. Press **Show me what could happen to my $…** to run the simulation. Afterwards the wizard collapses into a one-line summary with an *Edit my plan* button, and the report appears below.

### The report

For the whole mix, and then in **one tab per investment**, you get the same block:

- **Risk level** chip (Low / Medium / High / Very high, from past yearly swings) with what it means in a few words.
- **Four cards:** *If things go badly* (only 1 in 10 scenarios ends worse), *Most likely* (the middle scenario), *If things go well* (only 1 in 10 ends better), and *Chance of ending with less* than you put in.
- **One sentence** that says the same thing in words.
- **How to read this chart**, a short expandable guide.
- **The chart** with the goal / loss-limit lines and the scenario panel (below).
- **What the past 10 years looked like:** average growth per year, yearly swings, worst fall from a peak, growth per unit of risk. Each has a tooltip explaining it.

### When the report is ready

Two buttons appear at the top right of the page (Streamlit's own toolbar is hidden):

- **Save as PDF** downloads a report generated by the app (`report.py`, matplotlib + fpdf2): page 1 is the plan overview (amount, horizon, approach, method, costs, events, the investments with their dollar amounts and a pie chart); then one page for the whole mix and one per investment, each with the risk level, the four outcomes, the fan chart with the goal and loss-limit lines at your approach's defaults, what happens to those lines over the full horizon, and what the past looked like; the last page lists the growth rates used, the model's fitted parameters, the trust notes and the glossary.
- **Start over** clears everything and goes back to the welcome page.

### Goal and loss limit

Every chart has two lines you can drag up and down. Hover near a line until the cursor turns into ↕, then drag. Pressing anywhere else still zooms.

- **Green line (goal):** the gain you'd be happy with. It starts at your approach's goal for that chart and snaps to the nearest precomputed level.
- **Red line (loss limit):** the loss you couldn't accept. It starts at your approach's loss limit for that chart.

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
├── app.py                  # Dashboard: data, simulation, charts, report
├── form.py                 # Onboarding wizard (welcome → plan → mix → fine-tune → review)
├── report.py               # PDF report (matplotlib charts + fpdf2 layout)
├── constants.py            # Catalog, approaches, what-if presets, colours, small helpers
├── requirements.txt        # Python dependencies
├── assets/
│   └── logo.svg            # Logo (header and browser tab icon)
├── .streamlit/
│   └── config.toml         # Light theme and background colours
└── README.md
```

---

## Methodology

### Statistical model (fat tails + volatility regimes)

Daily log-returns are `drift + shock`. The shocks are correlated normals (Cholesky decomposition of the historical covariance) scaled, day by day, by two factors:

- a **Student-t factor** `sqrt((ν−2)/χ²_ν)`, one draw per day shared by all assets, so extreme days are as frequent as in the data and hit every asset together. ν is fitted from the fattest excess kurtosis among the assets (`ν = 4 + 6/κ`, clamped to 3–20).
- a **calm / stressed regime multiplier** from a two-state Markov chain. Stressed days are those whose 21-day rolling cross-asset squared return exceeds 1.5× the median; their share, average run length and variance ratio are measured on the data. The multipliers keep the overall variance unchanged.

Each path compounds daily for `P × years` steps, where `P` is the number of trading days per year observed in the data: about 252 when any exchange-traded asset is in the plan, about 365 for crypto-only plans.

### Expected growth (drift)

The drift used in the scenarios is **not** the past decade's return. Per asset, in yearly terms: `blended = 0.25 × past decade + 0.75 × anchor`, clamped to `anchor ± 5%`. Anchors: stocks and ETFs 7%, real estate 6%, crypto 8%, commodities 3%, bonds the **current 10-year Treasury yield** (`^TNX`). Then fees are subtracted and, if dividends are paid out, the trailing 12-month dividend yield. The report shows the past, anchor and used rate for every investment.

### Costs, inflation, dividends

- **Fees:** a yearly rate removed from the drift (`(1 − fee)` per year).
- **Inflation:** with *today's money* on, every simulated value is deflated by the inflation accrued to that day, so the goal, loss-limit and outcome numbers are all in today's purchasing power.
- **Dividends:** prices are total-return adjusted, so reinvestment is the default. With reinvestment off, the trailing dividend yield is removed from the drift.

### What-if events

`apply_shocks()` adds a total log-return move per asset class, spread evenly over a number of days, starting at a chosen year, to a random subset of scenarios given by the probability. Presets live in `SHOCK_PRESETS`; a custom shock is a dictionary `{"size": {class: move}, "days": n, "at_years": y, "probability": p}`.

### Data preparation

Prices are downloaded from Yahoo Finance (10 years of daily OHLC, adjusted for splits and dividends). Instruments quoted in another currency are converted to USD with the matching Yahoo FX rate (e.g. `EURUSD=X`); prices quoted in pence are divided by 100 first. All instruments are then aligned to the dates they have in common.

### Replay real history (block bootstrap)

Whole blocks of 21 consecutive real trading days are copied in sequence (with wrap-around) until the horizon is filled. Blocks preserve fat tails, skew, cross-asset correlation *and* the clustering of bad days that single-day resampling destroys. The sample mean is swapped for the anchored drift above.

### Statistics

- **Annualized return**: geometric, `exp(mean daily log-return × P) − 1` (equivalent to the CAGR over the window)
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

## How reliable is it?

We back-tested the model on 20+ years of real history: at every start date (every 3 months), the model was calibrated on the previous 10 years, exactly as the app does, and the realized value 1, 3 and 5 years later was compared with the predicted bands. If the bands are honest, about 10% of outcomes should fall below "if things go badly", 10% above "if things go well", and 50% inside the likely zone.

The first back-test (drift = past decade, the original design) exposed the weaknesses; the second uses the anchored drift the app now ships with. Bands are the plain-normal ones, so this isolates the effect of the drift.

| Asset | Horizon | Below P10 (old → new) | Above P90 (old → new) | Inside 25–75 (old → new) | Predicted median (old → new) | Realized median |
|---|---|---|---|---|---|---|
| S&P 500 (SPY) | 1 y | 8% → 7% | 3% → 4% | 65% → 65% | +8% → +7% | +14% |
| S&P 500 (SPY) | 5 y | 4% → 3% | 11% → 3% | 47% → 49% | +46% → +42% | +79% |
| Gold (GLD) | 3 y | 0% → 0% | 22% → 17% | 53% → 56% | +11% → +10% | +34% |
| US bonds (BND) | 1 y | 14% → 14% | 14% → 17% | 31% → 51% | +3% → +3% | +3% |
| US bonds (BND) | 5 y | **84% → 32%** | 0% → 0% | 0% → 5% | +19% → +13% | +1% |
| Long Treasuries (TLT) | 5 y | 32% → 21% | 0% → 0% | 37% → 53% | +39% → +18% | +9% |
| Bitcoin (5-y calibration) | 3 y | 18% → 0% | 0% → 0% | **35% → 76%** | **+546% → +44%** | +149% |

What this means:

- **Broad stock funds, 1–3 years:** the bands are roughly honest (tails near 10%, the likely zone holds about half the outcomes). The tool does its job: it shows a realistic range of risk.
- **The middle outcome was the weakest number** when it was the past decade's return. Anchoring it to long-run averages fixed the worst cases: bonds no longer inherit a falling-rate decade (BND at 5 years: 84% → 32% of outcomes below the bad case) and crypto no longer extrapolates (Bitcoin at 3 years: the likely zone now holds 76% of outcomes instead of 35%). The price is a slightly conservative middle for stocks.
- **Bonds** still depend on where rates go next; the app ties their expected growth to today's 10-year yield and says so.
- **Crypto:** growth is anchored to 8% a year; the enormous swings stay. The app treats the upside as speculative.
- **5 years and beyond:** treat the results as an illustration of how wide the range of outcomes can be, not as a forecast.

Fat tails were checked separately on the S&P 500: the statistical model now produces an excess kurtosis of 22 and a 5th-percentile one-year drawdown of −29% (block bootstrap: 15 and −31%), against 15 and −34% in the real data; the old normal model gave 0 and −26%.

Fixes applied after this review:

- The *average growth per year* statistic is now a geometric (CAGR-style) rate. Compounding the arithmetic daily mean overstated volatile assets badly (Bitcoin 105% a year instead of 64%; Tesla 66% instead of 39%).
- The drift is anchored to long-run averages (see *Expected growth*), which removes the crypto extrapolation and ties bonds to today's yield.
- Both engines now produce fat tails and clustered bad stretches (Student-t + regimes, block bootstrap).
- Fees, inflation and dividends are modeled.

Still open: calibrating on more than 10 years of history where it exists, and modeling taxes.

---

## Limitations & Disclaimer

This is an **educational tool**, not financial advice.

- Simulations are based on historical data; the future may differ.
- The GBM model assumes normally distributed log-returns, which underestimates extreme events.
- Taxes, transaction costs and rebalancing are not modeled. Fees are a flat yearly rate; dividends are either fully reinvested or fully paid out.
- The Sharpe ratio uses a 0% risk-free rate.
- All investments are analyzed over their common history only. Adding a young asset (e.g. Solana, data since 2020) shortens the history for the whole plan.
- Crypto's past growth was extreme, and the simulation extrapolates it. Plans with crypto can show very large, unrealistic upside.
- Currency conversion uses the daily closing FX rate; currency-hedging costs are not modeled.
- Candlesticks come from one representative simulated path, not from the whole distribution.
- Data quality depends on Yahoo Finance availability.

The long-run anchors (7% for stocks, 8% for crypto, and so on) are assumptions, not facts; they're shown in the report so you can judge them.

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

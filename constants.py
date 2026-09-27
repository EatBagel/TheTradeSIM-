import numpy as np
import streamlit as st

ENGINES = ["Statistical model", "Replay real history"]
OTHER = "Other (type a ticker)"
# Asset class -> market / country / category -> display name -> Yahoo Finance ticker.
CATALOG = {
    "Stocks": {
        "United States": {
            "Apple (US)": "AAPL", "Microsoft (US)": "MSFT", "NVIDIA (US)": "NVDA", "Amazon (US)": "AMZN",
            "Alphabet / Google (US)": "GOOGL", "Meta (US)": "META", "Tesla (US)": "TSLA",
            "JPMorgan Chase (US)": "JPM", "Berkshire Hathaway (US)": "BRK-B", "Blackstone (US)": "BX",
        },
        "Europe": {
            "SAP (Germany)": "SAP.DE", "ASML (Netherlands)": "ASML.AS", "LVMH (France)": "MC.PA",
            "Nestlé (Switzerland)": "NESN.SW", "Shell (UK)": "SHEL.L",
        },
        "Japan": {"Toyota (Japan)": "7203.T", "Sony (Japan)": "6758.T"},
    },
    "ETFs & index funds": {
        "United States": {
            "Total US market (VTI)": "VTI", "S&P 500 (VOO)": "VOO", "Nasdaq-100 (QQQ)": "QQQ",
            "US small caps (IWM)": "IWM",
        },
        "International": {
            "Developed markets ex-US (EFA)": "EFA", "Total international (VXUS)": "VXUS",
            "Emerging markets (VWO)": "VWO",
        },
    },
    "Bonds": {
        "United States": {
            "Total bond market (BND)": "BND", "Treasuries 1–3y (SHY)": "SHY",
            "Treasuries 7–10y (IEF)": "IEF", "Treasuries 20y+ (TLT)": "TLT",
            "Inflation-protected TIPS (TIP)": "TIP", "Investment-grade corporate (LQD)": "LQD",
            "High-yield corporate (HYG)": "HYG",
        },
        "Germany": {
            "Bunds, all maturities (IS0L)": "IS0L.DE", "Bunds 0–1y (EXVM)": "EXVM.DE",
            "Bunds 10.5y+ (EXX6)": "EXX6.DE",
        },
        "Eurozone": {
            "Government bonds (EUNH)": "EUNH.DE", "Government 1–3y (IBGS)": "IBGS.MI",
            "Government 7–10y (SXRQ)": "SXRQ.DE", "Government 15–30y (IBGL)": "IBGL.L",
            "Inflation-linked government (IBCI)": "IBCI.MI", "Corporate bonds (IEAC)": "IEAC.L",
        },
        "United Kingdom": {"Gilts (IGLT)": "IGLT.L", "Index-linked gilts (INXG)": "INXG.L"},
        "Japan": {"Japanese bonds, NOMURA-BPI (2510)": "2510.T"},
        "International": {
            "International ex-US, USD hedged (BNDX)": "BNDX",
            "International government (BWX)": "BWX",
            "Emerging markets, USD (EMB)": "EMB",
        },
    },
    "Crypto": {
        "Cryptocurrencies": {
            "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "XRP": "XRP-USD",
            "BNB": "BNB-USD", "Cardano": "ADA-USD", "Dogecoin": "DOGE-USD",
        },
    },
    "Commodities": {
        "Commodity ETFs": {"Gold (GLD)": "GLD", "Silver (SLV)": "SLV", "Oil (USO)": "USO",
                           "Broad commodities (DBC)": "DBC"},
    },
    "Real estate": {
        "REIT ETFs": {"US real estate (VNQ)": "VNQ", "International real estate (VNQI)": "VNQI"},
    },
}
ALLOW_OTHER = {"Stocks", "ETFs & index funds", "Crypto"}
TICKER_INFO = {t: (name, cls) for cls, groups in CATALOG.items()
               for items in groups.values() for name, t in items.items()}

BLUE = "#2a78d6"
BAND_OUTER = "rgba(42,120,214,0.12)"
BAND_INNER = "rgba(42,120,214,0.26)"
INK_2 = "#52514e"
INK_MUTED = "#8a8984"
UP = "#1baf7a"
DOWN = "#e34948"
TARGET_COLOR = "#008300"
STOP_COLOR = "#e34948"

# What-if events: total move (log return) per asset class, spread evenly over `days`.
SHOCK_PRESETS = {
    "Interest-rate cut": {"blurb": "The central bank cuts rates: bonds and real estate rally, stocks get a lift.",
                          "days": 5, "size": {"Bonds": 0.03, "Real estate": 0.04, "Stocks": 0.02, "ETFs & index funds": 0.02}},
    "New tariffs / trade war": {"blurb": "Trade barriers hit companies' profits.", "days": 10,
                                "size": {"Stocks": -0.08, "ETFs & index funds": -0.07, "Commodities": -0.03, "Crypto": -0.05}},
    "Bad quarterly earnings": {"blurb": "The companies you hold report a bad quarter.", "days": 2, "size": {"Stocks": -0.12}},
    "Recession": {"blurb": "A downturn like 2008 or 2020, spread over three months.", "days": 90,
                  "size": {"Stocks": -0.30, "ETFs & index funds": -0.25, "Real estate": -0.25, "Crypto": -0.45,
                           "Commodities": -0.15, "Bonds": 0.04}},
    "Inflation surprise": {"blurb": "Prices rise faster than expected and rates go up.", "days": 20,
                           "size": {"Bonds": -0.06, "Stocks": -0.06, "ETFs & index funds": -0.06, "Real estate": -0.08,
                                    "Commodities": 0.05}},
    "Crypto crackdown": {"blurb": "Regulators or an exchange failure hit crypto.", "days": 7, "size": {"Crypto": -0.35}},
}

STARTING_MIX = {"BND": 50, "VTI": 50}
# The approach doesn't pick investments; it sizes the default goal / loss-limit lines on every chart relative
# to that chart's own expected gain over the horizon (goal_k) and its typical yearly swing (stop_k).
APPROACHES = {
    "Play it safe": {"goal_k": 0.7, "stop_k": 0.75,
                     "blurb": "Settle for part of the expected gain, and get out at the first real dip."},
    "Balanced": {"goal_k": 1.0, "stop_k": 1.25,
                 "blurb": "Aim for the expected gain, and sit through a normal bad year."},
    "Aggressive": {"goal_k": 1.6, "stop_k": 2.0,
                   "blurb": "Aim well above the expected gain, and sit through a crash to get there."},
}

CLASS_BLURB = {
    "Stocks": "a share of one company",
    "ETFs & index funds": "a basket of many companies in one product",
    "Bonds": "loans to governments or companies; steadier, lower growth",
    "Crypto": "digital currencies; very large swings",
    "Commodities": "gold, oil and other raw materials",
    "Real estate": "funds that own buildings",
}


def money(v: float) -> str:
    return f"${v:,.0f}"


def pct(v: float) -> str:
    return f"{v:.1%}"


def mdm(v: float) -> str:
    """Money for st.markdown text, where a bare $ would start a math formula."""
    return money(v).replace("$", "\\$")


def step_header(number: int, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:12px;margin:6px 0 2px;">'
        f'<span style="background:{BLUE};color:#fff;border-radius:50%;width:28px;height:28px;display:inline-flex;'
        f'align-items:center;justify-content:center;font-weight:700;">{number}</span>'
        f'<span style="font-size:1.35rem;font-weight:700;">{title}</span></div>'
        f'<div style="color:{INK_2};margin-bottom:10px;">{subtitle}</div>', unsafe_allow_html=True)


def approach_levels(approach: dict, expected_gain: float, yearly_swing: float) -> tuple[float, float]:
    """Default goal and loss-limit fractions for one chart: a share of its expected gain over the horizon,
    and a multiple of its typical yearly swing, kept within sensible bounds."""
    goal = float(np.clip(approach["goal_k"] * expected_gain, 0.05, 5.0))
    stop = float(np.clip(approach["stop_k"] * yearly_swing, 0.03, 0.6))
    return goal, stop
GLOSSARY = [
    ("Scenario", "One possible future the simulator plays out. We run thousands and look at how they spread."),
    ("Most scenarios / likely zone", "The light band holds 8 in 10 scenarios; the darker band holds the middle half."),
    ("Most likely", "The middle result: half the scenarios end higher, half end lower."),
    ("If things go badly / well", "The result that only 1 in 10 scenarios is worse than, or better than."),
    ("Yearly swings", "How much the value typically moves up or down in a year. Also called volatility."),
    ("Worst fall from a peak", "The biggest drop from a high point to a low point in the past. Also called maximum drawdown."),
    ("Goal / loss limit", "The gain you'd sell at, and the loss you wouldn't accept. Traders call them target and stop-loss."),
    ("Bonds", "You lend money to a government or company and get it back with interest. Usually steadier than stocks."),
    ("ETF / index fund", "A single product that holds many stocks or bonds at once, so you're spread out."),
]


def risk_level(ann_vol: float) -> tuple[str, str, str]:
    """(label, color, plain-language meaning) from historical yearly swings."""
    if ann_vol < 0.07:
        return "Low", UP, "small ups and downs; slow, steady changes"
    if ann_vol < 0.15:
        return "Medium", "#eda100", "noticeable ups and downs; a bad year can hurt"
    if ann_vol < 0.30:
        return "High", "#eb6834", "big ups and downs; expect some scary drops"
    return "Very high", DOWN, "wild ups and downs; you could lose a large part of it"

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from pandas.tseries.holiday import USFederalHolidayCalendar

from constants import (APPROACHES, GLOSSARY, approach_levels, risk_level, BAND_INNER, BAND_OUTER, BLUE, DOWN, ENGINES, INK_2, INK_MUTED, SHOCK_PRESETS,
                       STOP_COLOR, TARGET_COLOR, UP, mdm, money, pct, step_header)
from form import plan_wizard
from report import build_pdf, line_outcomes

MIN_SPAN_HOURS = 24  # deepest zoom: one day of 1-hour candles
TARGET_CANDLES = 30
MAX_CANDLES = 60


PANEL_HEIGHT = 185
CARD_MIN_HEIGHT = 128  # room under each chart for the duration input and the target / stop-loss scenario panel

# Toggles traces tagged meta="line" / meta="candle" based on the visible x-span,
# and refits the y-axis to the visible data (y is fixed so zoom is x-only).
ZOOM_JS = """
var gd = document.getElementById('{plot_id}');
var BASE = __BASE__;
var H = 3600000, D = 86400000;
var MIN_SPAN = __MIN_SPAN__ * H, MAX_CANDLES = __MAX_CANDLES__, TARGET_CANDLES = __TARGET_CANDLES__;
var LADDER = [H, 2 * H, 4 * H, D, 7 * D, 30 * D, 91 * D, 365 * D];
var LABELS = ['1 hour', '2 hours', '4 hours', '1 day', '1 week', '1 month', '3 months', '1 year'];
var FULL = null;  // span of the initial, fully zoomed-out view; anything narrower shows candles
var snappedBucket;
var candleIdx = -1, lineIdx = [];
gd.data.forEach(function (t, i) {
  if (t.meta === 'candle') candleIdx = i; else if (t.meta === 'line') lineIdx.push(i);
});

function toMs(v) { return typeof v === 'number' ? v : Date.parse(String(v).replace(' ', 'T') + (String(v).length > 10 ? 'Z' : '')); }
function fmt(ms) { return new Date(ms).toISOString().slice(0, 23).replace('T', ' '); }
function lb(arr, v) { var lo = 0, hi = arr.length; while (lo < hi) { var m = (lo + hi) >> 1; if (arr[m] < v) lo = m + 1; else hi = m; } return lo; }
function slice(lv, a, b) {
  var i = lb(lv.t, a), j = lb(lv.t, b);
  return {t: lv.t.slice(i, j), o: lv.o.slice(i, j), h: lv.h.slice(i, j), l: lv.l.slice(i, j), c: lv.c.slice(i, j)};
}

// Simulated paths are daily; intraday bars are a seeded Brownian bridge between consecutive daily values.
function rng(seed) {
  return function () {
    seed = (seed + 0x6D2B79F5) | 0;
    var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function gauss(r) { return Math.sqrt(-2 * Math.log(1 - r())) * Math.cos(2 * Math.PI * r()); }
function simBars(a, b) {
  var S = BASE, n = S.hours.length, sub = 4, m = n * sub, sd = S.sigma / Math.sqrt(m);
  var out = {t: [], o: [], h: [], l: [], c: []};
  var i0 = Math.max(1, lb(S.days, a - D)), i1 = Math.min(S.days.length - 1, lb(S.days, b + D));
  for (var i = i0; i <= i1; i++) {
    var r = rng(S.seed * 100003 + i), x0 = Math.log(S.close[i - 1]), x1 = Math.log(S.close[i]);
    var w = [0];
    for (var k = 1; k <= m; k++) w.push(w[k - 1] + gauss(r) * sd);
    var prev = S.close[i - 1];
    for (var j = 0; j < n; j++) {
      var o = prev, hi = o, lo = o, c = o;
      for (var s = 1; s <= sub; s++) {
        var q = j * sub + s, f = q / m;
        c = Math.exp(x0 + w[q] - f * w[m] + f * (x1 - x0));
        if (c > hi) hi = c; if (c < lo) lo = c;
      }
      var t = S.days[i] + S.hours[j] * 60000;
      if (t >= a && t < b) { out.t.push(t); out.o.push(o); out.h.push(hi); out.l.push(lo); out.c.push(c); }
      prev = c;
    }
  }
  return out;
}

function keyOf(t, B) {
  if (B < D) return Math.floor(t / B) * B;
  var day = Math.floor(t / D);
  if (B === D) return day * D;
  if (B === 7 * D) return (Math.floor((day + 3) / 7) * 7 - 3) * D;
  var d = new Date(day * D), mo = d.getUTCMonth();
  if (B === 365 * D) return Date.UTC(d.getUTCFullYear(), 0, 1);
  if (B === 91 * D) mo -= mo % 3;
  return Date.UTC(d.getUTCFullYear(), mo, 1);
}
function countBuckets(ts, B) {
  var n = 0, prev = null;
  for (var i = 0; i < ts.length; i++) { var k = keyOf(ts[i], B); if (k !== prev) { n++; prev = k; } }
  return n;
}
// Bucket whose visible candle count is closest to TARGET_CANDLES (a month -> days, two years -> months,
// a day -> hours). Bars extend one window-width past each edge so edge gaps get hidden and panning is smooth.
function choose(a, b, only) {
  var bars = simBars(a - (b - a), b + (b - a)), view = slice(bars, a, b).t;
  var best = null;
  for (var i = 0; i < LADDER.length; i++) {
    if (only !== undefined && i !== only) continue;
    var n = countBuckets(view, LADDER[i]);
    var score = n === 0 ? Infinity : n > MAX_CANDLES ? 1e6 + n : Math.abs(n - TARGET_CANDLES);
    if (!best || score < best.score) best = {i: i, bars: bars, score: score};
  }
  return best;
}
// Aggregates bars into buckets and lists the empty stretches (nights, weekends) to hide from the axis.
function aggregate(bars, B) {
  var out = {x: [], o: [], h: [], l: [], c: [], k: [], breaks: []};
  for (var i = 0; i < bars.t.length; i++) {
    var k = keyOf(bars.t[i], B), n = out.k.length - 1;
    if (n < 0 || out.k[n] !== k) {
      out.k.push(k); out.x.push(k + B / 2);
      out.o.push(bars.o[i]); out.h.push(bars.h[i]); out.l.push(bars.l[i]); out.c.push(bars.c[i]);
    } else {
      if (bars.h[i] > out.h[n]) out.h[n] = bars.h[i];
      if (bars.l[i] < out.l[n]) out.l[n] = bars.l[i];
      out.c[n] = bars.c[i];
    }
  }
  if (B <= D) {
    for (var j = 0; j + 1 < out.k.length; j++) {
      var end = out.k[j] + B;
      if (out.k[j + 1] > end) out.breaks.push({bounds: [end, out.k[j + 1]]});
    }
  }
  return out;
}
// Fits the outcome bands and median in both modes, plus the candles or the typical-path line.
function fitY(a, b, agg) {
  var lo = Infinity, hi = -Infinity;
  function take(v) { if (v < lo) lo = v; if (v > hi) hi = v; }
  gd.data.forEach(function (t, i) {
    if (i === candleIdx || !t.x || !t.y || t.visible === 'legendonly') return;
    if (agg && t.meta === 'line') return;
    for (var j = 0; j < t.x.length; j++) { var d = toMs(t.x[j]); if (d >= a && d <= b) take(t.y[j]); }
  });
  if (agg) {
    for (var j = 0; j < agg.x.length; j++) if (agg.x[j] >= a && agg.x[j] <= b) { take(agg.l[j]); take(agg.h[j]); }
  }
  take(BR.up[level.target]); take(BR.down[level.stop]);
  if (!(lo < hi)) return null;
  var pad = (hi - lo) * 0.06;
  return [lo - pad * 1.5, hi + pad];
}

function update(range) {
  var a = toMs(range[0]), b = toMs(range[1]);
  if (snappedBucket === undefined && b - a < MIN_SPAN) {
    var mid = (a + b) / 2;
    Plotly.relayout(gd, {'xaxis.range': [fmt(mid - MIN_SPAN / 2), fmt(mid + MIN_SPAN / 2)]});
    return;
  }
  if (FULL === null) FULL = b - a;
  var agg = null, layout = {};
  if (candleIdx >= 0 && b - a < FULL * 0.95) {
    var forced = snappedBucket;
    snappedBucket = undefined;
    var ch = choose(a, b, forced);
    agg = aggregate(ch.bars, LADDER[ch.i]);
    // A view edge inside a hidden stretch breaks Plotly's axis, so snap it to the nearest visible time
    // (once; the follow-up pass keeps the same bucket so it can't loop).
    if (forced === undefined) {
      var na = a, nb = b;
      agg.breaks.forEach(function (br) {
        if (na > br.bounds[0] && na < br.bounds[1]) na = br.bounds[1];
        if (nb > br.bounds[0] && nb < br.bounds[1]) nb = br.bounds[0];
      });
      if (nb <= na) nb = na + (b - a);
      if (na !== a || nb !== b) {
        snappedBucket = ch.i;
        Plotly.relayout(gd, {'xaxis.range': [fmt(na), fmt(nb)]});
        return;
      }
    }
    // Times go to Plotly as naive date strings, like every other trace; numeric dates get shifted
    // into the browser's timezone, which misaligns candles, gaps and labels.
    Plotly.restyle(gd, {x: [agg.x.map(fmt)], open: [agg.o], high: [agg.h], low: [agg.l], close: [agg.c],
                        visible: true, name: 'Example scenario · ' + LABELS[ch.i]}, [candleIdx]);
    if (lineIdx.length) Plotly.restyle(gd, {visible: false}, lineIdx);
    layout['xaxis.rangebreaks'] = agg.breaks.map(function (br) { return {bounds: br.bounds.map(fmt)}; });
  } else {
    if (candleIdx >= 0) Plotly.restyle(gd, {visible: false}, [candleIdx]);
    if (lineIdx.length) Plotly.restyle(gd, {visible: true}, lineIdx);
    layout['xaxis.rangebreaks'] = [];
  }
  var y = fitY(a, b, agg);
  if (y) layout['yaxis.range'] = y;
  Plotly.relayout(gd, layout);
}
// ---- Target (green) and stop-loss (red) lines, checked within a user-chosen duration ----
// Each line snaps to a precomputed level; for every simulated path we know when it first touches each level
// and its value at the end of every month, so any target / stop-loss / duration is evaluated here instantly:
// whichever line a path touches first (before the check date) ends it, otherwise we read its value then.
var BR = BASE.barriers, INV = BASE.invested, MONTHS = BR.month_steps.length;
var TARGET = '__TARGET_COLOR__', STOP = '__STOP_COLOR__';
var level = {target: nearest(BR.up, INV * (1 + BASE.goal)), stop: nearest(BR.down, INV * (1 - BASE.stop)), months: MONTHS};
var drag = null, GRAB_PX = 8;

function nearest(arr, v) {
  var best = 0;
  for (var i = 1; i < arr.length; i++) if (Math.abs(arr[i] - v) < Math.abs(arr[best] - v)) best = i;
  return best;
}
function money(v) { return '$' + Math.round(v).toLocaleString('en-US'); }
function signedPct(v) { var p = (v / INV - 1) * 100; return (p >= 0 ? '+' : '−') + Math.abs(p).toFixed(0) + '%'; }
function duration(steps) {
  var years = steps / BASE.ppy;
  if (years < 1 / 12) return Math.max(1, Math.round(years * 365)) + ' days';
  if (years < 1) return Math.round(years * 12) + ' months';
  return years.toFixed(1) + ' years';
}
function monthsLabel(m) {
  if (m % 12 === 0) return (m / 12) + (m === 12 ? ' year' : ' years');
  return m < 12 ? m + (m === 1 ? ' month' : ' months') : (m / 12).toFixed(1) + ' years';
}
function checkStep() { return BR.month_steps[level.months - 1]; }
function checkDateMs() { return BASE.days[checkStep()]; }
function quantile(arr, f) {
  var a = arr.slice().sort(function (x, y) { return x - y; });
  return a[Math.round(f * (a.length - 1))];
}
function outcomes() {
  var iu = level.target, id = level.stop, end = checkStep(), finals = BR.monthly[level.months - 1], out = [];
  for (var p = 0; p < finals.length; p++) {
    var tu = BR.up_t[iu][p], td = BR.down_t[id][p];
    if (tu > end) tu = -1;
    if (td > end) td = -1;
    if (tu >= 0 && (td < 0 || tu < td)) out.push({kind: 'target', t: tu, v: BR.up[iu]});
    else if (td >= 0) out.push({kind: 'stop', t: td, v: BR.down[id]});
    else out.push({kind: 'none', t: end, v: finals[p]});
  }
  // Worst to best by exit value; among equal exits an earlier stop is worse and an earlier target is better.
  out.sort(function (x, y) {
    if (x.v !== y.v) return x.v - y.v;
    return x.kind === 'stop' ? x.t - y.t : y.t - x.t;
  });
  return out;
}
function describe(o) {
  if (o.kind === 'target') return {color: TARGET, head: 'You reach your goal', body: 'after ' + duration(o.t) + ', with ' + money(o.v)};
  if (o.kind === 'stop') return {color: STOP, head: 'You hit your loss limit', body: 'after ' + duration(o.t) + ', with ' + money(o.v)};
  return {color: '#52514e', head: 'Neither happens',
          body: 'you have ' + money(o.v) + ' (' + signedPct(o.v) + ') after ' + monthsLabel(level.months)};
}

// Panel: a static controls row (so typing isn't interrupted) and a results area redrawn on every change.
var panel = document.createElement('div');
panel.style.cssText = 'font-family:-apple-system,"Segoe UI",Roboto,sans-serif;color:#0b0b0b;font-size:13px;padding:4px 10px 0;';
var inputCss = 'font:inherit;padding:2px 6px;border:1px solid #c3c2b7;border-radius:4px;';
panel.innerHTML =
  '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;color:#52514e;margin-bottom:8px;">' +
  '<span>Drag the <b style="color:' + TARGET + '">green line</b> to the gain you would be happy with, and the <b style="color:' + STOP +
  '">red line</b> to the loss you could not accept.</span>' +
  '<span style="margin-left:auto;">If you keep it for <input class="dur" type="number" min="1" step="1" style="width:64px;' +
  inputCss + '"> <select class="unit" style="' + inputCss + '"><option value="1">months</option>' +
  '<option value="12">years</option></select> <span class="max"></span></span></div>' +
  '<div class="results"></div>';
gd.parentNode.appendChild(panel);
var durInput = panel.querySelector('.dur'), unitSel = panel.querySelector('.unit'), results = panel.querySelector('.results');
panel.querySelector('.max').textContent = '(max ' + monthsLabel(MONTHS) + ')';
if (MONTHS % 12 === 0) { unitSel.value = '12'; durInput.value = MONTHS / 12; } else { unitSel.value = '1'; durInput.value = MONTHS; }
function onDuration() {
  var m = Math.round(parseFloat(durInput.value) * parseInt(unitSel.value, 10));
  if (!(m >= 1)) return;
  level.months = Math.min(MONTHS, m);
  applyLevels(true);
}
durInput.addEventListener('change', onDuration);
unitSel.addEventListener('change', onDuration);

function renderResults() {
  var o = outcomes(), n = o.length, when = monthsLabel(level.months);
  var cards = [['If things go badly', 0.1], ['Most likely', 0.5], ['If things go well', 0.9]].map(function (pick) {
    var d = describe(o[Math.round(pick[1] * (n - 1))]);
    return '<div style="flex:1;border:1px solid #e4e3df;border-left:4px solid ' + d.color +
           ';border-radius:6px;padding:8px 10px;background:#fff;">' +
           '<div style="color:#52514e;font-size:12px;">' + pick[0] + '</div>' +
           '<div style="font-weight:600;margin:2px 0;color:' + d.color + ';">' + d.head + '</div>' +
           '<div>' + d.body + '</div></div>';
  }).join('');
  var tTimes = o.filter(function (k) { return k.kind === 'target'; }).map(function (k) { return k.t; });
  var sTimes = o.filter(function (k) { return k.kind === 'stop'; }).map(function (k) { return k.t; });
  var rest = o.filter(function (k) { return k.kind === 'none'; }).map(function (k) { return k.v; });
  function share(k) { return k > 0 && k * 100 < n ? '<1%' : Math.round(100 * k / n) + '%'; }
  var stats = [
    '<span style="color:' + TARGET + '">●</span> Goal reached first: <b>' + share(tTimes.length) + '</b>' +
      (tTimes.length ? ' of scenarios, typically after ' + duration(quantile(tTimes, 0.5)) : ''),
    '<span style="color:' + STOP + '">●</span> Loss limit hit first: <b>' + share(sTimes.length) + '</b>' +
      (sTimes.length ? ', typically after ' + duration(quantile(sTimes, 0.5)) : ''),
    '<span style="color:#8a8984">●</span> Neither within ' + when + ': <b>' + share(rest.length) + '</b>' +
      (rest.length ? ', ending with between ' + money(quantile(rest, 0.1)) + ' and ' + money(quantile(rest, 0.9)) : ''),
  ].map(function (t) { return '<span style="display:inline-block;margin-right:18px;">' + t + '</span>'; }).join('');
  results.innerHTML = '<div style="display:flex;gap:8px;">' + cards + '</div>' +
                      '<div style="margin-top:8px;line-height:1.7;">' + stats + '</div>';
}

// Redraws the two lines from today to the check date, the check-date marker, and the results.
function applyLevels(refit) {
  var x0 = fmt(BASE.days[0]), x1 = fmt(checkDateMs()), upd = {};
  [[0, BR.up[level.target], 'Goal '], [1, BR.down[level.stop], 'Loss limit ']].forEach(function (e) {
    var k = 'shapes[' + e[0] + ']';
    upd[k + '.y0'] = e[1]; upd[k + '.y1'] = e[1]; upd[k + '.x0'] = x0; upd[k + '.x1'] = x1;
    upd[k + '.label.text'] = e[2] + money(e[1]) + ' (' + signedPct(e[1]) + ')';
  });
  upd['shapes[2].x0'] = x1; upd['shapes[2].x1'] = x1;
  upd['shapes[2].label.text'] = 'You check on ' + new Date(checkDateMs()).toISOString().slice(0, 7);
  var p = Plotly.relayout(gd, upd);
  if (refit) p.then(function () { update(gd._fullLayout.xaxis.range); });
  renderResults();
}

// Custom drag: a press within GRAB_PX of a line (left of the check date) moves that line instead of
// starting a zoom box, so the thin lines are easy to grab.
function lineUnder(ev) {
  var L = gd._fullLayout, s = L._size, rect = gd.getBoundingClientRect();
  var x = ev.clientX - rect.left - s.l, y = ev.clientY - rect.top - s.t;
  if (x < 0 || x > s.w || y < -GRAB_PX || y > s.h + GRAB_PX) return -1;
  if (x > L.xaxis.d2p(fmt(checkDateMs())) + GRAB_PX) return -1;
  var best = -1, bestD = GRAB_PX + 1;
  [BR.up[level.target], BR.down[level.stop]].forEach(function (v, i) {
    var d = Math.abs(L.yaxis.l2p(v) - y);
    if (d < bestD) { bestD = d; best = i; }
  });
  return best;
}
gd.addEventListener('mousedown', function (ev) {
  var i = lineUnder(ev);
  if (i < 0) return;
  ev.stopPropagation(); ev.preventDefault();
  drag = i;
}, true);
document.addEventListener('mousemove', function (ev) {
  if (drag === null) {
    var cover = gd.querySelector('.nsewdrag');
    if (cover) cover.style.cursor = lineUnder(ev) >= 0 ? 'ns-resize' : '';
    return;
  }
  var L = gd._fullLayout, v = L.yaxis.p2l(ev.clientY - gd.getBoundingClientRect().top - L._size.t);
  var key = drag === 0 ? 'target' : 'stop', idx = nearest(drag === 0 ? BR.up : BR.down, v);
  if (idx !== level[key]) { level[key] = idx; applyLevels(false); }
});
document.addEventListener('mouseup', function () {
  if (drag === null) return;
  drag = null;
  applyLevels(true);
});

gd.on('plotly_relayout', function (ev) {
  if (ev['xaxis.range[0]'] !== undefined) update([ev['xaxis.range[0]'], ev['xaxis.range[1]']]);
  else if (ev['xaxis.range']) update(ev['xaxis.range']);
  else if (ev['xaxis.autorange']) update(gd._fullLayout.xaxis.range);
});
update(gd._fullLayout.xaxis.range);
applyLevels(true);

// Size the surrounding iframe to the content so no inner scrollbar appears, on screen or when printing.
// Measures chart + panel explicitly: the document itself is never shorter than the frame, so measuring
// it would grow the frame forever.
function fitFrame() {
  var f = window.frameElement;
  if (f) f.style.height = Math.ceil(gd.getBoundingClientRect().height + panel.getBoundingClientRect().height + 24) + 'px';
}
new ResizeObserver(fitFrame).observe(panel);
fitFrame();
"""


# ---------- data ----------

OHLC = ["Open", "High", "Low", "Close"]


@st.cache_data(ttl=86400, show_spinner=False)
def ticker_currency(ticker: str) -> str:
    try:
        return yf.Ticker(ticker).fast_info["currency"] or "USD"
    except Exception:
        return "USD"


@st.cache_data(ttl=86400, show_spinner=False)
def fx_to_usd(currency: str) -> pd.Series:
    fx = yf.download(f"{currency}USD=X", period="10y", auto_adjust=True, progress=False)["Close"]
    fx = (fx.iloc[:, 0] if isinstance(fx, pd.DataFrame) else fx).dropna()
    return fx[~fx.index.duplicated()]


def to_usd(df: pd.DataFrame, currency: str, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Converts each row with the FX close of its (naive, local) calendar day in `days`."""
    scale = 1.0
    if currency == "GBp":  # London quotes some securities in pence
        currency, scale = "GBP", 0.01
    if currency == "USD":
        return df * scale
    fx = fx_to_usd(currency)
    rate = fx.reindex(fx.index.union(days.unique())).ffill().bfill().reindex(days).to_numpy()
    return df.mul(rate * scale, axis=0)


def pick(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    try:
        df = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
    except KeyError:
        return None
    df = df[OHLC].dropna()
    return None if df.empty else df


@st.cache_data(ttl=3600, show_spinner=False)
def load_ohlc(tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Daily OHLC in USD, restricted to the dates every ticker has data for."""
    raw = yf.download(list(tickers), period="10y", auto_adjust=True, progress=False, group_by="ticker")
    out = {}
    for t in tickers:
        df = pick(raw, t)
        if df is None:
            continue
        df = to_usd(df, ticker_currency(t), df.index).dropna()
        if not df.empty:
            out[t] = df
    if out:
        common = sorted(set.intersection(*(set(df.index) for df in out.values())))
        out = {t: df.loc[common] for t, df in out.items()}
    return out


def periods_per_year(index: pd.DatetimeIndex) -> float:
    """~252 for exchange-traded assets, ~365 for crypto-only plans."""
    return len(index) / ((index[-1] - index[0]).days / 365.25)


# ---------- simulation ----------

def summarize_paths(paths: np.ndarray) -> dict:
    finals = paths[:, -1]
    typical = paths[np.argmin(np.abs(finals - np.median(finals)))]
    return {
        "pct": np.percentile(paths, [10, 25, 50, 75, 90], axis=0),
        "typical": typical,
        "finals": finals,
    }


def barrier_grid(paths: np.ndarray, invested: float, ppy: float, n_paths: int = 400, n_levels: int = 60) -> dict:
    """For a grid of target levels above and stop levels below `invested`, the step at which each path first
    touches the level (-1 = never), plus each path's value at the end of every month, so the browser can
    evaluate any target / stop-loss / duration the user picks."""
    p = paths[:n_paths]
    run_max = np.maximum.accumulate(p, axis=1)
    run_min = np.minimum.accumulate(p, axis=1)
    top = float(np.clip(np.percentile(run_max[:, -1], 99) / invested, 1.1, 50))
    bottom = float(np.clip(np.percentile(run_min[:, -1], 1) / invested, 0.02, 0.9))
    up = invested * np.geomspace(1.01, top, n_levels)
    down = invested * np.geomspace(0.99, bottom, n_levels)
    steps = p.shape[1]
    up_t = np.array([np.searchsorted(m, up, side="left") for m in run_max]).T
    down_t = np.array([np.searchsorted(-m, -down, side="left") for m in run_min]).T
    up_t[up_t >= steps] = -1
    down_t[down_t >= steps] = -1
    months = max(1, round((steps - 1) / ppy * 12))
    month_steps = np.minimum(np.round(np.arange(1, months + 1) * (steps - 1) / months).astype(int), steps - 1)
    return {
        "up": np.round(up, 2).tolist(), "down": np.round(down, 2).tolist(),
        "up_t": up_t.tolist(), "down_t": down_t.tolist(),
        "month_steps": month_steps.tolist(), "monthly": np.round(p[:, month_steps].T).astype(int).tolist(),
    }


LONG_RUN_RETURN = {  # yearly growth the drift is pulled toward; bonds use the current 10-year Treasury yield instead
    "Stocks": 0.07, "ETFs & index funds": 0.07, "Crypto": 0.08, "Commodities": 0.03, "Real estate": 0.06, "Other": 0.06,
}
SAMPLE_WEIGHT = 0.25  # how much the past decade counts versus the long-run anchor
DRIFT_BAND = 0.05     # the drift can't stray more than this from the anchor
BLOCK_DAYS = 21       # block bootstrap: one trading month per block

@st.cache_data(ttl=86400, show_spinner=False)
def treasury_yield() -> float:
    """Current 10-year US Treasury yield, the long-run anchor for bonds."""
    try:
        y = float(np.asarray(yf.download("^TNX", period="1mo", auto_adjust=True, progress=False)["Close"].dropna())[-1]) / 100
        return y if 0 < y < 0.2 else 0.04
    except Exception:
        return 0.04


@st.cache_data(ttl=86400, show_spinner=False)
def dividend_yield(ticker: str) -> float:
    """Dividends paid over the last 12 months as a share of the price."""
    try:
        tk = yf.Ticker(ticker)
        d = tk.dividends
        if d.empty:
            return 0.0
        paid = float(d[d.index >= d.index[-1] - pd.Timedelta(days=365)].sum())
        return float(np.clip(paid / float(tk.fast_info["last_price"]), 0, 0.15))
    except Exception:
        return 0.0


def anchored_drift(mu_sample: np.ndarray, ppy: float, classes: tuple, bond_yield: float, fee: float,
                   payout: tuple) -> tuple[np.ndarray, list[dict]]:
    """Per-step log drift per asset: the past decade's growth shrunk toward a long-run anchor and kept within
    ±DRIFT_BAND of it, minus yearly fees and, when dividends aren't reinvested, the dividend yield."""
    used, info = [], []
    for m, cls, py in zip(mu_sample, classes, payout):
        past = float(np.exp(m * ppy) - 1)
        anchor = bond_yield if cls == "Bonds" else LONG_RUN_RETURN.get(cls, LONG_RUN_RETURN["Other"])
        blended = float(np.clip(SAMPLE_WEIGHT * past + (1 - SAMPLE_WEIGHT) * anchor,
                                anchor - DRIFT_BAND, anchor + DRIFT_BAND))
        net = (1 + blended) * (1 - fee) / (1 + py) - 1
        used.append(np.log1p(net) / ppy)
        info.append({"past": past, "anchor": anchor, "blended": blended, "net": net})
    return np.array(used, np.float32), info


def calibrate(lr: np.ndarray) -> dict:
    """Fat-tail and calm/stressed-regime parameters from daily log returns of shape (T, n)."""
    mu = lr.mean(axis=0)
    cov = np.atleast_2d(np.cov(lr, rowvar=False))
    z = (lr - mu) / np.sqrt(np.diag(cov))
    kurt = float(((z ** 4).mean(axis=0) - 3).max())          # fattest tail among the assets
    nu = float(np.clip(4 + 6 / max(kurt, 1e-6), 3.0, 20.0))  # Student-t degrees of freedom with that kurtosis
    s2 = (z ** 2).mean(axis=1)                                # how big each day was, across assets
    rolling = pd.Series(s2).rolling(BLOCK_DAYS, min_periods=5).mean().bfill().to_numpy()
    stressed = rolling > 1.5 * np.median(rolling)
    p_s = float(np.clip(stressed.mean(), 0.02, 0.6))
    edges = np.flatnonzero(np.diff(np.r_[0, stressed.astype(int), 0]))
    mean_len = float(np.mean(edges[1::2] - edges[::2])) if len(edges) >= 2 else 15.0
    stay_s = 1 - 1 / max(mean_len, 2.0)
    stay_c = 1 - p_s * (1 - stay_s) / (1 - p_s)
    total = s2.mean()  # multipliers keep the overall variance unchanged
    m_s = float(np.sqrt(s2[stressed].mean() / total)) if stressed.any() else 1.0
    m_c = float(np.sqrt(s2[~stressed].mean() / total)) if (~stressed).any() else 1.0
    return {"mu": mu, "cov": cov, "nu": nu, "p_s": p_s, "stay_s": stay_s, "stay_c": stay_c,
            "m_s": m_s, "m_c": m_c, "mean_len": mean_len}


def simulate_regimes(n_sims: int, T: int, cal: dict, rng) -> np.ndarray:
    """Calm (False) / stressed (True) state for every scenario and day: a two-state Markov chain,
    vectorized across scenarios so the only Python loop is over days."""
    u = rng.random((n_sims, T), dtype=np.float32)
    state = u[:, 0] < cal["p_s"]
    out = np.empty((n_sims, T), dtype=bool)
    out[:, 0] = state
    for t in range(1, T):
        state = np.where(u[:, t] < np.where(state, cal["stay_s"], cal["stay_c"]), state, ~state)
        out[:, t] = state
    return out


def generate_steps(lr: np.ndarray, cal: dict, drift: np.ndarray, n_sims: int, T: int, engine: str, rng) -> np.ndarray:
    """Daily log returns of shape (n_sims, T, n_assets)."""
    n = lr.shape[1]
    if engine == ENGINES[0]:
        # Correlated normal shocks, scaled per day by a Student-t factor (fat tails; one draw per day shared by
        # all assets, so crashes hit everything together) and by the calm/stressed regime multiplier.
        chol = np.linalg.cholesky(cal["cov"] + 1e-10 * np.eye(n)).astype(np.float32)
        z = rng.standard_normal((n_sims, T, n), dtype=np.float32) @ chol.T
        tail = np.sqrt((cal["nu"] - 2) / rng.chisquare(cal["nu"], (n_sims, T))).astype(np.float32)
        regime = np.where(simulate_regimes(n_sims, T, cal, rng), cal["m_s"], cal["m_c"]).astype(np.float32)
        return z * (tail * regime)[:, :, None] + drift
    # Block bootstrap: whole real months are copied in sequence, so bad stretches stay clustered and
    # cross-asset moves stay exactly as observed; the sample drift is swapped for the anchored one.
    n_blocks = -(-T // BLOCK_DAYS)
    starts = rng.integers(0, len(lr), (n_sims, n_blocks))
    idx = ((starts[:, :, None] + np.arange(BLOCK_DAYS)) % len(lr)).reshape(n_sims, -1)[:, :T]
    return lr[idx].astype(np.float32) - cal["mu"].astype(np.float32) + drift


def apply_shocks(steps: np.ndarray, shocks: list[dict], classes: tuple, ppy: float, rng) -> np.ndarray:
    """Adds what-if events to the simulated log returns, in place. Each shock is
    {"size": {asset class: total log move}, "days": spread over, "at_years": when, "probability": share of scenarios}."""
    n_sims, T, _ = steps.shape
    for sh in shocks:
        start = min(int(round(sh["at_years"] * ppy)), T - 1)
        days = max(1, min(int(sh["days"]), T - start))
        per_day = np.array([sh["size"].get(c, 0.0) for c in classes], np.float32) / days
        if not per_day.any():
            continue
        hit = rng.random(n_sims) < sh.get("probability", 1.0)
        steps[hit, start:start + days, :] += per_day
    return steps


@st.cache_data(show_spinner=False, max_entries=8)
def run_simulation(logret: np.ndarray, weights: tuple, budget: float, steps_total: int, n_sims: int, engine: str,
                   ppy: float, drift: tuple, classes: tuple, shocks: tuple, inflation: float) -> dict:
    rng = np.random.default_rng(7)
    cal = calibrate(logret.astype(np.float64))
    steps = generate_steps(logret.astype(np.float32), cal, np.asarray(drift, np.float32), n_sims, steps_total, engine, rng)
    apply_shocks(steps, [{**SHOCK_PRESETS[name], "at_years": at, "probability": prob} for name, at, prob in shocks],
                 classes, ppy, rng)
    log_growth = np.cumsum(steps, axis=1, dtype=np.float32)
    del steps
    if inflation:  # today's money: deflate every day by the inflation accrued so far
        log_growth -= (np.log1p(inflation) / ppy * np.arange(1, steps_total + 1, dtype=np.float32))[None, :, None]
    n_assets = logret.shape[1]
    growth = np.concatenate([np.ones((n_sims, 1, n_assets), np.float32), np.exp(log_growth)], axis=1)
    del log_growth
    alloc = budget * np.asarray(weights, np.float32)
    asset_values = growth * alloc
    portfolio = asset_values.sum(axis=2)

    return {
        "portfolio": {**summarize_paths(portfolio), "barriers": barrier_grid(portfolio, budget, ppy)},
        "assets": [{**summarize_paths(asset_values[:, :, i]), "barriers": barrier_grid(asset_values[:, :, i], alloc[i], ppy)}
                   for i in range(n_assets)],
        "calibration": {k: cal[k] for k in ("nu", "p_s", "mean_len", "m_s")},
    }


# ---------- statistics ----------

def historical_stats(close: pd.Series, ppy: float) -> dict:
    r = close.pct_change().dropna()
    # Geometric (CAGR-style) growth: compounding the arithmetic mean overstates volatile assets badly.
    ann_ret = float(np.exp(np.log1p(r).mean() * ppy) - 1)
    ann_vol = r.std() * np.sqrt(ppy)
    return {
        "ann_ret": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": ann_ret / ann_vol if ann_vol else np.nan,
        "max_dd": (close / close.cummax() - 1).min(),
    }


def buy_shares(ohlc: dict[str, pd.DataFrame], weights: dict[str, float], budget: float, start) -> dict[str, float]:
    return {t: budget * w / ohlc[t].loc[start:, "Close"].iloc[0] for t, w in weights.items()}


def portfolio_ohlc(ohlc: dict[str, pd.DataFrame], shares: dict[str, float], start) -> pd.DataFrame:
    """Buy-and-hold portfolio value. High/Low are summed per asset, so they are an upper/lower bound."""
    return sum(ohlc[t].loc[start:] * s for t, s in shares.items())


# ---------- charts ----------

def _x(dates) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(dates)]


def _ms(index: pd.DatetimeIndex) -> list[int]:
    """Naive timestamps as epoch ms, so the chart shows them unshifted."""
    return list((pd.DatetimeIndex(index) - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1))


def _candle_trace() -> go.Candlestick:
    """Empty placeholder; the zoom script fills it with candles for the visible window."""
    return go.Candlestick(
        x=[], open=[], high=[], low=[], close=[], name="Candles",
        meta="candle", visible=False,
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
    )


def render_zoomable(fig: go.Figure, base: dict, height: int = 460) -> None:
    fig.update_layout(
        height=height,
        template="plotly_white",
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        dragmode="zoom",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(color="#0b0b0b"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fcfcfb",
        boxgap=0.2,  # candle body width as a share of the slot
    )
    fig.update_xaxes(type="date", rangeslider=dict(visible=True, thickness=0.07), gridcolor="#ecebe8")
    fig.update_yaxes(fixedrange=True, tickprefix="$", separatethousands=True, gridcolor="#ecebe8")
    script = (ZOOM_JS.replace("__MIN_SPAN__", str(MIN_SPAN_HOURS))
              .replace("__MAX_CANDLES__", str(MAX_CANDLES))
              .replace("__TARGET_CANDLES__", str(TARGET_CANDLES))
              .replace("__TARGET_COLOR__", TARGET_COLOR)
              .replace("__STOP_COLOR__", STOP_COLOR)
              .replace("__BASE__", json.dumps(base)))
    html = fig.to_html(
        include_plotlyjs="cdn",
        post_script=script,
        config={"displaylogo": False, "displayModeBar": False, "scrollZoom": True},
    ).replace("<body>", '<body style="margin:0;overflow:hidden;">', 1)
    st.iframe(html, height=height + PANEL_HEIGHT)


def _level_line(y: float, color: str, x0: str, x1: str, label_at: str, label_side: str) -> dict:
    """Target / stop-loss line from today to the check date; the script moves, snaps and relabels it."""
    return dict(type="line", xref="x", x0=x0, x1=x1, yref="y", y0=y, y1=y,
                line=dict(color=color, width=3), label=dict(textposition=label_at, yanchor=label_side, padding=6, font=dict(color=color, size=12)))


def _check_date_line(x: str) -> dict:
    return dict(type="line", xref="x", x0=x, x1=x, yref="paper", y0=0, y1=1,
                line=dict(color=INK_2, width=1.5, dash="dot"),
                label=dict(textposition="end", textangle=0, yanchor="top", xanchor="right",
                           font=dict(color=INK_2, size=11)))


def _event_line(x: str, label: str) -> dict:
    return dict(type="line", xref="x", x0=x, x1=x, yref="paper", y0=0, y1=1,
                line=dict(color=INK_MUTED, width=1, dash="dash"),
                label=dict(text=label, textposition="start", textangle=0, yanchor="bottom", xanchor="left",
                           font=dict(color=INK_MUTED, size=10)))


def fan_chart(dates: pd.DatetimeIndex, summary: dict, invested: float, bar_minutes: list[int], seed: int,
              ppy: float, goal: float, stop: float, markers: list = ()):
    """`goal` and `stop` are the approach's default gain / loss fractions for the draggable lines."""
    x = _x(dates)
    p10, p25, p50, p75, p90 = (list(row) for row in summary["pct"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=p90, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=p10, line=dict(width=0), fill="tonexty", fillcolor=BAND_OUTER,
                             name="Most scenarios (8 in 10)", hovertemplate="Bad case $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=p75, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=p25, line=dict(width=0), fill="tonexty", fillcolor=BAND_INNER,
                             name="Likely zone (half of scenarios)", hovertemplate="Likely low $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=p50, line=dict(color=INK_2, width=1.5, dash="dash"),
                             name="Middle outcome", hovertemplate="Middle $%{y:,.0f}<extra></extra>"))

    typical = summary["typical"].astype(float)
    fig.add_trace(go.Scatter(x=x, y=typical.round(2).tolist(), line=dict(color=BLUE, width=2), name="One example scenario",
                             meta="line", hovertemplate="Example $%{y:,.0f}<extra></extra>"))
    fig.add_trace(_candle_trace())
    fig.add_trace(go.Scatter(x=[x[0], x[-1]], y=[invested, invested], mode="lines", name="What you put in",
                             line=dict(color=INK_MUTED, width=1, dash="dot"), hoverinfo="skip"))
    fig.update_layout(shapes=[_level_line(invested * (1 + goal), TARGET_COLOR, x[0], x[-1], "start", "bottom"),
                              _level_line(invested * (1 - stop), STOP_COLOR, x[0], x[-1], "end", "top"),
                              _check_date_line(x[-1]), *[_event_line(xm, lab) for xm, lab in markers]])
    base = {
        "days": _ms(dates), "close": typical.round(4).tolist(),
        "sigma": float(np.diff(np.log(typical)).std()), "hours": bar_minutes, "seed": seed,
        "invested": invested, "ppy": ppy, "barriers": summary["barriers"], "goal": goal, "stop": stop,
    }
    return fig, base


# ---------- plan input ----------

@st.cache_data(show_spinner=False, max_entries=4)
def cached_report(key: str, _ctx: dict) -> bytes:
    """`key` identifies the plan and the data date; `_ctx` carries the (unhashed) simulation results."""
    return build_pdf(_ctx)


# ---------- UI ----------

LOGO_SVG = Path(__file__).with_name("assets").joinpath("logo.svg").read_text()

st.set_page_config(page_title="The Trade Sim", page_icon=str(Path(__file__).with_name("assets") / "logo.svg"),
                   layout="wide")
st.markdown(
    """<style>
    .stApp { background: linear-gradient(180deg, #e8f0fc 0px, #f5f8fd 380px); }
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer
      { display: none !important; }
    /* Same width on screen and on an A4 landscape page, so the PDF matches what you see. */
    .block-container { padding-top: 1.5rem; max-width: 1040px; }
    @media print {
      @page { size: A4 landscape; margin: 12mm; }
      .st-key-inputs, .st-key-actions { display: none !important; }
      .stApp { background: #fff !important; }
      [data-testid="stMain"], [data-testid="stAppViewContainer"], .stApp, .block-container
        { overflow: visible !important; height: auto !important; }
      [data-testid="stIFrame"], [data-testid="stVerticalBlockBorderWrapper"] { break-inside: avoid; }
      iframe { overflow: hidden !important; }
    }
    [data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border-radius: 12px; }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] { background: #fbfcfe; }
    </style>""", unsafe_allow_html=True)
actions = st.container(key="actions")  # top-right buttons, filled below once the report is ready
st.markdown(
    f'<div style="display:flex;align-items:center;gap:18px;margin:4px 0 10px;">'
    f'<div style="width:64px;height:64px;flex:none;filter:drop-shadow(0 4px 10px rgba(26,79,158,0.25));">{LOGO_SVG}</div>'
    f'<div><div style="font-size:2.3rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;">The Trade Sim</div>'
    f'<div style="color:{INK_2};font-size:1.1rem;margin-top:2px;">How risky is my investment?</div></div></div>',
    unsafe_allow_html=True)
st.markdown(
    "Tell us how much you'd invest, in what, and for how long. We play out thousands of possible futures on "
    "real market data and show you the **bad, the likely and the good** — in plain words. "
    "This is a learning tool, not advice."
)

with st.container(key="inputs"):
    plan_wizard()

plan = st.session_state.get("plan")
if not plan:
    st.stop()


with st.spinner("Getting 10 years of market data…"):
    ohlc = load_ohlc(tuple(plan["weights"]))
missing = [t for t in plan["weights"] if t not in ohlc]
if missing:
    st.error(f"We couldn't find price data for: {', '.join(missing)}. Check the ticker and try again.")
    st.stop()

tickers = list(plan["weights"])
names = plan["names"]
weights = np.array([plan["weights"][t] for t in tickers])
budget = plan["budget"]
closes = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers})
logret = np.log(closes).diff().dropna()
ppy = periods_per_year(closes.index)
steps_total = round(ppy * plan["years"])

classes = tuple(plan["classes"][t] for t in tickers)
with st.spinner("Looking up yields and dividends…"):
    bond_yield = treasury_yield() if "Bonds" in classes else 0.04
    payout = tuple(0.0 if plan["reinvest"] else dividend_yield(t) for t in tickers)
drift, drift_info = anchored_drift(logret.values.mean(axis=0), ppy, classes, bond_yield, plan["fee"], payout)
with st.spinner(f"Playing out {plan['n_sims']:,} possible futures…"):
    sim = run_simulation(logret.values, tuple(weights), budget, steps_total, plan["n_sims"], plan["engine"], ppy,
                         tuple(float(d) for d in drift), classes, plan["shocks"], plan["inflation"])

last_date = closes.index[-1]
# Future calendar for the simulated days and their intraday bars: crypto-only plans trade around the clock,
# anything else follows US trading days (weekends and federal holidays off) with a 9:30–16:00 session.
if ppy > 300:
    future_dates = pd.date_range(last_date, periods=steps_total + 1, freq="D")
    bar_minutes = [60 * h for h in range(24)]
else:
    trading_day = pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())
    future_dates = pd.DatetimeIndex([last_date]).append(
        pd.date_range(last_date + trading_day, periods=steps_total, freq=trading_day))
    bar_minutes = [570 + 60 * h for h in range(7)]
history_years = (last_date - closes.index[0]).days / 365.25
shock_markers = [(future_dates[min(round(at * ppy), steps_total)].strftime("%Y-%m-%d"),
                  f"{name}" + (f" ({prob:.0%} chance)" if prob < 1 else ""))
                 for name, at, prob in plan["shocks"]]
years_label = f"{plan['years']} year{'s' if plan['years'] > 1 else ''}"


def outcome_card(col, title: str, note: str, value: float, invested: float, color: str) -> None:
    change = value / invested - 1
    with col, st.container(border=True):
        st.markdown(
            f'<div style="min-height:{CARD_MIN_HEIGHT}px;">'
            f'<div style="color:{INK_2};font-size:0.9rem;">{title}</div>'
            f'<div style="font-size:1.7rem;font-weight:700;color:{color};line-height:1.3;">{money(value)}</div>'
            f'<div style="color:{UP if change >= 0 else DOWN};font-weight:600;white-space:nowrap;">{change:+.0%} vs start</div>'
            f'<div style="color:{INK_MUTED};font-size:0.8rem;margin-top:4px;">{note}</div></div>',
            unsafe_allow_html=True)


def outlook(summary: dict, invested: float, stats: dict, seed: int, what: str) -> dict:
    """Same block for the whole mix and for each investment: outcomes, chart, what the past looked like.
    Returns what the PDF report needs for the same block."""
    p10, p50, p90 = np.percentile(summary["finals"], [10, 50, 90])
    prob_loss = float((summary["finals"] < invested).mean())
    level, color, meaning = risk_level(stats["ann_vol"])
    st.markdown(
        f'<div style="margin:4px 0 10px;"><span style="background:{color};color:#fff;border-radius:12px;'
        f'padding:3px 12px;font-weight:600;">Risk level: {level}</span>'
        f'<span style="color:{INK_2};margin-left:10px;">{meaning}</span></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    outcome_card(c1, "If things go badly", "Only 1 in 10 scenarios ends worse than this", p10, invested, DOWN)
    outcome_card(c2, "Most likely", "Half the scenarios end above this, half below", p50, invested, "#0b0b0b")
    outcome_card(c3, "If things go well", "Only 1 in 10 scenarios ends better than this", p90, invested, UP)
    with c4, st.container(border=True):
        st.markdown(
            f'<div style="min-height:{CARD_MIN_HEIGHT}px;">'
            f'<div style="color:{INK_2};font-size:0.9rem;">Chance of ending with less</div>'
            f'<div style="font-size:1.7rem;font-weight:700;color:{DOWN if prob_loss >= 0.2 else "#0b0b0b"};'
            f'line-height:1.3;">{prob_loss:.0%}</div>'
            f'<div style="color:{INK_2};font-weight:600;white-space:nowrap;">than you put in</div>'
            f'<div style="color:{INK_MUTED};font-size:0.8rem;margin-top:4px;">Share of scenarios ending below {money(invested)}'
            f'</div></div>', unsafe_allow_html=True)
    st.markdown(
        f"> After **{years_label}**, {what} would most likely be worth about **{mdm(p50)}**. "
        f"If things go badly you'd have around **{mdm(p10)}**; if they go well, around **{mdm(p90)}**. "
        f"There's a **{prob_loss:.0%}** chance you'd end up with less than you put in."
    )
    with st.expander("How to read this chart"):
        st.markdown(
            "- **The blue bands** show where the money ends up in most of our scenarios: the light band holds "
            "8 in 10 of them, the darker band the middle half. The wider the band, the less certain the future.\n"
            "- **The dashed line** is the middle outcome. **The solid blue line** is one example scenario, "
            "so you can see how bumpy the ride can be.\n"
            "- **Green and red lines:** drag the green line to the gain you'd be happy with, and the red line to the "
            "loss you couldn't accept. The boxes below the chart tell you how likely you are to reach each one, "
            "and how soon. Use *If you keep it for* to check a shorter period.\n"
            "- **Zoom in** by dragging across the chart or scrolling. Up close, the example scenario turns into "
            "candles that show the ups and downs inside each month, day or hour. Double-click to zoom back out."
        )
    goal, stop = approach_levels(approach, p50 / invested - 1, stats["ann_vol"])
    st.caption(f"Lines start at your **{plan['approach']}** approach for this chart: goal **+{goal:.0%}** "
               f"({approach['goal_k']:.0%} of the expected gain over {years_label}), loss limit **−{stop:.0%}** "
               f"({approach['stop_k']:g}× the typical yearly swing of ±{pct(stats['ann_vol'])}). Drag them to explore.")
    render_zoomable(*fan_chart(future_dates, summary, invested, bar_minutes, seed=seed, ppy=ppy,
                               goal=goal, stop=stop, markers=shock_markers))
    section = dict(summary=summary, invested=invested, stats=stats, what=what, goal=goal, stop=stop,
                   risk=(level, color, meaning), lines=line_outcomes(summary["barriers"], invested, goal, stop))

    st.markdown(f"**What the past {history_years:.0f} years looked like**")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Average growth per year", pct(stats["ann_ret"]),
              help="How much it grew per year on average in the past. The future can be different.")
    s2.metric("Yearly swings", f"±{pct(stats['ann_vol'])}",
              help="In a typical year the value moved up or down by about this much. Bigger means a bumpier ride.")
    s3.metric("Worst fall from a peak", pct(stats["max_dd"]),
              help="The biggest drop from a high point to a low point in the past. This is what a bad stretch felt like.")
    s4.metric("Growth per unit of risk", f"{stats['sharpe']:.2f}",
              help="Average growth divided by yearly swings. Higher means more growth for the bumps you put up with. "
                   "Above 1 is good; below 0.5 means a lot of bumps for little growth.")
    return section


port = sim["portfolio"]
full_hist = portfolio_ohlc(ohlc, buy_shares(ohlc, plan["weights"], budget, closes.index[0]), closes.index[0])
asset_stats = {t: historical_stats(closes[t], ppy) for t in tickers}

st.divider()
approach = APPROACHES[plan["approach"]]
step_header(4, (f"{plan['name']}: " if plan.get("name") else "") + f"what could happen to your {money(budget)} in {years_label}",
            f"{plan['approach']} approach · " + ", ".join(f"{names[t]} {plan['weights'][t]:.0%}" for t in tickers)
            + f" · {plan['n_sims']:,} scenarios"
            + (f" · values in today's money ({plan['inflation']:.1%} inflation)" if plan["inflation"] else "")
            + f" · {plan['fee']:.1%} yearly fees" + ("" if plan["reinvest"] else " · dividends paid out")
            + (" · with events: " + ", ".join(n for n, _, _ in plan["shocks"]) if plan["shocks"] else "")
            + ".")
port_level = risk_level(historical_stats(full_hist["Close"], ppy)["ann_vol"])[0]
if plan["approach"] == "Play it safe" and port_level in ("High", "Very high"):
    st.warning(f"You chose to play it safe, but this mix's risk level is **{port_level.lower()}**. "
               "Expect it to hit your loss limit often. More bonds would calm it down.")
elif plan["approach"] == "Aggressive" and port_level == "Low":
    st.info("You chose an aggressive approach, but this mix's risk level is **low**: "
            "it will rarely reach a big goal. More stocks would give it more room to move.")
sections = [{**outlook(port, budget, historical_stats(full_hist["Close"], ppy), seed=1, what="your money"),
             "title": "Your whole mix", "subtitle": f"{money(budget)} invested across "
             + ", ".join(f"{names[t]} {plan['weights'][t]:.0%}" for t in tickers)}]

with st.expander("How much to trust this", expanded=True):
    st.markdown(
        "- **These are not predictions.** The size and timing of the ups and downs come from the **last "
        f"{history_years:.0f} years** ({closes.index[0]:%b %Y} to today). If the next years look different, "
        "so will the results.\n"
        "- **The spread is more trustworthy than the middle.** The bands held up well for broad stock funds over "
        "1–3 years in our back-test. The *most likely* number is a judgment call: it's anchored to long-run "
        "averages, not to the past decade (table below).\n"
        "- **Longer horizons are less reliable.** At 5 years and beyond, treat the numbers as an illustration of risk, "
        "not a forecast."
    )
    st.markdown("**Expected growth per year used in the scenarios.** The past decade counts for "
                f"{SAMPLE_WEIGHT:.0%}, a long-run anchor for {1 - SAMPLE_WEIGHT:.0%} (stocks 7%, bonds the current "
                f"10-year Treasury yield of {bond_yield:.1%}, crypto 8%), kept within ±{DRIFT_BAND:.0%} of the anchor, "
                f"minus {plan['fee']:.1%} fees" + ("" if plan["reinvest"] else " and the dividends paid out") + ".")
    st.dataframe(pd.DataFrame([{"Investment": names[t], "Past decade": pct(i["past"]), "Long-run anchor": pct(i["anchor"]),
                                "Used in the scenarios": pct(i["net"])} for t, i in zip(tickers, drift_info)]),
                 hide_index=True, width="stretch")
    cal = sim["calibration"]
    if plan["engine"] == ENGINES[0]:
        st.caption(f"Shocks follow a Student-t with {cal['nu']:.1f} degrees of freedom (fatter tails than a bell curve). "
                   f"Stressed periods cover {cal['p_s']:.0%} of days, last about {cal['mean_len']:.0f} trading days "
                   f"and carry {cal['m_s']:.1f}× the usual swings, all measured on your investments' history.")
    else:
        st.caption(f"Scenarios are built from whole real months ({BLOCK_DAYS} trading days), so crashes keep their "
                   "real size and duration.")
    crypto = [names[t] for t in tickers if t.endswith("-USD")]
    bonds = [names[t] for t in tickers if plan["classes"][t] == "Bonds"]
    tamed = [f"{names[t]} ({pct(i['past'])} → {pct(i['net'])})" for t, i in zip(tickers, drift_info)
             if i["past"] > i["anchor"] + DRIFT_BAND]
    trust_notes = []
    if tamed:
        trust_notes.append(f"Past decade tamed: {', '.join(tamed)}. These grew unusually fast; the scenarios use the "
                           "anchored rate instead, so the most likely outcome is far less rosy than the past.")
        st.info("**" + trust_notes[-1].replace("Past decade tamed:", "Past decade tamed:**", 1))
    if crypto:
        trust_notes.append(f"{', '.join(crypto)}: growth is anchored to 8% a year, but the swings are still the enormous "
                           "ones of the past decade. The downside here is believable; treat the upside as speculative.")
        st.warning("**" + trust_notes[-1].replace(":", ":**", 1))
    if bonds:
        trust_notes.append(f"{', '.join(bonds)}: expected growth is set to today's 10-year Treasury yield "
                           f"({bond_yield:.1%}), not to the past decade. Where rates go next is still the main unknown.")
        st.info("**" + trust_notes[-1].replace(":", ":**", 1))

if len(tickers) > 1:
    st.subheader("Look inside your mix")
    st.caption("Each tab shows only the part of your money that goes into that investment.")
    for i, (t, tab) in enumerate(zip(tickers, st.tabs([names[t] for t in tickers]))):
        with tab:
            invested = budget * weights[i]
            st.markdown(f"**{mdm(invested)}** of your money goes into **{names[t]}** ({pct(weights[i])} of the mix).")
            sections.append({**outlook(sim["assets"][i], invested, asset_stats[t], seed=2 + i,
                                       what=f"the {mdm(invested)} in {names[t]}"),
                             "title": names[t], "subtitle": f"{money(invested)} of your money ({pct(weights[i])} of the mix)"})

report_ctx = dict(
    plan=plan, years_label=years_label, ppy=ppy, dates=future_dates, history_years=history_years,
    data_since=f"{closes.index[0]:%b %Y}", bond_yield=bond_yield, calibration=sim["calibration"],
    markers=[(pd.Timestamp(x), lab) for x, lab in shock_markers], notes=trust_notes,
    mix=[{"name": names[t], "kind": plan["classes"][t], "share": float(plan["weights"][t])} for t in tickers],
    drift_rows=[(names[t], i) for t, i in zip(tickers, drift_info)], sections=sections,
)
with st.spinner("Preparing the PDF…"):
    report_pdf = cached_report(json.dumps({**plan, "shocks": [list(x) for x in plan["shocks"]]}, sort_keys=True)
                               + str(last_date), report_ctx)
with actions:
    _, c_pdf, c_reset = st.columns([6.4, 1.4, 1.4])
    c_pdf.download_button("Save as PDF", data=report_pdf, mime="application/pdf", width="stretch",
                          file_name=f"the-trade-sim-{(plan['name'] or 'report').lower().replace(' ', '-')}.pdf",
                          help="Plan overview on page 1, then a page of chart and statistics for the mix and for each investment")
    if c_reset.button("Start over", width="stretch", help="Clear everything and go back to the start"):
        for key in list(st.session_state):
            del st.session_state[key]
        st.rerun()

with st.expander("Words explained"):
    for term, meaning in GLOSSARY:
        st.markdown(f"**{term}** — {meaning}")

st.caption(f"Based on daily prices since {closes.index[0]:%b %Y}, the longest period all your investments have data "
           "for. Prices in other currencies are converted to US dollars. Data: Yahoo Finance.")
st.caption("This is a learning tool, not financial advice. The scenarios come from past prices; the future may be "
           "different. Taxes are not included.")

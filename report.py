"""PDF report: a plan overview on page 1, then one page of chart, outcomes and statistics for the whole mix
and for each investment, and a closing page on expected growth and how much to trust the numbers."""

import io
from datetime import date

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from fpdf import FPDF  # noqa: E402
from fpdf.fonts import FontFace  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from constants import (APPROACHES, BLUE, DOWN, GLOSSARY, INK_2, INK_MUTED, STOP_COLOR, TARGET_COLOR, UP,  # noqa: E402
                       money, pct)

PIE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
HEAD_FILL = (238, 244, 255)


def latin(s: str) -> str:
    """The built-in PDF fonts only know Latin-1; swap the few typographic characters we use."""
    for a, b in (("\\$", "$"), ("−", "-"), ("–", "-"), ("—", "-"), ("×", "x"), ("≈", "~"), ("·", "-"), ("’", "'"),
                 ("‹", "<"), ("›", ">"), ("✓", "ok"), ("…", "...")):
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def duration(steps: float, ppy: float) -> str:
    years = steps / ppy
    if years < 1 / 12:
        return f"{max(1, round(years * 365))} days"
    if years < 1:
        return f"{round(years * 12)} months"
    return f"{years:.1f} years"


# ---------- goal / loss-limit outcomes (same rules as the chart panel, at the full horizon) ----------

def line_outcomes(br: dict, invested: float, goal: float, stop: float) -> dict:
    up, down = np.array(br["up"]), np.array(br["down"])
    iu = int(np.argmin(np.abs(up - invested * (1 + goal))))
    idn = int(np.argmin(np.abs(down - invested * (1 - stop))))
    end = br["month_steps"][-1]
    finals = np.array(br["monthly"][-1], float)
    tu = np.array(br["up_t"][iu]); td = np.array(br["down_t"][idn])
    tu = np.where(tu > end, -1, tu); td = np.where(td > end, -1, td)
    goal_first = (tu >= 0) & ((td < 0) | (tu < td))
    stop_first = (td >= 0) & ~goal_first
    neither = ~goal_first & ~stop_first
    v = np.where(goal_first, up[iu], np.where(stop_first, down[idn], finals))
    t = np.where(goal_first, tu, np.where(stop_first, td, end))
    tie = np.where(stop_first, t, np.where(goal_first, -t, 0))  # earlier stop = worse, earlier goal = better
    order = np.lexsort((tie, v))
    cards = []
    for label, q in (("If things go badly", 0.1), ("Most likely", 0.5), ("If things go well", 0.9)):
        i = order[int(round(q * (len(order) - 1)))]
        kind = "goal" if goal_first[i] else "stop" if stop_first[i] else "none"
        cards.append((label, kind, float(t[i]), float(v[i])))
    return {
        "goal_level": float(up[iu]), "stop_level": float(down[idn]), "end": end,
        "p_goal": float(goal_first.mean()), "p_stop": float(stop_first.mean()), "p_none": float(neither.mean()),
        "t_goal": float(np.median(t[goal_first])) if goal_first.any() else None,
        "t_stop": float(np.median(t[stop_first])) if stop_first.any() else None,
        "none_range": (float(np.percentile(finals[neither], 10)), float(np.percentile(finals[neither], 90)))
        if neither.any() else None,
        "cards": cards,
    }


# ---------- figures ----------

def fan_png(dates, summary: dict, invested: float, goal_level: float, stop_level: float, markers: list) -> bytes:
    p10, p25, p50, p75, p90 = summary["pct"]
    fig, ax = plt.subplots(figsize=(7.4, 3.5), dpi=160)
    ax.fill_between(dates, p10, p90, color=BLUE, alpha=0.12, lw=0, label="Most scenarios (8 in 10)")
    ax.fill_between(dates, p25, p75, color=BLUE, alpha=0.26, lw=0, label="Likely zone (half of scenarios)")
    ax.plot(dates, p50, color=INK_2, ls="--", lw=1.1, label="Middle outcome")
    ax.plot(dates, summary["typical"], color=BLUE, lw=1.2, label="One example scenario")
    ax.axhline(invested, color=INK_MUTED, ls=":", lw=1, label="What you put in")
    ax.axhline(goal_level, color=TARGET_COLOR, lw=2, label=f"Goal {money(goal_level)}")
    ax.axhline(stop_level, color=STOP_COLOR, lw=2, label=f"Loss limit {money(stop_level)}")
    top = ax.get_ylim()[1]
    for x, label in markers:
        ax.axvline(x, color=INK_MUTED, ls="--", lw=0.8)
        ax.text(x, top, " " + label, fontsize=6.5, color=INK_2, va="top", ha="left")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(color="#ecebe8", lw=0.6)
    ax.tick_params(labelsize=7.5, colors=INK_2)
    ax.legend(fontsize=6.8, loc="upper left", ncol=2, frameon=False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def pie_png(rows: list[dict]) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 2.6), dpi=160)
    wedges, _ = ax.pie([r["share"] for r in rows], colors=PIE_COLORS[:len(rows)], startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2))
    ax.legend(wedges, [f"{r['name']}  {r['share']:.0%}" for r in rows], fontsize=7, loc="center left",
              bbox_to_anchor=(1.0, 0.5), frameon=False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ---------- document ----------

class Report(FPDF):
    def __init__(self, title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title = title
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*rgb(INK_MUTED))
        self.cell(0, 6, latin(self.doc_title), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*rgb(INK_MUTED))
        self.cell(0, 5, "The Trade Sim - educational tool, not financial advice. Scenarios come from past prices; "
                        "the future may differ.", align="L")
        self.cell(0, 5, f"{self.page_no()}", align="R")

    # small helpers
    def h1(self, text):
        self.set_font("Helvetica", "B", 20); self.set_text_color(11, 11, 11)
        self.cell(0, 10, latin(text), new_x="LMARGIN", new_y="NEXT")

    def h2(self, text, color=BLUE):
        self.set_font("Helvetica", "B", 13); self.set_text_color(*rgb(color))
        self.cell(0, 8, latin(text), new_x="LMARGIN", new_y="NEXT")

    def h3(self, text):
        self.set_font("Helvetica", "B", 10); self.set_text_color(11, 11, 11)
        self.cell(0, 6, latin(text), new_x="LMARGIN", new_y="NEXT")

    def para(self, text, size=9, color=INK_2, h=4.6):
        self.set_font("Helvetica", "", size); self.set_text_color(*rgb(color))
        self.multi_cell(0, h, latin(text), new_x="LMARGIN", new_y="NEXT")

    def rich(self, parts, size=9, h=4.6):
        """Inline bold/plain runs on one wrapped paragraph: parts = [(text, bold), ...]."""
        self.set_text_color(11, 11, 11)
        for text, bold in parts:
            self.set_font("Helvetica", "B" if bold else "", size)
            self.write(h, latin(text))
        self.ln(h + 1)

    def simple_table(self, headings, rows, widths, aligns):
        style = FontFace(emphasis="BOLD", color=rgb(BLUE), fill_color=HEAD_FILL)
        self.set_font("Helvetica", "", 8.6); self.set_text_color(11, 11, 11)
        with self.table(col_widths=widths, text_align=aligns, headings_style=style, line_height=5.6,
                        borders_layout="MINIMAL", padding=1, num_heading_rows=1 if headings else 0,
                        first_row_as_headings=bool(headings)) as table:
            if headings:
                r = table.row()
                for hcell in headings:
                    r.cell(latin(hcell))
            for row in rows:
                r = table.row()
                for cell in row:
                    r.cell(latin(str(cell)))
        self.ln(2)

    def cards(self, items):
        """items: [(title, value, sub, color_hex)] drawn as four equal boxes."""
        n = len(items); w = (self.w - self.l_margin - self.r_margin - 3 * (n - 1)) / n
        x0, y0 = self.l_margin, self.get_y()
        for i, (title, value, sub, color) in enumerate(items):
            x = x0 + i * (w + 3)
            self.set_draw_color(223, 229, 239); self.set_fill_color(251, 252, 254)
            self.rect(x, y0, w, 24, style="DF")
            self.set_xy(x + 2, y0 + 2); self.set_font("Helvetica", "", 7.5); self.set_text_color(*rgb(INK_2))
            self.cell(w - 4, 4, latin(title))
            self.set_xy(x + 2, y0 + 7); self.set_font("Helvetica", "B", 13); self.set_text_color(*rgb(color))
            self.cell(w - 4, 7, latin(value))
            self.set_xy(x + 2, y0 + 15); self.set_font("Helvetica", "", 7); self.set_text_color(*rgb(INK_MUTED))
            self.multi_cell(w - 4, 3.4, latin(sub))
        self.set_y(y0 + 27)


def _section_page(pdf: Report, sec: dict, ctx: dict) -> None:
    plan, ppy = ctx["plan"], ctx["ppy"]
    invested, summary, stats = sec["invested"], sec["summary"], sec["stats"]
    p10, p50, p90 = np.percentile(summary["finals"], [10, 50, 90])
    prob_loss = float((summary["finals"] < invested).mean())
    level, color, meaning = sec["risk"]
    pdf.add_page()
    pdf.h2(sec["title"])
    pdf.para(sec["subtitle"])
    pdf.rich([("Risk level: ", False), (level, True), (f" - {meaning}", False)], size=9)
    pdf.cards([
        ("If things go badly", money(p10), f"{p10 / invested - 1:+.0%} vs start - only 1 in 10 scenarios ends worse", DOWN),
        ("Most likely", money(p50), f"{p50 / invested - 1:+.0%} vs start - half end above, half below", "#0b0b0b"),
        ("If things go well", money(p90), f"{p90 / invested - 1:+.0%} vs start - only 1 in 10 scenarios ends better", UP),
        ("Chance of ending with less", f"{prob_loss:.0%}", f"of scenarios end below {money(invested)}",
         DOWN if prob_loss >= 0.2 else "#0b0b0b"),
    ])
    pdf.para(f"After {ctx['years_label']}, {sec['what']} would most likely be worth about {money(p50)}. If things go "
             f"badly you'd have around {money(p10)}; if they go well, around {money(p90)}. There's a {prob_loss:.0%} "
             f"chance you'd end up with less than you put in.", size=9, color="#0b0b0b")
    pdf.ln(1)
    pdf.image(io.BytesIO(fan_png(ctx["dates"], summary, invested, sec["lines"]["goal_level"], sec["lines"]["stop_level"],
                                 ctx["markers"])), w=pdf.w - pdf.l_margin - pdf.r_margin)
    pdf.ln(1)
    lo = sec["lines"]
    pdf.h3(f"Goal and loss limit ({plan['approach']} approach)")
    pdf.para(f"Goal +{sec['goal']:.0%} ({money(lo['goal_level'])}), loss limit -{sec['stop']:.0%} "
             f"({money(lo['stop_level'])}), checked over {ctx['years_label']}. A scenario ends as soon as it touches "
             "either line.", size=8.5)
    rows = []
    for label, kind, t, v in lo["cards"]:
        if kind == "goal":
            rows.append((label, "You reach your goal", f"after {duration(t, ppy)}, with {money(v)}"))
        elif kind == "stop":
            rows.append((label, "You hit your loss limit", f"after {duration(t, ppy)}, with {money(v)}"))
        else:
            rows.append((label, "Neither happens", f"you have {money(v)} ({v / invested - 1:+.0%}) after {ctx['years_label']}"))
    pdf.simple_table(("Scenario", "What happens", "When and how much"), rows, (40, 50, 88), ("LEFT", "LEFT", "LEFT"))
    bits = [f"Goal reached first: {lo['p_goal']:.0%}" + (f" (typically after {duration(lo['t_goal'], ppy)})" if lo["t_goal"] is not None else ""),
            f"loss limit hit first: {lo['p_stop']:.0%}" + (f" (typically after {duration(lo['t_stop'], ppy)})" if lo["t_stop"] is not None else ""),
            f"neither: {lo['p_none']:.0%}" + (f", ending between {money(lo['none_range'][0])} and {money(lo['none_range'][1])}" if lo["none_range"] else "")]
    pdf.para("; ".join(bits) + ".", size=8.5)
    pdf.h3(f"What the past {ctx['history_years']:.0f} years looked like")
    pdf.simple_table(("Average growth per year", "Yearly swings", "Worst fall from a peak", "Growth per unit of risk"),
                     [(pct(stats["ann_ret"]), f"±{pct(stats['ann_vol'])}", pct(stats["max_dd"]), f"{stats['sharpe']:.2f}")],
                     (45, 45, 45, 43), ("CENTER",) * 4)


def build_pdf(ctx: dict) -> bytes:
    plan = ctx["plan"]
    title = f"The Trade Sim - {plan['name']}" if plan.get("name") else "The Trade Sim - your plan"
    pdf = Report(title)

    # ---- page 1: plan overview ----
    pdf.add_page()
    pdf.h1(plan["name"] or "Your investment plan")
    pdf.para(f"The Trade Sim report - generated on {date.today():%B %d, %Y}. How risky is my investment?", size=9.5)
    pdf.ln(2)
    pdf.h2("Your plan")
    approach = APPROACHES[plan["approach"]]
    s = ctx
    facts = [
        ("Amount invested", money(plan["budget"])),
        ("Time horizon", ctx["years_label"]),
        ("Approach", f"{plan['approach']} - {approach['blurb']} Goal ~{approach['goal_k']:.0%} of the expected gain, "
                     f"loss limit ~{approach['stop_k']:g}x the typical yearly swing."),
        ("Method", f"{plan['engine']} - {plan['n_sims']:,} scenarios"),
        ("Costs", f"{plan['fee']:.1%} yearly fees; " + (f"results in today's money ({plan['inflation']:.1%} inflation); "
                                                       if plan["inflation"] else "inflation not applied; ")
                  + ("dividends reinvested" if plan["reinvest"] else "dividends paid out")),
        ("What-if events", ", ".join(f"{n} after {at:g} years" + (f" ({p:.0%} chance)" if p < 1 else "")
                                     for n, at, p in plan["shocks"]) or "none"),
        ("Data", f"daily prices since {s['data_since']}, {s['history_years']:.0f} years, converted to US dollars"),
    ]
    pdf.simple_table((), facts, (40, 138), ("LEFT", "LEFT"))
    pdf.h2("Where the money goes")
    rows = [(r["name"], r["kind"], f"{r['share']:.0%}", money(r["share"] * plan["budget"])) for r in ctx["mix"]]
    pdf.simple_table(("Investment", "Kind", "Share", "Amount"), rows, (78, 45, 25, 30), ("LEFT", "LEFT", "RIGHT", "RIGHT"))
    y = pdf.get_y()
    pdf.image(io.BytesIO(pie_png(ctx["mix"])), x=pdf.l_margin, y=y, w=110)
    pdf.set_y(y + 62)
    pdf.h2("What the next pages show")
    pdf.para("One page for the whole mix, then one for each investment, each with: the risk level, the four outcomes "
             "(a bad, a likely and a good scenario, and the chance of ending with less), a chart of where the money "
             "could go, what happens to your goal and loss limit, and what the past looked like. The last page explains "
             "the growth rates used and how much to trust the numbers. In the app, the lines can be dragged and the "
             "charts zoomed; here they're fixed at your approach's defaults over the full horizon.")

    # ---- one page per chart ----
    for sec in ctx["sections"]:
        _section_page(pdf, sec, ctx)

    # ---- closing page ----
    pdf.add_page()
    pdf.h2("How much to trust this")
    pdf.para(f"These are not predictions. The size and timing of the ups and downs come from the last "
             f"{ctx['history_years']:.0f} years. The spread is more trustworthy than the middle: in a back-test on 20+ "
             "years of history the bands held up well for broad stock funds over 1-3 years. The most likely number is "
             "a judgment call, anchored to long-run averages rather than to the past decade. At 5 years and beyond, "
             "treat the numbers as an illustration of risk, not a forecast.")
    pdf.h3("Expected growth per year used in the scenarios")
    pdf.para(f"The past decade counts for 25%, a long-run anchor for 75% (stocks 7%, bonds the current 10-year Treasury "
             f"yield of {ctx['bond_yield']:.1%}, crypto 8%), kept within ±5% of the anchor, minus {plan['fee']:.1%} fees"
             + ("" if plan["reinvest"] else " and the dividends paid out") + ".", size=8.5)
    pdf.simple_table(("Investment", "Past decade", "Long-run anchor", "Used in the scenarios"),
                     [(n, pct(i["past"]), pct(i["anchor"]), pct(i["net"])) for n, i in ctx["drift_rows"]],
                     (78, 33, 33, 34), ("LEFT", "RIGHT", "RIGHT", "RIGHT"))
    cal = ctx["calibration"]
    if plan["engine"].startswith("Statistical"):
        pdf.para(f"Statistical model: shocks follow a Student-t with {cal['nu']:.1f} degrees of freedom (fatter tails "
                 f"than a bell curve); stressed periods cover {cal['p_s']:.0%} of days, last about {cal['mean_len']:.0f} "
                 f"trading days and carry {cal['m_s']:.1f}x the usual swings, all measured on your investments' history.",
                 size=8.5)
    else:
        pdf.para("Replay real history: scenarios are built from whole real months, so crashes keep their real size and "
                 "duration.", size=8.5)
    for note in ctx["notes"]:
        pdf.para("- " + note, size=8.5, color="#0b0b0b")
    pdf.h3("Words explained")
    for term, meaning in GLOSSARY:
        pdf.rich([(term + ": ", True), (meaning, False)], size=8.3, h=4.2)
    return bytes(pdf.output())

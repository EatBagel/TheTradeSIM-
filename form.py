"""Onboarding wizard: welcome → your plan → your mix → fine-tune (optional) → review.

`plan_wizard()` draws the current page; when the user presses the final button it stores the plan
dictionary in st.session_state.plan and reruns. Everything it collects lives in st.session_state.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from constants import (ALLOW_OTHER, APPROACHES, BLUE, CATALOG, CLASS_BLURB, ENGINES, INK_MUTED, OTHER,
                       SHOCK_PRESETS, STARTING_MIX, TICKER_INFO, money, step_header)

PAGES = ["basic", "portfolio", "tune", "review"]
PAGE_TITLES = {"basic": "Your plan", "portfolio": "Your mix", "tune": "Fine-tune", "review": "Review"}
PIE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DEFAULT_SETTINGS = dict(n_sims=1000, engine=ENGINES[0], fee=0.003, inflation=0.025, real=True, reinvest=True, shocks=())


# ---------- state ----------

def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("page", "welcome")
    ss.setdefault("plan_name", "")
    ss.setdefault("budget", 10000)
    ss.setdefault("years", 10)
    ss.setdefault("approach", "Balanced")
    ss.setdefault("portfolio", [_row(t, w) for t, w in STARTING_MIX.items()])
    ss.setdefault("mix_v", 0)  # bumps to reset the mix table after programmatic changes
    ss.setdefault("settings", dict(DEFAULT_SETTINGS))
    if "flash" in ss:
        st.toast(ss.pop("flash"), icon="✅")


def _row(ticker: str, percentage: int, name: str | None = None, cls: str | None = None) -> dict:
    known_name, known_cls = TICKER_INFO.get(ticker, (ticker, "Other"))
    return {"investment": name or known_name, "type": cls or known_cls, "ticker": ticker, "percentage": int(percentage)}


def _go(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def _set_portfolio(rows: list[dict]) -> None:
    st.session_state.portfolio = rows
    st.session_state.mix_v += 1
    st.rerun()


def _total() -> int:
    return int(sum(r["percentage"] for r in st.session_state.portfolio))


def _breadcrumb(current: str) -> None:
    parts = []
    for i, p in enumerate(PAGES, 1):
        if p == current:
            parts.append(f'<span style="color:{BLUE};font-weight:700;">{i} · {PAGE_TITLES[p]}</span>')
        else:
            parts.append(f'<span style="color:{INK_MUTED};">{i} · {PAGE_TITLES[p]}</span>')
    st.markdown('<div style="margin-bottom:8px;font-size:0.9rem;">' + ' <span style="color:#c3c2b7">›</span> '.join(parts)
                + '</div>', unsafe_allow_html=True)


def _nav(back: str | None, next_label: str, next_page: str | None, next_ok: bool = True, key: str = "") -> bool:
    """Back / Next row. Returns True when Next was pressed and `next_page` is None (caller handles it)."""
    left, _, right = st.columns([1.2, 4, 2])
    if back and left.button("‹ Back", key=f"back_{key}", width="stretch"):
        _go(back)
    if right.button(next_label, key=f"next_{key}", type="primary", width="stretch", disabled=not next_ok):
        if next_page:
            _go(next_page)
        return True
    return False


# ---------- pieces ----------

def mix_pie(rows: list[dict], height: int = 260) -> go.Figure:
    fig = go.Figure(go.Pie(labels=[r["investment"] for r in rows], values=[r["percentage"] for r in rows], hole=0.45,
                           marker=dict(colors=PIE_COLORS[:len(rows)], line=dict(color="#fff", width=2)),
                           textinfo="percent", hovertemplate="%{label}: %{percent}<extra></extra>", sort=False))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                      legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=12)),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#0b0b0b"))
    return fig


def _plan_summary_line() -> str:
    ss = st.session_state
    name = f"**{ss.plan_name}** · " if ss.plan_name else ""
    return (f"{name}{money(ss.budget)} for {ss.years} year{'s' if ss.years > 1 else ''} · "
            f"{ss.approach} approach")


# ---------- pages ----------

def _page_welcome() -> None:
    with st.container(border=True):
        st.markdown("### Let's build your plan in a few short steps")
        st.markdown("You don't need to know anything about investing. We'll ask simple questions and explain the "
                    "words as we go. Nothing is stored anywhere.")
        for col, (title, text) in zip(st.columns(4), [
            ("1 · Your plan", "How much, for how long, and how you'd like to play it."),
            ("2 · Your mix", "What the money goes into: stocks, funds, bonds, crypto, gold, real estate…"),
            ("3 · Fine-tune", "Optional: fees, inflation, and what-if events like a recession."),
            ("4 · Review", "Check everything, then see what could happen to your money."),
        ]):
            with col, st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(text)
        st.write("")
        if st.button("Start building my plan", type="primary", width="stretch"):
            _go("basic")


def _page_basic() -> None:
    ss = st.session_state
    _breadcrumb("basic")
    with st.container(border=True):
        step_header(1, "Your plan", "A name for it, how much you'd put in, and how long you could leave it there.")
        # Widget state is dropped when a page is left, so values are copied into session state on Next.
        plan_name = st.text_input("Plan name (optional)", value=ss.plan_name, placeholder="e.g. My first savings plan")
        c1, c2 = st.columns(2)
        budget = c1.number_input("Amount ($)", min_value=100, max_value=10_000_000, step=500, value=int(ss.budget),
                                 help="The money you'd invest today, all at once.")
        years = c2.slider("Years you'd leave it invested", 1, 20, int(ss.years),
                          help="The simulator looks this far ahead. You can check shorter periods on the charts later.")
        st.markdown("**How do you want to play it?**")
        st.caption("This never changes what you invest in. It sets the gain you aim for and the loss you'd accept, "
                   "which become the starting positions of the goal and loss-limit lines on every chart.")
        approach = st.radio("Approach", list(APPROACHES), index=list(APPROACHES).index(ss.approach),
                            label_visibility="collapsed",
                            captions=[f"{a['blurb']} Goal ≈ {a['goal_k']:.0%} of the expected gain, "
                                      f"loss limit ≈ {a['stop_k']:g}× a typical yearly swing."
                                      for a in APPROACHES.values()])
    left, _, right = st.columns([1.2, 4, 2])
    if left.button("‹ Back", key="back_basic", width="stretch"):
        _go("welcome")
    if right.button("Next: your mix ›", key="next_basic", type="primary", width="stretch"):
        ss.plan_name, ss.budget, ss.years, ss.approach = plan_name, budget, years, approach
        _go("portfolio")


def _page_portfolio() -> None:
    ss = st.session_state
    _breadcrumb("portfolio")
    with st.container(border=True):
        step_header(2, "Your mix", "What does the money go into? Add investments until the shares add up to 100%.")
        st.caption(_plan_summary_line())

        with st.container(border=True):
            st.markdown("**Add an investment**")
            cls = st.selectbox("What kind?", list(CATALOG), format_func=lambda c: f"{c} — {CLASS_BLURB[c]}")
            if cls == "Bonds":  # only bonds are picked by country; everything else is one flat list
                options = CATALOG[cls][st.selectbox("Which country?", list(CATALOG[cls]))]
            else:
                options = {n: t for group in CATALOG[cls].values() for n, t in group.items()}
            name = st.selectbox("Which one?", [*options, *([OTHER] if cls in ALLOW_OTHER else [])])
            if name == OTHER:
                ticker = st.text_input("Yahoo Finance ticker", placeholder="e.g. AMD, EWJ, AVAX-USD",
                                       help="The short code used on finance sites, like AAPL for Apple. "
                                            "Press Enter after typing it.").strip().upper()
                name = ticker
            else:
                ticker = options[name]
            others = [r for r in ss.portfolio if r["ticker"] != ticker]
            room = 100 - sum(r["percentage"] for r in others)
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            share = c1.slider("Share of your money", 1, 100, min(20, room) if room >= 1 else 20, format="%d%%",
                              help=f"{room}% is still unassigned." if room > 0 else "The mix is already at 100%: "
                                   "adding more will put it over, then lower something or press *Scale to 100%*.")
            if c2.button("Add", type="primary", width="stretch", disabled=not ticker):
                ss.flash = f"{name} added"
                _set_portfolio(others + [_row(ticker, share, name, cls)])

        rows = ss.portfolio
        if not rows:
            st.info("Your mix is empty. Add at least one investment above.")
        else:
            st.markdown("**Your mix so far**")
            st.caption("Change a share by clicking on it, or delete a row (select it, then press the trash icon).")
            left, right = st.columns([3, 2])
            with left:
                edited = st.data_editor(
                    pd.DataFrame(rows)[["investment", "type", "percentage", "ticker"]],
                    key=f"mix_editor_{ss.mix_v}", hide_index=True, width="stretch", num_rows="delete",
                    disabled=["investment", "type"],
                    column_config={
                        "investment": st.column_config.TextColumn("Investment"),
                        "type": st.column_config.TextColumn("Kind"),
                        "percentage": st.column_config.NumberColumn("Share", min_value=0, max_value=100, step=1,
                                                                    format="%d%%"),
                        "ticker": None,
                    })
                new_rows = [_row(r["ticker"], r["percentage"], r["investment"], r["type"])
                            for r in edited.to_dict("records") if pd.notna(r["percentage"])]
                if new_rows != rows:
                    _set_portfolio(new_rows)
                total = _total()
                if total > 100:
                    st.error(f"That adds up to {total}%, more than the 100% you have.")
                elif total < 100:
                    st.warning(f"{total}% assigned; {100 - total}% still to go.")
                else:
                    st.success("All of your money is assigned (100%).")
                b1, b2 = st.columns(2)
                if len(rows) > 1 and b1.button("Split evenly", width="stretch"):
                    n = len(rows)
                    _set_portfolio([_row(r["ticker"], 100 // n + (1 if i < 100 % n else 0), r["investment"], r["type"])
                                    for i, r in enumerate(rows)])
                if total not in (0, 100) and b2.button("Scale to 100%", width="stretch",
                                                       help="Keeps the proportions, makes the total exactly 100%."):
                    scaled = [round(r["percentage"] * 100 / total) for r in rows]
                    scaled[0] += 100 - sum(scaled)
                    _set_portfolio([_row(r["ticker"], p, r["investment"], r["type"]) for r, p in zip(rows, scaled)])
            with right:
                st.plotly_chart(mix_pie(rows), width="stretch", config={"displayModeBar": False})
    _nav("basic", "Next: fine-tune ›", "tune", next_ok=bool(rows) and _total() == 100, key="portfolio")


def _page_tune() -> None:
    ss = st.session_state
    s = ss.settings
    _breadcrumb("tune")
    with st.container(border=True):
        step_header(3, "Fine-tune (optional)", "Sensible defaults are already set. Skip this if you're not sure.")
        n_sims = st.select_slider("How many scenarios to play out", [250, 500, 1000, 2000], value=s["n_sims"],
                                  help="More scenarios give steadier numbers but take longer.")
        engine = st.radio("How to imagine the future", ENGINES, index=ENGINES.index(s["engine"]),
                          format_func=lambda e: {
                              ENGINES[0]: "Statistical model — fat-tailed shocks and calm/stressed periods fitted to the data",
                              ENGINES[1]: "Replay real history — copies whole real months, so bad stretches stay together",
                          }[e])
        c1, c2 = st.columns(2)
        fee = c1.number_input("Yearly fees (%)", 0.0, 3.0, s["fee"] * 100, 0.1,
                              help="Fund and broker costs, taken out of the value every year.") / 100
        inflation = c2.number_input("Inflation (% a year)", 0.0, 10.0, s["inflation"] * 100, 0.5,
                                    help="Used to show results in today's money.") / 100
        real = st.checkbox("Show results in today's money (after inflation)", value=s["real"])
        reinvest = st.checkbox("Reinvest dividends", value=s["reinvest"],
                               help="Off: dividends are paid out to you instead of growing the investment; "
                                    "the value shown then leaves them out.")
        st.markdown("**What-if events**")
        st.caption("Add an event to every scenario to see how your plan would take it.")
        chosen = st.multiselect("Events", list(SHOCK_PRESETS), default=[n for n, _, _ in s["shocks"]],
                                format_func=lambda n: f"{n} — {SHOCK_PRESETS[n]['blurb']}", label_visibility="collapsed")
        shocks = ()
        if chosen:
            prev_at = s["shocks"][0][1] if s["shocks"] else min(1.0, float(ss.years))
            prev_p = int(s["shocks"][0][2] * 100) if s["shocks"] else 100
            c3, c4 = st.columns(2)
            at = c3.slider("When (years from now)", 0.0, float(ss.years), min(prev_at, float(ss.years)), 0.25)
            prob = c4.slider("Chance it happens (%)", 10, 100, prev_p, 10)
            shocks = tuple((n, at, prob / 100) for n in chosen)
    left, mid, right = st.columns([1.2, 2, 2])
    if left.button("‹ Back", key="back_tune", width="stretch"):
        _go("portfolio")
    if mid.button("Skip, use the defaults", key="skip_tune", width="stretch"):
        ss.settings = dict(DEFAULT_SETTINGS)
        _go("review")
    if right.button("Next: review ›", key="next_tune", type="primary", width="stretch"):
        ss.settings = dict(n_sims=n_sims, engine=engine, fee=fee, inflation=inflation, real=real, reinvest=reinvest,
                           shocks=shocks)
        _go("review")


def _build_plan() -> dict:
    ss = st.session_state
    rows = [r for r in ss.portfolio if r["percentage"] > 0]
    total = sum(r["percentage"] for r in rows)
    s = ss.settings
    return dict(name=ss.plan_name.strip(), budget=float(ss.budget), years=int(ss.years), approach=ss.approach,
                weights={r["ticker"]: r["percentage"] / total for r in rows},
                names={r["ticker"]: r["investment"] for r in rows}, classes={r["ticker"]: r["type"] for r in rows},
                n_sims=s["n_sims"], engine=s["engine"], fee=s["fee"], inflation=s["inflation"] if s["real"] else 0.0,
                reinvest=s["reinvest"], shocks=s["shocks"])


def _page_review() -> None:
    ss = st.session_state
    s = ss.settings
    _breadcrumb("review")
    with st.container(border=True):
        step_header(4, "Review your plan", "Everything below goes into the simulation. Change anything you like.")
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"**{ss.plan_name or 'Your plan'}**")
            events = ", ".join(n for n, _, _ in s["shocks"]) or "none"
            st.markdown(
                f"- **Amount:** {money(ss.budget)} for **{ss.years} year{'s' if ss.years > 1 else ''}**\n"
                f"- **Approach:** {ss.approach} — {APPROACHES[ss.approach]['blurb']}\n"
                f"- **Method:** {s['engine']} · {s['n_sims']:,} scenarios\n"
                f"- **Costs:** {s['fee']:.1%} yearly fees · "
                + (f"results in today's money ({s['inflation']:.1%} inflation)" if s["real"] else "inflation not applied")
                + " · dividends " + ("reinvested" if s["reinvest"] else "paid out") + "\n"
                f"- **What-if events:** {events}")
            df = pd.DataFrame(ss.portfolio)
            df["amount"] = [money(r["percentage"] / 100 * ss.budget) for r in ss.portfolio]
            st.dataframe(df[["investment", "type", "percentage", "amount"]], hide_index=True, width="stretch",
                         column_config={"investment": "Investment", "type": "Kind",
                                        "percentage": st.column_config.NumberColumn("Share", format="%d%%"),
                                        "amount": "Amount"})
        with right:
            st.plotly_chart(mix_pie(ss.portfolio, height=240), width="stretch", config={"displayModeBar": False})
        e1, e2, e3 = st.columns(3)
        if e1.button("Edit plan", width="stretch"):
            _go("basic")
        if e2.button("Edit mix", width="stretch"):
            _go("portfolio")
        if e3.button("Edit settings", width="stretch"):
            _go("tune")
    st.write("")
    if st.button(f"Show me what could happen to my {money(ss.budget)}", type="primary", width="stretch"):
        ss.plan = _build_plan()  # the app reads st.session_state.plan
        _go("done")
    return None


def _page_done() -> None:
    ss = st.session_state
    with st.container(border=True):
        c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
        c1.markdown(f"**Your plan:** {_plan_summary_line()} · "
                    + ", ".join(f"{r['investment']} {r['percentage']}%" for r in ss.portfolio))
        if c2.button("Edit my plan", width="stretch"):
            _go("review")


def plan_wizard() -> None:
    _init_state()
    page = st.session_state.page
    if page == "welcome":
        _page_welcome()
    elif page == "basic":
        _page_basic()
    elif page == "portfolio":
        _page_portfolio()
    elif page == "tune":
        _page_tune()
    elif page == "review":
        _page_review()
    else:
        _page_done()

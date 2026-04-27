"""
dashboard/Home.py  --  PR-Futures public dashboard landing page.

Run locally:
    cd D:/Trading/py-projects/pr-futures
    streamlit run dashboard/Home.py

Deploy:
    1. Push to GitHub.
    2. Go to share.streamlit.io → New app → select this repo.
    3. Set "Main file path" to  dashboard/Home.py
    4. Add SUPABASE_DB_URL in the Secrets section.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))  # allow `from _data import …`

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from _data import (
    compute_metrics,
    equity_curve_df,
    load_available_symbols,
    load_date_bounds,
    load_trades,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title  = "PR-Futures | Algo Dashboard",
    page_icon   = "📈",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Metric card style */
[data-testid="metric-container"] {
    background: #1C2333;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 16px 20px;
}
/* Equity value colour */
.pnl-pos { color: #22C55E; font-weight: 700; }
.pnl-neg { color: #EF4444; font-weight: 700; }
/* Hero */
.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(90deg, #00D4AA, #60A5FA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.hero-sub {
    color: #94A3B8;
    font-size: 1.05rem;
    margin-top: 4px;
}
.divider { border-top: 1px solid #2D3748; margin: 24px 0; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar filters ───────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/futures.png", width=56)
    st.markdown("## PR-Futures")
    st.markdown("Algorithmic Futures Trading")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown("### 🔍 Filter")

    # Data source quick-pick
    source = st.radio(
        "Data source",
        ["📊 Backtest", "📈 Paper Trading", "📅 Custom"],
        index=0,
        label_visibility="collapsed",
    )

    db_start, db_end = load_date_bounds()
    today = date.today()

    if source == "📊 Backtest":
        # Show all historical runs (exclude last 30 days = paper)
        d_start = date.fromisoformat(db_start)
        d_end   = today - timedelta(days=30)
    elif source == "📈 Paper Trading":
        d_start = today - timedelta(days=90)
        d_end   = today
    else:
        d_start = date.fromisoformat(db_start)
        d_end   = today

    if source == "📅 Custom":
        d_start = st.date_input("From", value=d_start)
        d_end   = st.date_input("To",   value=d_end)

    all_symbols = load_available_symbols()
    selected_symbols = st.multiselect(
        "Symbols",
        options=all_symbols,
        default=all_symbols,
        placeholder="All symbols",
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.caption("Data refreshes every 5 min")
    st.caption("Past performance does not guarantee future results.")

# ── Load data ─────────────────────────────────────────────────────────────────

df   = load_trades(str(d_start), str(d_end), selected_symbols or None)
m    = compute_metrics(df)
eq   = equity_curve_df(df)

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown('<p class="hero-title">PR-Futures Algo Dashboard</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Systematic reversal strategy · CME futures · '
    'Automated execution via IB Gateway</p>',
    unsafe_allow_html=True,
)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── No-data guard ─────────────────────────────────────────────────────────────

if df.empty:
    st.info(
        "No completed trades found for the selected filters. "
        "Try widening the date range or checking the database connection.",
        icon="ℹ️",
    )
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────

k1, k2, k3, k4, k5 = st.columns(5)

pnl_sign  = "+" if m["net_pnl"] >= 0 else ""
pf_str    = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
sharpe_color = "normal" if m["sharpe"] >= 0 else "inverse"

k1.metric(
    "Net P&L",
    f"{pnl_sign}${m['net_pnl']:,.0f}",
    delta=None,
)
k2.metric(
    "Win Rate",
    f"{m['win_rate']*100:.1f}%",
    f"{m['n_wins']}W / {m['n_losses']}L",
)
k3.metric(
    "Profit Factor",
    pf_str,
)
k4.metric(
    "Sharpe Ratio",
    f"{m['sharpe']:.2f}",
)
k5.metric(
    "Max Drawdown",
    f"${m['max_drawdown']:,.0f}",
    f"{m['n_trades']} trades",
    delta_color="inverse",
)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── Equity curve ──────────────────────────────────────────────────────────────

st.markdown("### 📈 Cumulative P&L")

fig = go.Figure()

# Equity area
final_eq = eq["equity"].iloc[-1] if not eq.empty else 0
line_col  = "#22C55E" if final_eq >= 0 else "#EF4444"
fill_col  = "rgba(34,197,94,0.08)" if final_eq >= 0 else "rgba(239,68,68,0.08)"

fig.add_trace(go.Scatter(
    x    = eq["entry_time"],
    y    = eq["equity"],
    name = "Cumulative P&L",
    mode = "lines",
    line = dict(color=line_col, width=2.5),
    fill = "tozeroy",
    fillcolor = fill_col,
    hovertemplate = "%{x|%Y-%m-%d %H:%M}<br><b>$%{y:,.0f}</b><extra></extra>",
))

# Zero line
fig.add_hline(y=0, line=dict(color="#4B5563", width=1, dash="dot"))

fig.update_layout(
    height          = 380,
    margin          = dict(l=0, r=0, t=10, b=0),
    plot_bgcolor    = "#0F1117",
    paper_bgcolor   = "#0F1117",
    font            = dict(color="#E2E8F0"),
    xaxis           = dict(showgrid=False, zeroline=False),
    yaxis           = dict(
        showgrid     = True,
        gridcolor    = "#1C2333",
        zeroline     = False,
        tickprefix   = "$",
        tickformat   = ",.0f",
    ),
    legend          = dict(bgcolor="rgba(0,0,0,0)"),
    hovermode       = "x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ── Bottom row: win-rate by symbol + recent trades ────────────────────────────

col_l, col_r = st.columns([1, 1.6], gap="large")

# Win rate by symbol
with col_l:
    st.markdown("### 🎯 Win Rate by Symbol")

    if not df.empty:
        sym_stats = (
            df.groupby("symbol")
            .agg(
                trades = ("pnl_net", "count"),
                wins   = ("win", "sum"),
                pnl    = ("pnl_net", "sum"),
            )
            .assign(win_rate=lambda x: x["wins"] / x["trades"] * 100)
            .sort_values("win_rate", ascending=True)
        )

        bar_colors = [
            "#22C55E" if wr >= 50 else "#EF4444"
            for wr in sym_stats["win_rate"]
        ]

        fig2 = go.Figure(go.Bar(
            x           = sym_stats["win_rate"],
            y           = sym_stats.index,
            orientation = "h",
            marker_color= bar_colors,
            text        = [f"{v:.0f}%" for v in sym_stats["win_rate"]],
            textposition= "outside",
            hovertemplate = (
                "<b>%{y}</b><br>"
                "Win rate: %{x:.1f}%<br>"
                "<extra></extra>"
            ),
        ))
        fig2.update_layout(
            height        = 300,
            margin        = dict(l=0, r=40, t=0, b=0),
            plot_bgcolor  = "#0F1117",
            paper_bgcolor = "#0F1117",
            font          = dict(color="#E2E8F0"),
            xaxis         = dict(showgrid=False, range=[0, 110], visible=False),
            yaxis         = dict(showgrid=False),
        )
        st.plotly_chart(fig2, use_container_width=True)

# Recent trades
with col_r:
    st.markdown("### 🕐 Recent Trades")

    recent = df.sort_values("entry_time", ascending=False).head(12)

    def _fmt_row(row):
        icon = "✅" if row["pnl_net"] > 0 else "❌" if row["pnl_net"] < 0 else "➖"
        sign = "+" if row["pnl_net"] >= 0 else ""
        return {
            ""       : icon,
            "Symbol" : row["symbol"],
            "Side"   : row["direction"],
            "Entry"  : row["entry_time"].strftime("%m/%d %H:%M"),
            "P&L"    : f"{sign}${row['pnl_net']:.0f}",
            "R"      : f"{row['r_multiple']:+.2f}R" if row["r_multiple"] is not None else "–",
            "Reason" : row["exit_reason"] or "–",
        }

    tbl = [_fmt_row(r) for _, r in recent.iterrows()]
    st.dataframe(
        tbl,
        use_container_width=True,
        hide_index=True,
        height=340,
        column_config={
            "P&L": st.column_config.TextColumn("P&L"),
        },
    )

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.caption(
    "⚠️ **Educational purposes only.** This dashboard presents historical and "
    "simulated paper-trading results. Past performance is not indicative of "
    "future results. Futures trading involves substantial risk of loss."
)

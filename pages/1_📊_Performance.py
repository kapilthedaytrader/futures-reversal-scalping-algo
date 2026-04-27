"""
pages/1_Performance.py  --  Deep performance analytics.

Charts:
  • Monthly P&L heatmap
  • Drawdown underwater chart
  • R-multiple distribution
  • Exit reason breakdown
  • Hour-of-day win rate
  • Long vs Short comparison
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from _data import (
    compute_metrics,
    equity_curve_df,
    load_available_symbols,
    load_date_bounds,
    load_trades,
    monthly_pnl_pivot,
)

st.set_page_config(page_title="Performance | PR-Futures", page_icon="📊", layout="wide")

# ── Sidebar (mirrors Home) ────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 Performance")
    source_label = st.radio(
        "Data source",
        ["📊 Backtest", "📈 Paper Trading", "📅 All"],
        index=0,
    )
    source_map = {
        "📊 Backtest":      "backtest",
        "📈 Paper Trading": "paper",
        "📅 All":           None,
    }
    source_filter = source_map[source_label]

    db_start, db_end = load_date_bounds(source_filter)
    d_start = st.date_input("From", value=date.fromisoformat(db_start))
    d_end   = st.date_input("To",   value=date.fromisoformat(db_end))

    all_syms = load_available_symbols()
    syms = st.multiselect("Symbols", all_syms, default=all_syms)

df = load_trades(str(d_start), str(d_end), syms or None, source_filter)
m  = compute_metrics(df)

st.markdown("# 📊 Performance Analysis")

if df.empty:
    st.info("No data for the selected filters.", icon="ℹ️")
    st.stop()

# ── Summary stats table ───────────────────────────────────────────────────────

st.markdown("### Key Statistics")

cols = st.columns(4)
stats_left = [
    ("Total Trades",     f"{m['n_trades']}"),
    ("Wins / Losses",    f"{m['n_wins']} / {m['n_losses']}"),
    ("Win Rate",         f"{m['win_rate']*100:.1f}%"),
    ("Profit Factor",    f"{m['profit_factor']:.2f}" if m['profit_factor'] != float('inf') else "∞"),
]
stats_right = [
    ("Net P&L",          f"${m['net_pnl']:+,.2f}"),
    ("Avg Win / Loss",   f"${m['avg_win']:+.0f} / ${m['avg_loss']:+.0f}"),
    ("Reward:Risk",      f"{m['rr_ratio']:.2f}"),
    ("Avg R-Multiple",   f"{m['avg_r']:+.2f}R"),
]
stats_extra = [
    ("Sharpe (ann.)",    f"{m['sharpe']:.2f}"),
    ("Max Drawdown",     f"${m['max_drawdown']:,.0f}"),
    ("Avg Hold Time",    f"{m['avg_hold_min']:.0f} min"),
    ("Symbols traded",   str(df["symbol"].nunique())),
]

for i, (label, value) in enumerate(stats_left):
    cols[0].metric(label, value)
for i, (label, value) in enumerate(stats_right):
    cols[1].metric(label, value)
for i, (label, value) in enumerate(stats_extra):
    cols[2].metric(label, value)

st.divider()

# ── Equity + Drawdown ─────────────────────────────────────────────────────────

st.markdown("### Equity Curve & Drawdown")

eq = equity_curve_df(df)

fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.7, 0.3],
    shared_xaxes=True,
    vertical_spacing=0.04,
)

final_pnl = eq["equity"].iloc[-1] if not eq.empty else 0
ec_color  = "#22C55E" if final_pnl >= 0 else "#EF4444"

fig.add_trace(go.Scatter(
    x=eq["entry_time"], y=eq["equity"],
    name="Equity", mode="lines",
    line=dict(color=ec_color, width=2),
    fill="tozeroy", fillcolor="rgba(34,197,94,0.07)",
    hovertemplate="%{x|%Y-%m-%d %H:%M}<br>$%{y:,.0f}<extra></extra>",
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=eq["entry_time"], y=eq["drawdown"],
    name="Drawdown", mode="lines",
    line=dict(color="#EF4444", width=1.5),
    fill="tozeroy", fillcolor="rgba(239,68,68,0.15)",
    hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
), row=2, col=1)

fig.update_layout(
    height=460, showlegend=False,
    plot_bgcolor="#0F1117", paper_bgcolor="#0F1117",
    font=dict(color="#E2E8F0"),
    margin=dict(l=0, r=0, t=10, b=0),
    hovermode="x unified",
)
for row in (1, 2):
    fig.update_xaxes(showgrid=False, row=row, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#1C2333",
                     tickprefix="$", tickformat=",.0f", row=row, col=1)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Monthly P&L heatmap ───────────────────────────────────────────────────────

st.markdown("### Monthly P&L Heatmap")

monthly = monthly_pnl_pivot(df)

if not monthly.empty:
    z_vals  = monthly.values.tolist()
    x_labels = list(monthly.columns)
    y_labels = [str(y) for y in monthly.index]

    text_vals = [
        [f"${v:+,.0f}" if not np.isnan(v) else "" for v in row]
        for row in monthly.values
    ]

    fig_heat = go.Figure(go.Heatmap(
        z          = z_vals,
        x          = x_labels,
        y          = y_labels,
        text       = text_vals,
        texttemplate = "%{text}",
        colorscale = [
            [0.0,  "#7F1D1D"],
            [0.35, "#EF4444"],
            [0.5,  "#1C2333"],
            [0.65, "#22C55E"],
            [1.0,  "#14532D"],
        ],
        zmid       = 0,
        showscale  = False,
        hovertemplate = "<b>%{y} %{x}</b><br>$%{z:+,.0f}<extra></extra>",
    ))
    fig_heat.update_layout(
        height=max(140, len(y_labels) * 50 + 60),
        plot_bgcolor="#0F1117", paper_bgcolor="#0F1117",
        font=dict(color="#E2E8F0"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Not enough data for monthly heatmap.")

st.divider()

# ── Bottom row: R-distribution + Exit reasons + Hour of day ──────────────────

c1, c2, c3 = st.columns(3)

# R-multiple distribution
with c1:
    st.markdown("### R-Multiple Distribution")
    r_vals = df["r_multiple"].dropna()
    if not r_vals.empty:
        fig_r = go.Figure(go.Histogram(
            x=r_vals,
            nbinsx=30,
            marker=dict(
                color=[
                    "#22C55E" if v >= 0 else "#EF4444"
                    for v in r_vals
                ],
                line=dict(width=0),
            ),
            hovertemplate="R: %{x:.2f}<br>Count: %{y}<extra></extra>",
        ))
        fig_r.add_vline(x=0, line=dict(color="#94A3B8", width=1, dash="dot"))
        fig_r.update_layout(
            height=280,
            plot_bgcolor="#0F1117", paper_bgcolor="#0F1117",
            font=dict(color="#E2E8F0"),
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="R-Multiple", showgrid=False),
            yaxis=dict(title="# Trades", showgrid=True, gridcolor="#1C2333"),
            showlegend=False,
        )
        st.plotly_chart(fig_r, use_container_width=True)
        st.caption(
            f"Avg: {r_vals.mean():+.2f}R  |  "
            f"Med: {r_vals.median():+.2f}R  |  "
            f"Best: {r_vals.max():+.2f}R  |  "
            f"Worst: {r_vals.min():+.2f}R"
        )

# Exit reason breakdown
with c2:
    st.markdown("### Exit Reasons")
    reasons = (
        df.groupby("exit_reason")
        .agg(trades=("pnl_net","count"), pnl=("pnl_net","sum"))
        .sort_values("trades", ascending=False)
    )
    if not reasons.empty:
        fig_ex = go.Figure(go.Bar(
            x=reasons["trades"],
            y=reasons.index,
            orientation="h",
            marker_color=[
                "#22C55E" if p >= 0 else "#EF4444"
                for p in reasons["pnl"]
            ],
            text=[f"{t} trades  ${p:+,.0f}" for t, p in zip(reasons["trades"], reasons["pnl"])],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} trades<extra></extra>",
        ))
        fig_ex.update_layout(
            height=280,
            plot_bgcolor="#0F1117", paper_bgcolor="#0F1117",
            font=dict(color="#E2E8F0"),
            margin=dict(l=0, r=120, t=10, b=0),
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_ex, use_container_width=True)

# Hour-of-day win rate
with c3:
    st.markdown("### Hour-of-Day (ET)")
    hourly = (
        df.groupby("entry_hour")
        .agg(trades=("pnl_net","count"), wins=("win","sum"), pnl=("pnl_net","sum"))
        .assign(win_rate=lambda x: x["wins"]/x["trades"]*100)
    )
    if not hourly.empty:
        fig_hr = go.Figure(go.Bar(
            x=hourly.index,
            y=hourly["win_rate"],
            marker_color=[
                "#22C55E" if wr >= 50 else "#EF4444"
                for wr in hourly["win_rate"]
            ],
            text=[f"{wr:.0f}%" for wr in hourly["win_rate"]],
            textposition="outside",
            hovertemplate="<b>%{x}:00 ET</b><br>Win rate: %{y:.1f}%<extra></extra>",
        ))
        fig_hr.add_hline(y=50, line=dict(color="#4B5563", width=1, dash="dot"))
        fig_hr.update_layout(
            height=280,
            plot_bgcolor="#0F1117", paper_bgcolor="#0F1117",
            font=dict(color="#E2E8F0"),
            margin=dict(l=0, r=0, t=10, b=20),
            xaxis=dict(title="Hour (ET)", showgrid=False, dtick=1),
            yaxis=dict(title="Win %", showgrid=True, gridcolor="#1C2333",
                       range=[0, 110]),
        )
        st.plotly_chart(fig_hr, use_container_width=True)

st.divider()

# ── Long vs Short ─────────────────────────────────────────────────────────────

st.markdown("### Long vs Short Breakdown")

side_stats = (
    df.groupby("direction")
    .agg(
        trades   = ("pnl_net", "count"),
        wins     = ("win",     "sum"),
        net_pnl  = ("pnl_net", "sum"),
        avg_r    = ("r_multiple", "mean"),
    )
    .assign(win_rate=lambda x: x["wins"] / x["trades"] * 100)
    .reset_index()
)
st.dataframe(
    side_stats.rename(columns={
        "direction": "Side", "trades": "Trades",
        "wins": "Wins", "win_rate": "Win %",
        "net_pnl": "Net P&L ($)", "avg_r": "Avg R",
    }).style.format({
        "Win %":      "{:.1f}",
        "Net P&L ($)": "${:+,.2f}",
        "Avg R":      "{:+.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Symbol breakdown ──────────────────────────────────────────────────────────

st.markdown("### Per-Symbol Breakdown")

sym_stats = (
    df.groupby("symbol")
    .agg(
        trades   = ("pnl_net", "count"),
        wins     = ("win",     "sum"),
        net_pnl  = ("pnl_net", "sum"),
        avg_r    = ("r_multiple", "mean"),
        avg_hold = ("hold_min",   "mean"),
    )
    .assign(win_rate=lambda x: x["wins"] / x["trades"] * 100)
    .sort_values("net_pnl", ascending=False)
    .reset_index()
)
st.dataframe(
    sym_stats.rename(columns={
        "symbol": "Symbol", "trades": "Trades",
        "wins": "Wins", "win_rate": "Win %",
        "net_pnl": "Net P&L ($)", "avg_r": "Avg R",
        "avg_hold": "Avg Hold (min)",
    }).style.format({
        "Win %":           "{:.1f}",
        "Net P&L ($)":     "${:+,.2f}",
        "Avg R":           "{:+.2f}",
        "Avg Hold (min)":  "{:.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)

"""
pages/2_Trade_Log.py  --  Filterable, sortable trade history table.

Features:
  • Filter by date range, symbol, direction, exit reason, outcome (W/L)
  • Sortable columns
  • Download as CSV
  • Per-trade colour coding
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

import pandas as pd
import streamlit as st

from _data import load_available_symbols, load_date_bounds, load_trades

st.set_page_config(page_title="Trade Log | PR-Futures", page_icon="📋", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📋 Trade Log")

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

    st.divider()
    st.markdown("### ⚙️ Column filters")

    direction_filter = st.multiselect(
        "Direction", ["LONG", "SHORT"], default=["LONG", "SHORT"]
    )
    outcome_filter = st.multiselect(
        "Outcome", ["Win", "Loss", "Breakeven"], default=["Win", "Loss", "Breakeven"]
    )

# ── Load + filter ─────────────────────────────────────────────────────────────

df = load_trades(str(d_start), str(d_end), syms or None, source_filter)

if df.empty:
    st.markdown("# 📋 Trade Log")
    st.info("No completed trades for the selected filters.", icon="ℹ️")
    st.stop()

# Apply sidebar filters
if direction_filter:
    df = df[df["direction"].isin(direction_filter)]

outcome_map = {
    "Win":        df["pnl_net"] > 0,
    "Loss":       df["pnl_net"] < 0,
    "Breakeven":  df["pnl_net"] == 0,
}
if outcome_filter and len(outcome_filter) < 3:
    mask = pd.Series(False, index=df.index)
    for o in outcome_filter:
        if o in outcome_map:
            mask = mask | outcome_map[o]
    df = df[mask]

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(f"# 📋 Trade Log  <span style='font-size:1rem;color:#94A3B8'>({len(df):,} trades)</span>",
            unsafe_allow_html=True)

col_dl, col_sort = st.columns([3, 1])
with col_sort:
    sort_by = st.selectbox(
        "Sort by",
        ["entry_time ↓", "entry_time ↑", "pnl_net ↓", "pnl_net ↑", "r_multiple ↓"],
        label_visibility="collapsed",
    )

# Apply sort
sort_map = {
    "entry_time ↓":  ("entry_time",  False),
    "entry_time ↑":  ("entry_time",  True),
    "pnl_net ↓":     ("pnl_net",     False),
    "pnl_net ↑":     ("pnl_net",     True),
    "r_multiple ↓":  ("r_multiple",  False),
}
sort_col, sort_asc = sort_map[sort_by]
df = df.sort_values(sort_col, ascending=sort_asc)

# ── Build display table ───────────────────────────────────────────────────────

def outcome_icon(pnl: float) -> str:
    if pnl > 0: return "✅"
    if pnl < 0: return "❌"
    return "➖"

display = pd.DataFrame({
    ""        : [outcome_icon(p) for p in df["pnl_net"]],
    "Symbol"  : df["symbol"].values,
    "Side"    : df["direction"].values,
    "Entry"   : [t.strftime("%Y-%m-%d %H:%M") for t in df["entry_time"]],
    "Exit"    : [t.strftime("%Y-%m-%d %H:%M") for t in df["exit_time"]],
    "Hold"    : [f"{h:.0f}m" for h in df["hold_min"]],
    "Entry $" : [f"{p:,.2f}" for p in df["entry_price"]],
    "Exit $"  : [f"{p:,.2f}" for p in df["exit_price"]],
    "Qty"     : df["contracts"].values,
    "P&L"     : [f"${p:+,.2f}" for p in df["pnl_net"]],
    "R"       : [
        f"{r:+.2f}R" if r is not None and str(r) != "nan" else "–"
        for r in df["r_multiple"]
    ],
    "Reason"  : df["exit_reason"].fillna("–").values,
})

# Download button
with col_dl:
    csv = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label    = "⬇️ Download CSV",
        data     = csv,
        file_name= f"pr_futures_trades_{d_start}_{d_end}.csv",
        mime     = "text/csv",
    )

# Render table
st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    height=min(600, len(display) * 35 + 40),
)

# ── Summary strip ─────────────────────────────────────────────────────────────

st.divider()
wins_shown  = (df["pnl_net"] > 0).sum()
total_shown = len(df)
pnl_shown   = df["pnl_net"].sum()
wr_shown    = wins_shown / total_shown * 100 if total_shown else 0

st.caption(
    f"Showing {total_shown:,} trades  ·  "
    f"Win rate {wr_shown:.1f}%  ({wins_shown}W / {total_shown - wins_shown}L)  ·  "
    f"Net P&L **${pnl_shown:+,.2f}**"
)

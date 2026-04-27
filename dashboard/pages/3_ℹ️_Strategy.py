"""
pages/3_Strategy.py  --  Strategy description / About page.

This is your public-facing pitch:
  • What the algo does (without giving away the secret sauce)
  • Risk management approach
  • Track record summary
  • CTA for future subscription
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta

import streamlit as st

from _data import compute_metrics, load_date_bounds, load_trades

st.set_page_config(page_title="Strategy | PR-Futures", page_icon="ℹ️", layout="wide")

# ── Load headline metrics for the "at a glance" box ──────────────────────────

db_start, db_end = load_date_bounds()
df_all = load_trades(db_start, db_end)
m      = compute_metrics(df_all)

# ── Page ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.section-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #00D4AA;
    margin-top: 2rem;
    margin-bottom: 0.5rem;
}
.card {
    background: #1C2333;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    color: #CBD5E1;
    line-height: 1.7;
}
.card b {
    color: #E2E8F0;
}
.card ul {
    margin: 8px 0 0 0;
    padding-left: 18px;
}
.card li {
    margin-bottom: 4px;
}
.tag {
    display: inline-block;
    background: #0F1117;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.8rem;
    margin: 3px;
    color: #94A3B8 !important;
    color: #94A3B8;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# PR-Futures Reversal Strategy")
st.markdown("*Systematic, rule-based momentum reversal trading on CME futures.*")

st.divider()

# ── At a glance ───────────────────────────────────────────────────────────────

st.markdown('<p class="section-title">At a Glance</p>', unsafe_allow_html=True)

if m:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Trades",   f"{m['n_trades']:,}")
    k2.metric("Win Rate",       f"{m['win_rate']*100:.1f}%")
    k3.metric(
        "Profit Factor",
        f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞",
    )
    k4.metric("Sharpe (ann.)", f"{m['sharpe']:.2f}")
    st.caption(
        f"Based on {m['n_trades']:,} completed trades from {db_start} to {db_end}. "
        "Results include both historical backtests and live paper trading."
    )

st.divider()

# ── What we trade ─────────────────────────────────────────────────────────────

st.markdown('<p class="section-title">What We Trade</p>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
<div class="card">
<b>📌 Instruments</b><br><br>
21 liquid CME/CBOT futures across four asset classes:
<br><br>
<span class="tag">🏦 Equity Index</span>
<span class="tag">MNQ · MES · NQ · ES</span>
<span class="tag">MYM · YM · M2K · RTY</span>
<br>
<span class="tag">🥇 Metals</span>
<span class="tag">MGC · GC · MSI · SI</span>
<br>
<span class="tag">🛢️ Energy</span>
<span class="tag">MCL · CL</span>
<br>
<span class="tag">💱 FX Futures</span>
<span class="tag">M6E · 6E · M6B · 6B · M6A · 6A</span>
</div>
""", unsafe_allow_html=True)

with col2:
    st.markdown("""
<div class="card">
<b>🕐 Session</b><br><br>
• <b>Equity Index & Metals</b>: CME Globex — Sunday 18:00 to Friday 17:00 ET<br>
• <b>FX Futures</b>: CME Globex — Sunday 17:00 to Friday 16:00 ET<br>
• <b>Active window</b>: Full ETH session, avoiding the final 15 minutes before close<br>
• <b>RTH mode available</b>: 09:45–15:15 ET for reduced overnight exposure
</div>
""", unsafe_allow_html=True)

st.divider()

# ── How the strategy works ─────────────────────────────────────────────────────

st.markdown('<p class="section-title">How It Works</p>', unsafe_allow_html=True)

st.markdown("""
The strategy identifies **exhausted momentum moves** — moments when price has
pushed too far, too fast from equilibrium — and fades the move back toward value.

It operates on two timeframes simultaneously:
""")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("""
<div class="card">
<b>Step 1 — 5-Min Setup</b><br><br>
The scanner monitors every 5-minute bar for a <em>cluster of conditions</em>
that signal an overextended move:
<ul>
  <li>Price extended beyond a volatility threshold from the 9-EMA</li>
  <li>Three consecutive candles of the same colour (momentum exhaustion pattern)</li>
  <li>Bar deviation confirms overextension relative to ATR</li>
  <li>Move must be at or near the session high or low</li>
</ul>
Only when <em>all conditions align</em> does a setup activate.
</div>
""", unsafe_allow_html=True)

with col_b:
    st.markdown("""
<div class="card">
<b>Step 2 — 1-Min Entry Trigger</b><br><br>
Once a setup is active, the strategy watches the 1-minute chart for a
<em>confirmed reversal candle</em>:
<ul>
  <li>Colour flip: red-to-green (long) or green-to-red (short)</li>
  <li>Bar must still be extended from the 9-EMA</li>
  <li>Bar must be at the session extreme (high or low)</li>
</ul>
All three must be true on the same bar. The order fires on the close
of that 1-minute candle — no look-ahead, no manual intervention.
</div>
""", unsafe_allow_html=True)

with col_c:
    st.markdown("""
<div class="card">
<b>Step 3 — Exit Management</b><br><br>
Risk is defined before the trade opens. Exit logic is fully automated:
<ul>
  <li><b>Stop loss</b>: placed at the trigger candle's high/low (1–2 ticks outside)</li>
  <li><b>Target 1</b>: 1× risk (partial exit, move stop to breakeven)</li>
  <li><b>Target 2</b>: 3× risk (remaining position)</li>
  <li><b>Trailing</b>: EMA-cross trail on the remainder if neither target is hit</li>
  <li><b>EOD close</b>: all positions closed before session maintenance break</li>
</ul>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Risk management ───────────────────────────────────────────────────────────

st.markdown('<p class="section-title">Risk Management</p>', unsafe_allow_html=True)

st.markdown("""
<div class="card">
<b>Fixed-R Position Sizing</b><br><br>

Every trade risks the same dollar amount — the <em>R</em>. Position size (contracts)
is calculated so that if the stop is hit, the loss equals exactly 1R.
This keeps any single loss small regardless of the instrument's volatility.

<br><br>

<b>Risk components per contract</b>:
<ul>
  <li>Price risk: entry-to-stop × contract multiplier</li>
  <li>Exit slippage allowance: 1 tick × tick value</li>
  <li>Round-trip commission: entry + exit</li>
</ul>

The broker (Interactive Brokers) executes market-on-close entries and limit-order
exits automatically. No manual intervention is ever needed once the bot is running.
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Technology ────────────────────────────────────────────────────────────────

st.markdown('<p class="section-title">Technology Stack</p>', unsafe_allow_html=True)

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("""
<div class="card">
<b>⚙️ Execution</b><br><br>
• <b>Broker</b>: Interactive Brokers — institutional-grade fills and data<br>
• <b>API</b>: IB Gateway + ib_insync (async Python)<br>
• <b>Infrastructure</b>: Linux VPS (Hetzner) with UPS-backed uptime<br>
• <b>Uptime</b>: IBC auto-login + systemd service restart on crash<br>
• <b>Monitoring</b>: Real-time alerts via Telegram and Discord
</div>
""", unsafe_allow_html=True)

with col_t2:
    st.markdown("""
<div class="card">
<b>📊 Research & Validation</b><br><br>
• <b>Backtest engine</b>: custom tick-accurate Python backtester<br>
• <b>Data source</b>: IBKR historical data (same feed as live execution)<br>
• <b>Database</b>: Supabase / PostgreSQL — every bar, setup, and trade logged<br>
• <b>Analysis</b>: This dashboard — built with Streamlit + Plotly
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Transparency ──────────────────────────────────────────────────────────────

st.markdown('<p class="section-title">Transparency</p>', unsafe_allow_html=True)

st.markdown("""
All trade data shown on this dashboard is sourced directly from the live database —
no cherry-picking, no smoothing. Backtests use the same data feed and the same
execution engine as paper trading. The only difference is that backtest orders are
simulated at bar-close rather than routed to a broker.

**Backtest assumptions:**
- Entry at the close of the trigger 1-minute candle (slight pessimism vs market-order fill)
- Slippage: 1 tick on exits
- Commission: actual IB commission schedule by instrument
- No partial fills, no requotes

These results **include losing periods** and **drawdowns**. We do not hide bad runs.
""")

st.divider()

# ── Subscription CTA ──────────────────────────────────────────────────────────

st.markdown('<p class="section-title">📬 Stay in the Loop</p>', unsafe_allow_html=True)

st.markdown("""
<div class="card">
We're preparing a <b>live signal subscription</b> — get real-time entry and exit
alerts on your phone as soon as the algo fires a trade.

<br><br>

• ✅ Telegram + Discord alerts (entry price, stop, R-risk per contract)<br>
• ✅ No software to install — alerts delivered to your existing apps<br>
• ✅ You choose your own broker and position size<br>
• ✅ No broker credentials shared with us — ever<br>

<br>

Interested? Drop us a message to be added to the early-access waitlist.
</div>
""", unsafe_allow_html=True)

# ── Disclaimer ────────────────────────────────────────────────────────────────

st.divider()
st.warning("""
**Risk Disclosure** · Futures trading involves substantial risk of loss and is not
appropriate for all investors. Past performance — whether backtested or from live
paper trading — is not indicative of future results. The strategy and signals
presented here are for **educational and informational purposes only** and do not
constitute financial advice. You are solely responsible for your own trading
decisions and any resulting losses.
""")

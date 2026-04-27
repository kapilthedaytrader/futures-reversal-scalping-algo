"""
dashboard/_data.py  --  Shared DB connection, queries, and metrics.

All Streamlit pages import from here.  The connection is cached as a
resource (persists across reruns).  Query results are cached with a 5-min
TTL so live paper-trading data refreshes automatically.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

# ── Month name lookup ─────────────────────────────────────────────────────────

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Valid source values stored in futures_runs.source
SOURCES = ("backtest", "paper")

# ── Connection ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Connecting to database…")
def get_conn():
    """
    Return a cached psycopg2 connection.

    Credential resolution order:
      1. Streamlit secrets  (SUPABASE_DB_URL)          — used on Streamlit Cloud
      2. .env file in the project root                  — used locally
      3. SUPABASE_DB_URL environment variable           — fallback
    """
    url = ""
    try:
        url = st.secrets.get("SUPABASE_DB_URL", "")
    except Exception:
        pass

    if not url:
        try:
            from dotenv import load_dotenv
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(dotenv_path=env_path)
        except ImportError:
            pass
        url = os.environ.get("SUPABASE_DB_URL", "")

    if not url:
        st.error(
            "**Database not configured.** "
            "Add `SUPABASE_DB_URL` to Streamlit secrets or your `.env` file."
        )
        st.stop()

    import psycopg2
    from urllib.parse import urlparse

    p = urlparse(url)
    conn = psycopg2.connect(
        host=p.hostname,
        port=p.port or 5432,
        dbname=(p.path or "/postgres").lstrip("/"),
        user=p.username,
        password=p.password,
        sslmode="require",
        connect_timeout=15,
        options="-c statement_timeout=30000",
    )
    conn.autocommit = True
    _ensure_source_column(conn)   # safe one-time migration
    return conn


@st.cache_resource          # runs exactly once per app lifetime
def _ensure_source_column(_conn=None) -> None:
    """
    Add `source VARCHAR(20) DEFAULT 'backtest'` to futures_runs if it doesn't
    exist yet.  Uses IF NOT EXISTS / DO NOTHING so it is completely idempotent.
    All rows that pre-date this migration keep their default value ('backtest'),
    which is correct — everything in the DB so far IS backtest data.
    """
    conn = _conn or get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE futures_runs
            ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'backtest'
        """)
        cur.close()
    except Exception:
        pass  # table may not exist yet; backtester creates it on first run


def _query(sql: str, params=None) -> pd.DataFrame:
    """Execute a SQL query and return a DataFrame. Reconnects once on error."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        cur.close()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        # Try to reset the connection (handles stale connections)
        try:
            conn.reset()
        except Exception:
            pass
        raise e


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading trades…")
def load_trades(
    start_date: str,
    end_date: str,
    symbols: Optional[List[str]] = None,
    source: Optional[str] = None,        # 'backtest' | 'paper' | None (= all)
) -> pd.DataFrame:
    """
    Load completed futures trades for the given date range + optional filters.
    `source` maps to futures_runs.source ('backtest' or 'paper').
    Timestamps are converted to US/Eastern.
    Returns an empty DataFrame if no rows match.
    """
    where_clauses = [
        "ft.entry_time >= %s",
        "ft.entry_time <= %s",
        "ft.exit_time IS NOT NULL",
    ]
    params: list = [start_date + " 00:00:00+00", end_date + " 23:59:59+00"]

    if symbols:
        where_clauses.append("ft.symbol = ANY(%s)")
        params.append(symbols)

    if source in SOURCES:
        where_clauses.append("fr.source = %s")
        params.append(source)

    sql = f"""
        SELECT
            ft.symbol,
            ft.direction,
            (ft.entry_time AT TIME ZONE 'America/New_York')  AS entry_time,
            (ft.exit_time  AT TIME ZONE 'America/New_York')  AS exit_time,
            ft.entry_price::float,
            ft.exit_price::float,
            ft.contracts,
            ft.pnl_net::float,
            ft.r_multiple::float,
            ft.exit_reason,
            ft.risk_per_contract::float,
            fr.source
        FROM  futures_trades ft
        JOIN  futures_runs   fr ON fr.id = ft.run_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY ft.entry_time
    """
    try:
        df = _query(sql, params)
    except Exception as e:
        st.warning(f"Could not load trades: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    # ── Type coercions ─────────────────────────────────────────────────────
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"]  = pd.to_datetime(df["exit_time"])

    # Derived columns
    df["win"]        = df["pnl_net"] > 0
    df["entry_date"] = df["entry_time"].dt.date
    df["entry_hour"] = df["entry_time"].dt.hour
    df["hold_min"]   = (
        (df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60
    ).round(1)

    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_available_symbols() -> List[str]:
    """Return all symbols that have at least one completed trade."""
    try:
        df = _query(
            "SELECT DISTINCT symbol FROM futures_trades "
            "WHERE exit_time IS NOT NULL ORDER BY 1"
        )
        return df["symbol"].tolist() if not df.empty else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_date_bounds(source: Optional[str] = None) -> tuple[str, str]:
    """
    Return (earliest_entry, latest_entry) date strings for the given source.
    source=None → across all runs.
    """
    try:
        if source in SOURCES:
            df = _query(
                """
                SELECT MIN(ft.entry_time)::date, MAX(ft.entry_time)::date
                FROM futures_trades ft
                JOIN futures_runs   fr ON fr.id = ft.run_id
                WHERE ft.exit_time IS NOT NULL AND fr.source = %s
                """,
                [source],
            )
        else:
            df = _query(
                "SELECT MIN(entry_time)::date, MAX(entry_time)::date "
                "FROM futures_trades WHERE exit_time IS NOT NULL"
            )
        if df.empty or df.iloc[0, 0] is None:
            return ("2023-01-01", "2025-12-31")
        return (str(df.iloc[0, 0]), str(df.iloc[0, 1]))
    except Exception:
        return ("2023-01-01", "2025-12-31")


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> Dict:
    """
    Compute a full set of performance statistics from a trades DataFrame.
    Returns an empty dict if df is empty.
    """
    if df.empty:
        return {}

    n     = len(df)
    wins  = df[df["pnl_net"] > 0]["pnl_net"]
    loss  = df[df["pnl_net"] < 0]["pnl_net"]

    net_pnl       = df["pnl_net"].sum()
    win_rate      = len(wins) / n if n else 0
    profit_factor = (
        wins.sum() / abs(loss.sum())
        if len(loss) > 0 and loss.sum() != 0
        else float("inf")
    )
    avg_win  = wins.mean() if len(wins) > 0 else 0.0
    avg_loss = loss.mean() if len(loss) > 0 else 0.0
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    # Equity curve → max drawdown
    eq          = df.sort_values("entry_time")["pnl_net"].cumsum()
    rolling_max = eq.cummax()
    drawdown    = eq - rolling_max
    max_dd      = drawdown.min()

    # Daily Sharpe (annualised)
    daily_pnl = df.groupby("entry_date")["pnl_net"].sum()
    sharpe    = 0.0
    if len(daily_pnl) >= 5:
        mu, sigma = daily_pnl.mean(), daily_pnl.std()
        sharpe = (mu / sigma * np.sqrt(252)) if sigma != 0 else 0.0

    avg_r    = df["r_multiple"].mean() if "r_multiple" in df.columns else 0.0
    avg_hold = df["hold_min"].mean()   if "hold_min"   in df.columns else 0.0

    return {
        "n_trades":      n,
        "n_wins":        len(wins),
        "n_losses":      len(loss),
        "win_rate":      win_rate,
        "profit_factor": profit_factor,
        "net_pnl":       net_pnl,
        "avg_win":       avg_win,
        "avg_loss":      avg_loss,
        "rr_ratio":      rr_ratio,
        "max_drawdown":  max_dd,
        "sharpe":        sharpe,
        "avg_r":         avg_r,
        "avg_hold_min":  avg_hold,
    }


# ── Chart helpers ─────────────────────────────────────────────────────────────

def equity_curve_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with columns [entry_time, equity, drawdown]."""
    if df.empty:
        return pd.DataFrame(columns=["entry_time", "equity", "drawdown"])
    s = df.sort_values("entry_time").copy()
    s["equity"]   = s["pnl_net"].cumsum()
    s["drawdown"] = s["equity"] - s["equity"].cummax()
    return s[["entry_time", "equity", "drawdown", "pnl_net"]]


def monthly_pnl_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a year × month-name pivot of net PnL.
    Positive values → green, negative → red in the heatmap.
    """
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["year"]  = d["entry_time"].dt.year
    d["month"] = d["entry_time"].dt.month
    pivot = d.groupby(["year", "month"])["pnl_net"].sum().unstack(fill_value=np.nan)
    pivot.columns = [MONTH_NAMES.get(c, str(c)) for c in pivot.columns]
    return pivot

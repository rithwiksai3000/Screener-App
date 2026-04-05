# pages/2_Watchlist.py
# Personal watchlist — track favourite stocks with live KPI data.

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

@st.cache_resource
def get_engine():
    try:
        host = st.secrets.get("DB_HOST", "localhost")
        user = st.secrets.get("DB_USER", "root")
        pw   = st.secrets.get("DB_PASS", "Bank1234")
        port = str(st.secrets.get("DB_PORT", "3306"))
        db   = st.secrets.get("DB_NAME", "bank_data")
    except Exception:
        import os as _os
        host = _os.getenv("DB_HOST", "localhost")
        user = _os.getenv("DB_USER", "root")
        pw   = _os.getenv("DB_PASS", "Bank1234")
        port = _os.getenv("DB_PORT", "3306")
        db   = _os.getenv("DB_NAME", "bank_data")
    return create_engine(f"mysql+mysqlconnector://{user}:{pw}@{host}:{port}/{db}")
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, section_header, trend_badge, score_badge

st.set_page_config(page_title="Watchlist · Screener", layout="wide", page_icon="⭐")
apply_theme()
sidebar_brand()

engine = get_engine()
USER_ID = "default"

def get_watchlist():
    try:
        return pd.read_sql(
            "SELECT ticker, added_date, notes FROM watchlist WHERE user_id = %s ORDER BY added_date DESC",
            engine, params=(USER_ID,)
        )
    except Exception:
        return pd.DataFrame(columns=["ticker", "added_date", "notes"])

def get_kpis_for_tickers(tickers: list) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    placeholders = ", ".join([f"'{t}'" for t in tickers])
    query = f"""
        SELECT ticker, total_score, fundamental_score, technical_score,
               current_price, rsi_val, long_term_trend, medium_term_trend,
               margin_val, rev_growth_val, price_strength_val, category, scan_date
        FROM daily_kpi_snapshot
        WHERE ticker IN ({placeholders})
          AND scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
    """
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">My Watchlist</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Track your favourite stocks with live KPI data
  </p>
</div>
""", unsafe_allow_html=True)

# ── Add Ticker form ────────────────────────────────────────────────────────────
with st.form("add_ticker_form"):
    c1, c2, c3 = st.columns([2, 3, 1])
    new_ticker = c1.text_input("Ticker", placeholder="e.g. AAPL").upper().strip()
    new_note   = c2.text_input("Note (optional)", placeholder="e.g. Watching for breakout")
    submitted  = c3.form_submit_button("Add Stock", use_container_width=True)

    if submitted and new_ticker:
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("INSERT IGNORE INTO watchlist (user_id, ticker, added_date, notes) VALUES (:u, :t, :d, :n)"),
                    {"u": USER_ID, "t": new_ticker, "d": str(date.today()), "n": new_note or None}
                )
                conn.commit()
            st.success(f"{new_ticker} added to your watchlist.")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ── Load data ──────────────────────────────────────────────────────────────────
wl = get_watchlist()

if wl.empty:
    st.info("Your watchlist is empty. Add tickers using the form above, or from the Scanner page.")
    st.stop()

tickers = wl["ticker"].tolist()
df_kpis = get_kpis_for_tickers(tickers)

if not df_kpis.empty:
    df_merged = pd.merge(wl, df_kpis, on="ticker", how="left")
else:
    df_merged = wl.copy()

# ── Summary metrics ────────────────────────────────────────────────────────────
st.divider()
if not df_kpis.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Watchlisted", len(wl))
    c2.metric("Avg Score", f"{df_kpis['total_score'].mean():.1f} / 10")
    c3.metric("Bullish", int(df_kpis["long_term_trend"].eq("Bullish").sum()))
    c4.metric("Golden Cross", int(df_kpis["medium_term_trend"].eq("Yes").sum()))
    st.divider()

# ── Stock cards ────────────────────────────────────────────────────────────────
st.markdown(section_header("Your Stocks", "📋"), unsafe_allow_html=True)

for _, row in df_merged.iterrows():
    ticker = row["ticker"]
    score  = row.get("total_score")
    price  = row.get("current_price")
    rsi    = row.get("rsi_val")
    trend  = row.get("long_term_trend", "N/A")
    gc     = row.get("medium_term_trend", "N/A")
    note   = row.get("notes", "")
    added  = row.get("added_date", "")

    # Accent left-border based on score
    if score is not None:
        accent = "#00ffc8" if score >= 7 else "#fbbf24" if score >= 5 else "#ef4444"
    else:
        accent = "#1a2840"

    score_html  = score_badge(score) if score is not None else '<span class="badge badge-neutral">No data</span>'
    trend_html  = trend_badge(str(trend))
    gc_html     = '<span class="badge badge-accent">Yes</span>' if gc == "Yes" else '<span class="badge badge-neutral">No</span>'

    st.markdown(f"""
<div class="sc-card" style="border-left:4px solid {accent}; margin-bottom:.75rem">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem">
    <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap">
      <span class="ticker-chip">{ticker}</span>
      {score_html}
      {trend_html}
      {gc_html}
      {"" if not note else f'<span style="color:var(--txt2);font-size:.8rem;font-style:italic">{note}</span>'}
    </div>
    <div style="text-align:right">
      <div style="font-size:1.4rem;font-weight:700;color:var(--txt0)">${f"{price:.2f}" if price else "N/A"}</div>
      <div style="font-size:.75rem;color:var(--txt2)">Current price</div>
    </div>
  </div>
  <div style="display:flex;gap:1.5rem;margin-top:.75rem;flex-wrap:wrap">
    <span style="font-size:.82rem;color:var(--txt2)">RSI: <strong style="color:var(--txt0)">{f"{rsi:.1f}" if rsi else "N/A"}</strong></span>
    <span style="font-size:.82rem;color:var(--txt2)">Added: <strong style="color:var(--txt0)">{added}</strong></span>
  </div>
</div>
""", unsafe_allow_html=True)

    if st.button(f"Remove {ticker}", key=f"rm_{ticker}"):
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM watchlist WHERE user_id = :u AND ticker = :t"),
                {"u": USER_ID, "t": ticker}
            )
            conn.commit()
        st.success(f"Removed {ticker}.")
        st.rerun()

st.divider()

with st.expander("Full Data Table"):
    show_cols = [c for c in [
        "ticker", "total_score", "current_price", "rsi_val",
        "long_term_trend", "medium_term_trend", "margin_val",
        "rev_growth_val", "price_strength_val", "added_date", "notes"
    ] if c in df_merged.columns]
    st.dataframe(df_merged[show_cols], use_container_width=True)
    csv = df_merged[show_cols].to_csv(index=False)
    st.download_button("Download CSV", csv, "watchlist.csv", "text/csv")

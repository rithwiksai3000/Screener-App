# pages/5_Trending.py
# Trending stocks — top scorers, biggest movers, sector heat map.

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine

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
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, sidebar_status, section_header, apply_plotly_theme

st.set_page_config(page_title="Trending · Screener", layout="wide", page_icon="🔥")
apply_theme()
sidebar_brand()

engine = get_engine()

@st.cache_data(ttl=300)
def load_latest():
    try:
        return pd.read_sql("""
            SELECT * FROM daily_kpi_snapshot
            WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
              AND scan_status = 'success'
        """, engine)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_previous():
    try:
        dates = pd.read_sql(
            "SELECT DISTINCT scan_date FROM daily_kpi_snapshot WHERE scan_status='success' ORDER BY scan_date DESC LIMIT 2",
            engine
        )
        if len(dates) < 2:
            return pd.DataFrame()
        prev_date = dates.iloc[1]["scan_date"]
        return pd.read_sql(
            f"SELECT ticker, total_score FROM daily_kpi_snapshot WHERE scan_date = '{prev_date}' AND scan_status='success'",
            engine
        )
    except Exception:
        return pd.DataFrame()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Trending Stocks</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Top scorers, score movers, and market-wide insights from the latest scan
  </p>
</div>
""", unsafe_allow_html=True)

df = load_latest()
df_prev = load_previous()

if df.empty:
    st.error("No scan data found. Run `python scheduler.py now` first.")
    st.stop()

sidebar_status(str(df["scan_date"].max()), len(df))

# ── Market summary metrics ─────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Stocks Scanned",  f"{len(df):,}")
c2.metric("Avg Score",        f"{df['total_score'].mean():.2f} / 10")
c3.metric("Strong Buy (≥7)",  int((df["total_score"] >= 7).sum()))
c4.metric("Bullish Trend",    int(df["long_term_trend"].eq("Bullish").sum()) if "long_term_trend" in df.columns else 0)
c5.metric("Golden Cross",     int(df["medium_term_trend"].eq("Yes").sum()) if "medium_term_trend" in df.columns else 0)

st.divider()

# ── Top 10 scorers ─────────────────────────────────────────────────────────────
st.markdown(section_header("Top 10 — Highest KPI Score", "🏆"), unsafe_allow_html=True)
top10 = df.nlargest(10, "total_score")[["ticker","total_score","fundamental_score","technical_score",
                                        "current_price","rsi_val","long_term_trend","category"]].reset_index(drop=True)

fig_top = go.Figure(go.Bar(
    x=top10["ticker"], y=top10["total_score"],
    marker_color=["#00ffc8" if s >= 7 else "#fbbf24" if s >= 5 else "#ef4444" for s in top10["total_score"]],
    marker_line_width=0, opacity=0.9,
    text=top10["total_score"].round(1), textposition="outside",
    hovertemplate="<b>%{x}</b><br>Score: %{y}<extra></extra>",
))
apply_plotly_theme(fig_top, height=320)
fig_top.update_layout(yaxis_range=[0, 11], yaxis_title="KPI Score")
st.plotly_chart(fig_top, use_container_width=True)

# ── Score movers ───────────────────────────────────────────────────────────────
if not df_prev.empty:
    st.divider()
    st.markdown(section_header("Biggest Score Movers vs Previous Scan", "📊"), unsafe_allow_html=True)
    merged = pd.merge(
        df[["ticker","total_score","current_price","category"]],
        df_prev.rename(columns={"total_score":"prev_score"}), on="ticker"
    )
    merged["score_change"] = merged["total_score"] - merged["prev_score"]

    col_up, col_dn = st.columns(2)

    with col_up:
        st.markdown("<div style='color:var(--txt2);font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem'>Biggest Upgrades</div>", unsafe_allow_html=True)
        for _, r in merged.nlargest(5, "score_change").iterrows():
            st.markdown(f"""
<div class="sc-card" style="border-left:4px solid #22c55e;margin-bottom:.4rem;padding:.7rem 1rem">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span class="ticker-chip">{r['ticker']}</span>
    <span style="color:#22c55e;font-weight:700;font-size:.95rem">+{r['score_change']:.1f}</span>
  </div>
  <div style="color:var(--txt2);font-size:.8rem;margin-top:.3rem">{r['prev_score']:.1f} → <strong style="color:var(--txt0)">{r['total_score']:.1f}</strong></div>
</div>""", unsafe_allow_html=True)

    with col_dn:
        st.markdown("<div style='color:var(--txt2);font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem'>Biggest Downgrades</div>", unsafe_allow_html=True)
        for _, r in merged.nsmallest(5, "score_change").iterrows():
            st.markdown(f"""
<div class="sc-card" style="border-left:4px solid #ef4444;margin-bottom:.4rem;padding:.7rem 1rem">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span class="ticker-chip">{r['ticker']}</span>
    <span style="color:#ef4444;font-weight:700;font-size:.95rem">{r['score_change']:.1f}</span>
  </div>
  <div style="color:var(--txt2);font-size:.8rem;margin-top:.3rem">{r['prev_score']:.1f} → <strong style="color:var(--txt0)">{r['total_score']:.1f}</strong></div>
</div>""", unsafe_allow_html=True)

st.divider()

# ── Score distribution ─────────────────────────────────────────────────────────
st.markdown(section_header("Score Distribution — Full Universe", "📈"), unsafe_allow_html=True)
col_hist, col_pie = st.columns(2)

with col_hist:
    fig_hist = go.Figure(go.Histogram(
        x=df["total_score"], nbinsx=20,
        marker_color="#00ffc8", opacity=0.85, marker_line_width=0,
    ))
    apply_plotly_theme(fig_hist, height=300)
    fig_hist.update_layout(xaxis_title="KPI Score", yaxis_title="Stocks", bargap=0.05)
    st.plotly_chart(fig_hist, use_container_width=True)

with col_pie:
    buckets = pd.cut(df["total_score"], bins=[0,3,5,7,10],
                     labels=["Low (0–3)","Medium (3–5)","Good (5–7)","Strong (7–10)"]).value_counts()
    fig_pie = go.Figure(go.Pie(
        labels=buckets.index, values=buckets.values, hole=0.5,
        marker_colors=["#ef4444","#f97316","#fbbf24","#00ffc8"],
    ))
    fig_pie.update_traces(textfont=dict(color="#e8edf5", size=11))
    apply_plotly_theme(fig_pie, height=300)
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ── RSI overview ───────────────────────────────────────────────────────────────
st.markdown(section_header("RSI Overview — Market Pulse", "⚡"), unsafe_allow_html=True)
if "rsi_val" in df.columns:
    df_rsi = df[["ticker","rsi_val","total_score"]].dropna()
    oversold   = df_rsi[df_rsi["rsi_val"] < 30]
    neutral    = df_rsi[(df_rsi["rsi_val"] >= 30) & (df_rsi["rsi_val"] <= 70)]
    overbought = df_rsi[df_rsi["rsi_val"] > 70]

    r1, r2, r3 = st.columns(3)
    r1.metric("Oversold (RSI < 30)",   len(oversold),   help="Potential bounce candidates")
    r2.metric("Neutral (30–70)",        len(neutral))
    r3.metric("Overbought (RSI > 70)", len(overbought), help="Watch for pullbacks")

    if not oversold.empty:
        st.markdown("<div style='color:var(--txt2);font-size:.8rem;font-weight:600;margin:.75rem 0 .4rem;text-transform:uppercase;letter-spacing:.05em'>Oversold Stocks (RSI < 30)</div>", unsafe_allow_html=True)
        st.dataframe(
            oversold.sort_values("total_score", ascending=False).reset_index(drop=True),
            use_container_width=True, height=200,
        )

st.divider()

with st.expander("Full Universe Table"):
    show_cols = [c for c in [
        "ticker","category","total_score","fundamental_score","technical_score",
        "current_price","rsi_val","long_term_trend","medium_term_trend",
        "margin_val","rev_growth_val","price_strength_val"
    ] if c in df.columns]
    st.dataframe(df[show_cols].sort_values("total_score", ascending=False).reset_index(drop=True),
                 use_container_width=True)
    st.download_button("Download CSV", df[show_cols].to_csv(index=False), "universe.csv", "text/csv")

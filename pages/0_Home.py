# pages/0_Home.py
# Home Dashboard — market overview, leaderboard, sector breakdown.

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

st.set_page_config(page_title="Market Dashboard · Screener", layout="wide", page_icon="📈")
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
def load_prev():
    try:
        dates = pd.read_sql(
            "SELECT DISTINCT scan_date FROM daily_kpi_snapshot WHERE scan_status='success' ORDER BY scan_date DESC LIMIT 2",
            engine
        )
        if len(dates) < 2:
            return pd.DataFrame()
        prev = dates.iloc[1]["scan_date"]
        return pd.read_sql(
            f"SELECT ticker, total_score FROM daily_kpi_snapshot WHERE scan_date='{prev}' AND scan_status='success'",
            engine
        )
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_scan_log():
    try:
        return pd.read_sql("SELECT * FROM scan_log ORDER BY run_date DESC LIMIT 5", engine)
    except Exception:
        return pd.DataFrame()

# ── Load data ──────────────────────────────────────────────────────────────────
df = load_latest()
df_prev = load_prev()

if df.empty:
    st.error("No scan data found. Run `python scheduler.py now` to populate the database.")
    st.stop()

last_scan = str(df["scan_date"].max())
sidebar_status(last_scan, len(df))

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Market Dashboard</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Real-time KPI overview across the S&amp;P 500 universe
  </p>
</div>
""", unsafe_allow_html=True)

# ── Summary metrics ────────────────────────────────────────────────────────────
top = df.loc[df["total_score"].idxmax()]
avg = df["total_score"].mean()
bullish_count = len(df[df["long_term_trend"] == "Bullish"])
high_score_count = len(df[df["total_score"] >= 9])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stocks Tracked", f"{len(df):,}")
c2.metric("Avg KPI Score", f"{avg:.1f} / 10")
c3.metric("Bullish Trend", f"{bullish_count}", f"{bullish_count/len(df)*100:.0f}% of universe")
c4.metric("High Scorers ≥ 9", f"{high_score_count}")

st.divider()

# ── Top 15 + Sector side by side ───────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown(section_header("Top 15 Stocks Today", "🏆"), unsafe_allow_html=True)
    top15 = df.nlargest(15, "total_score")[
        ["ticker", "sector", "total_score", "fundamental_score", "technical_score",
         "current_price", "rsi_val", "long_term_trend"]
    ].reset_index(drop=True)
    top15.index += 1

    def color_score(val):
        if val >= 9:   return "background-color: rgba(0,255,200,0.18); color:#00ffc8; font-weight:600"
        elif val >= 6: return "background-color: rgba(251,191,36,0.15); color:#fbbf24; font-weight:600"
        return "background-color: rgba(239,68,68,0.1); color:#ef4444"

    def color_trend(val):
        if val == "Bullish": return "color: #22c55e; font-weight:600"
        if val == "Bearish": return "color: #ef4444; font-weight:600"
        return "color: #9ca3af"

    st.dataframe(
        top15.style
            .map(color_score, subset=["total_score"])
            .map(color_trend, subset=["long_term_trend"]),
        use_container_width=True,
        height=520,
    )

with right:
    st.markdown(section_header("Sector Breakdown", "🗂"), unsafe_allow_html=True)
    sector_counts = df["sector"].value_counts().reset_index()
    sector_counts.columns = ["sector", "count"]
    fig_pie = px.pie(
        sector_counts, names="sector", values="count",
        color_discrete_sequence=["#00ffc8","#3b82f6","#fbbf24","#f97316","#a78bfa",
                                  "#ec4899","#22c55e","#06b6d4","#84cc16","#f43f5e","#64748b"],
        hole=0.48,
    )
    fig_pie.update_traces(textposition="inside", textinfo="label+percent",
                          textfont=dict(size=11, color="#e8edf5"))
    apply_plotly_theme(fig_pie, height=250)
    fig_pie.update_layout(showlegend=False, margin=dict(t=5,b=5,l=5,r=5))
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown(section_header("Avg Score by Sector"), unsafe_allow_html=True)
    sector_scores = df.groupby("sector")["total_score"].mean().sort_values(ascending=True).reset_index()
    fig_bar = px.bar(
        sector_scores, x="total_score", y="sector", orientation="h",
        color="total_score",
        color_continuous_scale=[[0,"#ef4444"],[0.5,"#fbbf24"],[1,"#00ffc8"]],
        labels={"total_score": "Avg Score", "sector": ""},
        range_x=[0, 10],
    )
    apply_plotly_theme(fig_bar, height=290)
    fig_bar.update_layout(coloraxis_showscale=False, margin=dict(t=5,b=5,l=5,r=5))
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Score distribution ─────────────────────────────────────────────────────────
st.markdown(section_header("Score Distribution — Full Universe", "📊"), unsafe_allow_html=True)
fig_hist = px.histogram(
    df, x="total_score", nbins=20,
    color_discrete_sequence=["#00ffc8"],
    labels={"total_score": "Total KPI Score", "count": "Stocks"},
)
fig_hist.update_traces(marker_line_width=0, opacity=0.85)
apply_plotly_theme(fig_hist, height=230)
fig_hist.update_layout(bargap=0.06, margin=dict(t=5,b=5))
st.plotly_chart(fig_hist, use_container_width=True)

st.divider()

# ── Most Improved ──────────────────────────────────────────────────────────────
if not df_prev.empty:
    st.markdown(section_header("Most Improved Since Last Scan", "📈"), unsafe_allow_html=True)
    merged = df[["ticker", "total_score", "sector"]].merge(
        df_prev.rename(columns={"total_score": "prev_score"}), on="ticker"
    )
    merged["change"] = merged["total_score"] - merged["prev_score"]
    top_improved = merged.nlargest(10, "change")[["ticker","sector","prev_score","total_score","change"]]
    top_improved.columns = ["Ticker","Sector","Prev Score","Score Today","Change"]

    def color_change(val):
        if val > 0: return "color:#22c55e; font-weight:600"
        if val < 0: return "color:#ef4444; font-weight:600"
        return "color:#9ca3af"

    st.dataframe(
        top_improved.style.map(color_change, subset=["Change"]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Run the scanner for a second day to see score changes over time.")

# ── Scan Log ───────────────────────────────────────────────────────────────────
df_log = load_scan_log()
if not df_log.empty:
    with st.expander("Recent Scan History"):
        st.dataframe(
            df_log[["run_date","total_scanned","total_succeeded","total_failed","duration_seconds"]],
            use_container_width=True, hide_index=True,
        )

# pages/6_Compare.py
# Side-by-side stock comparison — radar chart + metrics table.

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
from src.theme import apply_theme, sidebar_brand, section_header, trend_badge, score_badge, apply_plotly_theme

st.set_page_config(page_title="Compare · Screener", layout="wide", page_icon="⚖️")
apply_theme()
sidebar_brand()

engine = get_engine()

COLORS = ["#00ffc8", "#f97316", "#fbbf24", "#a78bfa"]

KPI_SCORE_COLS = [
    ("efficiency_score",        "Efficiency"),
    ("margin_score",            "Margin"),
    ("rev_growth_score",        "Rev Growth"),
    ("solvency_score",          "Solvency"),
    ("valuation_score",         "Valuation"),
    ("growth_adj_score",        "Growth Adj"),
    ("long_term_trend_score",   "LT Trend"),
    ("medium_term_trend_score", "MT Trend"),
    ("rsi_score",               "RSI"),
    ("price_strength_score",    "Price Strength"),
]

DISPLAY_ROWS = {
    "Sector":            "sector",
    "Category":          "category",
    "Current Price":     "current_price",
    "Total Score":       "total_score",
    "Fundamental Score": "fundamental_score",
    "Technical Score":   "technical_score",
    "Efficiency":        "efficiency_val",
    "Margin (%)":        "margin_val",
    "Rev Growth (%)":    "rev_growth_val",
    "Solvency":          "solvency_val",
    "Valuation":         "valuation_val",
    "Growth Adj":        "growth_adj_val",
    "RSI":               "rsi_val",
    "LT Trend":          "long_term_trend",
    "Golden Cross":      "medium_term_trend",
    "% from 52W High":   "price_strength_val",
}

@st.cache_data(ttl=300)
def load_snapshot():
    try:
        return pd.read_sql("""
            SELECT * FROM daily_kpi_snapshot
            WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
              AND scan_status = 'success'
        """, engine)
    except Exception:
        return pd.DataFrame()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Stock Comparison</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Compare up to 4 stocks side-by-side across all 10 KPIs
  </p>
</div>
""", unsafe_allow_html=True)

df_all = load_snapshot()
if df_all.empty:
    st.error("No scan data found. Run the batch scanner first.")
    st.stop()

all_tickers = sorted(df_all["ticker"].tolist())
selected = st.multiselect(
    "Select up to 4 stocks",
    options=all_tickers,
    default=all_tickers[:2] if len(all_tickers) >= 2 else all_tickers,
    max_selections=4,
)

if len(selected) < 2:
    st.info("Select at least 2 stocks to compare.")
    st.stop()

df = df_all[df_all["ticker"].isin(selected)].set_index("ticker")
st.divider()

# ── Summary cards ──────────────────────────────────────────────────────────────
st.markdown(section_header("Summary", "📋"), unsafe_allow_html=True)
cols = st.columns(len(selected))
for i, ticker in enumerate(selected):
    row = df.loc[ticker]
    with cols[i]:
        trend_html = trend_badge(str(row.get("long_term_trend", "N/A")))
        gc_html    = '<span class="badge badge-accent">Yes</span>' if row.get("medium_term_trend") == "Yes" else '<span class="badge badge-neutral">No</span>'
        st.markdown(f"""
<div class="sc-card" style="border-top:3px solid {COLORS[i]};padding:1rem">
  <div style="font-weight:700;font-size:1.1rem;color:{COLORS[i]};margin-bottom:.6rem">{ticker}</div>
  <div class="kv-row"><span class="kv-key">Total Score</span><span class="kv-value">{row['total_score']:.1f} / 10</span></div>
  <div class="kv-row"><span class="kv-key">Fund. Score</span><span class="kv-value">{row['fundamental_score']:.1f}</span></div>
  <div class="kv-row"><span class="kv-key">Tech. Score</span><span class="kv-value">{row['technical_score']:.1f}</span></div>
  <div class="kv-row"><span class="kv-key">Price</span><span class="kv-value">${row['current_price']:.2f}</span></div>
  <div class="kv-row"><span class="kv-key">RSI</span><span class="kv-value">{row['rsi_val']:.1f}</span></div>
  <div class="kv-row" style="border:none"><span class="kv-key">Trend</span><span>{trend_html}&nbsp;{gc_html}</span></div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Radar chart ────────────────────────────────────────────────────────────────
st.markdown(section_header("KPI Radar", "🕸"), unsafe_allow_html=True)
score_cols = [c for c, _ in KPI_SCORE_COLS if c in df.columns]
labels     = [label for c, label in KPI_SCORE_COLS if c in df.columns]

fig_radar = go.Figure()
for i, ticker in enumerate(selected):
    values = [df.loc[ticker, c] for c in score_cols]
    values_closed = values + [values[0]]
    labels_closed = labels + [labels[0]]
    hex_c = COLORS[i]
    # Build a semi-transparent fill from hex
    r, g, b = int(hex_c[1:3],16), int(hex_c[3:5],16), int(hex_c[5:7],16)
    fill_c = f"rgba({r},{g},{b},0.12)"
    fig_radar.add_trace(go.Scatterpolar(
        r=values_closed, theta=labels_closed, fill="toself",
        name=ticker, line_color=hex_c, fillcolor=fill_c, opacity=0.9,
    ))

fig_radar.update_layout(
    polar=dict(
        bgcolor="rgba(13,20,33,0.6)",
        radialaxis=dict(visible=True, range=[0,1], gridcolor="#1a2840", color="#5a6f8a", tickfont=dict(size=9)),
        angularaxis=dict(gridcolor="#1a2840", color="#9aaec8"),
    ),
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#c8d4e8"),
    legend=dict(bgcolor="#0d1421", bordercolor="#1a2840"),
    height=480, margin=dict(t=20, b=20),
)
st.plotly_chart(fig_radar, use_container_width=True)

st.divider()

# ── Stacked score bar ──────────────────────────────────────────────────────────
st.markdown(section_header("Score Breakdown", "📊"), unsafe_allow_html=True)
score_data = pd.DataFrame({
    "Ticker":      selected,
    "Fundamental": [df.loc[t, "fundamental_score"] for t in selected],
    "Technical":   [df.loc[t, "technical_score"]   for t in selected],
})
fig_bar = px.bar(
    score_data.melt(id_vars="Ticker", var_name="Type", value_name="Score"),
    x="Ticker", y="Score", color="Type", barmode="stack",
    color_discrete_map={"Fundamental": "#00ffc8", "Technical": "#a78bfa"},
    text_auto=True,
)
apply_plotly_theme(fig_bar, height=280)
fig_bar.update_layout(yaxis_range=[0, 10], legend=dict(bgcolor="#0d1421"))
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Full KPI table ─────────────────────────────────────────────────────────────
st.markdown(section_header("Full KPI Breakdown"), unsafe_allow_html=True)
table_data = {}
for label, col in DISPLAY_ROWS.items():
    if col in df.columns:
        table_data[label] = [
            round(df.loc[t, col], 2) if isinstance(df.loc[t, col], float) else df.loc[t, col]
            for t in selected
        ]

df_table = pd.DataFrame(table_data, index=selected).T
st.dataframe(df_table, use_container_width=True)
st.download_button("Download CSV", df_table.to_csv(), "comparison.csv", "text/csv")

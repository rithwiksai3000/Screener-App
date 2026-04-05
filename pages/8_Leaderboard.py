# pages/8_Leaderboard.py
# Screener Leaderboard — all stocks ranked by KPI score with visual score bars.

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
from src.theme import apply_theme, sidebar_brand, section_header, apply_plotly_theme

st.set_page_config(page_title="Leaderboard · Screener", layout="wide", page_icon="🥇")
apply_theme()
sidebar_brand()

engine = get_engine()

@st.cache_data(ttl=300)
def load_data():
    try:
        return pd.read_sql("""
            SELECT ticker, sector, category,
                   total_score, fundamental_score, technical_score,
                   current_price, rsi_val, long_term_trend, medium_term_trend,
                   price_strength_val, rev_growth_val, margin_val, scan_date
            FROM daily_kpi_snapshot
            WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
              AND scan_status = 'success'
            ORDER BY total_score DESC
        """, engine)
    except Exception:
        return pd.DataFrame()

df_all = load_data()

if df_all.empty:
    st.error("No scan data found. Run `python scheduler.py now` first.")
    st.stop()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Leaderboard</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    {len(df_all):,} stocks ranked by KPI score · Last scan: {df_all['scan_date'].max()}
  </p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Stocks",    f"{len(df_all):,}")
c2.metric("Avg Score",       f"{df_all['total_score'].mean():.1f} / 10")
c3.metric("Strong (≥ 9)",    len(df_all[df_all["total_score"] >= 9]))
c4.metric("Neutral (5–8.9)", len(df_all[(df_all["total_score"] >= 5) & (df_all["total_score"] < 9)]))
c5.metric("Weak (< 5)",      len(df_all[df_all["total_score"] < 5]))

st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    fc1, fc2, fc3, fc4 = st.columns(4)
    f_sector    = fc1.selectbox("Sector",    ["All"] + sorted(df_all["sector"].dropna().unique().tolist()))
    f_category  = fc2.selectbox("Category",  ["All", "Bank", "Non-Bank"])
    f_trend     = fc3.selectbox("LT Trend",  ["All", "Bullish", "Bearish"])
    f_min_score = fc4.slider("Min Score", 0.0, 10.0, 0.0, 0.5)

df = df_all.copy()
if f_sector    != "All": df = df[df["sector"]         == f_sector]
if f_category  != "All": df = df[df["category"]       == f_category]
if f_trend     != "All": df = df[df["long_term_trend"] == f_trend]
if f_min_score  > 0:     df = df[df["total_score"]    >= f_min_score]

df = df.reset_index(drop=True)
df.index += 1

st.markdown(f'<p style="color:var(--txt2);font-size:.82rem;margin:.25rem 0 1rem">Showing <strong style="color:var(--txt0)">{len(df)}</strong> stocks</p>', unsafe_allow_html=True)

# ── Top 30 chart ───────────────────────────────────────────────────────────────
st.markdown(section_header("Top 30 by Total Score", "🏆"), unsafe_allow_html=True)
top30 = df.head(30)
fig = go.Figure()
fig.add_trace(go.Bar(
    y=top30["ticker"], x=top30["fundamental_score"],
    name="Fundamental", orientation="h",
    marker_color="#00ffc8", marker_line_width=0, opacity=0.9,
    text=top30["fundamental_score"].round(1), textposition="inside",
))
fig.add_trace(go.Bar(
    y=top30["ticker"], x=top30["technical_score"],
    name="Technical", orientation="h",
    marker_color="#a78bfa", marker_line_width=0, opacity=0.9,
    text=top30["technical_score"].round(1), textposition="inside",
))
apply_plotly_theme(fig, height=max(380, len(top30) * 22))
fig.update_layout(
    barmode="stack",
    xaxis=dict(range=[0, 10], title="Score / 10"),
    yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
    legend=dict(orientation="h", y=1.04, bgcolor="#0d1421"),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Full ranked table (custom HTML) ───────────────────────────────────────────
st.markdown(section_header("Full Rankings"), unsafe_allow_html=True)

def score_bar_html(val, max_val=10):
    pct = min(val / max_val * 100, 100)
    color = "#00ffc8" if val >= 7 else "#fbbf24" if val >= 5 else "#ef4444"
    return (
        f'<div style="display:flex;align-items:center;gap:.4rem">'
        f'<div style="background:#192335;border-radius:3px;height:7px;width:70px;flex-shrink:0">'
        f'<div style="background:{color};border-radius:3px;height:7px;width:{pct:.0f}%"></div></div>'
        f'<span style="font-size:.8rem;color:{color};font-weight:600">{val:.1f}</span>'
        f'</div>'
    )

def trend_cell(val):
    if val == "Bullish": return '<span style="color:#22c55e;font-weight:600">Bullish</span>'
    if val == "Bearish": return '<span style="color:#ef4444;font-weight:600">Bearish</span>'
    return f'<span style="color:#9aaec8">{val}</span>'

rows_html = ""
for rank, (_, row) in enumerate(df.iterrows(), 1):
    score  = row["total_score"]
    row_bg = "rgba(0,255,200,.03)" if score >= 9 else ("rgba(239,68,68,.03)" if score < 5 else "transparent")
    rsi    = row["rsi_val"]
    rsi_color = "#ef4444" if rsi > 70 else "#00ffc8" if rsi < 35 else "#9aaec8"
    dip    = row["price_strength_val"]
    dip_str = f'{dip:.1f}%' if pd.notna(dip) else "—"

    rows_html += f"""
<tr style="background:{row_bg};border-bottom:1px solid #1a2840">
  <td style="padding:6px 10px;color:#5a6f8a;font-size:.8rem;width:36px">{rank}</td>
  <td style="padding:6px 10px;font-weight:700;color:#e8edf5">{row['ticker']}</td>
  <td style="padding:6px 10px;color:#7d8fa9;font-size:.8rem">{row.get('sector','')}</td>
  <td style="padding:6px 10px;min-width:120px">{score_bar_html(score)}</td>
  <td style="padding:6px 10px;min-width:100px">{score_bar_html(row['fundamental_score'], 6)}</td>
  <td style="padding:6px 10px;min-width:100px">{score_bar_html(row['technical_score'], 4)}</td>
  <td style="padding:6px 10px">{trend_cell(row.get('long_term_trend',''))}</td>
  <td style="padding:6px 10px;color:{rsi_color};font-weight:600">{rsi:.1f}</td>
  <td style="padding:6px 10px;color:#e8edf5">${row['current_price']:.2f}</td>
  <td style="padding:6px 10px;color:#7d8fa9;font-size:.8rem">{dip_str}</td>
</tr>"""

table_html = f"""
<div style="overflow-x:auto;overflow-y:auto;max-height:680px;border:1px solid #1a2840;border-radius:10px">
<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:.88rem;color:#e8edf5">
  <thead style="position:sticky;top:0;background:#131c2e;z-index:1">
    <tr style="color:#5a6f8a;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid #1a2840">
      <th style="padding:10px;text-align:left">#</th>
      <th style="padding:10px;text-align:left">Ticker</th>
      <th style="padding:10px;text-align:left">Sector</th>
      <th style="padding:10px;text-align:left">Total Score</th>
      <th style="padding:10px;text-align:left">Fundamental</th>
      <th style="padding:10px;text-align:left">Technical</th>
      <th style="padding:10px;text-align:left">Trend</th>
      <th style="padding:10px;text-align:left">RSI</th>
      <th style="padding:10px;text-align:left">Price</th>
      <th style="padding:10px;text-align:left">vs 52W High</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
</div>"""
st.markdown(table_html, unsafe_allow_html=True)

st.divider()

# ── Best per sector ────────────────────────────────────────────────────────────
st.markdown(section_header("Best Stock per Sector", "🌐"), unsafe_allow_html=True)
best_per_sector = (
    df_all.sort_values("total_score", ascending=False)
          .groupby("sector").first().reset_index()
          [["sector","ticker","total_score","fundamental_score","technical_score","long_term_trend"]]
          .sort_values("total_score", ascending=False)
)
fig_sector = px.bar(
    best_per_sector, x="ticker", y="total_score",
    color="total_score",
    color_continuous_scale=[[0,"#ef4444"],[0.5,"#fbbf24"],[1,"#00ffc8"]],
    text="sector",
    hover_data=["fundamental_score","technical_score","long_term_trend"],
    labels={"total_score": "Score", "ticker": "Top Ticker"},
)
fig_sector.update_traces(textposition="outside", marker_line_width=0)
apply_plotly_theme(fig_sector, height=340)
fig_sector.update_layout(coloraxis_showscale=False, yaxis_range=[0, 11])
st.plotly_chart(fig_sector, use_container_width=True)

st.download_button("Download Rankings CSV",
                   df.reset_index().rename(columns={"index":"rank"}).to_csv(index=False),
                   "leaderboard.csv", "text/csv")

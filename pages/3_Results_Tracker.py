# pages/3_Results_Tracker.py
# Tracks how stocks have performed AFTER being flagged by a scan.

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, section_header, apply_plotly_theme

st.set_page_config(page_title="Results Tracker · Screener", layout="wide", page_icon="📈")
apply_theme()
sidebar_brand()

engine = get_engine()

@st.cache_data(ttl=300)
def load_all_snapshots() -> pd.DataFrame:
    try:
        return pd.read_sql(
            "SELECT * FROM daily_kpi_snapshot WHERE scan_status = 'success' ORDER BY scan_date DESC",
            engine
        )
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_scan_log() -> pd.DataFrame:
    try:
        return pd.read_sql("SELECT * FROM scan_log ORDER BY run_date DESC", engine)
    except Exception:
        return pd.DataFrame()

def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "current_price" not in df.columns:
        return df
    df = df.copy()
    df["scan_date"] = pd.to_datetime(df["scan_date"])
    latest   = df.sort_values("scan_date").groupby("ticker").last()[["current_price","scan_date"]].rename(
        columns={"current_price":"latest_price","scan_date":"latest_date"})
    earliest = df.sort_values("scan_date").groupby("ticker").first()[["current_price","scan_date","total_score"]].rename(
        columns={"current_price":"entry_price","scan_date":"entry_date","total_score":"entry_score"})
    merged = pd.merge(earliest, latest, on="ticker")
    merged["return_pct"]   = ((merged["latest_price"] - merged["entry_price"]) / merged["entry_price"]) * 100
    merged["holding_days"] = (merged["latest_date"] - merged["entry_date"]).dt.days
    return merged.reset_index()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Results Tracker</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    See how stocks have performed since they first appeared in the scanner
  </p>
</div>
""", unsafe_allow_html=True)

df_all = load_all_snapshots()
df_log = load_scan_log()

if df_all.empty:
    st.error("No scan history found. Run the batch scanner first.")
    st.stop()

# ── Scan history ───────────────────────────────────────────────────────────────
st.markdown(section_header("Scan Run History", "🗓"), unsafe_allow_html=True)
if not df_log.empty:
    display_log = df_log[["run_date","total_scanned","total_succeeded","total_failed","duration_seconds"]].copy()
    display_log["duration_min"] = (display_log["duration_seconds"] / 60).round(1)
    st.dataframe(display_log.drop(columns=["duration_seconds"]), use_container_width=True)
else:
    st.info("No scan run logs found yet.")

st.divider()

# ── Returns analysis ───────────────────────────────────────────────────────────
st.markdown(section_header("Score vs. Subsequent Return", "📊"), unsafe_allow_html=True)
st.caption("Does a higher KPI score actually predict better returns?")

df_returns = compute_returns(df_all)

if not df_returns.empty and "return_pct" in df_returns.columns:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks Tracked", len(df_returns))
    c2.metric("Avg Return",    f"{df_returns['return_pct'].mean():.1f}%")
    c3.metric("Winners (>0%)", int((df_returns["return_pct"] > 0).sum()))
    c4.metric("Losers (<0%)",  int((df_returns["return_pct"] < 0).sum()))

    fig = go.Figure()
    colors = df_returns["return_pct"].apply(lambda x: "#00ffc8" if x > 0 else "#ef4444")
    fig.add_trace(go.Scatter(
        x=df_returns["entry_score"], y=df_returns["return_pct"],
        mode="markers+text", text=df_returns["ticker"],
        textposition="top center",
        marker=dict(color=colors, size=10, opacity=0.8, line=dict(width=0)),
        hovertemplate="<b>%{text}</b><br>Entry Score: %{x}<br>Return: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="#5a6f8a")
    apply_plotly_theme(fig, height=420)
    fig.update_layout(xaxis_title="KPI Score at Entry", yaxis_title="Return Since First Scan (%)")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(section_header("Top 10 Performers", "🏆"), unsafe_allow_html=True)
        top10 = df_returns.nlargest(10, "return_pct")[
            ["ticker","entry_score","entry_price","latest_price","return_pct","holding_days"]
        ].reset_index(drop=True)
        top10["return_pct"] = top10["return_pct"].round(1)
        def pos_color(val):
            return "color:#22c55e;font-weight:600" if val > 0 else "color:#ef4444;font-weight:600"
        st.dataframe(top10.style.applymap(pos_color, subset=["return_pct"]), use_container_width=True)

    with col_r:
        st.markdown(section_header("Bottom 10 Performers", "📉"), unsafe_allow_html=True)
        bot10 = df_returns.nsmallest(10, "return_pct")[
            ["ticker","entry_score","entry_price","latest_price","return_pct","holding_days"]
        ].reset_index(drop=True)
        bot10["return_pct"] = bot10["return_pct"].round(1)
        st.dataframe(bot10.style.applymap(pos_color, subset=["return_pct"]), use_container_width=True)

    st.divider()

    st.markdown(section_header("Avg Return by Score Bucket"), unsafe_allow_html=True)
    st.caption("Do stocks with higher scores actually outperform?")
    df_returns["score_bucket"] = pd.cut(
        df_returns["entry_score"], bins=[0,3,5,7,10],
        labels=["Low (0–3)","Medium (3–5)","Good (5–7)","Strong (7–10)"]
    )
    bucket_summary = df_returns.groupby("score_bucket", observed=False)["return_pct"].agg(["mean","count"]).reset_index()
    bucket_summary.columns = ["Score Bucket","Avg Return (%)","Stock Count"]
    bucket_summary["Avg Return (%)"] = bucket_summary["Avg Return (%)"].round(1)

    fig2 = go.Figure(go.Bar(
        x=bucket_summary["Score Bucket"], y=bucket_summary["Avg Return (%)"],
        marker_color=["#ef4444","#f97316","#fbbf24","#00ffc8"],
        marker_line_width=0, opacity=0.9,
        text=bucket_summary["Avg Return (%)"].astype(str) + "%",
        textposition="outside",
    ))
    apply_plotly_theme(fig2, height=320)
    fig2.update_layout(yaxis_title="Avg Return (%)")
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown(section_header("Score History — Single Stock", "🔎"), unsafe_allow_html=True)
    chosen = st.selectbox("Pick a ticker", sorted(df_all["ticker"].unique()))
    df_chosen = df_all[df_all["ticker"] == chosen].sort_values("scan_date")
    if not df_chosen.empty:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_chosen["scan_date"], y=df_chosen["total_score"],
            name="KPI Score", line=dict(color="#00ffc8", width=2), mode="lines+markers",
        ))
        fig3.add_trace(go.Scatter(
            x=df_chosen["scan_date"], y=df_chosen["current_price"],
            name="Price ($)", line=dict(color="#fbbf24", width=2), yaxis="y2", mode="lines",
        ))
        apply_plotly_theme(fig3, height=320)
        fig3.update_layout(
            yaxis=dict(title="KPI Score", gridcolor="#1a2840"),
            yaxis2=dict(title="Price ($)", overlaying="y", side="right", gridcolor="#1a2840"),
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig3, use_container_width=True)

else:
    st.info("Need at least 2 scan dates to compute returns. Run the scanner again tomorrow.")

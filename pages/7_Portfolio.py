# pages/7_Portfolio.py
# Portfolio Tracker — track holdings, view P&L, and monitor KPI health.

import streamlit as st
import pandas as pd
import plotly.express as px
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
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, section_header, trend_badge, apply_plotly_theme

st.set_page_config(page_title="Portfolio · Screener", layout="wide", page_icon="💼")
apply_theme()
sidebar_brand()

engine = get_engine()
USER_ID = "default"

def get_portfolio():
    try:
        return pd.read_sql(
            "SELECT * FROM portfolio WHERE user_id = %s ORDER BY buy_date DESC",
            engine, params=(USER_ID,)
        )
    except Exception:
        return pd.DataFrame(columns=["id","user_id","ticker","buy_price","shares","buy_date","notes"])

def get_kpis(tickers):
    if not tickers:
        return pd.DataFrame()
    placeholders = ", ".join([f"'{t}'" for t in tickers])
    try:
        return pd.read_sql(f"""
            SELECT ticker, current_price, total_score, fundamental_score, technical_score,
                   long_term_trend, rsi_val, sector, scan_date
            FROM daily_kpi_snapshot
            WHERE ticker IN ({placeholders})
              AND scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
              AND scan_status = 'success'
        """, engine)
    except Exception:
        return pd.DataFrame()

def add_holding(ticker, buy_price, shares, buy_date, notes):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO portfolio (user_id, ticker, buy_price, shares, buy_date, notes)
            VALUES (:uid, :t, :bp, :sh, :bd, :n)
            ON DUPLICATE KEY UPDATE buy_price=:bp, shares=:sh, buy_date=:bd, notes=:n
        """), {"uid": USER_ID, "t": ticker, "bp": buy_price, "sh": shares, "bd": str(buy_date), "n": notes})
        conn.commit()

def remove_holding(ticker):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM portfolio WHERE user_id=:uid AND ticker=:t"),
                     {"uid": USER_ID, "t": ticker})
        conn.commit()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Portfolio Tracker</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Track your holdings, monitor P&amp;L, and get KPI health alerts
  </p>
</div>
""", unsafe_allow_html=True)

df_port = get_portfolio()

# ── Add holding ────────────────────────────────────────────────────────────────
with st.expander("Add / Update Holding", expanded=df_port.empty):
    c1, c2, c3, c4 = st.columns(4)
    new_ticker    = c1.text_input("Ticker").upper().strip()
    new_buy_price = c2.number_input("Buy Price ($)", min_value=0.01, value=100.0, step=0.01)
    new_shares    = c3.number_input("Shares", min_value=0.01, value=10.0, step=0.01)
    new_date      = c4.date_input("Buy Date", value=date.today())
    new_notes     = st.text_input("Notes (optional)")
    if st.button("Add to Portfolio", type="primary"):
        if not new_ticker:
            st.error("Enter a ticker symbol.")
        else:
            add_holding(new_ticker, new_buy_price, new_shares, new_date, new_notes)
            st.success(f"{new_ticker} added.")
            st.cache_data.clear()
            st.rerun()

if df_port.empty:
    st.info("No holdings yet. Add your first position above.")
    st.stop()

# ── Compute P&L ────────────────────────────────────────────────────────────────
tickers = df_port["ticker"].tolist()
df_kpi  = get_kpis(tickers)
df      = df_port.merge(df_kpi, on="ticker", how="left")
df["current_price"] = df["current_price"].fillna(df["buy_price"])
df["market_value"]  = df["current_price"] * df["shares"]
df["cost_basis"]    = df["buy_price"]     * df["shares"]
df["pnl"]           = df["market_value"]  - df["cost_basis"]
df["pnl_pct"]       = ((df["current_price"] - df["buy_price"]) / df["buy_price"]) * 100

total_invested = df["cost_basis"].sum()
total_value    = df["market_value"].sum()
total_pnl      = df["pnl"].sum()
total_pnl_pct  = ((total_value - total_invested) / total_invested) * 100
avg_score      = df["total_score"].mean()

# ── Summary metrics ────────────────────────────────────────────────────────────
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Invested",  f"${total_invested:,.2f}")
c2.metric("Portfolio Value", f"${total_value:,.2f}")
c3.metric("Total P&L",       f"${total_pnl:,.2f}", f"{total_pnl_pct:+.2f}%")
c4.metric("Avg KPI Score",   f"{avg_score:.1f} / 10" if not pd.isna(avg_score) else "N/A")
st.divider()

# ── Holdings table ─────────────────────────────────────────────────────────────
st.markdown(section_header("Holdings", "📋"), unsafe_allow_html=True)

def style_pnl(val):
    if isinstance(val, (int, float)):
        return f"color:{'#22c55e' if val >= 0 else '#ef4444'};font-weight:600"
    return ""

def style_score(val):
    if isinstance(val, (int, float)):
        if val >= 7:   return "background-color:rgba(0,255,200,.18);color:#00ffc8;font-weight:600"
        elif val >= 5: return "background-color:rgba(251,191,36,.15);color:#fbbf24;font-weight:600"
        return "background-color:rgba(239,68,68,.1);color:#ef4444"
    return ""

def flag_health(row):
    flags = []
    if isinstance(row["total_score"], float) and row["total_score"] < 4: flags.append("Low Score")
    if isinstance(row["long_term_trend"], str) and row["long_term_trend"] == "Bearish": flags.append("Bearish")
    if isinstance(row["rsi_val"], float) and row["rsi_val"] > 75: flags.append("Overbought")
    return ", ".join(flags) if flags else "OK"

df["Health"] = df.apply(flag_health, axis=1)

display = df[[
    "ticker","sector","shares","buy_price","current_price",
    "cost_basis","market_value","pnl","pnl_pct",
    "total_score","long_term_trend","rsi_val","Health"
]].copy()
display.columns = [
    "Ticker","Sector","Shares","Buy Price","Current Price",
    "Cost Basis","Market Value","P&L ($)","P&L (%)",
    "KPI Score","Trend","RSI","Health"
]

st.dataframe(
    display.style
        .applymap(style_pnl, subset=["P&L ($)","P&L (%)"])
        .applymap(style_score, subset=["KPI Score"])
        .format({
            "Buy Price": "${:.2f}", "Current Price": "${:.2f}",
            "Cost Basis": "${:,.2f}", "Market Value": "${:,.2f}",
            "P&L ($)": "${:,.2f}", "P&L (%)": "{:+.2f}%",
            "KPI Score": "{:.1f}", "RSI": "{:.1f}",
        }),
    use_container_width=True, hide_index=True, height=400,
)

# ── Health flags ───────────────────────────────────────────────────────────────
flagged = display[display["Health"] != "OK"]
if not flagged.empty:
    flags_html = "".join([
        f'<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0"><span class="ticker-chip">{r["Ticker"]}</span><span style="color:var(--txt2);font-size:.85rem">{r["Health"]}</span></div>'
        for _, r in flagged.iterrows()
    ])
    st.markdown(f"""
<div style="background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);border-radius:10px;
            padding:.9rem 1.2rem;margin-top:.75rem">
  <div style="font-weight:600;color:#f59e0b;margin-bottom:.5rem">⚠️ {len(flagged)} holding(s) need attention</div>
  {flags_html}
</div>""", unsafe_allow_html=True)

st.divider()

# ── Charts ─────────────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.markdown(section_header("Allocation", "🥧"), unsafe_allow_html=True)
    fig_alloc = px.pie(
        df, names="ticker", values="market_value",
        color_discrete_sequence=["#00ffc8","#3b82f6","#fbbf24","#f97316","#a78bfa",
                                  "#ec4899","#22c55e","#06b6d4","#84cc16"],
        hole=0.45,
    )
    apply_plotly_theme(fig_alloc, height=300)
    fig_alloc.update_layout(showlegend=True, legend=dict(bgcolor="#0d1421"))
    st.plotly_chart(fig_alloc, use_container_width=True)

with col_r:
    st.markdown(section_header("P&L by Holding", "📊"), unsafe_allow_html=True)
    fig_pnl = px.bar(
        df.sort_values("pnl_pct"), x="ticker", y="pnl_pct",
        color="pnl_pct",
        color_continuous_scale=[[0,"#ef4444"],[0.5,"#fbbf24"],[1,"#00ffc8"]],
        text_auto=".1f",
        labels={"pnl_pct": "P&L (%)", "ticker": ""},
    )
    fig_pnl.update_traces(marker_line_width=0)
    apply_plotly_theme(fig_pnl, height=300)
    fig_pnl.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_pnl, use_container_width=True)

st.divider()

with st.expander("Remove a Holding"):
    remove_ticker = st.selectbox("Select ticker to remove", tickers)
    if st.button("Remove", type="secondary"):
        remove_holding(remove_ticker)
        st.success(f"{remove_ticker} removed.")
        st.cache_data.clear()
        st.rerun()

st.download_button("Download Portfolio CSV", display.to_csv(index=False), "portfolio.csv", "text/csv")

# pages/1_Scanner.py
# Custom Stock Scanner — filter the S&P 500 by any KPI combination.

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
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, sidebar_status, section_header, apply_plotly_theme

st.set_page_config(page_title="Scanner · Screener", layout="wide", page_icon="🔍")
apply_theme()
sidebar_brand()

engine = get_engine()

@st.cache_data(ttl=300)
def load_snapshot():
    try:
        return pd.read_sql("""
            SELECT * FROM daily_kpi_snapshot
            WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot)
              AND scan_status = 'success'
        """, engine)
    except Exception:
        return pd.DataFrame()

TEMPLATES = {
    "Golden Cross + Value": {
        "desc": "50D SMA above 200D SMA · price >10% below 52W high",
        "icon": "✨",
        "filters": {"medium_term_trend": "Yes", "price_strength_val_max": -10.0},
    },
    "Oversold Bounce": {
        "desc": "RSI < 35 · Long-term trend Bullish",
        "icon": "🔄",
        "filters": {"rsi_val_max": 35.0, "long_term_trend": "Bullish"},
    },
    "High Score Leaders": {
        "desc": "Total KPI Score ≥ 9",
        "icon": "🏆",
        "filters": {"total_score_min": 9.0},
    },
    "Strong Fundamentals": {
        "desc": "Fundamental Score ≥ 5 · Revenue Growth > 10%",
        "icon": "📊",
        "filters": {"fundamental_score_min": 5.0, "rev_growth_val_min": 10.0},
    },
    "Deep Value Dip": {
        "desc": "Price >20% below 52W High · Score ≥ 6",
        "icon": "💎",
        "filters": {"price_strength_val_max": -20.0, "total_score_min": 6.0},
    },
    "Momentum Leaders": {
        "desc": "Bullish + Golden Cross · RSI 40–65",
        "icon": "🚀",
        "filters": {
            "long_term_trend": "Bullish",
            "medium_term_trend": "Yes",
            "rsi_val_min": 40.0,
            "rsi_val_max": 65.0,
        },
    },
}

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Stock Scanner</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Filter the S&amp;P 500 by any combination of fundamental and technical criteria
  </p>
</div>
""", unsafe_allow_html=True)

df_all = load_snapshot()
if df_all.empty:
    st.error("No scan data found. Run `python scheduler.py now` first to populate the database.")
    st.stop()

latest_date = df_all["scan_date"].max() if "scan_date" in df_all.columns else "N/A"
sidebar_status(str(latest_date), len(df_all))

c1, c2, c3 = st.columns(3)
c1.metric("Stocks in Universe", f"{len(df_all):,}")
c2.metric("Last Scan Date", str(latest_date))
c3.metric("Avg Score", f"{df_all['total_score'].mean():.1f} / 10" if "total_score" in df_all.columns else "N/A")

st.divider()

# ── Templates ──────────────────────────────────────────────────────────────────
st.markdown(section_header("Quick Scan Templates", "⚡"), unsafe_allow_html=True)
tmpl_cols = st.columns(3)

for i, (name, tmpl) in enumerate(TEMPLATES.items()):
    with tmpl_cols[i % 3]:
        active = st.session_state.get("active_template_name") == name
        border_style = "border-color:var(--accent);box-shadow:0 0 12px var(--accent08)" if active else ""
        st.markdown(f"""
<div class="sc-card" style="{border_style}; cursor:pointer; margin-bottom:.5rem">
  <div style="font-size:1.3rem;margin-bottom:.3rem">{tmpl['icon']}</div>
  <div style="font-weight:600;color:var(--txt0);font-size:.9rem;margin-bottom:.3rem">{name}</div>
  <div style="color:var(--txt2);font-size:.78rem">{tmpl['desc']}</div>
</div>
""", unsafe_allow_html=True)
        if st.button("Use Template", key=f"tmpl_{i}", use_container_width=True):
            st.session_state["active_filters"] = tmpl["filters"]
            st.session_state["active_template_name"] = name
            st.rerun()

if "active_template_name" in st.session_state:
    st.markdown(f"""
<div style="background:var(--accent15);border:1px solid rgba(0,255,200,.3);border-radius:8px;
            padding:.6rem 1rem;font-size:.85rem;color:var(--accent);margin-top:.5rem">
  Active template: <strong>{st.session_state['active_template_name']}</strong> — adjust filters below or click Apply.
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Custom Filter Builder ──────────────────────────────────────────────────────
st.markdown(section_header("Custom Filters", "🎛"), unsafe_allow_html=True)

af = st.session_state.get("active_filters", {})

with st.expander("Score Filters", expanded=True):
    c1, c2, c3 = st.columns(3)
    f_total_min = c1.slider("Min Total Score",       0.0, 12.0, float(af.get("total_score_min", 0.0)), 0.5)
    f_fund_min  = c2.slider("Min Fundamental Score", 0.0, 8.0,  float(af.get("fundamental_score_min", 0.0)), 0.5)
    f_tech_min  = c3.slider("Min Technical Score",   0.0, 4.0,  float(af.get("technical_score_min", 0.0)), 0.5)

with st.expander("Technical Filters"):
    c1, c2, c3, c4 = st.columns(4)
    f_rsi_min     = c1.number_input("RSI Min", 0.0, 100.0, float(af.get("rsi_val_min", 0.0)), step=1.0)
    f_rsi_max     = c2.number_input("RSI Max", 0.0, 100.0, float(af.get("rsi_val_max", 100.0)), step=1.0)
    trend_opts    = ["Any", "Bullish", "Bearish"]
    trend_def     = af.get("long_term_trend", "Any")
    f_long_trend  = c3.selectbox("Long-term Trend", trend_opts,
                                  index=trend_opts.index(trend_def) if trend_def in trend_opts else 0)
    gc_opts       = ["Any", "Yes", "No"]
    gc_def        = af.get("medium_term_trend", "Any")
    f_golden      = c4.selectbox("Golden Cross (50>200)", gc_opts,
                                  index=gc_opts.index(gc_def) if gc_def in gc_opts else 0)
    c5, c6 = st.columns(2)
    f_dip_min = c5.number_input("Price from 52W High — Min (%)", -100.0, 0.0, -100.0, step=5.0)
    f_dip_max = c6.number_input("Price from 52W High — Max (%)", -100.0, 0.0,
                                 float(af.get("price_strength_val_max", 0.0)), step=5.0)

with st.expander("Fundamental Filters"):
    c1, c2, c3, c4 = st.columns(4)
    f_margin_min    = c1.number_input("Min Margin (%)", -100.0, 100.0,
                                       float(af.get("margin_val_min", -100.0)), step=1.0)
    f_revgrowth_min = c2.number_input("Min Rev Growth (%)", -100.0, 200.0,
                                       float(af.get("rev_growth_val_min", -100.0)), step=1.0)
    f_category      = c3.selectbox("Category", ["Any", "Bank", "Non-Bank"])
    sector_options  = ["Any"] + sorted(df_all["sector"].dropna().unique().tolist())
    f_sector        = c4.selectbox("Sector", sector_options)

if st.button("Apply Filters", type="primary", use_container_width=True):
    df = df_all.copy()
    if f_total_min > 0:   df = df[df["total_score"] >= f_total_min]
    if f_fund_min > 0:    df = df[df["fundamental_score"] >= f_fund_min]
    if f_tech_min > 0:    df = df[df["technical_score"] >= f_tech_min]
    if f_rsi_min > 0:     df = df[df["rsi_val"] >= f_rsi_min]
    if f_rsi_max < 100:   df = df[df["rsi_val"] <= f_rsi_max]
    if f_long_trend != "Any": df = df[df["long_term_trend"] == f_long_trend]
    if f_golden != "Any": df = df[df["medium_term_trend"] == f_golden]
    if f_dip_max < 0:     df = df[df["price_strength_val"] <= f_dip_max]
    if f_dip_min > -100:  df = df[df["price_strength_val"] >= f_dip_min]
    if f_margin_min > -100:    df = df[df["margin_val"] >= f_margin_min]
    if f_revgrowth_min > -100: df = df[df["rev_growth_val"] >= f_revgrowth_min]
    if f_category != "Any": df = df[df["category"] == f_category]
    if f_sector != "Any":   df = df[df["sector"] == f_sector]
    st.session_state["scan_results"] = df
    st.session_state["active_filters"] = {}

# ── Results ────────────────────────────────────────────────────────────────────
if "scan_results" in st.session_state:
    df_res = st.session_state["scan_results"]
    st.divider()

    res_count = len(df_res)
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1rem">
  <span style="font-size:1rem;font-weight:600;color:var(--txt0)">Results</span>
  <span class="badge badge-{'accent' if res_count > 0 else 'bearish'}">{res_count} stocks matched</span>
</div>
""", unsafe_allow_html=True)

    if df_res.empty:
        st.warning("No stocks matched the current filters. Try relaxing the criteria.")
    else:
        display_cols = [
            "ticker", "sector", "category", "total_score", "fundamental_score", "technical_score",
            "current_price", "rsi_val", "long_term_trend", "medium_term_trend",
            "margin_val", "rev_growth_val", "price_strength_val",
        ]
        display_cols = [c for c in display_cols if c in df_res.columns]
        df_display = df_res[display_cols].sort_values("total_score", ascending=False).reset_index(drop=True)

        def score_color(val):
            if val >= 9:   return "background-color:rgba(0,255,200,.18);color:#00ffc8;font-weight:600"
            elif val >= 6: return "background-color:rgba(251,191,36,.15);color:#fbbf24;font-weight:600"
            return "background-color:rgba(239,68,68,.1);color:#ef4444"

        def trend_color(val):
            if val == "Bullish": return "color:#22c55e;font-weight:600"
            if val == "Bearish": return "color:#ef4444;font-weight:600"
            return "color:#9ca3af"

        st.dataframe(
            df_display.style
                .applymap(score_color, subset=["total_score"])
                .applymap(trend_color, subset=["long_term_trend"] if "long_term_trend" in display_cols else []),
            use_container_width=True, height=500,
        )

        col_wl, col_dl = st.columns([2, 1])
        with col_wl:
            wl_ticker = st.selectbox("Add to Watchlist", df_display["ticker"].tolist(), key="scan_to_wl")
            if st.button("Add to Watchlist"):
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text("INSERT IGNORE INTO watchlist (user_id, ticker, added_date) VALUES ('default', :t, CURDATE())"),
                            {"t": wl_ticker}
                        )
                        conn.commit()
                    st.success(f"{wl_ticker} added to watchlist.")
                except Exception as e:
                    st.error(f"Error: {e}")
        with col_dl:
            st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
            csv = df_display.to_csv(index=False)
            st.download_button("Download CSV", csv, "scan_results.csv", "text/csv", use_container_width=True)

import os
import sys
# This adds your current folder to the Python path so it can find the 'src' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine


# --- SMART ENGINE CREATOR ---
def get_db_engine():
    # 1. Try to get credentials from Streamlit Secrets (Cloud)
    try:
        user = st.secrets["DB_USER"]
        password = st.secrets["DB_PASS"]
        host = st.secrets["DB_HOST"]
        port = st.secrets["DB_PORT"]
        db_name = st.secrets["DB_NAME"]
    # 2. Fallback to your local computer settings if Secrets aren't found
    except:
        user, password, host, port, db_name = 'root', 'Bank1234', 'localhost', '3306', 'bank_data'
    
    return create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}")

# Create the engine for the app to use
engine = get_db_engine()

from src.ingestion import ingest, upsert_kpi_report
from src.kpis import compute_fundamentals, compute_technicals
from src.Migration import run
from src.ml_engine import get_scenario_results
from src.ai_summary import generate_summary
from src.sentiment_engine import get_sentiment_analysis, sentiment_to_plain_english
from src.regime_engine import get_regime_analysis, build_regime_chart
from src.prophet_engine import (
    get_prophet_forecast, build_prophet_forecast_chart, build_seasonality_chart,
    build_monthly_avg_chart,
)
from src.ensemble_engine import compute_ensemble_score
from src.lstm_engine import get_lstm_forecast, build_lstm_chart
from src.valuation_engine import (
    get_revenue_valuation_inputs,
    calculate_revenue_intrinsic_value,
    build_sensitivity_table,
)
import chatbot_engine as ce
from chatbot_engine import process_stock_data, save_to_vector_db, get_chat_response

_db_engine = get_engine()

from src.ml_engine import (
    get_adaptive_forecasts,
    run_ai_signal_analysis,
    get_valuation_data,
    calculate_fair_value,
    detect_anomalies,
)



# --- New Helper for Technical Momentum Projection ---
def plot_momentum_cone(df_hist, simulation_df):
    """
    Creates the 60% Confidence Interval 'Cloud' for 3M and 6M horizons.
    """
    # 1. Calculate boundaries from your ML Engine's simulation results
    upper = simulation_df.quantile(0.80, axis=1)
    median = simulation_df.quantile(0.50, axis=1)
    lower = simulation_df.quantile(0.20, axis=1)

    # 2. Stitch to last historical price
    last_price = df_hist['Close'].iloc[-1]
    for s in [upper, median, lower]: s.iloc[0] = last_price

    # 3. Create Future Dates (Business Day Frequency)
    future_dates = pd.date_range(start=df_hist.index[-1], periods=len(median), freq='B')

    fig = go.Figure()
    # Shaded Cloud
    fig.add_trace(go.Scatter(x=future_dates, y=upper, line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=future_dates, y=lower, fill='tonexty',
                    fillcolor='rgba(0, 255, 200, 0.2)', name='60% Confidence Cone'))
    # Median Path
    fig.add_trace(go.Scatter(x=future_dates, y=median, name='Expected Momentum', line=dict(color='#00FFC8', dash='dash')))
    
    # Milestone Markers
    for idx, label in [(63, "3M"), (126, "6M")]:
        xs = future_dates[idx].strftime('%Y-%m-%d')
        fig.add_shape(type='line', x0=xs, x1=xs, y0=0, y1=1, yref='paper',
                      line=dict(color='#ffffff', width=1, dash='dot'))
        fig.add_annotation(x=xs, y=1, yref='paper', text=label, showarrow=False,
                           font=dict(color='#ffffff', size=11), xanchor='left')

    fig.update_layout(template="plotly_dark", height=400, margin=dict(t=20, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig



def get_separated_forecasts(simulation_df, last_price):
    """
    Slices the Monte Carlo simulation into 3M and 6M discrete data buckets.
    """
    # 63 trading days = 3 Months | 126 trading days = 6 Months
    m3_sim = simulation_df.iloc[:64] 
    m6_sim = simulation_df.iloc[:127]

    def get_bounds(df):
        upper, median, lower = df.quantile(0.80, axis=1), df.quantile(0.50, axis=1), df.quantile(0.20, axis=1)
        for s in [upper, median, lower]: s.iloc[0] = last_price
        return upper, median, lower

    return get_bounds(m3_sim), get_bounds(m6_sim)

# --- Step 21: Setup Chat Memory ---
if "messages" not in st.session_state:
    st.session_state.messages = [] # This is our storage bin for the conversation


# For Monte Carlo Simulation: Calculate the "Heartbeat" of the stock (Daily Return & Volatility)
def plot_forecast_chart(forecast_df):
    """
    Creates a professional, dark-themed chart for the Monte Carlo scenarios.
    """
    fig = go.Figure()

    # Bull Case - Neon Green (#00FFC8)
    fig.add_trace(go.Scatter(y=forecast_df['Bull_Case'], name='Bull Case (15%)',
                 line=dict(color='#00FFC8', width=2, dash='dot')))
    
    # Base Case - Gold (#FFD700)
    fig.add_trace(go.Scatter(y=forecast_df['Base_Case'], name='Base Case (12%)',
                  line=dict(color='#FFD700', width=3)))
    
    # Bear Case - Neon Red (#FF4B4B)
    fig.add_trace(go.Scatter(y=forecast_df['Bear_Case'], name='Bear Case (10%)',
                 line=dict(color='#FF4B4B', width=2, dash='dot')))

    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Days into Future (Trading Days)",
        yaxis_title="Predicted Price ($)",
        hovermode="x unified",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


# Feature Importance Helper Function (For the AI Forecast Tab)
def get_feature_importance_data(model, feature_columns):
    """
    Standalone helper: Extracts importance without touching your training logic.
    """
    # 1. Get raw scores from the trained XGBoost model
    importances = model.get_booster().get_score(importance_type='weight')
    
    # 2. Map internal names (f0, f1...) to your 10 KPI names
    # XGboost uses f0, f1, etc. This maps them back to 'rsi', 'margin', etc.
    feature_map = {f'f{i}': col for i, col in enumerate(feature_columns)}
    
    # 3. Create a clean dictionary of { 'KPI Name': Score }
    importance_dict = {feature_map.get(k, k): v for k, v in importances.items()}
    
    # 4. Sort it so the most influential KPI is at the top
    return dict(sorted(importance_dict.items(), key=lambda item: item[1], reverse=True))




# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(page_title="Analysis Engine · Screener", layout="wide", page_icon="📈")

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
from src.theme import apply_theme, sidebar_brand
apply_theme()
sidebar_brand()

st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Analysis Engine</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    12-Point fundamental &amp; technical deep-dive for any S&amp;P 500 stock
  </p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<div style='color:var(--txt2);font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem'>Search Stock</div>", unsafe_allow_html=True)
ticker_input = st.sidebar.text_input("", "NVDA", label_visibility="collapsed", placeholder="Ticker e.g. AAPL").upper().strip()
analyze_btn = st.sidebar.button("Run Analysis", type="primary", use_container_width=True)

if analyze_btn:
    with st.spinner(f"Analyzing {ticker_input}..."):
        # 1. Run Backend Logic
        temp_data = run(ticker_input)
        category = temp_data["category"]
        ingest(ticker_input)
        
        funda_results = compute_fundamentals(ticker_input, category)
        tech_results = compute_technicals(temp_data["df_stock"])
        
        funda_results.update(tech_results)
        results = funda_results
        
        # 2. Save to MySQL
        upsert_kpi_report(ticker_input, category, results)
        
        # 3. Calculate Score
        total_score = sum(v['score'] for k, v in results.items() if isinstance(v, dict) and 'score' in v)

        # 🚀 4. SAVE TO SESSION STATE
        st.session_state['analysis_done'] = True
        st.session_state['ticker'] = ticker_input
        st.session_state['temp_data'] = temp_data
        st.session_state['results'] = results
        st.session_state['total_score'] = total_score
        st.session_state['category'] = category
        
        # 🚀 5. RUN MONTE CARLO immediately
        df_for_sim = temp_data["df_stock"]
        if not df_for_sim.empty:
            sim_results = get_scenario_results(df_for_sim)
            st.session_state['forecast_df'] = sim_results
        
        st.session_state['analysis_done'] = True
        # ... (Rest of your existing session_state saves) ..

# ── CHECK THE NOTEPAD (The Dashboard Only Shows if analysis_done is True) ──
if st.session_state.get('analysis_done'):
    
    # Retrieve data from Notepad
    ticker = st.session_state['ticker']
    temp_data = st.session_state['temp_data']
    results = st.session_state['results']
    total_score = st.session_state['total_score']
    category = st.session_state['category']
    df_stock = temp_data["df_stock"]

    # ── Create the Tabs (Inside the state check!) ──
    tab_summary, tab_financials, tab_technicals, tab_aideepd, tab_aiverdict = st.tabs([
        "📊 Executive Summary",
        "🏦 Financial Health",
        "📈 Price Forecast",
        "🤖 AI Deep Dive",
        "⚡ AI Verdict",
    ])

    # ── TAB 1: EXECUTIVE SUMMARY ──────────────────────────────────────────────
    with tab_summary:
        st.markdown(f"""
<div class="explore-path">
  <span class="ep-step active">📊 Score &amp; Verdict</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🔬 KPI Breakdown</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">📅 Score History</span>
</div>
""", unsafe_allow_html=True)
        col_ring, col_stats = st.columns([1.2, 2])
        
        with col_ring:
            # Dynamic Ring Color
            ring_color = "#00FFC8" if total_score >= 10 else "#FFD700" if total_score >= 6 else "#FF4B4B"
            ring_label = "STRONG BUY" if total_score >= 10 else "NEUTRAL" if total_score >= 6 else "AVOID"

            st.markdown('<div class="score-ring-wrap">', unsafe_allow_html=True)
            fig = go.Figure(data=[go.Pie(
                values=[total_score, max(0, 12 - total_score)],
                hole=0.8,
                marker_colors=[ring_color, "#1a2840"],
                textinfo='none', hoverinfo='none', sort=False
            )])
            fig.add_annotation(
                text=f"<span style='font-size:58px; font-weight:800; color:{ring_color};'>{total_score}</span><br><span style='font-size:18px; color:#5a6f8a;'>/12</span>",
                showarrow=False, x=0.5, y=0.5
            )
            fig.update_layout(height=320, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"""
<div style="text-align:center;margin-top:-12px;animation:fadeInUp 0.6s ease both;">
  <span style="font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{ring_color};">{ring_label}</span><br>
  <span style="font-size:.72rem;color:var(--txt2);">{total_score} of 12 quality markers passed</span>
</div>
""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_stats:
            verdict_desc = (
                "All key quality and momentum markers are firing. Fundamentals are strong, technicals are aligned, and the risk/reward looks compelling."
                if total_score >= 10 else
                "Mixed signals — some fundamentals or technicals are not yet confirmed. Monitor for improvement before committing fully."
                if total_score >= 6 else
                "Multiple quality or momentum markers are failing. Risk is elevated. Review the KPI breakdown below before considering a position."
            )
            pulse_class = "pulse-safe" if total_score >= 10 else ""
            st.markdown(f"""
<div class="verdict-hero {pulse_class}" style="background:rgba(0,0,0,0.25);border:2px solid {ring_color};">
  <div class="verdict-hero-label">
    <span class="live-dot {'green' if total_score >= 10 else 'gold' if total_score >= 6 else 'red'}"></span>
    AI INVESTMENT VERDICT · {ticker}
  </div>
  <div class="verdict-hero-title" style="color:{ring_color};">
    {'STRONG BUY' if total_score >= 10 else 'NEUTRAL' if total_score >= 6 else 'AVOID'}
  </div>
  <div class="verdict-hero-sub">{verdict_desc}</div>
</div>
""", unsafe_allow_html=True)
            
            st.write("")
            m1, m2, m3 = st.columns(3)
            m1.metric("Category", category)
            m1.caption(f"Asset Class: {category}")
            m2.metric("Trend Status", results.get('LongTermTrend', {}).get('formatted', 'N/A'))
            m3.metric("RSI (14D)", results.get('RSI', {}).get('formatted', 'N/A'))

        # ── Ensemble badge (populated after AI Advisor tab runs) ─────────────
        ens = st.session_state.get('ensemble')
        if ens:
            eb1, eb2, eb3 = st.columns(3)
            eb1.metric("AI Conviction Score", f"{ens['score']:.0f} / 100")
            eb2.metric("AI Verdict", ens['label'])
            eb3.metric("Signals Used", f"{len(ens['components'])} models")
            st.caption("Run the AI Advisor tab to refresh this score.")

        # ── AI Summary ────────────────────────────────────────────────────────
        st.divider()
        summary_text = generate_summary(ticker, results, total_score, category)
        st.markdown(f"""
<div class="insight">
  <div class="insight-label">✦ AI ANALYST SUMMARY</div>
  <div class="insight-text">{summary_text}</div>
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">2</div>
  <div class="ch-text">
    <div class="ch-title">KPI Breakdown</div>
    <div class="ch-sub">All 12 quality &amp; momentum markers — hover each card for context</div>
  </div>
</div>
<div class="ch-line"></div>
""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        all_metrics = [v for k, v in results.items() if isinstance(v, dict) and 'label' in v]

        for i, m in enumerate(all_metrics):
            target_col = c1 if i < (len(all_metrics)/2) else c2
            
            if m['score'] == 1:
                border_color = "#00FFC8"
                score_icon   = "✅"
                score_class  = "g-card-accent"
            elif m['score'] == 0.5:
                border_color = "#FFD700"
                score_icon   = "⚠️"
                score_class  = "g-card-warn"
            else:
                border_color = "#FF4B4B"
                score_icon   = "❌"
                score_class  = "g-card-danger"

            anim_delay = f"animation-delay:{(i%6)*0.05:.2f}s"
            target_col.markdown(f"""
<div class="g-card {score_class}" style="{anim_delay};margin-bottom:.6rem;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
    <span style="color:var(--txt2);font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">{m['label']}</span>
    <span style="font-size:.85rem;">{score_icon}</span>
  </div>
  <div style="font-size:1.15rem;font-weight:800;color:{border_color};">{m['formatted']}</div>
  <div style="font-size:.72rem;color:var(--txt2);margin-top:.25rem;">Target: {m.get('threshold', 'N/A')}</div>
</div>
""", unsafe_allow_html=True)
        # ── SCORE HISTORY CHART ───────────────────────────────────────────────
        st.divider()
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">3</div>
  <div class="ch-text">
    <div class="ch-title">Score History</div>
    <div class="ch-sub">Track how the KPI score has evolved over time — improving or deteriorating?</div>
  </div>
</div>
<div class="ch-line"></div>
""", unsafe_allow_html=True)

        try:
            df_hist = pd.read_sql(
                "SELECT scan_date, total_score, fundamental_score, technical_score "
                "FROM daily_kpi_snapshot WHERE ticker = %s AND scan_status = 'success' "
                "ORDER BY scan_date ASC",
                _db_engine, params=(ticker,)
            )
            df_hist["scan_date"] = pd.to_datetime(df_hist["scan_date"])
        except Exception:
            df_hist = pd.DataFrame()

        if df_hist.empty or len(df_hist) < 2:
            st.info("Score history builds up over time as the nightly scanner runs. Check back after a few more daily scans.")
        else:
            period_map = {"30D": 30, "60D": 60, "90D": 90, "All": 9999}
            period = st.radio("Period", list(period_map.keys()), horizontal=True, index=0)
            cutoff = pd.Timestamp.today() - pd.Timedelta(days=period_map[period])
            df_plot = df_hist[df_hist["scan_date"] >= cutoff]

            fig_hist = go.Figure()
            fig_hist.add_trace(go.Scatter(
                x=df_plot["scan_date"], y=df_plot["total_score"],
                name="Total Score", line=dict(color="#00FFC8", width=3),
                mode="lines+markers",
            ))
            fig_hist.add_trace(go.Scatter(
                x=df_plot["scan_date"], y=df_plot["fundamental_score"],
                name="Fundamental", line=dict(color="#FFD700", width=2, dash="dot"),
            ))
            fig_hist.add_trace(go.Scatter(
                x=df_plot["scan_date"], y=df_plot["technical_score"],
                name="Technical", line=dict(color="#A78BFA", width=2, dash="dot"),
            ))
            fig_hist.add_hrect(y0=9, y1=12, fillcolor="rgba(0,255,200,0.05)", line_width=0, annotation_text="Strong Zone")
            fig_hist.add_hrect(y0=0, y1=4,  fillcolor="rgba(255,75,75,0.05)",  line_width=0, annotation_text="Weak Zone")
            fig_hist.update_layout(
                template="plotly_dark", height=300,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(range=[0, 12], gridcolor="#30363d"),
                xaxis=dict(gridcolor="#30363d"),
                legend=dict(orientation="h", y=1.1),
                margin=dict(t=10, b=10),
            )
            st.plotly_chart(fig_hist, use_container_width=True)

            # trend indicator
            if len(df_plot) >= 2:
                delta = df_plot["total_score"].iloc[-1] - df_plot["total_score"].iloc[0]
                if delta > 0:
                    st.success(f"Improving — score up {delta:+.1f} pts over this period.")
                elif delta < 0:
                    st.warning(f"Deteriorating — score down {delta:+.1f} pts over this period.")
                else:
                    st.info("Score is flat over this period.")

       # ── TAB 2: FINANCIAL HEALTH (Final Elite Version) ────────────────────────
    with tab_financials:
        st.markdown(f"""
<div class="explore-path">
  <span class="ep-step active">💹 Revenue &amp; Earnings</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">📐 Margin Efficiency</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🏗 Capital Structure</span>
</div>
<div style="margin-bottom:1.2rem">
  <div style="font-size:1.4rem;font-weight:800;color:var(--txt0);">{ticker} — Financial Deep-Dive</div>
  <div style="font-size:.82rem;color:var(--txt2);margin-top:.2rem;">Chronological view of revenue, earnings, margins, and balance sheet health</div>
</div>
""", unsafe_allow_html=True)
        
        # Pull data from the results of your Migration script
        df_isy = temp_data["df_isy"]
        df_bs = temp_data.get("df_bs")

        # 1. Top Metric Row (Pulling from your existing KPI results)
        m1, m2, m3 = st.columns(3)
        rev_score = results.get('RevGrowth', {}).get('score')
        m1.metric("Revenue Growth", results.get('RevGrowth', {}).get('formatted', 'N/A'),
                  delta="Pass" if rev_score == 1 else "Fail",
                  delta_color="normal" if rev_score == 1 else "inverse")
        m2.metric("Net Margin", results.get('Margin', {}).get('formatted', 'N/A'))
        m3.metric("Equity/Asset Ratio", results.get('Solvency', {}).get('formatted', 'N/A'))

        st.divider()

        # ── PRE-PROCESSING: Chronological Sort & Clean Labels ──
        # This ensures time moves Left-to-Right (2023 -> 2026)
        df_isy_plot = df_isy.sort_index()
        # Create a "Year Only" version of the index for cleaner X-axis labels
        df_isy_plot.index = pd.to_datetime(df_isy_plot.index).year

        # ── 1. REVENUE VS EARNINGS FUNNEL (Grouped Bars) ──
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">1</div>
  <div class="ch-text">
    <div class="ch-title">Revenue vs. Earnings Funnel</div>
    <div class="ch-sub">Is the company growing its top line and converting revenue to profit?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        funnel_cols = [c for c in ['Total Revenue', 'Operating Income', 'Net Income'] if c in df_isy_plot.columns]
        
        fig_funnel = go.Figure()
        colors_funnel = {'Total Revenue': '#00FFC8', 'Operating Income': '#FFA500', 'Net Income': '#FF00FF'}
        
        for col in funnel_cols:
            fig_funnel.add_trace(go.Bar(
                x=df_isy_plot.index, y=df_isy_plot[col], name=col,
                marker_color=colors_funnel.get(col)
            ))

        fig_funnel.update_layout(
            template="plotly_dark", barmode='group', height=400,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
            xaxis=dict(type='category', title="Fiscal Year")
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

        # ── 2 & 3: MARGINS & CAPITAL (Two-Column Layout) ──
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("""
<div class="ch-marker" style="margin-top:1.2rem;">
  <div class="ch-num">2</div>
  <div class="ch-text">
    <div class="ch-title">Margin Efficiency</div>
    <div class="ch-sub">How much of each dollar of revenue becomes profit?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
            # Calculate percentages on the sorted dataframe
            df_isy_plot['Net Margin %'] = (df_isy_plot['Net Income'] / df_isy_plot['Total Revenue']) * 100
            
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Scatter(
                x=df_isy_plot.index, y=df_isy_plot['Net Margin %'], 
                name="Net Margin", 
                line=dict(color='#00CC96', width=4),
                mode='lines+markers'
            ))
            fig_margin.update_layout(
                template="plotly_dark", height=300,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(ticksuffix="%"), 
                xaxis=dict(type='category', title="Fiscal Year"),
                margin=dict(l=0, r=0, t=20, b=0)
            )
            st.plotly_chart(fig_margin, use_container_width=True)

        with col_right:
            st.markdown("""
<div class="ch-marker" style="margin-top:1.2rem;">
  <div class="ch-num">3</div>
  <div class="ch-text">
    <div class="ch-title">Capital Structure</div>
    <div class="ch-sub">How much debt is the company carrying vs. its own equity?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
            if df_bs is not None and not df_bs.empty:
                # Sort and Clean Balance Sheet Data
                df_bs_plot = df_bs.sort_index()
                df_bs_plot.index = pd.to_datetime(df_bs_plot.index).year
                
                equity_label = "Stockholders Equity"
                debt_label = "Total Debt"
                
                if equity_label in df_bs_plot.columns and debt_label in df_bs_plot.columns:
                    fig_cap = go.Figure()
                    fig_cap.add_trace(go.Bar(x=df_bs_plot.index, y=df_bs_plot[equity_label], name="Equity", marker_color='#00FFC8'))
                    fig_cap.add_trace(go.Bar(x=df_bs_plot.index, y=df_bs_plot[debt_label], name="Debt", marker_color='#FF4B4B'))
                    
                    fig_cap.update_layout(
                        template="plotly_dark", barmode='stack', height=300,
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(type='category', title="Fiscal Year"),
                        margin=dict(l=0, r=0, t=20, b=0),
                        legend=dict(orientation="h", y=-0.2)
                    )
                    st.plotly_chart(fig_cap, use_container_width=True)
                else:
                    st.info("Equity/Debt columns missing from Balance Sheet data.")
            else:
                st.info("Balance Sheet data (df_bs) not found for this ticker.")
                
                
                
    
    # ── TAB 3: PRICE FORECAST ─────────────────────────────────────────────────
    with tab_technicals:
        st.markdown(f"""
<div class="explore-path">
  <span class="ep-step active">🎲 Monte Carlo · 4 Horizons</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">📅 Prophet · Seasonality</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🧠 LSTM · 30-Day Target</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">⚖️ Model Comparison</span>
</div>
<div style="margin-bottom:.5rem">
  <div style="font-size:1.4rem;font-weight:800;color:var(--txt0);">Where Could {ticker} Go From Here?</div>
</div>
<div class="tab-intro">
  Three independent AI models — each answering a <strong>different question</strong> across a <strong>different time horizon</strong>.
  They will not always agree, and that disagreement is <strong>valuable signal, not an error</strong>.
  Read each model's description before comparing outputs — understanding the question is as important as the answer.
</div>
""", unsafe_allow_html=True)

        df_stock = st.session_state.get('temp_data', {}).get('df_stock')
        forecast_df = st.session_state.get('forecast_df')

        if df_stock is not None and not df_stock.empty:
            curr_price = float(df_stock['Close'].iloc[-1])



            if forecast_df is not None:
                with st.spinner("Running 1,000 simulations..."):
                    forecasts = get_adaptive_forecasts(df_stock)
                    try:
                        raw_date_val = df_stock['Date'].iloc[-1]
                    except Exception:
                        raw_date_val = df_stock.index[-1]
                    last_date_obj  = pd.to_datetime(raw_date_val)
                    future_dates   = pd.date_range(start=last_date_obj, periods=366, freq='B')

                st.markdown("""
<div class="ch-marker">
  <div class="ch-num">1</div>
  <div class="ch-text">
    <div class="ch-title">Monte Carlo Simulation — 4 Time Horizons</div>
    <div class="ch-sub">1,000 random price paths · statistical range of outcomes · 3, 6, 9 &amp; 12 months forward</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
                st.markdown("""
<div class="insight">
  <div class="insight-label">🎲 What This Model Answers</div>
  <div class="insight-text">
    <em>Where could this stock statistically end up, given how it has behaved in the past?</em><br>
    Runs 1,000 random price paths using the stock's historical drift and volatility. The Expected line is the median of all paths.
    The shaded band is the likely range (20th–80th percentile).
    <strong>Blind spot:</strong> Does not know about earnings, news, or valuations — only historical price behaviour.
  </div>
</div>
""", unsafe_allow_html=True)

                horizon_labels = [
                    ("3-Month Outlook",  0, "#00FFC8"),
                    ("6-Month Outlook",  1, "#FFD700"),
                    ("9-Month Outlook",  2, "#FFA500"),
                    ("12-Month Outlook", 3, "#FF4B4B"),
                ]
                col_row1_left, col_row1_right = st.columns(2)
                col_row2_left, col_row2_right = st.columns(2)
                cols = [col_row1_left, col_row1_right, col_row2_left, col_row2_right]

                for i, (label, idx, color) in enumerate(horizon_labels):
                    with cols[i]:
                        up, med, low = forecasts[idx]
                        days = len(up)
                        best  = float(up.iloc[-1])
                        mid   = float(med.iloc[-1])
                        worst = float(low.iloc[-1])

                        # plain-English verdict
                        mid_chg  = ((mid   - curr_price) / curr_price) * 100
                        best_chg = ((best  - curr_price) / curr_price) * 100
                        worst_chg= ((worst - curr_price) / curr_price) * 100

                        verdict_color = "#00FFC8" if mid_chg >= 3 else "#FFD700" if mid_chg >= -3 else "#FF4B4B"
                        verdict_text  = ("Likely to rise" if mid_chg >= 3
                                         else "Roughly flat" if mid_chg >= -3
                                         else "At risk of falling")

                        st.markdown(f"""
                        <div class="g-card" style="border-left:4px solid {color};animation-delay:{i*0.08:.2f}s;margin-bottom:.4rem;">
                            <b style="color:{color};">{label}</b><br>
                            <span style="color:{verdict_color}; font-size:14px; font-weight:bold;">{verdict_text}</span><br>
                            <span style="color:#c9d1d9; font-size:12px;">
                                Best case: <b style="color:#00FFC8;">${best:.2f} ({best_chg:+.1f}%)</b> |
                                Expected: <b style="color:#c9d1d9;">${mid:.2f} ({mid_chg:+.1f}%)</b> |
                                Worst case: <b style="color:#FF4B4B;">${worst:.2f} ({worst_chg:+.1f}%)</b>
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=future_dates[:days], y=up,  line=dict(width=0), showlegend=False))
                        fig.add_trace(go.Scatter(x=future_dates[:days], y=low, fill='tonexty',
                                                 fillcolor='rgba(255,255,255,0.07)', name='Range', showlegend=False))
                        fig.add_trace(go.Scatter(x=future_dates[:days], y=med, name='Expected Path',
                                                 line=dict(color=color, width=2)))
                        fig.add_hline(y=curr_price, line_dash="dot", line_color="#484f58",
                                      annotation_text=f"Today ${curr_price:.2f}", annotation_position="top left")
                        fig.update_layout(template="plotly_dark", height=220,
                                          margin=dict(l=0, r=0, t=5, b=0), showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Forecast will appear here after analysis completes.")

            # ── PROPHET: Seasonal Trend Analysis ─────────────────────────────
            st.divider()
            st.markdown("""
<div class="ch-marker">
  <div class="ch-num">2</div>
  <div class="ch-text">
    <div class="ch-title">Seasonal Trend Analysis — Prophet</div>
    <div class="ch-sub">Structural multi-year trend + calendar seasonality decomposition · 6-month forward projection</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
            st.markdown("""
<div class="insight">
  <div class="insight-label">📅 What This Model Answers</div>
  <div class="insight-text">
    <em>Is there a structural trend and a repeating calendar pattern in this stock's price?</em><br>
    Prophet decomposes price into trend, yearly seasonality, and weekly patterns — then projects 6 months forward.
    It finds <strong>repeating structure</strong>, not random paths.
    <strong>Key distinction:</strong> A Bear regime + Upward Prophet trend is not a contradiction — one is short-term noise, the other is long-term direction.
  </div>
</div>
""", unsafe_allow_html=True)

            with st.spinner("Running seasonal decomposition..."):
                prophet_result = get_prophet_forecast(df_stock, periods=180)

            if prophet_result.get('error'):
                st.info(f"Seasonal analysis: {prophet_result['error']}")
            else:
                pr = prophet_result
                pct_color = "#00FFC8" if pr['pct_change_6m'] >= 0 else "#FF4B4B"
                t_color   = "#00FFC8" if pr['trend_direction'] == "Upward" else \
                            "#FF4B4B" if pr['trend_direction'] == "Downward" else "#FFD700"

                # ── Summary metrics row ───────────────────────────────────────
                pm1, pm2, pm3, pm4 = st.columns(4)
                pm1.metric("Trend Direction",  pr['trend_direction'])
                pm2.metric("Trend Drift",      f"${abs(pr['trend_slope']):.2f}/month",
                           delta="Up" if pr['trend_direction']=="Upward" else
                                 ("Down" if pr['trend_direction']=="Downward" else "Flat"))
                pm3.metric("6M Forecast",      f"${pr['target_6m']:.2f}",
                           delta=f"{pr['pct_change_6m']:+.1f}%")
                pm4.metric("80% Range",        f"${pr['target_6m_low']:.0f} - ${pr['target_6m_high']:.0f}")

                # ── Plain-English explanation ─────────────────────────────────
                st.markdown(f"""
<div class="g-card" style="border-left:4px solid {t_color};">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:{t_color};margin-bottom:.4rem;">
    Prophet Interpretation
  </div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.7;">{pr['plain_english']}</div>
</div>
""", unsafe_allow_html=True)

                # ── Forecast chart ────────────────────────────────────────────
                st.plotly_chart(
                    build_prophet_forecast_chart(prophet_result),
                    use_container_width=True
                )

                # ── Historical Monthly Performance (raw data, all years) ──────
                st.markdown("#### When is this stock historically strongest?")
                st.caption(
                    "Computed directly from every month of actual price history since the stock's "
                    "earliest available data — no model, no smoothing. "
                    "Hover any bar to see how often (% of years) that month was positive."
                )

                avg_fig, raw_best, raw_worst, raw_summary = build_monthly_avg_chart(df_stock)

                sc1, sc2 = st.columns([2, 1])
                with sc1:
                    st.plotly_chart(avg_fig, use_container_width=True)
                with sc2:
                    best_str  = ", ".join(raw_best)
                    worst_str = ", ".join(raw_worst)
                    st.markdown(f"""
                    <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-top:8px;">
                        <p style="color:#c9d1d9; font-size:11px; margin:0 0 10px 0; text-transform:uppercase;">Seasonal Calendar</p>
                        <p style="color:#00FFC8; font-size:13px; margin:0 0 6px 0;">
                            <b>Best months to own:</b><br>{best_str}
                        </p>
                        <p style="color:#FF4B4B; font-size:13px; margin:0 0 12px 0;">
                            <b>Historically weakest:</b><br>{worst_str}
                        </p>
                        <p style="color:#c9d1d9; font-size:11px; margin:0; line-height:1.5;">
                            Based on actual returns — not model estimates. Each month's
                            rank reflects its average performance and how consistently
                            it was positive across all available years.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Weekly seasonality (from Prophet — only needs a few weeks of data)
                    with st.expander("Day-of-week patterns"):
                        for d in pr['weekly_seasonal']:
                            d_color = "#00FFC8" if d['avg_effect'] > 0.1 else \
                                      "#FF4B4B" if d['avg_effect'] < -0.1 else "#8b949e"
                            st.markdown(
                                f"<span style='color:{d_color};'><b>{d['day']}</b></span>"
                                f"<span style='color:#c9d1d9; font-size:12px;'>"
                                f" {d['avg_effect']:+.2f}%</span>",
                                unsafe_allow_html=True
                            )

            # ── LSTM: Deep Learning 30-Day Target ────────────────────────────
            st.divider()
            st.markdown("""
<div class="ch-marker">
  <div class="ch-num">3</div>
  <div class="ch-text">
    <div class="ch-title">Deep Learning Price Target — LSTM</div>
    <div class="ch-sub">Sequence pattern recognition · 30-day momentum signal · trained on last 40 days of price action</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
            st.markdown("""
<div class="insight">
  <div class="insight-label">🧠 What This Model Answers</div>
  <div class="insight-text">
    <em>What does the recent price momentum pattern suggest will happen in the next 30 days?</em><br>
    An LSTM neural network trained on 1 year of price sequences learned to recognize patterns like momentum builds,
    consolidation before moves, and mean-reversion after sharp drops.
    <strong>Blind spot:</strong> No concept of valuation or market environment — purely price-sequence pattern matching.
  </div>
</div>
""", unsafe_allow_html=True)

            with st.spinner("Training deep learning model... (~30–45 seconds)"):
                lstm_result = get_lstm_forecast(df_stock, forecast_days=30)

            if lstm_result.get('error'):
                st.info(f"LSTM forecast: {lstm_result['error']}")
            else:
                lr = lstm_result
                pct_color = "#00FFC8" if lr['pct_change_30d'] >= 0 else "#FF4B4B"

                # ── Summary metric row ────────────────────────────────────────
                lm1, lm2, lm3, lm4 = st.columns(4)
                lm1.metric("Today's Price",       f"${lr['last_price']:.2f}")
                lm2.metric("30-Day DL Target",    f"${lr['target_30d']:.2f}",
                           delta=f"{lr['pct_change_30d']:+.1f}%")
                lm3.metric("90% Range",
                           f"${lr['target_30d_low']:.2f} – ${lr['target_30d_high']:.2f}")
                lm4.metric("Model Train Loss",    f"{lr['train_loss']:.5f}")

                # ── Plain-English explanation ─────────────────────────────────
                st.markdown(f"""
<div class="g-card" style="border-left:4px solid #A78BFA;">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#A78BFA;margin-bottom:.4rem;">
    LSTM Interpretation
  </div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.7;">{lr['plain_english']}</div>
</div>
""", unsafe_allow_html=True)

                # ── LSTM forecast chart ───────────────────────────────────────
                st.plotly_chart(
                    build_lstm_chart(df_stock, lstm_result),
                    use_container_width=True
                )

                # ── Comparison card vs Monte Carlo & Prophet ──────────────────
                st.markdown("""
<div class="ch-marker" style="margin-top:1.5rem;">
  <div class="ch-num" style="background:linear-gradient(135deg,#f97316,#fbbf24);">⚖</div>
  <div class="ch-text">
    <div class="ch-title">Model Consensus Panel</div>
    <div class="ch-sub">See how all 3 forecasts compare — agreement strengthens conviction, disagreement reveals uncertainty</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
                mc_base = float(st.session_state.get('forecast_df', pd.DataFrame()).get(
                    'Base_Case', pd.Series([lr['last_price']])).iloc[-1]) \
                    if st.session_state.get('forecast_df') is not None else None

                comp_data = [
                    ("Monte Carlo (Base)",  mc_base,               "#FFD700",  "Randomness + volatility"),
                    ("Prophet (6M trend)",  prophet_result.get('target_6m') if 'prophet_result' in dir() and not prophet_result.get('error') else None, "#00FFC8",  "Trend + seasonality"),
                    ("LSTM Deep Learning",  lr['target_30d'],      "#A78BFA",  "Sequential pattern learning"),
                ]
                cc1, cc2, cc3 = st.columns(3)
                for col, (model_name, price, color, desc) in zip([cc1, cc2, cc3], comp_data):
                    if price is not None:
                        chg = ((price - lr['last_price']) / lr['last_price']) * 100
                        chg_color = "#00FFC8" if chg >= 0 else "#FF4B4B"
                        col.markdown(f"""
<div class="g-card" style="border-left:4px solid {color};text-align:center;">
  <div style="font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--txt2);margin-bottom:.3rem;">{model_name}</div>
  <div style="font-size:1.5rem;font-weight:800;color:{color};">${price:.2f}</div>
  <div style="font-size:.88rem;font-weight:700;color:{chg_color};">{chg:+.1f}%</div>
  <div style="font-size:.72rem;color:var(--txt2);margin-top:.3rem;">{desc}</div>
</div>""", unsafe_allow_html=True)

        else:
            st.info("Enter a ticker and click Run Analysis to see the forecast.")


    # ── TAB 4: AI DEEP DIVE ───────────────────────────────────────────────────
    with tab_aideepd:
        ticker    = st.session_state['ticker']
        category  = st.session_state['category']
        df_for_ml = st.session_state['temp_data']['df_stock']
        curr_p    = float(df_for_ml['Close'].iloc[-1])

        st.markdown(f"""
<div class="explore-path">
  <span class="ep-step active">🌡 Market Regime</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🚨 Anomaly Radar</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">📊 3 Scenarios</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🔍 Feature Importance</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">💰 Intrinsic Value</span>
</div>
<div style="margin-bottom:.5rem">
  <div style="font-size:1.4rem;font-weight:800;color:var(--txt0);">AI Deep Dive — {ticker}</div>
</div>
<div class="tab-intro">
  Five AI models, five different questions about the same stock.
  <strong>Disagreement between models is normal and informative</strong> — each is looking at a different dimension of risk and opportunity.
  Read each model's description before comparing outputs.
</div>
""", unsafe_allow_html=True)

        # ── SECTION 1: Market Regime (HMM) ───────────────────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">1</div>
  <div class="ch-text">
    <div class="ch-title">Market Regime — Hidden Markov Model</div>
    <div class="ch-sub">What mode is the market in right now? Bull · Sideways · Bear — and how long has it been there?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">🌡 What This Model Answers</div>
  <div class="insight-text">
    <em>What mode is the market in for this stock right now — trending up, down, or sideways?</em><br>
    An HMM trained on years of daily returns and volatility clusters behaviour into 3 states: Bull, Bear, and Sideways.
    <strong>Important:</strong> A Bear regime ≠ sell immediately. A Bear regime + strong fundamentals could be your best entry point — buying quality on sale.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Detecting market regime..."):
            regime_data = get_regime_analysis(df_for_ml)

        if regime_data.get('error'):
            st.info(f"Regime detection: {regime_data['error']}")
        else:
            reg        = regime_data['current_regime']
            reg_color  = regime_data['regime_color']
            reg_conf   = regime_data['confidence']
            reg_streak = regime_data['streak_days']
            reg_since  = regime_data['regime_since']

            rb1, rb2, rb3, rb4 = st.columns(4)
            live_dot_color = "green" if reg == "Bull" else "red" if reg == "Bear" else "gold"
            rb1.markdown(f"""
<div class="g-card" style="border:2px solid {reg_color};text-align:center;padding:1rem;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--txt2);margin-bottom:.4rem;">
    <span class="live-dot {live_dot_color}"></span>CURRENT REGIME
  </div>
  <div style="font-size:1.6rem;font-weight:800;color:{reg_color};">{reg}</div>
  <div style="font-size:.72rem;color:var(--txt2);margin-top:.25rem;">Live · updates every scan</div>
</div>""", unsafe_allow_html=True)
            rb2.metric("Regime Since",  reg_since)
            rb3.metric("Streak",        f"{reg_streak} trading days")
            rb4.metric("AI Confidence", f"{reg_conf*100:.0f}%")

            st.write("")
            st.markdown(f"""
<div class="g-card" style="border-left:4px solid {reg_color};">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{reg_color};margin-bottom:.4rem;">HMM Interpretation</div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.7;">{regime_data['plain_english']}</div>
</div>
""", unsafe_allow_html=True)

            st.caption("Price chart with regime background (green = Bull, red = Bear, yellow = Sideways):")
            st.plotly_chart(
                build_regime_chart(df_for_ml, regime_data['regime_series']),
                use_container_width=True
            )

            with st.expander("How often has this stock been in each regime?"):
                for s in regime_data['state_stats']:
                    pct   = s['pct_of_time']
                    bar_w = int(pct)
                    st.markdown(f"""
                    <div style="margin-bottom:10px;">
                        <span style="color:{s['color']}; font-weight:bold; font-size:13px;">{s['regime']}</span>
                        <span style="color:#c9d1d9; font-size:12px; margin-left:10px;">
                            {s['days']} days ({pct}% of time) &nbsp;|&nbsp;
                            Avg daily return: <b style="color:{s['color']};">{s['avg_return']:+.3f}%</b> &nbsp;|&nbsp;
                            Avg daily vol: {s['avg_vol']:.3f}%
                        </span>
                        <div style="background:#21262d; border-radius:4px; height:8px; margin-top:4px;">
                            <div style="background:{s['color']}; border-radius:4px; height:8px; width:{bar_w}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.divider()

        # ── SECTION 2: Risk Radar (Isolation Forest) ──────────────────────────
        st.divider()
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">2</div>
  <div class="ch-text">
    <div class="ch-title">Anomaly Radar — Isolation Forest</div>
    <div class="ch-sub">Is today's trading behaviour statistically unusual compared to this stock's own history?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">🚨 What This Model Answers</div>
  <div class="insight-text">
    <em>Is today's price and volume activity statistically abnormal compared to this stock's own history?</em><br>
    Isolation Forest trained on 4 years of data learned what "normal" looks like for this specific stock — and flags any day where the combination of price move + volume is an outlier.
    <strong>Important:</strong> An anomaly flag is not automatically bearish — it could be earnings, insider buying, or a short squeeze. Check the news first.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Scanning for anomalies..."):
            risk_data = detect_anomalies(df_for_ml, ticker)
            risk_msg  = risk_data['risk_message']

        if risk_data['is_anomaly']:
            st.markdown(f"""
<div class="g-card pulse-danger" style="background:rgba(239,68,68,.08);border-color:#ef4444;">
  <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;">
    <span class="live-dot red"></span>
    <span style="font-size:1.1rem;font-weight:800;color:#ef4444;">Unusual Activity Detected</span>
  </div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.65;">
    The AI has flagged <strong>{ticker}</strong>'s current trading as <strong>statistically unusual</strong> compared to its normal behaviour.
    This is not necessarily bad — it could be earnings news, insider buying, or heightened volatility.
    <strong>Recommended action: check the news before making a decision.</strong>
  </div>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
<div class="g-card pulse-safe" style="background:rgba(0,255,200,.04);border-color:rgba(0,255,200,.35);">
  <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;">
    <span class="live-dot green"></span>
    <span style="font-size:1.1rem;font-weight:800;color:#00ffc8;">Normal Trading Conditions</span>
  </div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.65;">
    {ticker}'s current price and volume activity is <strong>within normal statistical range</strong> for this stock.
    No unusual market activity has been detected.
  </div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ── SECTION 3: Scenario Forecast (3 possible futures) ────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">3</div>
  <div class="ch-text">
    <div class="ch-title">3 Possible Futures — Scenario Engine</div>
    <div class="ch-sub">Deterministic Bear / Base / Bull scenarios under different growth assumptions · 12-month horizon</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">📊 What This Model Answers</div>
  <div class="insight-text">
    <em>What is a realistic range of outcomes under different growth assumptions?</em><br>
    Uses three fixed growth scenarios (10/12/15% annual targets) to show where price lands if the stock behaves consistently with each.
    <strong>Unlike Monte Carlo</strong> (randomness), these are deterministic — useful for stress-testing: "am I comfortable with the bear case?"
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Running scenario engine..."):
            forecast_df = get_scenario_results(df_for_ml)

        if forecast_df is not None and not forecast_df.empty:
            bull_p = float(forecast_df['Bull_Case'].iloc[-1])
            base_p = float(forecast_df['Base_Case'].iloc[-1])
            bear_p = float(forecast_df['Bear_Case'].iloc[-1])

            bull_chg = ((bull_p - curr_p) / curr_p) * 100
            base_chg = ((base_p - curr_p) / curr_p) * 100
            bear_chg = ((bear_p - curr_p) / curr_p) * 100

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(f"""
<div class="g-card g-card-accent" style="text-align:center;animation-delay:0s;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--txt2);margin-bottom:.4rem;">BEST CASE · Bull</div>
  <div style="font-size:1.7rem;font-weight:800;color:#00FFC8;">${bull_p:.2f}</div>
  <div style="font-size:1rem;font-weight:700;color:#00FFC8;">{bull_chg:+.1f}%</div>
  <div style="font-size:.75rem;color:var(--txt2);margin-top:.4rem;">Growth accelerates · market stays positive</div>
</div>""", unsafe_allow_html=True)
            with sc2:
                st.markdown(f"""
<div class="g-card g-card-warn" style="text-align:center;animation-delay:0.08s;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--txt2);margin-bottom:.4rem;">MOST LIKELY · Base</div>
  <div style="font-size:1.7rem;font-weight:800;color:#FFD700;">${base_p:.2f}</div>
  <div style="font-size:1rem;font-weight:700;color:#FFD700;">{base_chg:+.1f}%</div>
  <div style="font-size:.75rem;color:var(--txt2);margin-top:.4rem;">Historical trends continue as expected</div>
</div>""", unsafe_allow_html=True)
            with sc3:
                st.markdown(f"""
<div class="g-card g-card-danger" style="text-align:center;animation-delay:0.16s;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--txt2);margin-bottom:.4rem;">WORST CASE · Bear</div>
  <div style="font-size:1.7rem;font-weight:800;color:#FF4B4B;">${bear_p:.2f}</div>
  <div style="font-size:1rem;font-weight:700;color:#FF4B4B;">{bear_chg:+.1f}%</div>
  <div style="font-size:.75rem;color:var(--txt2);margin-top:.4rem;">Growth slows or market conditions deteriorate</div>
</div>""", unsafe_allow_html=True)

            st.plotly_chart(plot_forecast_chart(forecast_df), use_container_width=True)

        st.divider()

        # ── SECTION 4: Feature Importance ────────────────────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">4</div>
  <div class="ch-text">
    <div class="ch-title">What the AI Is Paying Attention To — XGBoost</div>
    <div class="ch-sub">Which KPIs drove the confidence prediction? Understand the reasoning, not just the verdict.</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">🔍 What This Model Answers</div>
  <div class="insight-text">
    <em>Which financial and technical signals had the most influence on the AI's confidence prediction?</em><br>
    XGBoost learned: "when a stock has these KPI characteristics, how often did it hit a +10/12/15% return?"
    The chart shows the top drivers — if "Debt Level" ranks highest, solvency is what's making or breaking the prediction.
    <strong>This is the AI showing its work.</strong>
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("AI model thinking..."):
            try:
                conf_bull, trained_model = run_ai_signal_analysis(ticker, category, df_for_ml, target_return=0.15)
                conf_base, _             = run_ai_signal_analysis(ticker, category, df_for_ml, target_return=0.12)
                conf_bear, _             = run_ai_signal_analysis(ticker, category, df_for_ml, target_return=0.10)
                ai_ok = True
            except Exception as e:
                st.warning(f"AI confidence model needs more data: {e}")
                ai_ok = False

        if ai_ok:
            kpi_names = ['efficiency', 'margin', 'rev_growth', 'solvency', 'valuation',
                         'peg_ratio', 'roce', 'roic',
                         'rsi', 'above_sma200', 'golden_cross', 'dist_52w_high']
            importance_data = get_feature_importance_data(trained_model, kpi_names)

            KPI_FRIENDLY = {
                'efficiency':    'Profitability (ROE/ROA)',
                'margin':        'Profit Margin',
                'rev_growth':    'Revenue Growth',
                'solvency':      'Debt Level',
                'valuation':     'Stock Valuation (P/E)',
                'peg_ratio':     'Growth-Adjusted Value',
                'roce':          'Return on Capital (ROCE)',
                'roic':          'Return on Investment (ROIC)',
                'rsi':           'Momentum (RSI)',
                'above_sma200':  'Long-Term Trend',
                'golden_cross':  'Short-Term Trend Signal',
                'dist_52w_high': 'Distance from Peak',
            }

            if importance_data:
                top5 = dict(list(importance_data.items())[:5])
                friendly_labels = [KPI_FRIENDLY.get(k, k) for k in top5.keys()]
                fig_imp = go.Figure(go.Bar(
                    x=list(top5.values()), y=friendly_labels,
                    orientation='h', marker_color='#00FFC8',
                    text=[f"{v:.0f}" for v in top5.values()], textposition='outside',
                ))
                fig_imp.update_layout(
                    template="plotly_dark", height=280,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="AI Attention Score",
                    yaxis={'categoryorder': 'total ascending'},
                    margin=dict(l=10, r=40, t=10, b=30),
                )
                st.plotly_chart(fig_imp, use_container_width=True)
        else:
            ai_ok = False

        st.divider()

        # ── SECTION 5: Revenue-Based Intrinsic Value Calculator ───────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">5</div>
  <div class="ch-text">
    <div class="ch-title">Intrinsic Value Calculator — Build Your Own Thesis</div>
    <div class="ch-sub">Adjust growth, discount rate, and exit multiple — see what this stock is worth on YOUR assumptions</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">💰 Your Assumptions, Your Price</div>
  <div class="insight-text">
    Adjust the four sliders below and see what the stock is worth <strong>based on your view of the future</strong> — not the AI's.
    As Warren Buffett says: <em>"It's better to be approximately right than precisely wrong."</em>
    The sensitivity table shows how your price target changes across different assumption combinations.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Fetching valuation inputs..."):
            vi = get_revenue_valuation_inputs(
                ticker,
                df_isq=st.session_state['temp_data'].get('df_isq'),
            )

        if vi.get('error'):
            st.warning(f"Could not load valuation data: {vi['error']}")
        else:
            # ── Context row ───────────────────────────────────────────────────
            ci1, ci2, ci3, ci4 = st.columns(4)
            ci1.metric("TTM Revenue",        f"${vi['ttm_revenue_bn']:.2f}B")
            ci2.metric("Shares Outstanding", f"{vi['shares_bn']:.2f}B")
            ci3.metric("Current Price",      f"${vi['current_price']:.2f}")
            ci4.metric("Current P/S",        f"{vi['current_ps']:.1f}x" if vi['current_ps'] else "N/A")

            st.markdown(
                f"<p style='color:#c9d1d9; font-size:12px; margin:4px 0 12px 0;'>"
                f"Sector: <b style='color:#c9d1d9;'>{vi['sector']}</b> — "
                f"defaults below are calibrated for this sector. Adjust them to reflect your own view.</p>",
                unsafe_allow_html=True
            )

            # ── Sliders ───────────────────────────────────────────────────────
            sl1, sl2 = st.columns(2)
            with sl1:
                growth_rate = st.slider(
                    "Annual Revenue Growth Rate (%)",
                    min_value=1, max_value=35,
                    value=int(vi['suggested_growth'] * 100),
                    step=1,
                    help="How fast do you expect the company's revenue to grow per year for the next 5 years?",
                    key="rv_growth"
                ) / 100

                discount_rate = st.slider(
                    "Required Annual Return (Discount Rate) (%)",
                    min_value=5, max_value=20,
                    value=10, step=1,
                    help="The annual return you need from this investment. 10% is common (market average ~7% + risk premium).",
                    key="rv_discount"
                ) / 100

            with sl2:
                terminal_ps = st.slider(
                    "Terminal P/S Multiple (exit valuation)",
                    min_value=1.0, max_value=20.0,
                    value=float(vi['suggested_ps']),
                    step=0.5,
                    help="The price-to-sales ratio you expect the stock to trade at in year 5. Use a conservative number — companies rarely maintain today's premium.",
                    key="rv_ps"
                )

                margin_of_safety = st.slider(
                    "Margin of Safety (%)",
                    min_value=0, max_value=50,
                    value=30, step=5,
                    help="A buffer below intrinsic value to protect you if your assumptions are wrong. Buffett typically uses 25–50%.",
                    key="rv_mos"
                ) / 100

            # ── Run calculation ───────────────────────────────────────────────
            result = calculate_revenue_intrinsic_value(
                ttm_revenue_bn   = vi['ttm_revenue_bn'],
                shares_bn        = vi['shares_bn'],
                current_price    = vi['current_price'],
                growth_rate      = growth_rate,
                terminal_ps      = terminal_ps,
                discount_rate    = discount_rate,
                margin_of_safety = margin_of_safety,
            )

            # ── Revenue projection table ──────────────────────────────────────
            st.markdown("#### Step-by-Step Revenue Projection")
            proj_cols = st.columns(5)
            for i, row in enumerate(result['year_projections']):
                proj_cols[i].markdown(f"""
                <div style="background:#161b22; border:1px solid #30363d; border-radius:8px;
                            padding:12px; text-align:center;">
                    <p style="color:#c9d1d9; font-size:11px; margin:0;">{row['year']}</p>
                    <p style="color:#c9d1d9; font-size:15px; font-weight:bold; margin:4px 0 0 0;">
                        ${row['revenue_bn']:.2f}B
                    </p>
                </div>""", unsafe_allow_html=True)

            st.markdown(
                f"<p style='color:#c9d1d9; font-size:12px; margin:8px 0 16px 0;'>"
                f"Year 5 revenue of <b style='color:#c9d1d9;'>${result['year5_revenue_bn']:.2f}B</b> "
                f"× {terminal_ps:.1f}x P/S = "
                f"<b style='color:#c9d1d9;'>${result['future_market_cap_bn']:.2f}B</b> future market cap → "
                f"<b style='color:#c9d1d9;'>${result['future_price']:.2f}</b> per share in year 5</p>",
                unsafe_allow_html=True
            )

            # ── Key results row ───────────────────────────────────────────────
            rv1, rv2, rv3, rv4 = st.columns(4)
            rv1.metric("Future Price (Year 5)",  f"${result['future_price']:.2f}")
            rv2.metric("Intrinsic Value Today",  f"${result['present_value']:.2f}",
                       delta=f"{result['upside_to_pv_pct']:+.1f}% vs market")
            rv3.metric("Fair Buy Price",         f"${result['fair_buy_price']:.2f}",
                       delta=f"{result['upside_to_fbp_pct']:+.1f}% vs market")
            rv4.metric("Implied Return (if bought today)", f"{result['implied_return_pct']:+.1f}% / yr")

            # ── Verdict card ──────────────────────────────────────────────────
            vc = result['verdict_color']
            st.markdown(f"""
<div class="g-card" style="border:2px solid {vc};margin:12px 0;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:{vc};margin-bottom:.5rem;">
    Valuation Verdict
  </div>
  <div style="font-size:1.2rem;font-weight:800;color:{vc};margin-bottom:.4rem;">{result['verdict']}</div>
  <div style="font-size:.9rem;color:var(--txt0);line-height:1.65;">{result['verdict_desc']}</div>
</div>""", unsafe_allow_html=True)

            # ── Sensitivity table ─────────────────────────────────────────────
            with st.expander("Sensitivity analysis — how much do assumptions matter?"):
                st.caption(
                    "Each cell shows the **fair buy price** under that combination of growth rate "
                    "and terminal P/S. Green = current price is already in buy zone. "
                    "Red = still overvalued even under that scenario."
                )
                sens_df = build_sensitivity_table(
                    vi['ttm_revenue_bn'], vi['shares_bn'], vi['current_price'],
                    growth_rate, terminal_ps, discount_rate, margin_of_safety,
                )

                def color_cell(val):
                    try:
                        v = float(val)
                        if vi['current_price'] <= v:
                            return 'background-color:#0a2a1a; color:#00FFC8; font-weight:bold'
                        elif vi['current_price'] <= v * 1.2:
                            return 'background-color:#2a2a0a; color:#FFD700'
                        else:
                            return 'background-color:#2a0a0a; color:#FF4B4B'
                    except Exception:
                        return ''

                styled = sens_df.style.format("${:.2f}").applymap(color_cell)
                st.dataframe(styled, use_container_width=True)

                st.markdown(
                    "<p style='color:#c9d1d9; font-size:11px; margin:6px 0 0 0;'>"
                    f"Discount rate: {discount_rate*100:.0f}% | "
                    f"Margin of safety: {margin_of_safety*100:.0f}% | "
                    f"Projection: 5 years</p>",
                    unsafe_allow_html=True
                )

            # ── Plain-English walkthrough ─────────────────────────────────────
            with st.expander("Show me how this was calculated (step by step)"):
                st.markdown(f"""
**Starting point:** TTM Revenue = **${vi['ttm_revenue_bn']:.2f}B** | Shares = **{vi['shares_bn']:.3f}B** | Price today = **${vi['current_price']:.2f}**

**Your assumptions:** {growth_rate*100:.0f}% annual growth | {terminal_ps:.1f}x terminal P/S | {discount_rate*100:.0f}% required return | {margin_of_safety*100:.0f}% margin of safety

**Step 1 — Project revenue 5 years forward at {growth_rate*100:.0f}%/yr:**
""")
                for row in result['year_projections']:
                    st.markdown(f"- {row['year']}: **${row['revenue_bn']:.3f}B**")

                st.markdown(f"""
**Step 2 — Apply terminal P/S multiple:**
${result['year5_revenue_bn']:.3f}B × {terminal_ps:.1f}x = **${result['future_market_cap_bn']:.2f}B** future market cap

**Step 3 — Divide by shares outstanding:**
${result['future_market_cap_bn']:.2f}B ÷ {vi['shares_bn']:.3f}B shares = **${result['future_price']:.2f} per share** in year 5

**Step 4 — Discount back to today at {discount_rate*100:.0f}%/yr:**
${result['future_price']:.2f} ÷ (1.{discount_rate*100:.0f})⁵ = **${result['present_value']:.2f}** intrinsic value

**Step 5 — Apply {margin_of_safety*100:.0f}% margin of safety:**
${result['present_value']:.2f} × (1 − {margin_of_safety:.2f}) = **${result['fair_buy_price']:.2f}** fair buy price

> **Conclusion:** {'✅ The stock is trading below your fair buy price — looks attractive at current price.' if vi['current_price'] <= result['fair_buy_price'] else f'⚠️ The stock needs to drop to ${result["fair_buy_price"]:.2f} to enter your buy zone.' }
""")


    # ── TAB 5: AI VERDICT (last tab) ─────────────────────────────────────────
    with tab_aiverdict:
        ticker    = st.session_state['ticker']
        category  = st.session_state['category']
        df_for_ml = st.session_state['temp_data']['df_stock']
        df_isy    = st.session_state['temp_data']['df_isy']
        df_bs     = st.session_state['temp_data'].get('df_bs')
        curr_p    = float(df_for_ml['Close'].iloc[-1])

        st.markdown(f"""
<div class="explore-path">
  <span class="ep-step active">💰 Fair Value</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">📰 News Pulse</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">🎯 AI Confidence</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">⚡ Final Verdict</span>
  <span class="ep-arrow">›</span>
  <span class="ep-step">💬 Ask the AI</span>
</div>
<div style="margin-bottom:.5rem">
  <div style="font-size:1.4rem;font-weight:800;color:var(--txt0);">AI Verdict — {ticker}</div>
</div>
<div class="tab-intro">
  Four signals. Four different questions. Read them <strong>in order</strong> — together they tell a story no single signal can.
  When they disagree, that disagreement is <strong>information, not an error</strong>.
  A stock with great fundamentals, negative news, and moderate odds is telling you something specific about timing.
</div>
""", unsafe_allow_html=True)

        # ── SECTION 1: Fair Value ─────────────────────────────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">1</div>
  <div class="ch-text">
    <div class="ch-title">Fair Value — Random Forest Valuation</div>
    <div class="ch-sub">Is this stock cheap or expensive based on its financial track record? Independent of market sentiment.</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">💰 What This Model Answers</div>
  <div class="insight-text">
    <em>What should this stock be trading at, based purely on its financial history?</em><br>
    The AI looks at 4 years of earnings, revenue, and growth to estimate an intrinsic value — independent of what the market says.
    <strong>Can disagree with Price Forecast:</strong> fundamentally undervalued + short-term downtrend is not a contradiction — it's a timing signal.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Calculating fair value..."):
            try:
                df_funda_val = get_valuation_data(ticker)
                if not df_funda_val.empty:
                    fair_value = calculate_fair_value(df_funda_val, df_for_ml)
                    price_diff = ((fair_value - curr_p) / curr_p) * 100

                    fv1, fv2, fv3 = st.columns(3)
                    fv1.metric("Today's Price",  f"${curr_p:.2f}")
                    fv2.metric("AI Fair Value",  f"${fair_value:.2f}", f"{price_diff:+.1f}% vs market")
                    gap_label = "Undervalued" if price_diff > 10 else "Overvalued" if price_diff < -10 else "Fairly Priced"
                    fv3.metric("Verdict", gap_label)

                    if price_diff > 10:
                        st.success(f"The AI thinks {ticker} is **undervalued by {price_diff:.1f}%**. "
                                   f"Based on its financial history, it should be worth around ${fair_value:.2f}. "
                                   f"This could be a buying opportunity.")
                    elif price_diff < -10:
                        st.warning(f"The AI thinks {ticker} is **overvalued by {abs(price_diff):.1f}%**. "
                                   f"The current price of ${curr_p:.2f} is above what the fundamentals suggest. "
                                   f"Consider waiting for a pullback.")
                    else:
                        st.info(f"{ticker} appears **fairly priced** — the market price is close to what the AI "
                                f"would expect given the company's financials.")
                else:
                    st.warning("Not enough financial history to calculate fair value for this ticker.")
                    fair_value = None
            except Exception as e:
                st.error(f"Fair value calculation failed: {e}")
                fair_value = None

        st.divider()

        # ── SECTION 2: News Pulse (FinBERT Sentiment) ────────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">2</div>
  <div class="ch-text">
    <div class="ch-title">News Pulse — FinBERT Sentiment Engine</div>
    <div class="ch-sub">What is the market hearing right now? Real-time narrative analysis across recent headlines.</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">📰 What This Model Answers</div>
  <div class="insight-text">
    <em>What narrative is the market forming about this company right now?</em><br>
    FinBERT (trained on Wall Street reports) reads the latest headlines and scores each Positive / Negative / Neutral —
    catching narrative shifts that price charts can't see.
    <strong>Real-time horizon:</strong> last 24–72 hours. A stock can have strong fundamentals and negative news simultaneously — both are valid, different timeframe signals.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Reading the news..."):
            sentiment_result = get_sentiment_analysis(ticker)

        if sentiment_result.get('error') and sentiment_result['headline_count'] == 0:
            st.info(f"No recent news found for {ticker}.")
        else:
            s_label = sentiment_result['overall_label']
            s_pct   = sentiment_result['sentiment_pct']
            s_net   = sentiment_result['overall_score']
            s_count = sentiment_result['headline_count']
            s_color = "#00FFC8" if s_label == "Positive" else "#FF4B4B" if s_label == "Negative" else "#FFD700"

            sg1, sg2 = st.columns([1, 2])
            with sg1:
                fig_sent = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=s_pct,
                    number={'suffix': '', 'font': {'size': 32, 'color': s_color}, 'valueformat': '.0f'},
                    delta={'reference': 50, 'relative': False,
                           'increasing': {'color': '#00FFC8'}, 'decreasing': {'color': '#FF4B4B'}},
                    title={'text': f"News Sentiment<br><span style='font-size:14px;color:{s_color}'>{s_label}</span>",
                           'font': {'color': '#c9d1d9'}},
                    gauge={
                        'axis': {'range': [0, 100], 'tickvals': [0, 25, 50, 75, 100],
                                 'ticktext': ['Very\nNeg', 'Neg', 'Neutral', 'Pos', 'Very\nPos']},
                        'bar': {'color': s_color},
                        'steps': [
                            {'range': [0,  25], 'color': '#1f1215'},
                            {'range': [25, 45], 'color': '#1a1a1a'},
                            {'range': [45, 55], 'color': '#1a1a1a'},
                            {'range': [55, 75], 'color': '#121f15'},
                            {'range': [75,100], 'color': '#0a1f12'},
                        ],
                        'threshold': {'line': {'color': '#ffffff', 'width': 2}, 'value': 50},
                    },
                    domain={'x': [0, 1], 'y': [0, 1]}
                ))
                fig_sent.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=0),
                                       template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sent, use_container_width=True, config={'displayModeBar': False})

            with sg2:
                plain = sentiment_to_plain_english(sentiment_result)
                st.markdown(f"""
                <div style="background:#161b22; border:1px solid #30363d; border-left:5px solid {s_color};
                            border-radius:8px; padding:16px; margin-bottom:12px;">
                    <p style="color:#c9d1d9; font-size:11px; margin:0 0 6px 0; text-transform:uppercase;">
                        AI Sentiment Summary — {s_count} headlines analysed
                    </p>
                    <p style="color:#e6edf3; font-size:14px; line-height:1.6; margin:0;">{plain}</p>
                    <p style="color:#9aaec8; font-size:11px; margin:8px 0 0 0;">
                        Net score: <b style="color:{s_color};">{s_net:+.3f}</b>
                        &nbsp;|&nbsp; Positive: {sentiment_result['avg_positive']*100:.0f}%
                        &nbsp;|&nbsp; Negative: {sentiment_result['avg_negative']*100:.0f}%
                        &nbsp;|&nbsp; Neutral: {sentiment_result['avg_neutral']*100:.0f}%
                    </p>
                </div>
                """, unsafe_allow_html=True)

            with st.expander(f"See all {s_count} scored headlines"):
                for h in sentiment_result['headlines']:
                    h_color = "#00FFC8" if h['label'] == "Positive" else "#FF4B4B" if h['label'] == "Negative" else "#8b949e"
                    age_str = f"{h['age_hours']:.0f}h ago" if h['age_hours'] < 48 else f"{h['age_hours']/24:.0f}d ago"
                    st.markdown(f"""
                    <div style="border-bottom:1px solid #21262d; padding:8px 0; display:flex; align-items:center; gap:10px;">
                        <span style="color:{h_color}; font-weight:bold; min-width:70px; font-size:12px;">{h['label']} {h['score']*100:.0f}%</span>
                        <span style="color:#c9d1d9; font-size:13px;">{h['title']}</span>
                        <span style="color:#9aaec8; font-size:11px; margin-left:auto;">{age_str}</span>
                    </div>
                    """, unsafe_allow_html=True)

        st.divider()

        # ── SECTION 3: AI Confidence (XGBoost gauges) ────────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">3</div>
  <div class="ch-text">
    <div class="ch-title">AI Confidence Gauges — XGBoost Pattern Matching</div>
    <div class="ch-sub">Based on similar historical KPI patterns — what % of the time did comparable stocks hit their return targets?</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="insight">
  <div class="insight-label">🎯 What This Model Answers</div>
  <div class="insight-text">
    <em>Based on stocks with similar KPI patterns — what are the odds this one hits its return targets?</em><br>
    XGBoost was trained on years of data to answer: "when a stock has this profile, how often did it return 10/12/15%?"
    It's <strong>historical pattern-matching, not prediction</strong>.
    Ignores today's news entirely — pairs with FinBERT Sentiment for the complete picture.
  </div>
</div>
""", unsafe_allow_html=True)

        # ai_ok / trained_model / conf_* computed in tab_aideepd (runs before this tab)
        _ai_ok = 'ai_ok' in dir() and ai_ok
        if _ai_ok:
            g1, g2, g3 = st.columns(3)
            gauge_configs = [
                (g1, conf_bull, "+15% Return", "Best Case Target"),
                (g2, conf_base, "+12% Return", "Most Likely Target"),
                (g3, conf_bear, "+10% Return", "Conservative Target"),
            ]
            for col, score, target, subtitle in gauge_configs:
                with col:
                    if score >= 65:
                        verdict = "High confidence"
                        v_color = "#00FFC8"
                    elif score >= 40:
                        verdict = "Moderate odds"
                        v_color = "#FFD700"
                    else:
                        verdict = "Low probability"
                        v_color = "#FF4B4B"

                    fig_g = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=score,
                        number={'suffix': '%', 'font': {'size': 30, 'color': v_color}, 'valueformat': '.0f'},
                        gauge={
                            'axis': {'range': [0, 100], 'tickwidth': 1},
                            'bar': {'color': v_color},
                            'steps': [
                                {'range': [0, 40],  'color': '#1a1f2e'},
                                {'range': [40, 65], 'color': '#1e2a1e'},
                                {'range': [65, 100], 'color': '#1a2a1a'},
                            ],
                        },
                        domain={'x': [0, 1], 'y': [0, 1]}
                    ))
                    fig_g.update_layout(height=180, margin=dict(l=10, r=10, t=10, b=0),
                                        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
                    st.markdown(f"""
                    <div style="text-align:center; margin-top:-10px;">
                        <b style="color:white;">{target}</b><br>
                        <span style="color:{v_color}; font-size:13px;">{verdict}</span><br>
                        <span style="color:#9aaec8; font-size:11px;">{subtitle}</span>
                    </div>""", unsafe_allow_html=True)
        else:
            st.info("Visit the **AI Deep Dive** tab first so the AI model runs, then return here for the full verdict.")

        st.divider()

        # ── SECTION 4: Ensemble Consensus Score + Chatbot ────────────────────
        st.markdown("""
<div class="ch-marker">
  <div class="ch-num">4</div>
  <div class="ch-text">
    <div class="ch-title">Final Verdict — Ensemble Consensus</div>
    <div class="ch-sub">All signals combined with calibrated weights · a moderate score means signals are genuinely mixed</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)

        # ── Signal consensus panel (pre-ensemble summary) ─────────────────────
        def _sig_row(icon, name, label, color, score_pct, delay):
            bar_w = int(score_pct)
            return f"""
<div class="sig-row anim-fadein" style="animation-delay:{delay:.2f}s;">
  <span class="sig-icon">{icon}</span>
  <span class="sig-name">{name}</span>
  <div class="sig-bar-bg"><div class="sig-bar-fill" style="width:{bar_w}%;background:{color};"></div></div>
  <span class="sig-pct" style="color:{color};">{score_pct:.0f}%</span>
  <span class="sig-badge" style="background:rgba(0,0,0,0.3);color:{color};border:1px solid {color}33;">{label}</span>
</div>"""

        # Build consensus rows from available data
        sig_rows_html = ""
        # KPI score (scale to 0-100)
        kpi_pct = min((total_score / 12) * 100, 100)
        kpi_color = "#00ffc8" if kpi_pct >= 70 else "#fbbf24" if kpi_pct >= 42 else "#ef4444"
        kpi_label = "Strong" if kpi_pct >= 70 else "Moderate" if kpi_pct >= 42 else "Weak"
        sig_rows_html += _sig_row("📊", f"KPI Quality Score — {total_score}/12", kpi_label, kpi_color, kpi_pct, 0.0)

        if 'regime_data' in dir() and not regime_data.get('error'):
            r_label = regime_data.get('current_regime', 'Sideways')
            r_color = regime_data.get('regime_color', '#fbbf24')
            r_pct   = {"Bull": 80, "Bear": 20, "Sideways": 50}.get(r_label, 50)
            sig_rows_html += _sig_row("🌡", f"Market Regime — {r_label} ({regime_data.get('streak_days',0)} days)", r_label, r_color, r_pct, 0.06)

        if 'prophet_result' in dir() and not prophet_result.get('error'):
            p_label = prophet_result.get('trend_direction', 'Flat')
            p_color = "#00ffc8" if p_label == "Upward" else "#ef4444" if p_label == "Downward" else "#fbbf24"
            p_pct   = {"Upward": 75, "Downward": 25, "Flat": 50}.get(p_label, 50)
            sig_rows_html += _sig_row("📅", f"Seasonal Trend — {p_label} (Prophet 6M)", p_label, p_color, p_pct, 0.12)

        if 'sentiment_result' in dir() and not sentiment_result.get('error'):
            s_pct_val = sentiment_result.get('sentiment_pct', 50)
            s_label_val = sentiment_result.get('overall_label', 'Neutral')
            s_color_val = "#00ffc8" if s_label_val == "Positive" else "#ef4444" if s_label_val == "Negative" else "#fbbf24"
            sig_rows_html += _sig_row("📰", f"News Sentiment — {s_label_val} ({sentiment_result.get('headline_count',0)} headlines)", s_label_val, s_color_val, s_pct_val, 0.18)

        if _ai_ok:
            xgb_color = "#00ffc8" if conf_base >= 65 else "#fbbf24" if conf_base >= 40 else "#ef4444"
            xgb_label = "High Confidence" if conf_base >= 65 else "Moderate" if conf_base >= 40 else "Low Probability"
            sig_rows_html += _sig_row("🎯", f"XGBoost Pattern Match — +12% target probability", xgb_label, xgb_color, conf_base, 0.24)

        if 'risk_data' in dir():
            anom_label = "Anomaly Detected" if risk_data.get('is_anomaly') else "Normal Activity"
            anom_color = "#ef4444" if risk_data.get('is_anomaly') else "#00ffc8"
            anom_pct   = 30 if risk_data.get('is_anomaly') else 75
            sig_rows_html += _sig_row("🚨", f"Anomaly Radar — {anom_label}", anom_label, anom_color, anom_pct, 0.30)

        st.markdown(f"""
<div style="margin-bottom:1.4rem;">
  <div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--txt2);margin-bottom:.7rem;">
    Signal Consensus — All Models at a Glance
  </div>
  {sig_rows_html}
</div>
""", unsafe_allow_html=True)

        st.markdown("""
<div class="insight" style="margin-bottom:1.2rem;">
  <div class="insight-label">⚡ What The Ensemble Does</div>
  <div class="insight-text">
    Combines every signal above with calibrated weights into one final score.
    <strong>A moderate score (40–60%) is not indecision</strong> — it means the signals are genuinely mixed, which is itself valuable information.
    When models disagree, the ensemble gives you the honest answer.
  </div>
</div>
""", unsafe_allow_html=True)

        ensemble = compute_ensemble_score(
            total_kpi_score     = total_score,
            xgb_confidence      = conf_base if _ai_ok else None,
            regime_label        = regime_data.get('current_regime', 'Sideways') if 'regime_data' in dir() else 'Sideways',
            prophet_trend       = prophet_result.get('trend_direction', 'Flat') if 'prophet_result' in dir() else 'Flat',
            sentiment_pct       = sentiment_result.get('sentiment_pct', 50) if 'sentiment_result' in dir() else None,
            is_anomaly          = risk_data.get('is_anomaly', False) if 'risk_data' in dir() else False,
            xgb_available       = _ai_ok,
            sentiment_available = 'sentiment_result' in dir() and not sentiment_result.get('error'),
            prophet_available   = 'prophet_result' in dir() and not prophet_result.get('error'),
        )
        st.session_state['ensemble'] = ensemble

        e_score = ensemble['score']
        e_color = ensemble['color']
        e_label = ensemble['label']

        ec1, ec2 = st.columns([1, 2])
        with ec1:
            fig_ens = go.Figure(go.Indicator(
                mode="gauge+number",
                value=e_score,
                number={'font': {'size': 44, 'color': e_color}, 'valueformat': '.0f'},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1,
                             'tickvals': [0,25,42,58,75,100],
                             'ticktext': ['0','Avoid','Wait','Watch','Buy','100']},
                    'bar': {'color': e_color, 'thickness': 0.25},
                    'steps': [
                        {'range': [0,  25], 'color': '#1f1215'},
                        {'range': [25, 42], 'color': '#1f1a12'},
                        {'range': [42, 58], 'color': '#1a1a1a'},
                        {'range': [58, 75], 'color': '#121f15'},
                        {'range': [75,100], 'color': '#0a1f12'},
                    ],
                    'threshold': {'line': {'color': e_color, 'width': 3}, 'value': e_score},
                },
                domain={'x': [0, 1], 'y': [0, 1]}
            ))
            fig_ens.update_layout(
                height=240, margin=dict(l=10,r=10,t=30,b=0),
                template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig_ens, use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<h3 style='text-align:center;color:{e_color};margin-top:-10px;'>{e_label}</h3>",
                        unsafe_allow_html=True)

        with ec2:
            st.markdown(f"""
<div class="g-card" style="border-left:5px solid {e_color};margin-bottom:.75rem;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{e_color};margin-bottom:.4rem;">
    <span class="live-dot {'green' if e_score >= 75 else 'gold' if e_score >= 42 else 'red'}"></span>
    ENSEMBLE INTERPRETATION
  </div>
  <div style="font-size:.92rem;color:var(--txt0);line-height:1.7;">{ensemble['plain_english']}</div>
</div>
""", unsafe_allow_html=True)

            st.markdown("""<div style="font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--txt2);margin-bottom:.5rem;">Component Weights</div>""",
                        unsafe_allow_html=True)
            for comp in ensemble['components']:
                bar_w = int(comp['raw_score'])
                st.markdown(f"""
<div class="sig-row">
  <span class="sig-name">{comp['label']}</span>
  <span style="font-size:.7rem;color:var(--txt2);">wt {comp['weight_pct']:.0f}%</span>
  <div class="sig-bar-bg"><div class="sig-bar-fill" style="width:{bar_w}%;background:{comp['color']};"></div></div>
  <span class="sig-pct" style="color:{comp['color']};">{comp['raw_score']:.0f}</span>
</div>
""", unsafe_allow_html=True)

        if e_score >= 75:
            st.balloons()

        st.divider()

        # ── RAG CHATBOT ───────────────────────────────────────────────────────
        st.divider()
        st.markdown(f"""
<div class="ch-marker">
  <div class="ch-num">5</div>
  <div class="ch-text">
    <div class="ch-title">AI Analyst — Ask Anything About {ticker}</div>
    <div class="ch-sub">The AI has read all financial data, KPI scores, price history, ML results, and news for this stock</div>
  </div>
</div><div class="ch-line"></div>
""", unsafe_allow_html=True)
        st.markdown(f"""
<div class="insight">
  <div class="insight-label">💬 Your Personal AI Analyst</div>
  <div class="insight-text">
    Ask anything in plain English — <em>"Should I buy {ticker} right now?"</em>, <em>"What are the biggest risks?"</em>,
    <em>"How does the fair value compare to the forecast?"</em>
    The AI has synthesised every model's output into a single knowledge base. Start with the suggested questions below, then dig deeper.
  </div>
</div>
""", unsafe_allow_html=True)

        with st.spinner("Loading AI analyst knowledge base..."):
            try:
                chatbot_context = {
                    'df_historical_tech':  df_for_ml,
                    'df_isy':              df_isy,
                    'df_bs':               df_bs,
                    'total_score':         total_score,
                    'risk_message':        risk_msg if 'risk_msg' in dir() else 'N/A',
                    'kpi_summary':         str({k: v.get('formatted','') for k,v in results.items() if isinstance(v,dict) and 'formatted' in v}),
                    'fair_value':          str(fair_value) if 'fair_value' in dir() and fair_value is not None else 'N/A',
                    'ai_confidence_bull':  str(conf_bull) if _ai_ok else 'N/A',
                    'scenario_base':       str(base_p) if 'forecast_df' in dir() and forecast_df is not None else 'N/A',
                    'news_sentiment':      sentiment_to_plain_english(sentiment_result) if 'sentiment_result' in dir() else 'N/A',
                    'market_regime':       regime_data.get('plain_english', 'N/A') if 'regime_data' in dir() else 'N/A',
                    'prophet_forecast':    prophet_result.get('plain_english', 'N/A') if 'prophet_result' in dir() else 'N/A',
                    'ensemble_verdict':    ensemble.get('plain_english', 'N/A'),
                    'lstm_forecast':       lstm_result.get('plain_english', 'N/A') if 'lstm_result' in dir() else 'N/A',
                }
                all_docs = ce.process_stock_data(ticker, chatbot_context)
                ce.save_to_vector_db(all_docs)
            except Exception:
                pass

        if st.session_state.get('_pending_sq'):
            pending_q = st.session_state.pop('_pending_sq')
            st.session_state.messages.append({"role": "user", "content": pending_q})
            with st.spinner("Analyzing..."):
                response_raw = ce.get_chat_response(pending_q, ticker)
            if isinstance(response_raw, list) and len(response_raw) > 0:
                clean_text = response_raw[0].get('text', 'No response found.')
            else:
                clean_text = str(response_raw)
            st.session_state.messages.append({"role": "assistant", "content": clean_text})

        suggested_questions = [
            f"Should I buy {ticker} right now?",
            f"What are the biggest risks for {ticker}?",
            f"How has {ticker}'s revenue been trending?",
            f"Is {ticker} cheap or expensive compared to its history?",
            f"What does the news sentiment say about {ticker}?",
        ]
        st.markdown("**Suggested questions:**")
        sq_cols = st.columns(len(suggested_questions))
        for i, q in enumerate(suggested_questions):
            if sq_cols[i].button(q, key=f"sq_{i}", use_container_width=True):
                st.session_state['_pending_sq'] = q
                st.rerun()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_question = st.chat_input(f"Ask me anything about {ticker}...")
        if user_question:
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    response_raw = ce.get_chat_response(user_question, ticker)
                if isinstance(response_raw, list) and len(response_raw) > 0:
                    clean_text = response_raw[0].get('text', 'No response found.')
                else:
                    clean_text = str(response_raw)
                st.markdown(clean_text)
            st.session_state.messages.append({"role": "assistant", "content": clean_text})

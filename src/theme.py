"""
src/theme.py
Shared design-system for the Screener app.
Call apply_theme() at the top of every page (after st.set_page_config).
"""

import streamlit as st


# ── Color tokens ──────────────────────────────────────────────────────────────
ACCENT   = "#00ffc8"
BLUE     = "#3b82f6"
SUCCESS  = "#22c55e"
WARNING  = "#f59e0b"
DANGER   = "#ef4444"
GOLD     = "#fbbf24"

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(13,20,33,0.6)",
    font=dict(family="Inter, sans-serif", color="#c8d4e8"),
    xaxis=dict(gridcolor="#1a2840", zeroline=False),
    yaxis=dict(gridcolor="#1a2840", zeroline=False),
    margin=dict(t=30, b=30, l=10, r=10),
)

_CSS = """
/* ── Google Font ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root tokens ─────────────────────────────────────────────────────────── */
:root {
    --bg0:      #060b14;
    --bg1:      #0d1421;
    --bg2:      #131c2e;
    --bg3:      #192335;
    --border:   #1a2840;
    --border2:  #233552;
    --accent:   #00ffc8;
    --accent15: rgba(0,255,200,.15);
    --accent08: rgba(0,255,200,.08);
    --blue:     #3b82f6;
    --txt0:     #e8edf5;
    --txt1:     #b8cce0;
    --txt2:     #9aaec8;
    --success:  #22c55e;
    --warning:  #f59e0b;
    --danger:   #ef4444;
    --gold:     #fbbf24;
}

/* ── Global reset ────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.main, .block-container {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg0) !important;
    color: var(--txt0) !important;
}

/* ── Block container padding ─────────────────────────────────────────────── */
.block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1400px;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg1) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1rem !important;
}
/* sidebar nav link active state */
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: var(--accent15) !important;
    border-left: 3px solid var(--accent) !important;
    border-radius: 0 8px 8px 0 !important;
}
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    color: var(--txt1) !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    transition: background .15s, color .15s !important;
}
[data-testid="stSidebarNavLink"]:hover {
    background: var(--accent08) !important;
    color: var(--accent) !important;
}
[data-testid="stSidebarNavLink"] span { font-size: 0.88rem !important; }

/* ── Headings ─────────────────────────────────────────────────────────────── */
h1 {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
    background: linear-gradient(90deg, var(--accent) 0%, #60efff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0 !important;
    line-height: 1.2 !important;
}
h2 {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: var(--txt0) !important;
    letter-spacing: -0.3px !important;
}
h3 {
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: var(--txt1) !important;
}
/* st.caption / small text */
[data-testid="stCaptionContainer"] p,
small, .st-emotion-cache-16idsys p {
    color: var(--txt1) !important;
    font-size: 0.82rem !important;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.25rem 0 !important;
}

/* ── Metric cards ────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stMetric"]:hover {
    border-color: var(--border2) !important;
    box-shadow: 0 0 18px rgba(0,255,200,.06) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--accent) !important;
    letter-spacing: -0.5px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    color: var(--txt2) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}

/* ── Dataframe / table ───────────────────────────────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stDataFrameContainer"] {
    background: var(--bg1) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
.dvn-scroller { background: var(--bg1) !important; }
/* header row */
.col_heading {
    background: var(--bg2) !important;
    color: var(--txt2) !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    border-bottom: 1px solid var(--border) !important;
}
/* data cells */
.data {
    background: var(--bg1) !important;
    color: var(--txt0) !important;
    font-size: 0.88rem !important;
    border-color: var(--border) !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button {
    background: var(--bg2) !important;
    color: var(--txt0) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.45rem 1.1rem !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: var(--accent15) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow: 0 0 12px rgba(0,255,200,.15) !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: #060b14 !important;
    border-color: var(--accent) !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #00e6b3 !important;
    box-shadow: 0 0 20px rgba(0,255,200,.35) !important;
}

/* ── Form submit button ───────────────────────────────────────────────────── */
[data-testid="stFormSubmitButton"] > button {
    background: var(--accent) !important;
    color: #060b14 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: all .2s !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: #00e6b3 !important;
    box-shadow: 0 0 16px rgba(0,255,200,.3) !important;
}

/* ── Inputs / select / text area ────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 8px !important;
    color: var(--txt0) !important;
    font-size: 0.88rem !important;
    transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent08) !important;
}
/* dropdown menus */
[data-baseweb="popover"] ul {
    background: var(--bg2) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 8px !important;
}
[data-baseweb="popover"] li {
    color: var(--txt0) !important;
    font-size: 0.88rem !important;
}
[data-baseweb="popover"] li:hover,
[data-baseweb="option"][aria-selected="true"] {
    background: var(--accent15) !important;
    color: var(--accent) !important;
}

/* ── Labels above inputs ─────────────────────────────────────────────────── */
[data-testid="stWidgetLabel"] p,
.stSelectbox label, .stMultiSelect label,
.stTextInput label, .stNumberInput label,
.stSlider label, .stRadio label, .stCheckbox label {
    color: var(--txt2) !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* ── Slider ──────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stThumbValue"] {
    color: var(--accent) !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--bg1) !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 2px !important;
}
[data-testid="stTabs"] button[role="tab"] {
    background: transparent !important;
    color: var(--txt2) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 0.5rem 1rem !important;
    border: none !important;
    transition: color .15s, background .15s !important;
}
[data-testid="stTabs"] button[role="tab"]:hover {
    color: var(--txt0) !important;
    background: var(--accent08) !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: var(--accent) !important;
    background: var(--accent08) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg1) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    color: var(--txt1) !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
}

/* ── Alert / info / warning / error boxes ────────────────────────────────── */
[data-testid="stAlertContainer"][data-baseweb="notification"] {
    border-radius: 10px !important;
    border-left-width: 3px !important;
    font-size: 0.88rem !important;
}

/* ── Checkbox ────────────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label span {
    color: var(--txt1) !important;
    font-size: 0.88rem !important;
}

/* ── Radio ───────────────────────────────────────────────────────────────── */
[data-testid="stRadio"] label span { color: var(--txt1) !important; font-size: 0.88rem !important; }

/* ── Progress bar ────────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div > div {
    background: var(--accent) !important;
}

/* ── Spinner ─────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: var(--accent) !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg1); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--txt2); }

/* ── Plotly chart containers ─────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    background: transparent !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Column gap reduction ────────────────────────────────────────────────── */
[data-testid="column"] { gap: 0.75rem !important; }
[data-testid="stHorizontalBlock"] { gap: 1rem !important; }

/* ── Tooltip ─────────────────────────────────────────────────────────────── */
[data-baseweb="tooltip"] [role="tooltip"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border2) !important;
    color: var(--txt0) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
}

/* ── Custom component classes ────────────────────────────────────────────── */

/* Stat card */
.sc-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    transition: border-color .2s, box-shadow .2s;
}
.sc-card:hover {
    border-color: var(--border2);
    box-shadow: 0 0 22px rgba(0,255,200,.05);
}
.sc-card-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--txt2);
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: .35rem;
}
.sc-card-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -.5px;
    line-height: 1.1;
}
.sc-card-sub {
    font-size: 0.78rem;
    color: var(--txt2);
    margin-top: .25rem;
}

/* Section header */
.sc-section {
    font-size: 1rem;
    font-weight: 600;
    color: var(--txt0);
    padding-bottom: .5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: .5rem;
}

/* Pill badges */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: .03em;
}
.badge-bullish  { background: rgba(34,197,94,.18);  color: #22c55e; }
.badge-bearish  { background: rgba(239,68,68,.18);  color: #ef4444; }
.badge-neutral  { background: rgba(156,163,175,.18);color: #9ca3af; }
.badge-accent   { background: rgba(0,255,200,.15);  color: var(--accent); }
.badge-warning  { background: rgba(245,158,11,.18); color: var(--warning); }
.badge-blue     { background: rgba(59,130,246,.18); color: var(--blue); }
.badge-gold     { background: rgba(251,191,36,.18); color: var(--gold); }

/* Score bar */
.score-bar-wrap {
    background: var(--bg3);
    border-radius: 5px;
    height: 7px;
    width: 100%;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 5px;
    background: linear-gradient(90deg, var(--accent) 0%, #60efff 100%);
    transition: width .4s ease;
}

/* Info kv row */
.kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: .45rem 0;
    border-bottom: 1px solid var(--border);
    font-size: .88rem;
}
.kv-row:last-child { border-bottom: none; }
.kv-key   { color: var(--txt2); font-weight: 500; }
.kv-value { color: var(--txt0); font-weight: 600; }

/* Page hero banner */
.page-hero {
    background: linear-gradient(135deg, var(--bg2) 0%, var(--bg1) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.page-hero-title {
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(90deg, var(--accent) 0%, #60efff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.page-hero-sub {
    font-size: .82rem;
    color: var(--txt2);
    margin-top: .2rem;
}

/* Ticker chip */
.ticker-chip {
    display: inline-block;
    background: var(--accent15);
    color: var(--accent);
    border: 1px solid rgba(0,255,200,.3);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: .82rem;
    font-weight: 700;
    letter-spacing: .05em;
    cursor: default;
}

/* ── Sidebar brand block (injected via st.sidebar.markdown) ───────────────── */
.sb-brand {
    display: flex;
    align-items: center;
    gap: .7rem;
    padding: .5rem 0 1.2rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
}
.sb-logo {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--accent) 0%, #3b82f6 100%);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; font-weight: 800; color: #060b14;
    flex-shrink: 0;
}
.sb-name { font-size: 1rem; font-weight: 700; color: var(--txt0); line-height: 1.1; }
.sb-version { font-size: .7rem; color: var(--txt2); }

.sb-status {
    display: flex;
    align-items: center;
    gap: .4rem;
    padding: .6rem .8rem;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: .78rem;
    color: var(--txt2);
    margin-bottom: 1rem;
}
.sb-dot-green { width:7px; height:7px; background:var(--success); border-radius:50%; flex-shrink:0; }
.sb-dot-red   { width:7px; height:7px; background:var(--danger);  border-radius:50%; flex-shrink:0; }

/* ══════════════════════════════════════════════════════════════════
   IMMERSIVE / INTERACTIVE LAYER
   ══════════════════════════════════════════════════════════════════ */

/* ── Keyframe animations ─────────────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInLeft {
  from { opacity: 0; transform: translateX(-18px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 8px rgba(0,255,200,.18); }
  50%       { box-shadow: 0 0 32px rgba(0,255,200,.55), 0 0 60px rgba(0,255,200,.12); }
}
@keyframes pulseDanger {
  0%, 100% { box-shadow: 0 0 8px rgba(239,68,68,.18); }
  50%       { box-shadow: 0 0 32px rgba(239,68,68,.5), 0 0 60px rgba(239,68,68,.1); }
}
@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.2; }
}
@keyframes slideRight {
  from { width: 0; }
  to   { width: 100%; }
}
@keyframes orbitPulse {
  0%, 100% { transform: scale(1);    opacity: 0.9; }
  50%       { transform: scale(1.04); opacity: 0.6; }
}

/* Animation utility classes */
.anim-fadein   { animation: fadeInUp   0.5s ease both; }
.anim-fadein-1 { animation: fadeInUp   0.5s 0.08s ease both; }
.anim-fadein-2 { animation: fadeInUp   0.5s 0.18s ease both; }
.anim-fadein-3 { animation: fadeInUp   0.5s 0.28s ease both; }
.anim-fadein-4 { animation: fadeInUp   0.5s 0.38s ease both; }
.anim-left     { animation: fadeInLeft 0.45s ease both; }

/* ── Chapter / story markers ─────────────────────────────────────── */
.ch-marker {
  display: flex; align-items: flex-start; gap: 1rem;
  margin: 2.2rem 0 1.1rem;
  animation: fadeInLeft 0.45s ease both;
}
.ch-num {
  width: 38px; height: 38px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--accent) 0%, #3b82f6 100%);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.88rem; font-weight: 800; color: #060b14;
  box-shadow: 0 0 18px rgba(0,255,200,.38);
}
.ch-text { padding-top: 3px; }
.ch-title { font-size: 1.05rem; font-weight: 700; color: var(--txt0); line-height: 1.25; }
.ch-sub   { font-size: 0.78rem; color: var(--txt2); margin-top: 3px; line-height: 1.5; }
.ch-line {
  height: 1px; background: linear-gradient(90deg, var(--accent) 0%, transparent 100%);
  margin-bottom: 1rem; animation: slideRight 0.6s ease both;
}

/* ── Glowing interactive card ─────────────────────────────────────── */
.g-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.15rem 1.35rem;
  transition: border-color .28s, box-shadow .28s, transform .28s;
  animation: fadeInUp 0.45s ease both;
}
.g-card:hover {
  border-color: rgba(0,255,200,.38);
  box-shadow: 0 0 28px rgba(0,255,200,.1), 0 6px 24px rgba(0,0,0,.4);
  transform: translateY(-3px);
  cursor: default;
}
.g-card-accent { border-top: 3px solid var(--accent); }
.g-card-warn   { border-top: 3px solid var(--warning); }
.g-card-danger { border-top: 3px solid var(--danger); }

/* ── Insight callout banner ──────────────────────────────────────── */
.insight {
  background: linear-gradient(135deg, rgba(0,255,200,.07) 0%, rgba(59,130,246,.05) 100%);
  border: 1px solid rgba(0,255,200,.2);
  border-radius: 12px;
  padding: 1rem 1.4rem;
  margin: 0.8rem 0;
  animation: fadeInUp 0.4s ease both;
}
.insight-label {
  font-size: 0.68rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--accent); margin-bottom: .4rem;
  display: flex; align-items: center; gap: .4rem;
}
.insight-text { font-size: .88rem; color: var(--txt0); line-height: 1.7; }

/* ── Live dot indicators ─────────────────────────────────────────── */
.live-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  vertical-align: middle; margin-right: 5px;
}
.live-dot.green { background: var(--success); animation: blink 2.4s ease infinite; }
.live-dot.red   { background: var(--danger);  animation: blink 1.8s ease infinite; }
.live-dot.gold  { background: var(--gold);    animation: blink 2.8s ease infinite; }
.live-dot.blue  { background: var(--blue);    animation: blink 2.2s ease infinite; }

/* ── Pulsing anomaly cards ───────────────────────────────────────── */
.pulse-danger { animation: pulseDanger 2.2s ease-in-out infinite !important; }
.pulse-safe   { animation: pulseGlow   3.2s ease-in-out infinite !important; }

/* ── Signal consensus rows ───────────────────────────────────────── */
.sig-row {
  display: flex; align-items: center; gap: .75rem;
  padding: .6rem .9rem;
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: 9px;
  margin-bottom: .4rem;
  transition: border-color .2s, background .2s;
  animation: fadeInLeft 0.4s ease both;
}
.sig-row:hover { background: var(--bg2); border-color: var(--border2); }
.sig-icon  { font-size: 1rem; width: 22px; text-align: center; flex-shrink: 0; }
.sig-name  { font-size: .82rem; color: var(--txt1); font-weight: 500; flex: 1; }
.sig-badge { font-size: .75rem; font-weight: 700; padding: 2px 9px; border-radius: 12px; flex-shrink: 0; }
.sig-bar-bg {
  width: 80px; height: 5px; background: var(--bg3); border-radius: 3px; flex-shrink: 0;
}
.sig-bar-fill { height: 100%; border-radius: 3px; }
.sig-pct { font-size: .75rem; color: var(--txt2); width: 34px; text-align: right; flex-shrink: 0; }

/* ── Verdict hero (animated) ─────────────────────────────────────── */
.verdict-hero {
  border-radius: 14px;
  padding: 1.5rem 1.8rem;
  position: relative; overflow: hidden;
  animation: fadeInUp 0.5s ease both;
}
.verdict-hero::before {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(0,255,200,.04) 0%, transparent 60%);
  pointer-events: none;
}
.verdict-hero-label {
  font-size: .7rem; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; color: var(--txt2); margin-bottom: .5rem;
}
.verdict-hero-title {
  font-size: 1.6rem; font-weight: 800; line-height: 1.2; margin-bottom: .5rem;
}
.verdict-hero-sub { font-size: .9rem; color: var(--txt1); line-height: 1.6; }

/* ── Exploration path tracker ────────────────────────────────────── */
.explore-path {
  display: flex; align-items: center; gap: .4rem;
  padding: .55rem 1.1rem;
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: 40px; margin-bottom: 1.5rem;
  overflow-x: auto; white-space: nowrap;
  animation: fadeInUp 0.3s ease both;
}
.ep-step {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .25rem .75rem; border-radius: 16px;
  font-size: .72rem; font-weight: 600; color: var(--txt2);
  transition: all .2s;
}
.ep-step.active { background: var(--accent15); color: var(--accent); }
.ep-step.done   { background: rgba(34,197,94,.1); color: var(--success); }
.ep-arrow { color: var(--border2); font-size: .65rem; }

/* ── Score radial glow ───────────────────────────────────────────── */
.score-ring-wrap {
  position: relative;
  padding: .5rem;
  animation: orbitPulse 4s ease-in-out infinite;
}
.score-ring-wrap::after {
  content: '';
  position: absolute;
  inset: -10px; border-radius: 50%;
  background: radial-gradient(circle, rgba(0,255,200,.12) 0%, transparent 70%);
  pointer-events: none;
}

/* ── Tab subheader label ─────────────────────────────────────────── */
.tab-intro {
  background: linear-gradient(135deg, var(--bg2) 0%, var(--bg1) 100%);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  padding: .85rem 1.2rem;
  margin-bottom: 1.2rem;
  font-size: .88rem; color: var(--txt1); line-height: 1.65;
  animation: fadeInUp 0.4s ease both;
}
.tab-intro strong { color: var(--txt0); }
"""


def apply_theme():
    """Inject the full design-system CSS. Call once at top of every page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def sidebar_brand():
    """Render the branded header inside the sidebar."""
    st.sidebar.markdown("""
<div class="sb-brand">
  <div class="sb-logo">S</div>
  <div>
    <div class="sb-name">Screener</div>
    <div class="sb-version">S&amp;P 500 · v2.0</div>
  </div>
</div>
""", unsafe_allow_html=True)


def sidebar_status(last_scan: str = None, stock_count: int = None):
    """Show a live-status pill in the sidebar."""
    if last_scan:
        st.sidebar.markdown(f"""
<div class="sb-status">
  <div class="sb-dot-green"></div>
  <span>Last scan: <strong style="color:#e8edf5">{last_scan}</strong></span>
</div>
""", unsafe_allow_html=True)
    if stock_count:
        st.sidebar.caption(f"{stock_count:,} stocks tracked")


# ── HTML helpers ──────────────────────────────────────────────────────────────

def badge(text: str, kind: str = "accent") -> str:
    """Return an inline badge HTML string. kind: accent|bullish|bearish|neutral|warning|blue|gold"""
    return f'<span class="badge badge-{kind}">{text}</span>'


def score_bar(score: float, max_score: float = 10.0) -> str:
    """Return an HTML score-bar string."""
    pct = min(max(score / max_score * 100, 0), 100)
    color = "#22c55e" if pct >= 70 else ("#f59e0b" if pct >= 40 else "#ef4444")
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>'
        f'</div>'
    )


def stat_card(label: str, value: str, sub: str = "", accent_value: bool = True) -> str:
    """Return an HTML stat card."""
    val_style = "color:var(--accent)" if accent_value else "color:var(--txt0)"
    return f"""
<div class="sc-card">
  <div class="sc-card-label">{label}</div>
  <div class="sc-card-value" style="{val_style}">{value}</div>
  {"" if not sub else f'<div class="sc-card-sub">{sub}</div>'}
</div>"""


def section_header(title: str, icon: str = "") -> str:
    prefix = f"{icon} " if icon else ""
    return f'<div class="sc-section">{prefix}{title}</div>'


def ticker_chip(ticker: str) -> str:
    return f'<span class="ticker-chip">{ticker}</span>'


def trend_badge(trend: str) -> str:
    if trend == "Bullish":
        return badge("Bullish", "bullish")
    if trend == "Bearish":
        return badge("Bearish", "bearish")
    return badge(trend or "—", "neutral")


def score_badge(score: float, max_score: float = 10.0) -> str:
    pct = score / max_score
    kind = "accent" if pct >= 0.7 else ("warning" if pct >= 0.4 else "bearish")
    return badge(f"{score:.0f}/{max_score:.0f}", kind)


def page_hero(title: str, subtitle: str = "", right_html: str = "") -> None:
    """Render a prominent page banner."""
    st.markdown(f"""
<div class="page-hero">
  <div>
    <div class="page-hero-title">{title}</div>
    {"" if not subtitle else f'<div class="page-hero-sub">{subtitle}</div>'}
  </div>
  {right_html}
</div>
""", unsafe_allow_html=True)


def apply_plotly_theme(fig, height: int = 350):
    """Apply the shared Plotly dark theme to any figure."""
    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=height,
    )
    return fig

# pages/4_Alerts.py
# In-app alerts — get notified when any stock hits a condition you set.

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
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.theme import apply_theme, sidebar_brand, section_header
from src.alert_engine import save_email_config, get_email_config, check_alerts as engine_check, send_alert_email

st.set_page_config(page_title="Alerts · Screener", layout="wide", page_icon="🔔")
apply_theme()
sidebar_brand()

engine = get_engine()
USER_ID = "default"

FIELD_LABELS = {
    "total_score":        "Total KPI Score",
    "fundamental_score":  "Fundamental Score",
    "technical_score":    "Technical Score",
    "rsi_val":            "RSI (14-Day)",
    "current_price":      "Current Price ($)",
    "margin_val":         "Operating Margin (%)",
    "rev_growth_val":     "Revenue Growth (%)",
    "price_strength_val": "% from 52W High",
}
OPERATORS = {">": "Greater than", "<": "Less than", ">=": "At least", "<=": "At most", "==": "Exactly"}

def get_alerts():
    try:
        return pd.read_sql(
            "SELECT * FROM alerts WHERE user_id = %s ORDER BY created_at DESC",
            engine, params=(USER_ID,)
        )
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def get_latest_snapshot():
    try:
        return pd.read_sql(
            """SELECT * FROM daily_kpi_snapshot
               WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
               AND scan_status = 'success'""",
            engine
        )
    except Exception:
        return pd.DataFrame()

def check_alerts_local(alerts_df, snapshot_df):
    if alerts_df.empty or snapshot_df.empty:
        return []
    triggered = []
    for _, alert in alerts_df.iterrows():
        if not alert.get("is_active", True):
            continue
        ticker, field, op, threshold = alert["ticker"], alert["field_name"], alert["operator"], float(alert["threshold_value"])
        rows = snapshot_df[snapshot_df["ticker"] == ticker] if ticker and ticker != "ANY" else snapshot_df
        if rows.empty or field not in rows.columns:
            continue
        for _, row in rows.iterrows():
            val = row.get(field)
            if val is None or pd.isna(val):
                continue
            val = float(val)
            hit = ((op==">" and val>threshold) or (op=="<" and val<threshold) or
                   (op==">=" and val>=threshold) or (op=="<=" and val<=threshold) or
                   (op=="==" and abs(val-threshold)<0.01))
            if hit:
                triggered.append({"alert_id": alert["id"], "ticker": row["ticker"],
                    "field": FIELD_LABELS.get(field, field), "condition": f"{op} {threshold}",
                    "current_value": round(val, 2), "total_score": row.get("total_score"),
                    "current_price": row.get("current_price")})
    return triggered

def update_last_triggered(alert_ids):
    if not alert_ids:
        return
    with engine.connect() as conn:
        for aid in alert_ids:
            conn.execute(text("UPDATE alerts SET last_triggered = :t WHERE id = :id"),
                         {"t": datetime.now(), "id": aid})
        conn.commit()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem">
  <h1 style="margin-bottom:.2rem">Alerts</h1>
  <p style="color:var(--txt2);font-size:.85rem;margin:0">
    Get notified when any stock hits a condition you define
  </p>
</div>
""", unsafe_allow_html=True)

df_snap   = get_latest_snapshot()
df_alerts = get_alerts()

# ── Triggered alerts ───────────────────────────────────────────────────────────
if not df_alerts.empty and not df_snap.empty:
    triggered = check_alerts_local(df_alerts, df_snap)
    if triggered:
        st.markdown(f"""
<div style="background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);border-radius:10px;
            padding:1rem 1.25rem;margin-bottom:1rem">
  <div style="font-weight:700;color:#ef4444;margin-bottom:.6rem">🚨 {len(triggered)} alert(s) triggered right now</div>
""" + "".join([f"""
  <div style="display:flex;gap:1rem;align-items:center;padding:.4rem 0;border-bottom:1px solid rgba(239,68,68,.15)">
    <span class="ticker-chip">{t['ticker']}</span>
    <span style="color:var(--txt1);font-size:.88rem">{t['field']} is <strong style="color:#ef4444">{t['current_value']}</strong> (alert: {t['condition']})</span>
    <span style="color:var(--txt2);font-size:.8rem;margin-left:auto">Score: {t.get('total_score','N/A')} · ${t.get('current_price','N/A')}</span>
  </div>""" for t in triggered]) + """
</div>""", unsafe_allow_html=True)
        update_last_triggered(list({t["alert_id"] for t in triggered}))
    else:
        st.markdown("""
<div style="background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:8px;
            padding:.7rem 1rem;margin-bottom:1rem;color:#22c55e;font-size:.88rem;font-weight:600">
  ✅ No alerts currently triggered
</div>""", unsafe_allow_html=True)

st.divider()

# ── Create alert ───────────────────────────────────────────────────────────────
st.markdown(section_header("Create New Alert", "➕"), unsafe_allow_html=True)

with st.form("create_alert"):
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    ticker_opt   = ["ANY"] + sorted(df_snap["ticker"].tolist() if not df_snap.empty else [])
    alert_ticker = c1.selectbox("Ticker (or ANY)", ticker_opt)
    field_key    = c2.selectbox("Condition Field", list(FIELD_LABELS.keys()),
                                format_func=lambda k: FIELD_LABELS[k])
    op_key       = c3.selectbox("Operator", list(OPERATORS.keys()), format_func=lambda k: OPERATORS[k])
    threshold    = c4.number_input("Threshold", value=0.0, step=0.5)

    if st.form_submit_button("Create Alert", type="primary"):
        ticker_save = None if alert_ticker == "ANY" else alert_ticker
        with engine.connect() as conn:
            conn.execute(text("""INSERT INTO alerts (user_id, ticker, field_name, operator, threshold_value, created_at)
                                 VALUES (:u, :t, :f, :op, :v, :ts)"""),
                         {"u": USER_ID, "t": ticker_save, "f": field_key, "op": op_key,
                          "v": threshold, "ts": datetime.now()})
            conn.commit()
        st.success(f"Alert created: {FIELD_LABELS[field_key]} {op_key} {threshold}" +
                   (f" for {alert_ticker}" if alert_ticker != "ANY" else " for ALL stocks"))
        st.rerun()

st.divider()

# ── Manage alerts ──────────────────────────────────────────────────────────────
st.markdown(section_header("Active Alerts", "🔔"), unsafe_allow_html=True)

if df_alerts.empty:
    st.info("No alerts set yet. Create one above.")
else:
    for _, alert in df_alerts.iterrows():
        ticker_label = alert.get("ticker") or "ANY ticker"
        field_label  = FIELD_LABELS.get(alert["field_name"], alert["field_name"])
        active       = bool(alert.get("is_active", True))
        last_hit     = alert.get("last_triggered")
        accent       = "#00ffc8" if active else "#5a6f8a"

        st.markdown(f"""
<div class="sc-card" style="border-left:4px solid {accent};margin-bottom:.6rem">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
    <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap">
      <span class="ticker-chip">{ticker_label}</span>
      <span style="color:var(--txt1);font-size:.88rem">{field_label} <strong>{alert['operator']} {alert['threshold_value']}</strong></span>
      {"" if active else '<span class="badge badge-neutral">Disabled</span>'}
    </div>
    <span style="color:var(--txt2);font-size:.75rem">Created: {str(alert.get('created_at',''))[:10]}{f" · Last hit: {str(last_hit)[:16]}" if last_hit else ""}</span>
  </div>
</div>
""", unsafe_allow_html=True)

        c1, c2, _ = st.columns([1, 1, 6])
        with c1:
            if st.button("Delete", key=f"del_{alert['id']}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM alerts WHERE id = :id"), {"id": alert["id"]})
                    conn.commit()
                st.rerun()
        with c2:
            if st.button("Disable" if active else "Enable", key=f"tog_{alert['id']}"):
                with engine.connect() as conn:
                    conn.execute(text("UPDATE alerts SET is_active = :v WHERE id = :id"),
                                 {"v": not active, "id": alert["id"]})
                    conn.commit()
                st.rerun()

st.divider()

# ── Email config ───────────────────────────────────────────────────────────────
st.markdown(section_header("Email Notifications", "✉️"), unsafe_allow_html=True)
cfg = get_email_config(USER_ID)

with st.expander("Configure Email", expanded=not bool(cfg.get("sender_email"))):
    st.caption("Alerts are checked after every nightly scan. Uses Gmail App Passwords.")
    ec1, ec2 = st.columns(2)
    sender_in    = ec1.text_input("Sender Gmail",     value=cfg.get("sender_email",""),    placeholder="you@gmail.com")
    recipient_in = ec2.text_input("Recipient Email",  value=cfg.get("recipient_email",""), placeholder="alerts@example.com")
    password_in  = st.text_input("Gmail App Password",value=cfg.get("app_password",""),    type="password", placeholder="xxxx xxxx xxxx xxxx")

    cs, ct = st.columns(2)
    if cs.button("Save Config", type="primary"):
        if sender_in and password_in and recipient_in:
            save_email_config(USER_ID, sender_in, password_in.replace(" ",""), recipient_in)
            st.success("Email config saved.")
            st.rerun()
        else:
            st.error("Fill in all three fields.")
    if ct.button("Send Test Email"):
        if not cfg.get("sender_email"):
            st.error("Save your config first.")
        else:
            ok = send_alert_email([{"ticker":"TEST","field":"total_score","operator":">=","threshold":7,"actual":8.5,"score":8.5}], cfg)
            st.success("Test email sent!") if ok else st.error("Send failed — check app password.")

if cfg.get("sender_email"):
    st.info(f"Emails: **{cfg['sender_email']}** → **{cfg['recipient_email']}**")

st.divider()

# ── Suggestions ────────────────────────────────────────────────────────────────
st.markdown(section_header("Suggested Alerts", "💡"), unsafe_allow_html=True)
suggestions = [
    ("RSI Oversold",    "rsi_val",            "<",  30,  "Notify when RSI drops below 30"),
    ("High Score",      "total_score",         ">=", 8,   "Score ≥ 8 — strong buy zone"),
    ("Near 52W High",   "price_strength_val",  ">", -5,   "Within 5% of 52W High"),
    ("Deep Value Dip",  "price_strength_val",  "<", -20,  "Price >20% below 52W High"),
]
s_cols = st.columns(2)
for i, (name, field, op, val, desc) in enumerate(suggestions):
    with s_cols[i % 2]:
        st.markdown(f"""
<div class="sc-card" style="margin-bottom:.5rem">
  <div style="font-weight:600;color:var(--txt0);font-size:.9rem;margin-bottom:.2rem">{name}</div>
  <div style="color:var(--txt2);font-size:.78rem;margin-bottom:.4rem">{desc}</div>
  <code style="font-size:.78rem;color:var(--accent)">{FIELD_LABELS[field]} {op} {val}</code>
</div>""", unsafe_allow_html=True)

# src/alert_engine.py
# Checks all saved alerts against the latest KPI snapshot and sends email notifications.

import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from sqlalchemy import create_engine, text

import os as _os

def _get_engine():
    host     = _os.getenv("DB_HOST", "localhost")
    user     = _os.getenv("DB_USER", "root")
    password = _os.getenv("DB_PASS", "Bank1234")
    port     = _os.getenv("DB_PORT", "3306")
    db       = _os.getenv("DB_NAME", "bank_data")
    return create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}")

# ── Email Config Table ─────────────────────────────────────────────────────────

def get_email_config(user_id="default") -> dict:
    try:
        df = pd.read_sql(
            "SELECT * FROM email_config WHERE user_id = %s LIMIT 1",
            _get_engine(), params=(user_id,)
        )
        if df.empty:
            return {}
        return df.iloc[0].to_dict()
    except Exception:
        return {}


def save_email_config(user_id, sender_email, app_password, recipient_email):
    with _get_engine().connect() as conn:
        conn.execute(text("""
            INSERT INTO email_config (user_id, sender_email, app_password, recipient_email)
            VALUES (:uid, :se, :ap, :re)
            ON DUPLICATE KEY UPDATE sender_email=:se, app_password=:ap, recipient_email=:re
        """), {"uid": user_id, "se": sender_email, "ap": app_password, "re": recipient_email})
        conn.commit()


# ── Alert Evaluation ───────────────────────────────────────────────────────────

OPERATORS = {">": "__gt__", "<": "__lt__", ">=": "__ge__", "<=": "__le__", "==": "__eq__"}

def _evaluate(actual_val, operator: str, threshold: float) -> bool:
    try:
        op_fn = getattr(float(actual_val), OPERATORS[operator])
        return op_fn(threshold)
    except Exception:
        return False


def check_alerts(user_id="default") -> list[dict]:
    """
    Compares all saved alerts against today's snapshot.
    Returns a list of triggered alert dicts.
    """
    try:
        df_alerts = pd.read_sql(
            "SELECT * FROM alerts WHERE user_id = %s AND is_active = 1",
            _get_engine(), params=(user_id,)
        )
    except Exception:
        return []

    if df_alerts.empty:
        return []

    try:
        df_snap = pd.read_sql("""
            SELECT * FROM daily_kpi_snapshot
            WHERE scan_date = (SELECT MAX(scan_date) FROM daily_kpi_snapshot WHERE scan_status='success')
              AND scan_status = 'success'
        """, _get_engine())
    except Exception:
        return []

    triggered = []

    for _, alert in df_alerts.iterrows():
        ticker     = alert.get("ticker")
        field      = alert.get("field_name")
        operator   = alert.get("operator")
        threshold  = alert.get("threshold_value")

        # Filter snapshot — if ticker is None, check all tickers
        df_check = df_snap[df_snap["ticker"] == ticker] if ticker else df_snap

        if field not in df_check.columns:
            continue

        for _, row in df_check.iterrows():
            actual = row[field]
            if pd.isna(actual):
                continue
            if _evaluate(actual, operator, threshold):
                triggered.append({
                    "alert_id":  alert["id"],
                    "ticker":    row["ticker"],
                    "field":     field,
                    "operator":  operator,
                    "threshold": threshold,
                    "actual":    actual,
                    "score":     row.get("total_score"),
                })

    return triggered


# ── Email Sender ───────────────────────────────────────────────────────────────

def send_alert_email(triggered: list[dict], config: dict) -> bool:
    """
    Sends a summary email of all triggered alerts.
    Returns True on success.
    """
    if not triggered or not config:
        return False

    sender    = config.get("sender_email")
    password  = config.get("app_password")
    recipient = config.get("recipient_email")

    if not all([sender, password, recipient]):
        print("[AlertEngine] Email config incomplete — skipping send.")
        return False

    today = date.today().strftime("%b %d, %Y")
    subject = f"[Screener] {len(triggered)} Alert(s) Triggered — {today}"

    # Build HTML body
    rows_html = ""
    for t in triggered:
        color = "#00FFC8" if t["actual"] > t["threshold"] else "#FF4B4B"
        rows_html += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #30363d;"><b>{t['ticker']}</b></td>
            <td style="padding:8px; border-bottom:1px solid #30363d;">{t['field']}</td>
            <td style="padding:8px; border-bottom:1px solid #30363d;">{t['operator']} {t['threshold']}</td>
            <td style="padding:8px; border-bottom:1px solid #30363d; color:{color};"><b>{round(t['actual'], 2)}</b></td>
            <td style="padding:8px; border-bottom:1px solid #30363d;">{round(t['score'], 1) if t['score'] else 'N/A'}</td>
        </tr>"""

    html_body = f"""
    <html><body style="background:#0e1117; color:#c9d1d9; font-family:sans-serif; padding:20px;">
        <h2 style="color:#00FFC8;">Stock Screener — Alert Summary</h2>
        <p style="color:#8b949e;">{today} | {len(triggered)} condition(s) triggered</p>
        <table style="width:100%; border-collapse:collapse; background:#161b22;">
            <thead>
                <tr style="background:#21262d; color:#8b949e; font-size:12px;">
                    <th style="padding:10px; text-align:left;">Ticker</th>
                    <th style="padding:10px; text-align:left;">Field</th>
                    <th style="padding:10px; text-align:left;">Condition</th>
                    <th style="padding:10px; text-align:left;">Actual Value</th>
                    <th style="padding:10px; text-align:left;">KPI Score</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p style="color:#484f58; margin-top:20px; font-size:12px;">
            Sent by your Stock Screener — manage alerts at localhost:8501
        </p>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = recipient
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, recipient, msg.as_string())

        print(f"[AlertEngine] Email sent — {len(triggered)} alerts to {recipient}")
        return True

    except Exception as e:
        print(f"[AlertEngine] Email send failed: {e}")
        return False


# ── Main Entry Point (called by batch_scanner after each run) ─────────────────

def run_alert_check(user_id="default"):
    """Full pipeline: check alerts, send email if anything triggered."""
    print(f"[AlertEngine] Checking alerts for user '{user_id}'...")
    triggered = check_alerts(user_id)

    if not triggered:
        print("[AlertEngine] No alerts triggered.")
        return

    print(f"[AlertEngine] {len(triggered)} alert(s) triggered.")
    config = get_email_config(user_id)
    send_alert_email(triggered, config)

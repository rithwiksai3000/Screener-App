# src/batch_scanner.py
# Core batch scanning engine.
# Iterates over the ticker universe, computes all 10 KPIs, saves to daily_kpi_snapshot.

import time
import pandas as pd
import numpy as np
from datetime import datetime, date
from sqlalchemy import create_engine, text

from src.Migration import run as migration_run
from src.kpis import compute_fundamentals, compute_technicals
from src.universe import get_sp500_tickers
from src.sector_map import get_sector
from src.alert_engine import run_alert_check

# ── DB Connection ──────────────────────────────────────────────────────────────
import os as _os

def _get_engine():
    host     = _os.getenv("DB_HOST", "localhost")
    user     = _os.getenv("DB_USER", "root")
    password = _os.getenv("DB_PASS", "Bank1234")
    port     = _os.getenv("DB_PORT", "3306")
    db       = _os.getenv("DB_NAME", "bank_data")
    return create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}")

# ── Constants ──────────────────────────────────────────────────────────────────
DELAY_BETWEEN_TICKERS = 2   # seconds — avoids yfinance rate limiting
BATCH_SIZE = 50             # process in batches, print progress every N tickers
BASE_PATH = r"C:\Users\rithw\Screener"


# ── Internal Helpers ───────────────────────────────────────────────────────────

def _upsert_financials(ticker: str, category: str, temp_data: dict):
    """
    Saves the financial DataFrames from Migration.run() to MySQL.
    Mirrors ingestion.ingest() but avoids calling Migration.run() a second time.
    """
    dataframes = {
        "balance_sheet_annual":       temp_data["df_bs"],
        "cash_flow_annual":           temp_data["df_csy"],
        "income_statement_annual":    temp_data["df_isy"],
        "income_statement_quarterly": temp_data["df_isq"],
    }

    for table_name, df in dataframes.items():
        if df is None or df.empty:
            continue
        df_to_save = df.reset_index().rename(columns={"index": "Date"})
        df_to_save["Company"]  = ticker
        df_to_save["Category"] = category
        header_cols = ["Date", "Company", "Category"]
        data_cols   = [c for c in df_to_save.columns if c not in header_cols]
        df_to_save  = df_to_save[header_cols + data_cols]

        _eng = _get_engine()
        with _eng.connect() as conn:
            conn.execute(
                text(f"DELETE FROM {table_name} WHERE Company = :t"),
                {"t": ticker}
            )
            conn.commit()
        df_to_save.to_sql(table_name, con=_eng, if_exists="append", index=False)


def _save_kpi_snapshot(ticker: str, category: str, funda: dict, tech: dict, df_stock: pd.DataFrame):
    """
    Saves the computed KPI results into daily_kpi_snapshot.
    Upserts: deletes today's row for this ticker, then inserts fresh.
    """
    today = date.today()

    # Price data — df_stock has SMA columns added by compute_technicals()
    latest = df_stock.iloc[-1]
    current_price  = float(latest["Close"])
    sma_50         = float(latest["SMA_50"])   if "SMA_50"  in df_stock.columns else None
    sma_200        = float(latest["SMA_200"])  if "SMA_200" in df_stock.columns else None
    high_52w       = float(df_stock["High"].tail(252).max())

    # Scores
    fund_score = float(funda.get("Fundamental_Total", 0))
    tech_score = float(sum(
        v.get("score", 0) for v in tech.values() if isinstance(v, dict) and "score" in v
    ))
    total_score = fund_score + tech_score

    row = {
        "scan_date":   today,
        "ticker":      ticker,
        "category":    category,

        # Fundamentals
        "efficiency_val":   funda.get("Efficiency",  {}).get("value"),
        "efficiency_score": funda.get("Efficiency",  {}).get("score"),
        "margin_val":       funda.get("Margin",       {}).get("value"),
        "margin_score":     funda.get("Margin",       {}).get("score"),
        "rev_growth_val":   funda.get("RevGrowth",   {}).get("value"),
        "rev_growth_score": funda.get("RevGrowth",   {}).get("score"),
        "solvency_val":     funda.get("Solvency",    {}).get("value"),
        "solvency_score":   funda.get("Solvency",    {}).get("score"),
        "valuation_val":    funda.get("Valuation",   {}).get("value"),
        "valuation_score":  funda.get("Valuation",   {}).get("score"),
        "growth_adj_val":   funda.get("Growth_Adj", {}).get("value"),
        "growth_adj_score": funda.get("Growth_Adj", {}).get("score"),
        "roce_val":         funda.get("ROCE",       {}).get("value"),
        "roce_score":       funda.get("ROCE",       {}).get("score"),
        "roic_val":         funda.get("ROIC",       {}).get("value"),
        "roic_score":       funda.get("ROIC",       {}).get("score"),

        # Technicals
        "rsi_val":                  tech.get("RSI",              {}).get("value"),
        "rsi_score":                tech.get("RSI",              {}).get("score"),
        "long_term_trend":          tech.get("LongTermTrend",    {}).get("formatted"),
        "long_term_trend_score":    tech.get("LongTermTrend",    {}).get("score"),
        "medium_term_trend":        tech.get("MediumTermTrend",  {}).get("formatted"),
        "medium_term_trend_score":  tech.get("MediumTermTrend",  {}).get("score"),
        "price_strength_val":       tech.get("PriceStrength",   {}).get("value"),
        "price_strength_score":     tech.get("PriceStrength",   {}).get("score"),

        # Aggregates
        "fundamental_score": fund_score,
        "technical_score":   tech_score,
        "total_score":       total_score,

        # Price
        "current_price": current_price,
        "sma_50":        sma_50,
        "sma_200":       sma_200,
        "high_52w":      high_52w,

        "sector":      get_sector(ticker),
        "scan_status": "success",
    }

    df_row = pd.DataFrame([row])
    _eng = _get_engine()

    with _eng.connect() as conn:
        conn.execute(
            text("DELETE FROM daily_kpi_snapshot WHERE ticker = :t AND scan_date = :d"),
            {"t": ticker, "d": str(today)}
        )
        conn.commit()

    df_row.to_sql("daily_kpi_snapshot", con=_eng, if_exists="append", index=False)


def _save_failed_snapshot(ticker: str, error: str):
    """Records a failed ticker scan so we can retry or investigate later."""
    today = date.today()
    row = {"scan_date": today, "ticker": ticker, "scan_status": "failed", "error_msg": str(error)[:500]}
    df_row = pd.DataFrame([row])
    _eng = _get_engine()
    with _eng.connect() as conn:
        conn.execute(
            text("DELETE FROM daily_kpi_snapshot WHERE ticker = :t AND scan_date = :d"),
            {"t": ticker, "d": str(today)}
        )
        conn.commit()
    df_row.to_sql("daily_kpi_snapshot", con=_eng, if_exists="append", index=False)


# ── Per-Ticker Scanner ─────────────────────────────────────────────────────────

def scan_single_ticker(ticker: str) -> bool:
    """
    Full pipeline for one ticker:
    Migration → MySQL financials → KPI computation → snapshot save.
    Returns True on success, False on failure.
    """
    try:
        # Step 1: Fetch all data (one API hit)
        temp_data = migration_run(ticker)
        category  = temp_data["category"]
        df_stock  = temp_data["df_stock"].copy()

        # Step 2: Save financials to MySQL
        _upsert_financials(ticker, category, temp_data)

        # Step 3: Compute KPIs
        funda = compute_fundamentals(ticker, category)
        tech  = compute_technicals(df_stock)

        # Guard: if technicals returned an error dict
        if "Error" in tech:
            raise ValueError(tech["Error"])

        # Step 4: Save snapshot
        _save_kpi_snapshot(ticker, category, funda, tech, df_stock)

        return True

    except Exception as e:
        print(f"  [FAIL] {ticker}: {e}")
        _save_failed_snapshot(ticker, str(e))
        return False


# ── Batch Runner ───────────────────────────────────────────────────────────────

def run_full_batch(tickers: list[str] = None, delay: float = DELAY_BETWEEN_TICKERS) -> dict:
    """
    Runs the full batch scan across all tickers.
    Returns a summary dict with counts and failed tickers.
    """
    if tickers is None:
        tickers = get_sp500_tickers()

    total       = len(tickers)
    succeeded   = 0
    failed      = []
    start_time  = datetime.now()

    print(f"\n{'='*60}")
    print(f"[Batch Scanner] Starting — {total} tickers — {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i:>3}/{total}] Scanning {ticker:<10}", end=" ... ")

        ok = scan_single_ticker(ticker)

        if ok:
            succeeded += 1
            print("OK")
        else:
            failed.append(ticker)
            print("FAILED")

        # Progress checkpoint
        if i % BATCH_SIZE == 0:
            elapsed = (datetime.now() - start_time).seconds
            rate    = i / elapsed if elapsed > 0 else 0
            eta_s   = (total - i) / rate if rate > 0 else 0
            print(f"\n  --- Checkpoint: {i}/{total} done | ETA: {eta_s/60:.0f} min ---\n")

        # Rate limit buffer
        if i < total:
            time.sleep(delay)

    duration = (datetime.now() - start_time).total_seconds()

    # Log the run
    _log_scan_run(total, succeeded, len(failed), failed, duration)

    # Check alerts and send email notifications
    try:
        run_alert_check()
    except Exception as e:
        print(f"[AlertEngine] Error during alert check: {e}")

    summary = {
        "total":     total,
        "succeeded": succeeded,
        "failed":    len(failed),
        "failed_tickers": failed,
        "duration_min": round(duration / 60, 1),
    }

    print(f"\n{'='*60}")
    print(f"[Batch Scanner] Done in {summary['duration_min']} min")
    print(f"  Succeeded : {succeeded}")
    print(f"  Failed    : {len(failed)}")
    if failed:
        print(f"  Failed tickers: {', '.join(failed)}")
    print(f"{'='*60}\n")

    return summary


def retry_failed(delay: float = DELAY_BETWEEN_TICKERS) -> dict:
    """
    Re-runs only the tickers that failed in today's scan.
    """
    today = date.today()
    with _get_engine().connect() as conn:
        result = conn.execute(
            text("SELECT ticker FROM daily_kpi_snapshot WHERE scan_date = :d AND scan_status = 'failed'"),
            {"d": str(today)}
        )
        failed_tickers = [row[0] for row in result]

    if not failed_tickers:
        print("[Retry] No failed tickers to retry.")
        return {}

    print(f"[Retry] Retrying {len(failed_tickers)} failed tickers...")
    return run_full_batch(failed_tickers, delay=delay)


def _log_scan_run(total, succeeded, failed_count, failed_list, duration):
    row = {
        "run_date":         datetime.now(),
        "total_scanned":    total,
        "total_succeeded":  succeeded,
        "total_failed":     failed_count,
        "failed_tickers":   ", ".join(failed_list) if failed_list else None,
        "duration_seconds": round(duration, 1),
    }
    pd.DataFrame([row]).to_sql("scan_log", con=_get_engine(), if_exists="append", index=False)


# ── Quick Test: Single Ticker ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        t = sys.argv[1].upper()
        print(f"Testing single ticker: {t}")
        ok = scan_single_ticker(t)
        print("Result:", "SUCCESS" if ok else "FAILED")
    else:
        # Run full batch
        run_full_batch()

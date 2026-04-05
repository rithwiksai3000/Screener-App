# -*- coding: utf-8 -*-
import sys, os
from sqlalchemy import create_engine, text
from src.Migration import run
import pandas as pd


# Ensure Python can find Migration.py if it's in the same folder
sys.path.insert(0, os.path.dirname(__file__))   

# ── 1. Database Connection ─────────────────────────────────────────────────────
def _get_engine():
    host     = os.getenv("DB_HOST", "localhost")
    user     = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", "Bank1234")
    port     = os.getenv("DB_PORT", "3306")
    db_name  = os.getenv("DB_NAME", "bank_data")
    return create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}")


# ── 2. Main Ingestion Function ─────────────────────────────────────────────────
def ingest(ticker: str):
    """
    Runs Migration.run() for the given ticker, then upserts all
    financial tables into MySQL.
    """
    # ── 2a. Extract & clean via Migration.py ──
    result   = run(ticker)
    ticker   = result["ticker"]
    category = result["category"]

    # ── 2b. Map cleaned DataFrames ──
    dataframes = {
        "balance_sheet_annual":       result["df_bs"],
        "cash_flow_annual":           result["df_csy"],
        "income_statement_annual":    result["df_isy"],
        "income_statement_quarterly": result["df_isq"],
    }

    # ── 2c. Upsert loop ──
    for table_name, df in dataframes.items():
        df_to_save = df.reset_index().rename(columns={"index": "Date"})
        df_to_save["Company"]  = ticker
        df_to_save["Category"] = category

        header_cols = ["Date", "Company", "Category"]
        data_cols   = [c for c in df_to_save.columns if c not in header_cols]
        df_to_save  = df_to_save[header_cols + data_cols]

        eng = _get_engine()
        with eng.connect() as conn:
            conn.execute(
                text(f"DELETE FROM {table_name} WHERE Company = :ticker"),
                {"ticker": ticker}
            )
            conn.commit()

        df_to_save.columns = [c.replace(' ', '_') for c in df_to_save.columns]

# --- STEP 2: Update your existing to_sql line ---
# We use 'replace' to automatically create the missing columns in Railway
        df_to_save.to_sql(
        table_name, 
        con=eng, 
        if_exists="replace", 
        index=False, 
        method="multi", 
        chunksize=500
        )
        print(f"  [OK] {table_name} - {len(df_to_save)} rows written for {ticker}")

    print(f"[OK] Raw Data Ingestion complete for {ticker}")


# ── 2d. New Result Saving Function ───────────────────────────────────────────
def upsert_kpi_report(ticker, category, results):
    """Saves specific KPI values and the final 10-point score to MySQL."""
    
    # Calculate the Grand Total from all 10 possible points
    grand_total = sum(v['score'] for k, v in results.items() if isinstance(v, dict) and 'score' in v)
    
    # Extract raw values for the table columns
    data = {
        "Date": [pd.Timestamp.now().date()],
        "Company": [ticker],
        "Category": [category],
        "Efficiency_Val": [results.get('Efficiency', {}).get('value', 0)],
        "Margin_Val": [results.get('Margin', {}).get('value', 0)],
        "RevGrowth_Val": [results.get('RevGrowth', {}).get('value', 0)],
        "Solvency_Val": [results.get('Solvency', {}).get('value', 0)],
        "Valuation_Val": [results.get('Valuation', {}).get('value', 0)],
        "GrowthAdj_Val": [results.get('Growth_Adj', {}).get('value', 0)],
        "RSI_Val": [results.get('RSI', {}).get('value', 0)],
        "Price_Dist_52W": [results.get('PriceStrength', {}).get('value', 0)],
        "Final_Score": [grand_total]
    }
    
    df_report = pd.DataFrame(data)
    eng = _get_engine()

    # ── Safe Delete to Prevent Duplicates ──
    with eng.connect() as conn:
        table_exists = conn.execute(text("SHOW TABLES LIKE 'kpi_report_card'")).fetchone()

        if table_exists:
            conn.execute(text("DELETE FROM kpi_report_card WHERE Company = :t"), {"t": ticker})
            conn.commit()
            print(f"  Existing report for {ticker} cleared.")
        else:
            print("  Initial run: Creating 'kpi_report_card' table.")

    # ── Write to SQL (ONLY ONCE) ──
    df_report.to_sql("kpi_report_card", con=eng, if_exists="append", index=False)
    print(f"  [OK] Detailed KPIs and Score ({grand_total}/10) saved to 'kpi_report_card'.")


# ── 3. Entry point ─────────────────────────────────────────────────────────────
# This block is now empty to prevent double-prompts when running test_run.py
if __name__ == "__main__":
    pass

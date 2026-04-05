# -*- coding: utf-8 -*-
import yfinance as yf
import requests
from curl_cffi.requests import Session
import time
import pandas as pd
import numpy as np
import os

session = Session(impersonate="chrome")
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
def run(ticker):
    session = Session(impersonate="chrome")
    ticker = ticker.upper().strip()
    time.sleep(2)
    ticker_obj = yf.Ticker(ticker, session = session)

    # --- 1. Define Standard Columns ---
    master_bs_cols = [
        "Total Assets", "Stockholders Equity", "Total Debt",
        "Current Liabilities", "Working Capital", "Tangible Book Value",
        "Retained Earnings"
    ]
    master_is_cols = [
        "Total Revenue", "Operating Income", "Net Income", "Tax Provision",
        "Reconciled Depreciation", "Interest Expense", "Interest Income",
        "Net Interest Income"
    ]
    master_cf_cols = [
        "Free Cash Flow", "Operating Cash Flow", "Capital Expenditure",
        "Change In Working Capital"
    ]

    # --- 2. Define Fallback Mappings (The "Smart Mapper") ---
    # If the preferred key is missing, look for these alternatives
    mapping_is = {
        "Operating Income": ["Operating Income", "Pretax Income", "EBIT", "Normalized Income"],
        "Net Income":       ["Net Income", "Net Income Common Stockholders", "Net Income from Continuing Ops"]
    }

    # --- 3. Helper Function for Safe Extraction ---
    def safe_extract(df_raw, master_cols, mapping):
        if df_raw is None or df_raw.empty:
            return pd.DataFrame(columns=master_cols)
        
        # Transpose so Dates are rows and Metrics are columns
        df_t = df_raw.T
        
        # Apply Fallbacks: Fill missing standard cols with sector-specific alternatives
        for target, fallbacks in mapping.items():
            if target not in df_t.columns or df_t[target].isnull().all():
                for fallback in fallbacks:
                    if fallback in df_t.columns and not df_t[fallback].isnull().all():
                        df_t[target] = df_t[fallback]
                        break
        
        # Reindex to your strict master list (this keeps your DB schema clean)
        df_final = df_t.reindex(columns=master_cols)
        
        # Convert to numeric, handle billions, and round
        return (df_final.apply(pd.to_numeric, errors="coerce") / 1e9).dropna(how="all").round(2)

    # --- 4. Download and Save Raw CSVs ---
    data_to_fetch = {
        "historical_prices":          ticker_obj.history(period="max"),
        "income_statement_annual":    ticker_obj.financials,
        "income_statement_quarterly": ticker_obj.quarterly_financials,
        "balance_sheet_annual":       ticker_obj.balance_sheet,
        "cashflow_annual":            ticker_obj.cashflow,
    }

    os.makedirs("data", exist_ok=True)
    print(f"--- Downloading data for {ticker} ---")
    for name, df in data_to_fetch.items():
        if df is not None and not df.empty:
            filepath = f"data/{ticker}_{name}.csv"
            df.to_csv(filepath)
            print(f"  Saved: {filepath}")
        else:
            print(f"  Warning: {name} not available.")

    # --- 5. Determine Category ---
    info     = ticker_obj.info
    industry = info.get("industry", "Unknown")
    sector   = info.get("sector",   "Unknown")
    category = "Bank" if ("Bank" in industry or "Bank" in sector) else "Non-Bank"
    print(f"  Category: {category}")

    # --- 6. Process Prices ---
    df_sp    = pd.read_csv(f"data/{ticker}_historical_prices.csv")
    df_stock = df_sp.copy()
    df_stock["Date"] = pd.to_datetime(df_stock["Date"], utc=True).dt.date
    df_stock = df_stock[["Date", "Open", "High", "Low", "Close", "Volume"]]
    df_stock = df_stock[df_stock["Date"].apply(lambda d: d.year) >= 2000]
    df_stock = df_stock.reset_index(drop=True)
    df_stock.index += 1

    # --- 7. Process Financials with Safe Mapping ---
    
    # Balance Sheet (Annual)
    df_b  = pd.read_csv(f"data/{ticker}_balance_sheet_annual.csv", index_col=0)
    df_bs = safe_extract(df_b, master_bs_cols, {}) 

    # Income Statement (Annual)
    df_iy  = pd.read_csv(f"data/{ticker}_income_statement_annual.csv", index_col=0)
    df_isy = safe_extract(df_iy, master_is_cols, mapping_is)

    # Income Statement (Quarterly)
    df_iq  = pd.read_csv(f"data/{ticker}_income_statement_quarterly.csv", index_col=0)
    df_isq = safe_extract(df_iq, master_is_cols, mapping_is)

    # Cashflow (Annual)
    df_cy  = pd.read_csv(f"data/{ticker}_cashflow_annual.csv", index_col=0)
    df_csy = safe_extract(df_cy, master_cf_cols, {})

    return {
        "ticker":   ticker,
        "category": category,
        "df_stock": df_stock,
        "df_bs":    df_bs,
        "df_isy":   df_isy,
        "df_isq":   df_isq,
        "df_csy":   df_csy,
    }

if __name__ == "__main__":
    t = input("Enter ticker: ")
    r = run(t)
    print("\n--- Processed Income Statement (Annual) ---")
    print(r["df_isy"].head())


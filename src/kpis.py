# src/kpis.py
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine

# ── DB Connection ────────────────────────────────────────────────────────────
# This block pulls directly from your Streamlit Secrets
host     = os.getenv("DB_HOST", "switchyard.proxy.rlwy.net")
user     = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASS", "renzjSvgntOxWmFngxRwzOeJCFvNMVBf")
port     = os.getenv("DB_PORT", "27808")
db_name  = os.getenv("DB_NAME", "railway")

# Added 'pool_pre_ping' to stop that InterfaceError you saw!
engine = create_engine(
    f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}",
    pool_pre_ping=True
)

def compute_fundamentals(ticker: str, category: str) -> dict:
    # ── Pull tables from MySQL ────────────────────────────────────────────────
    try:
        query = f"SELECT * FROM income_statement_annual WHERE Company = '{ticker}'"
        df_income = pd.read_sql(query, con=engine)
    except Exception as e:
        print(f"Database connection failed: {e}")
        df_income = pd.DataFrame()

# --- STEP 2: Secure the Balance Sheet Pull ---
    try:
        query_bal = f"SELECT * FROM balance_sheet_annual WHERE Company = '{ticker}'"
        df_balance = pd.read_sql(query_bal, con=engine)
    except Exception as e:
        print(f"Error fetching balance data: {e}")
        df_balance = pd.DataFrame()
    

    # ── Merge + sort oldest → newest ─────────────────────────────────────────
    df_funda = pd.merge(df_income, df_balance, on=['Date', 'Company', 'Category'], how='inner')
    df_funda['Date'] = pd.to_datetime(df_funda['Date'])
    df_funda = df_funda.sort_values('Date').reset_index(drop=True)
    
    latest = df_funda.iloc[-1]
    results = {}

    # ── KPI #1 — Efficiency (ROE/ROA) ────────────────────────────────────────
    if category == "Bank":
        val = (latest['Net Income'] / latest['Total Assets']) * 100
        score = 1.0 if val > 1.5 else 0.5 if val > 1.0 else 0
        label, thresh = "ROA", "> 1.0%"
    else:
        val = (latest['Net Income'] / latest['Stockholders Equity']) * 100
        score = 1.0 if val > 25 else 0.5 if val > 15 else 0
        label, thresh = "ROE", "> 15%"
    results['Efficiency'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.1f}%", "score": score, "threshold": thresh}

    # ── KPI #2 — Margin ──────────────────────────────────────────────────────
    if category == "Bank":
        val = (latest['Net Interest Income'] / latest['Total Assets']) * 100
        score = 1.0 if val > 4 else 0.5 if val > 3 else 0
        label, thresh = "NIM", "> 3%"
    else:
        val = (latest['Operating Income'] / latest['Total Revenue']) * 100
        score = 1.0 if val > 20 else 0.5 if val > 10 else 0
        label, thresh = "Op Margin", "> 10%"
    results['Margin'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.1f}%", "score": score, "threshold": thresh}

    # ── KPI #3 — Revenue Growth ──────────────────────────────────────────────
    if len(df_funda) > 1:
        prev_rev = df_funda.iloc[-2]['Total Revenue']
        val = ((latest['Total Revenue'] - prev_rev) / prev_rev) * 100 if prev_rev != 0 else 0
    else:
        val = 0
    score = 1.0 if val > 15 else 0.5 if val > 7 else 0
    results['RevGrowth'] = {"label": "YoY Rev Growth", "value": round(val, 2), "formatted": f"{val:.1f}%", "score": score, "threshold": "> 7%"}

    # ── KPI #4 — Solvency (Risk) ─────────────────────────────────────────────
    if category == "Bank":
        val = (latest['Stockholders Equity'] / latest['Total Assets']) * 100
        score = 1.0 if val > 12 else 0.5 if val > 8 else 0
        label, thresh = "Equity/Assets", "> 8%"
    else:
        val = latest['Total Debt'] / latest['Stockholders Equity']
        score = 1.0 if val < 0.5 else 0.5 if val < 1.5 else 0
        label, thresh = "Debt-to-Equity", "< 1.5x"
    results['Solvency'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.2f}x", "score": score, "threshold": thresh}

    # ── KPI #5 — Valuation ───────────────────────────────────────────────────
    ticker_obj = yf.Ticker(ticker)
    curr_price = ticker_obj.fast_info['last_price']
    if category == "Bank":
        val = curr_price / (latest['Tangible Book Value'] if 'Tangible Book Value' in latest else latest['Stockholders Equity'])
        score = 1.0 if val < 1.0 else 0.5 if val < 1.5 else 0
        label, thresh = "P/B Ratio", "< 1.5x"
    else:
        val = curr_price / (latest['Net Income'] / 1.0)
        score = 1.0 if 0 < val < 15 else 0.5 if val < 25 else 0
        label, thresh = "P/E Ratio", "0 - 20"
    results['Valuation'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.1f}x", "score": score, "threshold": thresh}

    # ── KPI #6 — Growth Adjusted (PEG) ───────────────────────────────────────
    if category == "Bank":
        eff = results['Efficiency']['value'] / 10
        pb = results['Valuation']['value']
        val = round(pb / eff, 2) if eff > 0 else 0
        score = 1.0 if (0 < val < 1.0) else 0.5 if val < 1.5 else 0
        label, thresh = "P/B to ROE", "< 1.0"
    else:
        rev_g = results['RevGrowth']['value']
        pe = results['Valuation']['value']
        val = round(pe / rev_g, 2) if rev_g > 0 else 0
        score = 1.0 if 0 < val < 1.0 else 0.5 if val < 2.0 else 0
        label, thresh = "PEG Ratio", "0 - 1.5"
    results['Growth_Adj'] = {"label": label, "value": val, "formatted": f"{val:.2f}", "score": score, "threshold": thresh}

    # ── KPI #7 — ROCE (Return on Capital Employed) ──────────────────────────
    if category == "Bank":
        capital_employed = latest['Total Assets']  # Banks don't report Current Liabilities
        val = (latest['Net Income'] / capital_employed) * 100 if capital_employed > 0 else 0
        score = 1.0 if val > 1.5 else 0.5 if val > 0.8 else 0
        label, thresh = "ROCE", "> 1%"
    else:
        capital_employed = latest['Total Assets'] - latest['Current Liabilities']
        val = (latest['Operating Income'] / capital_employed) * 100 if capital_employed > 0 else 0
        score = 1.0 if val > 20 else 0.5 if val > 12 else 0
        label, thresh = "ROCE", "> 12%"
    results['ROCE'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.1f}%", "score": score, "threshold": thresh}

    # ── KPI #8 — ROIC (Return on Invested Capital) ──────────────────────────
    total_debt = latest['Total Debt'] if pd.notna(latest.get('Total Debt')) else 0
    invested_capital = latest['Stockholders Equity'] + total_debt
    net_income = latest['Net Income']
    tax = latest.get('Tax Provision', 0) or 0
    pre_tax = net_income + tax
    tax_rate = max(0.0, min((tax / pre_tax) if pre_tax > 0 else 0.21, 0.50))
    nopat = latest['Operating Income'] * (1 - tax_rate)
    if category == "Bank":
        val = (net_income / invested_capital) * 100 if invested_capital > 0 else 0
        score = 1.0 if val > 12 else 0.5 if val > 8 else 0
        label, thresh = "ROIC", "> 8%"
    else:
        val = (nopat / invested_capital) * 100 if invested_capital > 0 else 0
        score = 1.0 if val > 15 else 0.5 if val > 10 else 0
        label, thresh = "ROIC", "> 10%"
    results['ROIC'] = {"label": label, "value": round(val, 2), "formatted": f"{val:.1f}%", "score": score, "threshold": thresh}

    # ── Print all 8 fundamental KPIs ─────────────────────────────────────────
    print(f"  KPI #1 {results['Efficiency']['label']} -> {results['Efficiency']['formatted']} | Score: {results['Efficiency']['score']}")
    print(f"  KPI #2 {results['Margin']['label']} -> {results['Margin']['formatted']} | Score: {results['Margin']['score']}")
    print(f"  KPI #3 {results['RevGrowth']['label']} -> {results['RevGrowth']['formatted']} | Score: {results['RevGrowth']['score']}")
    print(f"  KPI #4 {results['Solvency']['label']} -> {results['Solvency']['formatted']} | Score: {results['Solvency']['score']}")
    print(f"  KPI #5 {results['Valuation']['label']} -> {results['Valuation']['formatted']} | Score: {results['Valuation']['score']}")
    print(f"  KPI #6 {results['Growth_Adj']['label']} -> {results['Growth_Adj']['formatted']} | Score: {results['Growth_Adj']['score']}")
    print(f"  KPI #7 {results['ROCE']['label']} -> {results['ROCE']['formatted']} | Score: {results['ROCE']['score']}")
    print(f"  KPI #8 {results['ROIC']['label']} -> {results['ROIC']['formatted']} | Score: {results['ROIC']['score']}")

    results['Fundamental_Total'] = sum(item['score'] for item in results.values() if isinstance(item, dict) and 'score' in item)
    return results



def compute_technicals(df_stock) -> dict:
    # ── 1. PREPARE THE DATA ──────────────────────────────────────────────────
    if len(df_stock) < 200:
        return {"Error": "Insufficient data for Technical Analysis"}

    df_stock['SMA_200'] = df_stock['Close'].rolling(window=200).mean()
    df_stock['SMA_50']  = df_stock['Close'].rolling(window=50).mean()
    
    delta = df_stock['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_stock['RSI'] = 100 - (100 / (1 + rs))

    latest = df_stock.iloc[-1]
    curr_price = latest['Close']
    
    high_52w = df_stock['High'].tail(252).max()
    dist_from_high = (curr_price / high_52w) - 1

    results = {}

    # ── KPI #7 — Long-Term Trend (SMA 200) ────────────────────────────────────
    # Dynamic: 1.0 if Price is above SMA 200 (Uptrend)
    score_7 = 1.0 if curr_price > latest['SMA_200'] else 0
    results['LongTermTrend'] = {
        "label"    : "Price > 200-Day SMA",
        "value"    : round(latest['SMA_200'], 2),
        "formatted": "Bullish" if curr_price > latest['SMA_200'] else "Bearish",
        "threshold": "Price > SMA200",
        "score"    : score_7,
    }

    # ── KPI #8 — Medium-Term Trend (Golden Cross) ─────────────────────────────
    # Dynamic: 1.0 if 50 SMA is above 200 SMA
    score_8 = 1.0 if latest['SMA_50'] > latest['SMA_200'] else 0
    results['MediumTermTrend'] = {
        "label"    : "50-Day > 200-Day (Golden Cross)",
        "value"    : round(latest['SMA_50'], 2),
        "formatted": "Yes" if latest['SMA_50'] > latest['SMA_200'] else "No",
        "threshold": "SMA50 > SMA200",
        "score"    : score_8,
    }

    # ── KPI #9 — RSI Momentum ─────────────────────────────────────────────────
    # Dynamic: 1.0 for Oversold/Value (RSI < 40), 0.5 for Neutral (40-60)
    rsi_val = latest['RSI']
    score_9 = 1.0 if rsi_val < 40 else 0.5 if rsi_val < 65 else 0
    results['RSI'] = {
        "label"    : "RSI (14-Day)",
        "value"    : round(rsi_val, 2),
        "formatted": f"{rsi_val:.1f}",
        "threshold": "30 < RSI < 70",
        "score"    : score_9,
    }

    # ── KPI #10 — Price Strength (Value/Dip Logic) ──────────────────────────
    # Dynamic: 1.0 if dip > 20% (Great Value), 0.5 if dip > 10% (Good Value)
    score_10 = 1.0 if dist_from_high < -0.20 else 0.5 if dist_from_high < -0.10 else 0
    results['PriceStrength'] = {
        "label"    : "Value Pullback (Dip)",
        "value"    : round(dist_from_high * 100, 2),
        "formatted": f"{dist_from_high*100:.1f}% from high",
        "threshold": "< -10%", 
        "score"    : score_10,
    }    

    # ── YOUR ORIGINAL PRINT LOGIC (Kept Exactly the Same) ───────────────────
    print(f"  KPI #9  {results['LongTermTrend']['label']:<30} -> {results['LongTermTrend']['formatted']:<12} | Score: {results['LongTermTrend']['score']}")
    print(f"  KPI #10 {results['MediumTermTrend']['label']:<30} -> {results['MediumTermTrend']['formatted']:<12} | Score: {results['MediumTermTrend']['score']}")
    print(f"  KPI #11 {results['RSI']['label']:<30} -> {results['RSI']['formatted']:<12} | Score: {results['RSI']['score']}")
    print(f"  KPI #12 {results['PriceStrength']['label']:<30} -> {results['PriceStrength']['formatted']:<12} | Score: {results['PriceStrength']['score']}")

    return results

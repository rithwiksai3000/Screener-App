# test_run.py (ROOT FOLDER)
# Now we can import them directly
# test_run.py (ROOT FOLDER)
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Add upsert_kpi_report to this line
from src.ingestion import ingest, upsert_kpi_report 
from src.kpis import compute_fundamentals, compute_technicals 
from src.Migration import run

def main():
    ticker = input("Enter ticker (e.g., TSLA or JPM): ").upper().strip()
    
    # 1. Ingest Data
    print(f"\n--- [1/3] Updating Database for {ticker} ---")
    ingest(ticker)
    
    # 2. Get Data & Category
    temp_data = run(ticker)
    category = temp_data["category"]
    
    # 3. Compute Both Pillars
    print(f"--- [2/3] Calculating Fundamentals & Technicals ---")
    funda_results = compute_fundamentals(ticker, category)
    tech_results = compute_technicals(temp_data["df_stock"])
    
    # Combine results
    funda_results.update(tech_results)
    results = funda_results
    
    # 4. Print Report (The loop we wrote earlier goes here)
    print(f"\n--- [3/3] {ticker} 10-POINT ENGINE REPORT ---")
    # ... (your print loop) ...
    
    # 5. Final Verdict & Total Score calculation
    total_score = sum(item['score'] for item in results.values() if isinstance(item, dict) and 'score' in item)
    print(f"GRAND TOTAL SCORE: {total_score}/10")

    # ── 6. Save the analysis to the Database ─────────────────────────────────
    # PLACE IT HERE
    upsert_kpi_report(ticker, category, results)
    print(f"\n✅ Analysis for {ticker} is now stored in MySQL.")

if __name__ == "__main__":
    main()
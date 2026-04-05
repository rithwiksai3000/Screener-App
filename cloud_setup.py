import sqlalchemy
from sqlalchemy import create_engine, text

# --- EXACT RAILWAY CREDENTIALS ---
USER = "root"
PASS = "renzjSvgntOxWmFngxRwzOeJCFvNMVBf"
HOST = "switchyard.proxy.rlwy.net"
PORT = "27808"
DB   = "railway"

# Using mysql+mysqlconnector for compatibility
engine = create_engine(f"mysql+mysqlconnector://{USER}:{PASS}@{HOST}:{PORT}/{DB}")

tables = [
    "CREATE TABLE IF NOT EXISTS kpi_report_card (Date DATE, Company VARCHAR(20), Category VARCHAR(50), Efficiency_Val FLOAT, Margin_Val FLOAT, RevGrowth_Val FLOAT, Solvency_Val FLOAT, Valuation_Val FLOAT, GrowthAdj_Val FLOAT, RSI_Val FLOAT, Price_Dist_52W FLOAT, Final_Score FLOAT)",
    "CREATE TABLE IF NOT EXISTS balance_sheet_annual (Date DATE, Company VARCHAR(20), Category VARCHAR(50))",
    "CREATE TABLE IF NOT EXISTS income_statement_annual (Date DATE, Company VARCHAR(20), Category VARCHAR(50))",
    "CREATE TABLE IF NOT EXISTS cash_flow_annual (Date DATE, Company VARCHAR(20), Category VARCHAR(50))"
]

print("Connecting to Railway...")
try:
    with engine.connect() as conn:
        for table_cmd in tables:
            conn.execute(text(table_cmd))
            print(f"Verified Table: {table_cmd.split(' ')[5]}")
        conn.commit()
    print("\n[SUCCESS] Cloud Database is now ready!")
except Exception as e:
    print(f"\n[ERROR] Still can't connect: {e}")
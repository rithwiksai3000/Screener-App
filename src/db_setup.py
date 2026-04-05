# src/db_setup.py
# Creates all new tables needed for the screener platform.
# Run this ONCE before running the batch scanner.

from sqlalchemy import create_engine, text

DB_CONFIG = {
    "user": "root",
    "password": "Bank1234",
    "host": "localhost",
    "port": "3306",
    "db": "bank_data",
}

engine = create_engine(
    f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['db']}"
)

TABLES = {
    "daily_kpi_snapshot": """
        CREATE TABLE IF NOT EXISTS daily_kpi_snapshot (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            scan_date       DATE NOT NULL,
            ticker          VARCHAR(20) NOT NULL,
            category        VARCHAR(20),

            -- Fundamental KPIs (6)
            efficiency_val      FLOAT,  efficiency_score    FLOAT,
            margin_val          FLOAT,  margin_score        FLOAT,
            rev_growth_val      FLOAT,  rev_growth_score    FLOAT,
            solvency_val        FLOAT,  solvency_score      FLOAT,
            valuation_val       FLOAT,  valuation_score     FLOAT,
            growth_adj_val      FLOAT,  growth_adj_score    FLOAT,

            -- Technical KPIs (4)
            rsi_val                 FLOAT,  rsi_score               FLOAT,
            long_term_trend         VARCHAR(10),  long_term_trend_score   FLOAT,
            medium_term_trend       VARCHAR(5),   medium_term_trend_score FLOAT,
            price_strength_val      FLOAT,  price_strength_score    FLOAT,

            -- Aggregate Scores
            fundamental_score   FLOAT,
            technical_score     FLOAT,
            total_score         FLOAT,

            -- Price Snapshot
            current_price   FLOAT,
            sma_50          FLOAT,
            sma_200         FLOAT,
            high_52w        FLOAT,

            -- Metadata
            scan_status     VARCHAR(10) DEFAULT 'success',
            error_msg       TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

            UNIQUE KEY uq_ticker_date (ticker, scan_date)
        )
    """,

    "watchlist": """
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            user_id     VARCHAR(50)  NOT NULL DEFAULT 'default',
            ticker      VARCHAR(20)  NOT NULL,
            added_date  DATE,
            notes       TEXT,
            UNIQUE KEY uq_user_ticker (user_id, ticker)
        )
    """,

    "alerts": """
        CREATE TABLE IF NOT EXISTS alerts (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            user_id          VARCHAR(50) NOT NULL DEFAULT 'default',
            ticker           VARCHAR(20),
            field_name       VARCHAR(50),
            operator         VARCHAR(5),
            threshold_value  FLOAT,
            is_active        BOOLEAN DEFAULT TRUE,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_triggered   DATETIME
        )
    """,

    "scan_log": """
        CREATE TABLE IF NOT EXISTS scan_log (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            run_date            DATETIME NOT NULL,
            total_scanned       INT DEFAULT 0,
            total_succeeded     INT DEFAULT 0,
            total_failed        INT DEFAULT 0,
            failed_tickers      TEXT,
            duration_seconds    FLOAT,
            notes               TEXT
        )
    """,
}


def setup_database():
    """Creates all screener tables in the existing bank_data database."""
    with engine.connect() as conn:
        for table_name, ddl in TABLES.items():
            conn.execute(text(ddl))
            conn.commit()
            print(f"  [DB] Table '{table_name}' — OK")
    print("\n[DB] All screener tables are ready.")


if __name__ == "__main__":
    setup_database()

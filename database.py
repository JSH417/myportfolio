import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "portfolio.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Assets table (보유 자산 - ETF, 주식, 달러 RP, 현금)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,                 -- 예: 'KODEX 200', 'Vanguard S&P 500 ETF', '외화RP'
        asset_type TEXT NOT NULL,          -- 'KR_ETF', 'US_ETF', 'USD_RP', 'CASH_KRW', 'CASH_USD'
        currency TEXT NOT NULL,            -- 'KRW' or 'USD'
        quantity REAL NOT NULL DEFAULT 0,  -- 보유 수량 (달러RP인 경우 USD 금액 자체)
        avg_price REAL NOT NULL DEFAULT 0, -- 평균 매입단가 (KRW 종목은 원, USD 종목은 달러, RP는 1.0 또는 매수가)
        current_price REAL DEFAULT 0,      -- 최신 현재가 (USD 종목은 달러, KRW 종목은 원)
        target_weight REAL DEFAULT 0,      -- 목표 비중 (%)
        dividend_yield REAL DEFAULT 0,     -- 연간 예상 배당률 (%)
        div_frequency TEXT DEFAULT 'QUARTERLY', -- 'MONTHLY', 'QUARTERLY', 'YEARLY', 'NONE'
        account TEXT DEFAULT 'ISA',        -- 'CMA', 'ISA', '연금저축', '달러RP'
        note TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, account)            -- 계좌별로 동일 종목 복수 보유 허용
    );
    """)

    # 계좌별 동일 종목 복수 보유 허용을 위한 복합 유니크(symbol, account) 마이그레이션
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='assets'")
    table_sql_row = cursor.fetchone()
    if table_sql_row:
        table_sql = table_sql_row[0]
        if "UNIQUE(symbol, account)" not in table_sql and "UNIQUE (symbol, account)" not in table_sql:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                currency TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                avg_price REAL NOT NULL DEFAULT 0,
                current_price REAL DEFAULT 0,
                target_weight REAL DEFAULT 0,
                dividend_yield REAL DEFAULT 0,
                div_frequency TEXT DEFAULT 'QUARTERLY',
                account TEXT DEFAULT 'ISA',
                note TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, account)
            );
            """)
            cursor.execute("""
            INSERT OR IGNORE INTO assets_v2 
            SELECT id, symbol, name, asset_type, currency, quantity, avg_price, current_price, target_weight, dividend_yield, div_frequency, COALESCE(account, 'ISA'), note, updated_at 
            FROM assets;
            """)
            cursor.execute("DROP TABLE assets;")
            cursor.execute("ALTER TABLE assets_v2 RENAME TO assets;")

    # 2. Transactions table (매매 및 입출금 내역)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER,
        symbol TEXT NOT NULL,
        trade_type TEXT NOT NULL,          -- 'BUY', 'SELL', 'DEPOSIT', 'WITHDRAW', 'INTEREST'
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        currency TEXT NOT NULL,            -- 'KRW' or 'USD'
        exchange_rate REAL DEFAULT 1.0,    -- 거래 당시 환율 (선택)
        trade_date TEXT NOT NULL,          -- 'YYYY-MM-DD'
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
    );
    """)

    # 3. Exchange Rate Cache (환율 캐시)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exchange_rates (
        currency_pair TEXT PRIMARY KEY,    -- 'USD/KRW'
        rate REAL NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

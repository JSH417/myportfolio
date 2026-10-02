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
        symbol TEXT NOT NULL UNIQUE,       -- 예: '069500'(KODEX 200), 'VOO', 'USD_RP'(달러RP)
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
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 계좌 컬럼 자동 마이그레이션 확인
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(assets)").fetchall()]
    if "account" not in cols:
        cursor.execute("ALTER TABLE assets ADD COLUMN account TEXT DEFAULT 'ISA'")

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

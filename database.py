import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "portfolio.db")

# 복구용 기본 자산 목록 (DB가 비어있을 경우 자동 시딩)
DEFAULT_ASSETS = [
    ("360750", "TIGER 미국배당다우존스", "KR_ETF", "KRW", 1.0, 15220.0, 14055.0, 0.0, 3.8, "MONTHLY", "연금저축"),
    ("360200", "TIGER 미국S&P500", "KR_ETF", "KRW", 294.0, 27196.0, 25780.0, 0.0, 1.5, "QUARTERLY", "ISA"),
    ("379810", "KODEX 미국나스닥100TR", "KR_ETF", "KRW", 93.0, 27721.0, 27385.0, 0.0, 0.5, "QUARTERLY", "ISA"),
    ("411060", "ACE KRX금현물", "KR_ETF", "KRW", 22.0, 26063.0, 25515.0, 0.0, 0.0, "NONE", "ISA"),
    ("453850", "ACE 미국30년국채액티브", "KR_ETF", "KRW", 0.0, 8270.0, 8270.0, 20.0, 4.2, "MONTHLY", "ISA"),
    ("360750", "TIGER 미국배당다우존스", "KR_ETF", "KRW", 217.0, 14543.0, 14055.0, 0.0, 3.8, "MONTHLY", "ISA"),
    ("497880", "SOL CD금리&머니마켓액티브", "KR_ETF", "KRW", 78.0, 50119.0, 50045.0, 0.0, 3.5, "MONTHLY", "ISA"),
    ("USD_RP", "온라인전용_수시RP(USD)", "USD_RP", "USD", 56.0, 1.0, 1.0, 0.0, 3.35, "MONTHLY", "달러RP"),
    ("CASH_KRW", "발행어음 CMA", "CASH_KRW", "KRW", 2350000.0, 1.0, 1.0, 0.0, 2.60, "MONTHLY", "CMA"),
    ("CASH_KRW", "원화 예수금", "CASH_KRW", "KRW", 26038.0, 1.0, 1.0, 0.0, 0.0, "NONE", "ISA")
]

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        pg_query = query.replace('?', '%s')
        if params is not None:
            return self._cursor.execute(pg_query, params)
        return self._cursor.execute(pg_query)

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        import psycopg2.extras
        return PostgresCursorWrapper(self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url and (db_url.startswith("postgres://") or db_url.startswith("postgresql://")):
        import psycopg2
        fixed_url = db_url.replace("postgres://", "postgresql://", 1)
        raw_conn = psycopg2.connect(fixed_url)
        return PostgresConnectionWrapper(raw_conn)
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url and (db_url.startswith("postgres://") or db_url.startswith("postgresql://")):
        import psycopg2
        fixed_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(fixed_url)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            currency TEXT NOT NULL,
            quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
            avg_price DOUBLE PRECISION NOT NULL DEFAULT 0,
            current_price DOUBLE PRECISION DEFAULT 0,
            target_weight DOUBLE PRECISION DEFAULT 0,
            dividend_yield DOUBLE PRECISION DEFAULT 0,
            div_frequency TEXT DEFAULT 'QUARTERLY',
            account TEXT DEFAULT 'ISA',
            note TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, account)
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id SERIAL PRIMARY KEY,
            record_date TEXT NOT NULL UNIQUE,
            total_val_krw DOUBLE PRECISION NOT NULL,
            total_val_usd DOUBLE PRECISION NOT NULL,
            total_invested_krw DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency_pair TEXT PRIMARY KEY,
            rate DOUBLE PRECISION NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()

        # 데이터가 비어있으면 기본 복구 데이터로 자동 시딩
        c.execute("SELECT COUNT(*) FROM assets")
        count = c.fetchone()[0]
        if count == 0:
            for a in DEFAULT_ASSETS:
                c.execute("""
                    INSERT INTO assets (symbol, name, asset_type, currency, quantity, avg_price, current_price, target_weight, dividend_yield, div_frequency, account)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(symbol, account) DO NOTHING
                """, a)
            conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
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
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT NOT NULL UNIQUE,
            total_val_krw REAL NOT NULL,
            total_val_usd REAL NOT NULL,
            total_invested_krw REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency_pair TEXT PRIMARY KEY,
            rate REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM assets")
        count = cursor.fetchone()[0]
        if count == 0:
            for a in DEFAULT_ASSETS:
                cursor.execute("""
                    INSERT OR IGNORE INTO assets (symbol, name, asset_type, currency, quantity, avg_price, current_price, target_weight, dividend_yield, div_frequency, account)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, a)
            conn.commit()
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

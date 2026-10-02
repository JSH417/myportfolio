import sqlite3

conn = sqlite3.connect('portfolio.db')
c = conn.cursor()

# 1. assets 테이블에 실제 캡처 데이터 반영 (56 USD, 연 3.35%)
c.execute("""
    UPDATE assets 
    SET name = '온라인전용_수시RP(USD)',
        quantity = 56.0,
        avg_price = 1.0,
        current_price = 1.0,
        dividend_yield = 3.35,
        div_frequency = 'MONTHLY'
    WHERE symbol = 'USD_RP'
""")

# 2. 계좌 총 자산 변화 추이 기록용 history 테이블 생성
c.execute("""
CREATE TABLE IF NOT EXISTS portfolio_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL,          -- 'YYYY-MM-DD'
    total_val_krw REAL NOT NULL,
    total_val_usd REAL NOT NULL,
    total_invested_krw REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# 3. 테스트 및 시각화를 위한 최근 30일 자산 변화 샘플 히스토리 생성 (초기 데이터)
c.execute("SELECT COUNT(*) FROM portfolio_history")
if c.fetchone()[0] == 0:
    import datetime
    today = datetime.date.today()
    # 최근 14일간 자산 변화 추이 예시 (점진적 우상향)
    base_krw = 23500000.0
    for i in range(14, -1, -1):
        dt = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        daily_val = base_krw + (14 - i) * 65000 + (i % 3) * 20000
        daily_inv = 23000000.0 + (14 - i) * 40000
        c.execute("""
            INSERT INTO portfolio_history (record_date, total_val_krw, total_val_usd, total_invested_krw)
            VALUES (?, ?, ?, ?)
        """, (dt, daily_val, daily_val / 1380.0, daily_inv))

conn.commit()
conn.close()
print("RP updated & portfolio_history initialized successfully")

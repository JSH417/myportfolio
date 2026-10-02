import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "portfolio.db")

def seed_sample_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 샘플 데이터: 한국 ETF, 미국 ETF, 달러 RP
    samples = [
        ("069500", "KODEX 200", "KR_ETF", "KRW", 150, 36200, 37500, "국내 대형주 대표 ETF"),
        ("379800", "TIGER 미국S&P500", "KR_ETF", "KRW", 200, 18100, 19400, "국내 상장 미국 S&P500"),
        ("VOO", "Vanguard S&P 500 ETF", "US_ETF", "USD", 15, 480.5, 520.0, "미국 직투 S&P500 ETF"),
        ("SCHD", "Schwab US Dividend Equity ETF", "US_ETF", "USD", 50, 78.2, 83.1, "미국 배당성장 ETF"),
        ("USD_RP", "외화 RP (수시)", "USD_RP", "USD", 5000.0, 1.0, 1.0, "모으고 있는 달러 RP")
    ]
    
    for s in samples:
        c.execute("""
            INSERT INTO assets (symbol, name, asset_type, currency, quantity, avg_price, current_price, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO NOTHING
        """, s)
        
    conn.commit()
    conn.close()
    print("샘플 데이터 등록 완료.")

if __name__ == "__main__":
    seed_sample_data()

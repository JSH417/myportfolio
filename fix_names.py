import sqlite3

conn = sqlite3.connect('portfolio.db')
c = conn.cursor()
c.execute("UPDATE assets SET name = ? WHERE symbol = ?", ('온라인전용_수시RP(USD)', 'USD_RP'))
c.execute("UPDATE assets SET name = ? WHERE symbol = ?", ('TIGER 미국S&P500', '379800'))
conn.commit()
conn.close()
print("Cleaned up successfully")

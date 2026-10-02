import sqlite3

conn = sqlite3.connect('portfolio.db')
c = conn.cursor()
cols = [r[1] for r in c.execute('PRAGMA table_info(assets)').fetchall()]
for col, ctype in [('target_weight', 'REAL DEFAULT 0'), ('dividend_yield', 'REAL DEFAULT 0'), ('div_frequency', 'TEXT DEFAULT "QUARTERLY"')]:
    if col not in cols:
        c.execute(f'ALTER TABLE assets ADD COLUMN {col} {ctype}')
conn.commit()

targets = [
    (15.0, 1.6, 'QUARTERLY', '069500'),
    (25.0, 1.4, 'MONTHLY', '379800'),
    (25.0, 1.4, 'QUARTERLY', 'VOO'),
    (15.0, 3.5, 'QUARTERLY', 'SCHD'),
    (20.0, 4.2, 'MONTHLY', 'USD_RP')
]

for tw, dy, df, sym in targets:
    c.execute("""
        UPDATE assets SET target_weight = ?, dividend_yield = ?, div_frequency = ? WHERE symbol = ?
    """, (tw, dy, df, sym))

conn.commit()
conn.close()
print("DB updated successfully")

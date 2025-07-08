import sqlite3

DATABASE = "orders.db"

conn = sqlite3.connect(DATABASE)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    summary TEXT,
    total INTEGER,
    payment_reference TEXT,
    delivery TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print("✅ 'orders' table created successfully.")

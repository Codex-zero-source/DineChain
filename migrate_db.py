import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to SQLite
db_path = "orders.db"
sqlite_conn = sqlite3.connect(db_path)
sqlite_cursor = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_url = os.getenv("DATABASE_URL")
pg_conn = psycopg2.connect(pg_url)
pg_cursor = pg_conn.cursor()

# Create table in PostgreSQL
pg_cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT,
    summary TEXT,
    delivery TEXT,
    total INTEGER,
    paid BOOLEAN,
    reference TEXT,
    timestamp TEXT
)
""")
pg_conn.commit()

# Read all rows from SQLite
sqlite_cursor.execute("SELECT id, chat_id, summary, delivery, total, paid, reference, timestamp FROM orders")
rows = sqlite_cursor.fetchall()

# Insert into PostgreSQL
for row in rows:
    pg_cursor.execute(
        """
        INSERT INTO orders (id, chat_id, summary, delivery, total, paid, reference, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        row
    )
pg_conn.commit()

print(f"✅ Migrated {len(rows)} orders to PostgreSQL")

sqlite_conn.close()
pg_conn.close()

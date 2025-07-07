# migrate.py
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

# ==========================
# admin.py (Blueprint Module)
# ==========================

from flask import Blueprint, render_template_string, g
import sqlite3
import os
import psycopg2
import psycopg2.extras

admin_bp = Blueprint("admin", __name__)
DATABASE_URL = os.getenv("DATABASE_URL")
IS_SQLITE = not DATABASE_URL or DATABASE_URL.endswith(".db")

TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Orders Admin</title></head>
<body>
<h2>Orders</h2>
<table border="1" cellpadding="8">
<tr><th>ID</th><th>Chat ID</th><th>Summary</th><th>Delivery</th><th>Total</th><th>Paid</th><th>Ref</th><th>Time</th></tr>
{% for order in orders %}
<tr>
<td>{{ order['id'] }}</td><td>{{ order['chat_id'] }}</td>
<td>{{ order['summary'] }}</td><td>{{ order['delivery'] }}</td>
<td>{{ order['total'] }}</td><td>{{ '✅' if order['paid'] else '❌' }}</td>
<td>{{ order['reference'] or '-' }}</td><td>{{ order['timestamp'] }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@admin_bp.route("/admin")
def admin_dashboard():
    if IS_SQLITE:
        conn = sqlite3.connect("orders.db")
        conn.row_factory = sqlite3.Row
    else:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY timestamp DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template_string(TEMPLATE, orders=orders)

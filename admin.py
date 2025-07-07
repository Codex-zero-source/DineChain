# admin.py
from flask import Blueprint, render_template_string, g
import sqlite3
import os

admin_bp = Blueprint("admin", __name__)
DATABASE = os.path.join(os.path.dirname(__file__), 'orders.db')

# HTML template
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Restaurant Orders Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        h2 { color: #333; }
    </style>
</head>
<body>
    <h2>Orders Dashboard</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Chat ID</th>
            <th>Order Summary</th>
            <th>Delivery Info</th>
            <th>Total (₦)</th>
            <th>Paid</th>
            <th>Reference</th>
            <th>Timestamp</th>
        </tr>
        {% for order in orders %}
        <tr>
            <td>{{ order["id"] }}</td>
            <td>{{ order["chat_id"] }}</td>
            <td>{{ order["summary"] }}</td>
            <td>{{ order["delivery"] }}</td>
            <td>{{ order["total"] }}</td>
            <td>{{ '✅' if order["paid"] else '❌' }}</td>
            <td>{{ order["reference"] or '-' }}</td>
            <td>{{ order.get("timestamp", '-') }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

# DB connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@admin_bp.teardown_app_request
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@admin_bp.route("/admin")
def dashboard():
    cur = get_db().cursor()
    try:
        cur.execute("SELECT * FROM orders ORDER BY timestamp DESC")
    except sqlite3.OperationalError:
        cur.execute("SELECT * FROM orders")  # fallback if timestamp column doesn't exist
    orders = cur.fetchall()
    return render_template_string(TEMPLATE, orders=orders)

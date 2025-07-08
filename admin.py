from flask import Blueprint, render_template_string, request, abort
import os
import psycopg
from psycopg.rows import dict_row
from psycopg.pool import ConnectionPool

admin_bp = Blueprint("admin", __name__)
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

# Create a connection pool
pool = ConnectionPool(conninfo=DATABASE_URL)

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
    # Simple token-based authentication
    provided_token = request.args.get("token")
    if not ADMIN_TOKEN or provided_token != ADMIN_TOKEN:
        abort(401) # Unauthorized

    with pool.getconn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM orders ORDER BY timestamp DESC")
            orders = cur.fetchall()
    return render_template_string(TEMPLATE, orders=orders)

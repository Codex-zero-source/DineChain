from flask import Blueprint, render_template_string
import os
import psycopg2
import psycopg2.extras

admin_bp = Blueprint("admin", __name__)
DATABASE_URL = os.getenv("DATABASE_URL")

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
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY timestamp DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template_string(TEMPLATE, orders=orders)

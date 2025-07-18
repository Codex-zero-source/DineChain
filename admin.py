from flask import Blueprint, render_template_string, request, abort
import os
from orders import get_db_conn

admin_bp = Blueprint("admin", __name__)

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Orders Admin</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 {
            text-align: center;
            color: #5a67d8;
        }
        #searchInput {
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        thead tr {
            background-color: #5a67d8;
            color: white;
            text-align: left;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        tbody tr:hover {
            background-color: #f5f5f5;
        }
        tbody tr:nth-child(even) {
            background-color: #fafafa;
        }
        .private-key {
            display: none;
        }
    </style>
</head>
<body>
<div class="container">
    <h2>Admin - Orders</h2>
    <input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Search for orders by any field...">
    <table id="ordersTable">
        <thead>
            <tr><th>ID</th><th>Chat ID</th><th>Customer Name</th><th>Platform</th><th>Summary</th><th>Delivery</th><th>Total</th><th>Paid</th><th>Ref</th><th>Private Key</th><th>Time</th></tr>
        </thead>
        <tbody>
        {% for order in orders %}
        <tr>
            <td>{{ order['id'] }}</td><td>{{ order['chat_id'] }}</td>
            <td>{{ order['customer_name'] }}</td><td>{{ order['platform'] }}</td>
            <td>{{ order['summary'] }}</td><td>{{ order['delivery'] }}</td>
            <td>{{ order['total'] }}</td><td>{{ '✅' if order['paid'] else '❌' }}</td>
            <td>{{ order['reference'] or '-' }}</td>
            <td>
                {% if order['payment_method'] == 'crypto' and order['paid'] and order['private_key'] %}
                    <button onclick="togglePrivateKey(this)">Show</button>
                    <span class="private-key">{{ order['private_key'] }}</span>
                {% else %}
                    -
                {% endif %}
            </td>
            <td>{{ order['timestamp'] }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</div>

<script>
function searchTable() {
    var input, filter, table, tbody, tr, td, i, j, txtValue;
    input = document.getElementById("searchInput");
    filter = input.value.toUpperCase();
    table = document.getElementById("ordersTable");
    tbody = table.getElementsByTagName("tbody")[0];
    tr = tbody.getElementsByTagName("tr");

    for (i = 0; i < tr.length; i++) {
        tr[i].style.display = "none";
        td = tr[i].getElementsByTagName("td");
        for (j = 0; j < td.length; j++) {
            if (td[j]) {
                txtValue = td[j].textContent || td[j].innerText;
                if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                    break;
                }
            }
        }
    }
}

function togglePrivateKey(button) {
    var keySpan = button.nextElementSibling;
    if (keySpan.style.display === 'none') {
        keySpan.style.display = 'inline';
        button.textContent = 'Hide';
    } else {
        keySpan.style.display = 'none';
        button.textContent = 'Show';
    }
}
</script>

</body>
</html>
"""

@admin_bp.route("/admin")
async def admin_dashboard():
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT * FROM orders ORDER BY timestamp DESC")
        orders = await cursor.fetchall()
    return render_template_string(TEMPLATE, orders=orders)

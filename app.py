import os
import json
import re
import sqlite3
import openai
import requests
from flask import Flask, request, g
from dotenv import load_dotenv
from paystack import create_paystack_link
from set_webhook import set_webhook
from admin import admin_bp

load_dotenv()
app = Flask(__name__)
app.register_blueprint(admin_bp)


# Load menu.json
with open("menu.json") as f:
    MENU = json.load(f)

def format_menu(menu):
    lines = []
    for category, items in menu.items():
        line = ", ".join([f"{item} (₦{price})" for item, price in items.items()])
        lines.append(f"{category.capitalize()}: {line}")
    return "\n".join(lines)

MENU_TEXT = format_menu(MENU)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

client = openai.OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

DATABASE = "orders.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                order_summary TEXT,
                delivery TEXT,
                total INTEGER,
                reference TEXT,
                paid INTEGER DEFAULT 0
            )
        """)
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

@app.route("/", methods=["GET"])
def home():
    return "Bot is alive ✅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    message = data.get("message")
    if not message or "text" not in message:
        return "ignored", 200

    chat_id = str(message["chat"]["id"])
    user_text = message["text"]

    db = get_db()
    cursor = db.execute("SELECT * FROM orders WHERE chat_id = ? AND paid = 0", (chat_id,))
    unpaid_order = cursor.fetchone()

    if unpaid_order:
        send_message(chat_id, "⚠️ You have an unpaid order. Would you like to add to it or start a new order? Please reply with 'add' or 'restart'.")
        return "awaiting clarification", 200

    history = [
        {
            "role": "system",
            "content": f"""
You are a polite and helpful restaurant customer service bot.
You help customers:
- Place orders
- Confirm sizes and quantity
- Calculate total based on this menu:
{MENU_TEXT}

Each price is for 1 portion, and all prices are in naira.
After confirming order, ask if customer will:
1. Dine in (ask for table number)
2. Do home delivery (ask for delivery address)

Format the total like 'Total: ₦3000' and be concise.
"""
        },
        {"role": "user", "content": user_text}
    ]

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=history,
        temperature=0.7,
        max_tokens=300
    )

    assistant_reply = response.choices[0].message.content or ""
    send_message(chat_id, assistant_reply)

    total_match = re.search(r"total[:\s]*₦?(\d+)", assistant_reply, re.IGNORECASE)
    if total_match:
        total = int(total_match.group(1))
        order_summary = assistant_reply.split("complete payment")[0].strip()

        delivery_match = re.search(r"(table\s*number\s*:?.+|home delivery to .+)", user_text, re.IGNORECASE)
        delivery_info = delivery_match.group(0).strip() if delivery_match else "Not provided"

        payment_link, reference = create_paystack_link("customer@example.com", total, chat_id, order_summary, delivery_info)

        db.execute("""
            INSERT INTO orders (chat_id, order_summary, delivery, total, reference)
            VALUES (?, ?, ?, ?, ?)
        """, (chat_id, order_summary, delivery_info, total, reference))
        db.commit()

        send_message(chat_id, f"\nPlease complete payment here: {payment_link}")

    return "ok", 200

@app.route("/verify", methods=["GET"])
def verify_payment():
    reference = request.args.get("reference")
    if not reference:
        return "Missing reference", 400

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    data = r.json()

    if data["status"] and data["data"]["status"] == "success":
        chat_id = str(data["data"]["metadata"].get("chat_id"))
        db = get_db()
        db.execute("UPDATE orders SET paid = 1 WHERE reference = ?", (reference,))
        db.commit()

        order = db.execute("SELECT order_summary, delivery FROM orders WHERE reference = ?", (reference,)).fetchone()

        send_message(chat_id, "✅ Order confirmed! Thank you for your payment.")
        send_message(KITCHEN_CHAT_ID, f"food: {order[0]} | sum: ₦{data['data']['amount']//100} | {order[1]}")
        return "Payment confirmed", 200

    else:
        chat_id = str(data.get("data", {}).get("metadata", {}).get("chat_id"))
        if chat_id:
            send_message(chat_id, "❌ Payment failed. Please try again.")
        return "Payment failed", 400

if __name__ == "__main__":
    init_db()
    set_webhook()
    app.run(host="0.0.0.0", port=5000, debug=True)

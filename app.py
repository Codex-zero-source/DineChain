import os
import json
import requests
import re
from flask import Flask, request
from dotenv import load_dotenv
from paystack import create_paystack_link
from set_webhook import set_webhook
from admin import admin_bp
from openai import OpenAI
from orders import get_db_conn, init_db

load_dotenv()
app = Flask(__name__)
app.register_blueprint(admin_bp)

# Initialize the database
init_db()

# Load menu
with open("menu.json") as f:
    MENU = json.load(f)

def format_menu(menu):
    lines = []
    for category, items in menu.items():
        line = ", ".join([f"{item} (₦{price})" for item, price in items.items()])
        lines.append(f"{category.capitalize()}: {line}")
    return "\n".join(lines)

MENU_TEXT = format_menu(MENU)

# 🔐 Environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

client = OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

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

    conn = get_db_conn()
    cursor = conn.cursor()

    # Check for unpaid orders
    cursor.execute("SELECT * FROM orders WHERE chat_id = ? AND paid = 0", (chat_id,))
    unpaid_order = cursor.fetchone()
    if unpaid_order:
        send_message(chat_id, "⚠️ You have an unpaid order. Reply with 'add' or 'restart'.")
        conn.close()
        return "awaiting", 200

    # Retrieve conversation history
    cursor.execute("SELECT history FROM conversations WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    history = json.loads(result['history']) if result else []

    if not history:
        history = [{
            "role": "system",
            "content": (
                "You are a polite and helpful restaurant customer service bot. "
                "You help customers place orders, confirm their choices, ask for size or quantity, and calculate total cost. "
                "Try to keep the conversation short and concise. "
                "When you display the menu, only show items from the food and drinks category. "
                "Each price is for 1 portion. "
                "Before confirming order, ask if customer will: 1. Dine in (ask for table number), or 2. Do home delivery (ask for delivery address). "
                "All prices and products are in naira. "
                "Only show the total price when user is done with the order."
                "Please include the total price in your reply, formatted like 'Total: ₦3000'. "
            )
        }]

    history.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[{"role": msg["role"], "content": msg["content"]} for msg in history],
        temperature=0.7,
        max_tokens=300
    )

    assistant_reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": assistant_reply})

    # Save conversation history
    cursor.execute(
        "INSERT INTO conversations (chat_id, history) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET history = excluded.history",
        (chat_id, json.dumps(history))
    )
    conn.commit()

    match = re.search(r"total[:\s]*₦?([\d,]+)", assistant_reply, re.IGNORECASE)
    if match:
        total_str = match.group(1).replace(",", "")
        total = int(total_str)
        order_summary = assistant_reply.split("complete payment")[0].strip()
        delivery_match = re.search(r"(table\s*number\s*:?.+|home delivery to .+)", user_text, re.IGNORECASE)
        delivery_info = delivery_match.group(0).strip() if delivery_match else "Not provided"

        link, ref = create_paystack_link("customer@example.com", total, chat_id, order_summary, delivery_info)

        cursor.execute(
            "INSERT INTO orders (chat_id, summary, delivery, total, reference) VALUES (?, ?, ?, ?, ?)",
            (chat_id, order_summary, delivery_info, total, ref)
        )
        conn.commit()

        assistant_reply += f"\n\nPlease complete payment here: {link}"

    send_message(chat_id, assistant_reply)
    conn.close()
    return "ok", 200

# Verify payment status via Paystack
@app.route("/verify", methods=["GET"])
def verify():
    ref = request.args.get("reference")
    if not ref:
        return "Missing reference", 400

    # Verify payment status via Paystack
    r = requests.get(
        f"https://api.paystack.co/transaction/verify/{ref}",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    )
    data = r.json()

    if data.get("status") and data["data"].get("status") == "success":
        chat_id = str(data["data"]["metadata"].get("chat_id"))
        delivery = data["data"]["metadata"].get("delivery")

        conn = get_db_conn()
        cursor = conn.cursor()

        # Mark order as paid
        cursor.execute("UPDATE orders SET paid = 1 WHERE reference = ?", (ref,))
        # Get order details
        cursor.execute("SELECT summary, total FROM orders WHERE reference = ?", (ref,))
        order = cursor.fetchone()

        # Clear conversation/cart session
        cursor.execute("UPDATE conversations SET history = NULL WHERE chat_id = ?", (chat_id,))

        conn.commit()
        conn.close()

        # Notify user and kitchen
        send_message(chat_id, "✅ Order confirmed! Please wait for your order")
        send_message(KITCHEN_CHAT_ID, f"🍽️ Order: {order['summary']} | ₦{order['total']} | {delivery}")
        return "confirmed", 200

    # If payment failed
    chat_id = str(data.get("data", {}).get("metadata", {}).get("chat_id"))
    if chat_id:
        send_message(chat_id, "❌ Payment failed. Try again.")
    return "failed", 400

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000, debug=True)

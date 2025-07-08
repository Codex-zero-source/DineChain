import os
import json
import requests
import re
import psycopg2
from flask import Flask, request
from dotenv import load_dotenv
from paystack import create_paystack_link
from set_webhook import set_webhook
from admin import admin_bp
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
app.register_blueprint(admin_bp)

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
DATABASE_URL = os.getenv("DATABASE_URL")

client = OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))
conversation_history = {}
pending_orders = {}

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def get_pg_conn():
    return psycopg2.connect(DATABASE_URL)

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

    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE chat_id = %s AND paid = FALSE", (chat_id,))
            unpaid_order = cur.fetchone()

    if unpaid_order:
        send_message(chat_id, "⚠️ You have an unpaid order. Reply with 'add' or 'restart'.")
        return "awaiting", 200

    history = conversation_history.get(chat_id, [])
    if not history:
        history = [{
                "role": "system",
                "content": (
                    "You are a polite and helpful restaurant customer service bot. "
                    "You help customers place orders, confirm their choices, ask for size or quantity, and calculate total cost. "
                    "After calculating, generate a Paystack payment link using `create_paystack_link`. "
                    "Try to keep the conversation short and concise. "
                    "When you display the menu, only show items from the food and drinks category. "
                    "Each price is for 1 portion. "
                    "Before confirming order, ask if customer will: 1. Dine in (ask for table number), or 2. Do home delivery (ask for delivery address). "
                    "All prices and products are in naira. "
                    "Please include the total price in your reply, formatted like 'Total: ₦3000'. "
                    "Always end your response with the line: Total: ₦xxxx"
                )
            }]

    if chat_id in pending_orders and not pending_orders[chat_id]["paid"]:
        if "start over" in user_text.lower():
            pending_orders.pop(chat_id)
            history = history[:1]
        else:
            send_message(chat_id, "🛒 Unpaid order. Type 'start over' or add to it.")
            return "wait", 200

    history.append({"role": "user", "content": user_text})
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=history,
        temperature=0.7,
        max_tokens=300
    )

    assistant_reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": assistant_reply})
    conversation_history[chat_id] = history

    match = re.search(r"total[:\s]*₦?(\d+)", assistant_reply, re.IGNORECASE)
    if match:
        total = int(match.group(1))
        order_summary = assistant_reply.split("complete payment")[0].strip()
        delivery_match = re.search(r"(table\s*number\s*:?.+|home delivery to .+)", user_text, re.IGNORECASE)
        delivery_info = delivery_match.group(0).strip() if delivery_match else "Not provided"

        link, ref = create_paystack_link("customer@example.com", total, chat_id, order_summary, delivery_info)

        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO orders (chat_id, summary, delivery, total, reference, paid, timestamp)
                    VALUES (%s, %s, %s, %s, %s, FALSE, NOW())
                """, (chat_id, order_summary, delivery_info, total, ref))
                conn.commit()

        assistant_reply += f"\n\nPlease complete payment here: {link}"
        pending_orders[chat_id] = {
            "summary": order_summary,
            "total": total,
            "ref": ref,
            "paid": False
        }

    send_message(chat_id, assistant_reply)
    return "ok", 200

@app.route("/verify", methods=["GET"])
def verify():
    ref = request.args.get("reference")
    if not ref:
        return "Missing reference", 400

    r = requests.get(f"https://api.paystack.co/transaction/verify/{ref}", headers={"Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"})
    data = r.json()

    if data["status"] and data["data"]["status"] == "success":
        chat_id = str(data["data"]["metadata"].get("chat_id"))
        delivery = data["data"]["metadata"].get("delivery")

        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE orders SET paid = TRUE WHERE reference = %s", (ref,))
                cur.execute("SELECT summary FROM orders WHERE reference = %s", (ref,))
                order = cur.fetchone()

        send_message(chat_id, "✅ Order confirmed! Thank you.")
        send_message(KITCHEN_CHAT_ID, f"🍽️ Order: {order[0]} | ₦{data['data']['amount'] // 100} | {delivery}")
        return "confirmed", 200

    chat_id = str(data.get("data", {}).get("metadata", {}).get("chat_id"))
    if chat_id:
        send_message(chat_id, "❌ Payment failed. Try again.")
    return "failed", 400

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000, debug=True)

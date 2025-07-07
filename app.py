import os
import json
import openai
import requests
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from paystack import create_paystack_link
from set_webhook import set_webhook
from datetime import datetime

load_dotenv()
app = Flask(__name__)

# Load menu.json
with open("menu.json") as f:
    MENU = json.load(f)

# Format into a readable string for system prompt
def format_menu(menu):
    lines = []
    for category, items in menu.items():
        line = ", ".join([f"{item} (₦{price})" for item, price in items.items()])
        lines.append(f"{category.capitalize()}: {line}")
    return "\n".join(lines)

MENU_TEXT = format_menu(MENU)

# 🔐 Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

client = openai.OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

conversation_history = {}
pending_orders = {}

# 📨 Telegram send
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

    chat_id = message["chat"]["id"]
    user_text = message["text"]
    user_name = message["from"].get("first_name", "Customer")

    history = conversation_history.get(chat_id, [])
    if not history:
        history = [
            {
                "role": "system",
                "content": (
                    "You are a polite and helpful restaurant customer service bot. "
                    "You help customers place orders, confirm their choices, ask for size or quantity, and calculate total cost. "
                    "After calculating, generate a Paystack payment link using `create_paystack_link`. "
                    f"Try to keep the conversation short and concise. If the user asks for a menu, just say 'Here's our today's menu:\n{MENU_TEXT}'"
                    "When you display the menu, only some menu items are displayed from foods and drinks category."
                    "Each price is for 1 portion"
                    "Before confirming order, ask if customer will: 1. Dine in (ask for table number) 2. Do home delivery (ask for delivery address)"
                    "All prices and products are in naira. "
                    "Each price to food item is for 1 portion. "
                    "Please include the total price in your reply, formatted like 'Total: ₦3000'. "
                    "Always end your response with the line: Total: ₦xxxx"
                )
            }
        ]

    if chat_id in pending_orders and not pending_orders[chat_id].get("paid"):
        if "start over" in user_text.lower():
            pending_orders.pop(chat_id, None)
            history = history[:1]  # reset to just system prompt
        else:
            send_message(chat_id, "🛒 You have an unpaid order. Would you like to add to it or type 'start over' to begin a new one?")
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

    total_match = re.search(r"total[:\s]*₦?(\d+)", assistant_reply, re.IGNORECASE)
    if total_match:
        total = int(total_match.group(1))
        order_summary = assistant_reply.split("complete payment")[0].strip()

        payment_link, ref = create_paystack_link(
            "customer@example.com",
            total,
            chat_id,
            order_summary,
            {}  # Add empty dict for delivery_info parameter
        )

        assistant_reply += f"\n\nPlease complete payment here: {payment_link}"
        pending_orders[chat_id] = {
            "summary": order_summary,
            "total": total,
            "ref": ref,
            "paid": False
        }

    send_message(chat_id, assistant_reply)
    return "ok", 200

@app.route("/verify", methods=["GET"])
def verify_payment():
    reference = request.args.get("reference")
    if not reference:
        return "Missing reference", 400

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }
    r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    data = r.json()

    if data["status"] and data["data"]["status"] == "success":
        chat_id = data["data"]["metadata"].get("chat_id")
        order_summary = data["data"]["metadata"].get("order_summary")

        confirmation_message = f"✅ Payment successful!\n\nOrder: {order_summary}"
        send_message(chat_id, confirmation_message)

        send_message(KITCHEN_CHAT_ID, f"🚞 Order:{order_summary}")

        if chat_id in pending_orders:
            pending_orders[chat_id]["paid"] = True
            conversation_history[chat_id] = conversation_history[chat_id][:1]  # reset for next session

        return "Payment confirmed", 200
    else:
        chat_id = data.get("data", {}).get("metadata", {}).get("chat_id")
        if chat_id:
            send_message(chat_id, "❌ Payment failed. Please try again.")
        return "Payment failed", 400

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000, debug=True)

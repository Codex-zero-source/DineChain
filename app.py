import os
import json
import re
import openai
import requests
from flask import Flask, request
from dotenv import load_dotenv
from paystack import create_paystack_link
from set_webhook import set_webhook

load_dotenv()
app = Flask(__name__)

# Load menu.json
with open("menu.json") as f:
    MENU = json.load(f)

# Format menu for LLM prompt
def format_menu(menu):
    lines = []
    for category, items in menu.items():
        line = ", ".join([f"{item} (₦{price})" for item, price in items.items()])
        lines.append(f"{category.capitalize()}: {line}")
    return "\n".join(lines)

MENU_TEXT = format_menu(MENU)

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# LLM Client
client = openai.OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

conversation_history = {}

# Send Telegram message
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

    history = conversation_history.get(chat_id, [])
    if not history:
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
            }
        ]

    history.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=history,
        temperature=0.7,
        max_tokens=200
    )

    assistant_reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": assistant_reply})
    conversation_history[chat_id] = history

    # Extract total
    total_match = re.search(r"total[:\s]*₦?(\d+)", assistant_reply, re.IGNORECASE)
    if total_match:
        total = int(total_match.group(1))
        order_summary = assistant_reply.split("complete payment")[0].strip()

        delivery_match = re.search(r"(table\s*number\s*:?\s*\w+|home delivery to .+)", user_text, re.IGNORECASE)
        delivery_info = delivery_match.group(0) if delivery_match else "Not provided"

        payment_link, ref = create_paystack_link(
            "customer@example.com",
            total,
            chat_id,
            order_summary,
            delivery_info
        )

        assistant_reply += f"\n\nPlease complete payment here: {payment_link}"

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
        delivery = data["data"]["metadata"].get("delivery", "Not provided")

        send_message(chat_id, "✅ Order confirmed! Thank you for your payment.")
        send_message(KITCHEN_CHAT_ID, f"📦 New Order:\n{order_summary}\n🏧 {delivery}")
        return "Payment confirmed", 200
    else:
        chat_id = data.get("data", {}).get("metadata", {}).get("chat_id")
        if chat_id:
            send_message(chat_id, "❌ Payment failed. Please try again.")
        return "Payment failed", 400

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000, debug=True)

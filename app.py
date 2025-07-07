import os
import json
import openai
import requests
import re
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
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

client = OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

conversation_history = {}
pending_orders = {}

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

    # Handle session
    history = conversation_history.get(chat_id, [])
    if not history:
        history = [
            {
                "role": "system",
                "content": (
                    "You are a polite and helpful restaurant customer service bot. "
                    "You help customers place orders, confirm their choices, ask for size or quantity, and calculate total cost. "
                    "After calculating, generate a Paystack payment link using `create_paystack_link`. "
                    f"Try to keep the conversation short and concise."
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

    # 🧾 Check if user has pending unpaid order
    if chat_id in pending_orders and not pending_orders[chat_id]["paid"]:
        if "start over" in user_text.lower():
            pending_orders.pop(chat_id, None)
            history = history[:1]  # reset to just system prompt
        else:
            send_message(chat_id, "🛒 You have an unpaid order. Type 'start over' to begin a new one, or add more to this order.")
            return "wait", 200

    # ➕ Add user message
    history.append({"role": "user", "content": user_text})

    # 🧠 Call LLM
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[{"role": str(msg["role"]), "content": str(msg["content"])} for msg in history],  # type: ignore
        temperature=0.7,
        max_tokens=300
    )

    assistant_reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": assistant_reply})
    conversation_history[chat_id] = history

    # 💳 Extract total & create Paystack payment link
    total_match = re.search(r"total[:\s]*₦?(\d+)", assistant_reply, re.IGNORECASE)
    if total_match:
        naira_total = int(total_match.group(1))
        kobo_total = naira_total * 100  # ✅ Convert to kobo for Paystack

        order_summary = assistant_reply.split("complete payment")[0].strip()

        payment_link, ref = create_paystack_link(
            "customer@example.com",
            kobo_total,
            chat_id,
            order_summary,
            delivery_info={} # Add delivery info if needed
        )

        assistant_reply += f"\n\nPlease complete payment here: {payment_link}"

        pending_orders[chat_id] = {
            "summary": order_summary,
            "total": naira_total,
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

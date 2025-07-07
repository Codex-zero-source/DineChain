import os
import json
import openai
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from orders import calculate_total
from paystack import create_paystack_link
from set_webhook import set_webhook

load_dotenv()
app = Flask(__name__)
# Load menu.json
with open("menu.json") as f:
    MENU = json.load(f)

# Format into a readable string for system prompt
def format_menu(menu):
    lines = []
    for category, items in menu.items():
        item_line = ", ".join(items.keys())
        lines.append(f"{category.capitalize()}: {item_line}")
    return "\n".join(lines)

MENU_TEXT = format_menu(MENU)

# 🔐 Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")  # <- Telegram Group ID for kitchen
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# 🤖 LLM Client
client = openai.OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

conversation_history = {}
user_references = {}

# 📨 Telegram send
def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


@app.route("/", methods=["GET"])
def home():
    return "Bot is alive ✅", 200


# 📥 Telegram Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # ✅ Only handle valid user text messages
    message = data.get("message")
    if not message or "text" not in message:
        return "ignored", 200

    chat_id = message["chat"]["id"]
    user_text = message["text"]
    user_name = message["from"].get("first_name", "Customer")

    # 🧠 Build LLM chat history
    history = conversation_history.get(chat_id, [])
    if not history:
        history = [
            {
                "role": "system",
                "content": (
                    "You are a polite and helpful restaurant customer service bot. "
                    "You help customers place orders, confirm their choices, ask for size or quantity, and calculate total cost. "
                    "After calculating, generate a Paystack payment link using `create_paystack_link`."
                )
            },
            {
             "role": "system",
             "content": f"Menu today:\n{MENU_TEXT}"
            }

        ]

    history.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=history,
        temperature=0.7,
        max_tokens=200
    )

    # There are two potential errors here:
    # 1. assistant_reply could be None, which would cause a TypeError when using += with a string.
    # 2. The type of the dicts being appended to history may not always match the expected type if assistant_reply is None.

    assistant_reply = response.choices[0].message.content
    if assistant_reply is None:
        assistant_reply = ""
    history.append({"role": "assistant", "content": assistant_reply})
    conversation_history[chat_id] = history

    # 💰 Calculate total
    total, items = calculate_total(user_text)

    if total > 0:
        item_list = "\n".join([f"{name}: ₦{price}" for name, price in items])
        payment_link, reference = create_paystack_link("customer@example.com", total)  # You can use user_name here too

        # Store reference → chat_id mapping
        user_references[reference] = {
            "chat_id": chat_id,
            "items": items,
            "user": user_name,
            "total": total
        }

        assistant_reply += (
            f"\n\nYour order:\n{item_list}\nTotal: ₦{total}"
            f"\n👉 [Click here to pay]({payment_link})"
        )

    send_message(chat_id, assistant_reply)
    return "ok", 200

@app.route("/verify", methods=["GET"])
def verify_payment():
    reference = request.args.get("reference")
    if not reference or reference not in user_references:
        return jsonify({"error": "Invalid or unknown reference"}), 400

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }
    r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    result = r.json()

    user_data = user_references[reference]
    chat_id = user_data["chat_id"]
    total = user_data["total"]
    items = user_data["items"]
    user_name = user_data["user"]

    if result["data"]["status"] == "success":
        # ✅ Notify user
        send_message(chat_id, f"✅ Payment of ₦{total} confirmed! Your order is being prepared.")

        # 🧑‍🍳 Send to kitchen
        order_summary = "\n".join([f"• {item}: ₦{price}" for item, price in items])
        kitchen_note = (
            f"🍽️ New Order from {user_name}:\n{order_summary}\nTotal: ₦{total}"
        )
        send_message(KITCHEN_CHAT_ID, kitchen_note)

    else:
        send_message(chat_id, "❌ Payment failed. Please try again.")

    # Clean up memory
    del user_references[reference]
    return jsonify({"status": "checked"}), 200

if __name__ == "__main__":
    set_webhook()

    app.run(host="0.0.0.0", port=5000, debug=True)


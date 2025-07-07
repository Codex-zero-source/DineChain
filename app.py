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
             "content": (
                f"Try to keep the conversation short and concise. If the user asks for a menu, just say 'Here's our today's menu:\n{MENU_TEXT}'"
                "All prices and products are in naira"
                "each price to food item is for 1 portion"
             )
            },
            {
                "role": "user",
                "content": "I'd like another order, no long text"
            },
            {
                "role": "assistant",
                "content": f"Okay, what would you like to have today? Here's our menu:\n{MENU_TEXT}"
            },
            {
                "role": "user",
                "content": "I'd like to order jollof rice 2 portions, with beef"
            },
            {
                "role": "assistant",
                "content": f"Okay, what would you like to have today? Here's our menu:\n{MENU_TEXT}"
            }
        ]

    history.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages= history,  # history is highlighted because the type checker expects an Iterable[ChatCompletionMessageParam], but history is a list of dicts; to fix, ensure history matches the expected schema or use the OpenAI types.
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
        order_summary = f"{item_list}\nTotal: ₦{total}"

        payment_link, ref = create_paystack_link(
        "customer@example.com",
        total,
        chat_id,
        order_summary
    )

    assistant_reply += f"\n\nYour order:\n{order_summary}\nPlease complete payment: {payment_link}"


    send_message(chat_id, assistant_reply)
    return "ok", 200

@app.route("/verify", methods=["GET"])
def verify_payment():
    reference = request.args.get("reference")
    if not reference:
        return "Missing reference", 400

    headers = {
        "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"
    }
    r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    data = r.json()

    print("🎯 Payment verification response:", data)
    if data["status"] and data["data"]["status"] == "success":
        # ✅ Payment successful

        chat_id = data["data"]["metadata"].get("chat_id")
        order_summary = data["data"]["metadata"].get("order_summary")

        confirmation_message = f"✅ Your payment was successful! 🎉\n\nOrder: {order_summary}"
        send_message(chat_id, confirmation_message)

        # Send to kitchen
        kitchen_id = os.getenv("KITCHEN_ID")
        send_message(kitchen_id, f"📦 New Order Received:\n{order_summary}")

        return "Payment confirmed", 200

    else:
        # ❌ Payment failed
        chat_id = data.get("data", {}).get("metadata", {}).get("chat_id")
        if chat_id:
            send_message(chat_id, "❌ Payment failed. Please try again.")
        return "Payment failed", 400

if __name__ == "__main__":
    set_webhook()

    app.run(host="0.0.0.0", port=5000, debug=True)


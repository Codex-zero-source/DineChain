import os
import json
import requests
import re
import httpx
from flask import Flask, request
from dotenv import load_dotenv
from twilio.twiml.messaging_response import MessagingResponse
from paystack import create_paystack_link
from set_webhook import set_webhook
from admin import admin_bp
from openai import OpenAI
from orders import get_db_conn, init_db
import asyncio

load_dotenv()
app = Flask(__name__)
app.register_blueprint(admin_bp)

# Initialize the database asynchronously before starting the app
asyncio.run(init_db())

# The set_webhook() function is not async and should be handled differently.
# For now, it's removed from the app startup sequence. A separate script or manual call is better.
# set_webhook()

# 🔐 Environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

client = OpenAI(api_key=LLM_API_KEY, base_url=os.getenv("BASE_URL"))

async def send_user_message(platform, chat_id, text):
    if platform == "telegram":
        async with httpx.AsyncClient() as http_client:
            url = f"{BASE_URL}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            await http_client.post(url, json=payload)
    elif platform == "whatsapp":
        from twilio.rest import Client
        
        def send_twilio_message():
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=text,
                from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                to=chat_id
            )
        
        await asyncio.to_thread(send_twilio_message)

@app.route("/", methods=["GET"])
def home():
    return "Bot is alive ✅", 200

@app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json()
    message = data.get("message")
    if not message or "text" not in message:
        return "ignored", 200

    chat_id = str(message["chat"]["id"])
    user_text = message["text"]
    customer_name = message.get('from', {}).get('first_name', 'Valued Customer')
    platform = "telegram"

    await process_message(platform, chat_id, user_text, customer_name)
    return "ok", 200

@app.route("/twilio_webhook", methods=["POST"])
async def twilio_webhook():
    data = request.form
    user_text = data.get('Body', '').strip()
    chat_id = data.get('From', '')
    customer_name = data.get('ProfileName', 'Valued Customer')
    platform = "whatsapp"
    
    if not user_text:
        return str(MessagingResponse())

    await process_message(platform, chat_id, user_text, customer_name)
    
    # Twilio requires a TwiML response
    response = MessagingResponse()
    return str(response)

async def process_message(platform, chat_id, user_text, customer_name):
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        
        # Check for unpaid orders
        await cursor.execute("SELECT * FROM orders WHERE chat_id = ? AND platform = ? AND paid = 0", (chat_id, platform))
        unpaid_order = await cursor.fetchone()
        if unpaid_order:
            await send_user_message(platform, chat_id, "⚠️ You have an unpaid order. Reply with 'add' or 'restart'.")
            return

        # Retrieve conversation history
        await cursor.execute("SELECT history FROM conversations WHERE chat_id = ? AND platform = ?", (chat_id, platform))
        result = await cursor.fetchone()
        history = json.loads(result['history']) if result and result['history'] else []

        if not history:
            history = [{
                "role": "system",
                "content": (
                    "You are a friendly and helpful restaurant chatbot. Make your replies lively and engaging, but limit your use of 'food' emojis (🍲, 🍛, 🍕, 🌯, etc.) to no more than two per message. Use them thoughtfully to add personality without overwhelming the user. Always prioritize clarity and helpfulness."
                    "You are the JollofAI, an AI-powered assistant for taking orders, handling payments, and guiding customers through our menu. Here is today’s menu:\n\n"
                    "Food:\n"
                    "If you receive questions unrelated to ordering, payments, or the menu, politely reply: 'I'm here to help with orders and our menu. Please let me know what you'd like from our menu.'"
                    "• Soup & Sauce: Stew (₦3000), Palm Oil Stew (₦3000), Egg Sauce (₦3000), Chicken Sauce (₦5000), Carrot Sauce (₦3000), Prawn Sauce (Request), Ofada Sauce (Request), Vegetable Soup (₦6000), Egusi Soup (₦8,500), Ogbono Soup (₦8,500), Okra Soup (₦6,500), Eforiro (₦7,000), Oha Soup (Request), White Soup (Request), Afang Soup (Request), Bitter Leaf Soup (Request), Banga Soup (Request)\n"
                    "• Rice: Jollof Rice (₦5,000), Fried Rice (₦7,000), White Rice (₦4,000), Ofada Rice (₦7,000), Palm Oil Jollof (₦6,000), Basmati Rice (₦10,000)\n"
                    "• Noodles & Pasta: Indomie (₦5,000), Macaroni (₦5,000), Spaghetti (₦5,000), Couscous (₦6,000)\n"
                    "• Swallow (per wrap): Eba (₦2,000), Semovita (₦2,000), Wheat Meal (₦4,000), Poundo Yam (₦5,000)\n\n"
                    "Drinks:\n"
                    "• Wine: 4th Street (₦5,000), Four Cousins Red/Rose/White (₦8,000), Andri 4 Rosè (₦10,000), Carlo Rossi (₦10,000)\n"
                    "• Cocktail: Sex on the Beach, Jack Baileys, Jack Mojito, Limoncello, Green Screwdriver (all ₦3,000)\n"
                    "• Non-Alcoholic Wine: Pure Heaven Can (₦1,000), Pure Heaven (₦3,000), J&W (₦2,500), Eva Wine (₦4,500), Chamdor (₦5,000), Martinellis (₦8,000)\n"
                    "• Milkshakes: Banana, Vanilla, Chocolate, Strawberry, Oreo, Apple (all ₦3,000)\n"
                    "• Mocktail: Chapman, Virgin Lime Mojito, Watermelon Mojito, Mint Mojito, Electric Lemonade, Mint Lemonade (₦2,000), Green Goddess, Sunrise, Strawberry Mojito, Bloody Paloma, Fruit Punch, Pina Colada, Pineapple Fizz (₦2,500), Blue Lagoon (₦3,500), Blue Rum Paradise (₦2,500)\n"
                    "• Beer: Heineken, Budweiser, Desperado (Bottle/Can: ₦1,000/₦800), Legend (₦800), Smirnoff Ice (₦1,000), Guinness Stout (₦1,000/₦800), Tiger (₦800), Star Radler (₦700), Goldberg (₦800/₦700), Hero (₦600)\n\n"
                        "Workflow:\n"
                    "1. Greet the customer and ask for their name for the order.\n"
                    "2. Offer selections from the menu categories above based on the user's preferences.\n"
                    "3. Guide them to select items, quantities, keep responses short and ask “Home delivery or dine in? If home delivery, please provide your address.”\n"
                    "4. When they finish selecting, ask “Is that everything? Please confirm when you’re done.”\n"
                    "5. Once confirmed, calculate the total and reply `Total: ₦XXXX`.\n"
                    "6. Generate a Paystack payment link and send it to the user.\n"
                    "7. After payment, verify the transaction using the reference. Then:\n"
                    "   - Send a confirmation message to the customer with a breakdown of their paid order (receipt).\n"
                    "   - Clear the customer session data.\n"
                    "   - Notify the kitchen via the kitchen group chat with a summary of the order.\n"
                    "8. If the customer provided a delivery address before payment, include it in the notification to the kitchen.\n"
                    "   🍽️ Order for <Name> (chat_id) on <platform>:\n"
                    "   Jollof Rice: ₦5,000\n"
                    "   Vanilla Milkshake: ₦3,000\n"
                    "   Total: ₦8,000\n"
                    "   Delivery: Table 15\n\n"
                    "Recommendations:\n"
                    "- If unsure, suggest combos dynamically by category and budget:\n"
                    "  • Affordable (under ₦7,000)\n"
                    "  • Average (₦7,000–₦10,000)\n"
                    "  • Premium (above ₦10,000)\n"
                    "- Quick-snack: Indomie or Sharwarma + Pure Heaven or Chapman.\n"
                    "- Surprise Me: pick a mid-range combo.\n"
                    "- Spicy: Egusi Soup or Ofada Sauce + Spicy Mocktail.\n"
                    "- Sweet: Chocolate Milkshake or Sweet Wine.\n\n"
                    "Format recommendations as:\n"
                    "💡 You might enjoy our: \n"
                    "🥤 Vanilla Milkshake (₦3,000)\n"
                )
            }]

        history.append({"role": "user", "content": user_text})

        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": msg["role"], "content": msg["content"]} for msg in history],  # type: ignore
            temperature=0.7,
            max_tokens=300
        )

        assistant_reply = response.choices[0].message.content or ""
        history.append({"role": "assistant", "content": assistant_reply})

        # Save conversation history
        await cursor.execute(
            "INSERT INTO conversations (chat_id, platform, history) VALUES (?, ?, ?) ON CONFLICT(chat_id, platform) DO UPDATE SET history = excluded.history",
            (chat_id, platform, json.dumps(history))
        )
        await conn.commit()

        match = re.search(r"total[:\s]*₦?([\d,]+)", assistant_reply, re.IGNORECASE)
        if match:
            total_str = match.group(1).replace(",", "")
            total = int(total_str)
            order_summary = assistant_reply.split("complete payment")[0].strip()
            delivery_match = re.search(r"(table\s*number\s*:?.+|home delivery to .+)", user_text, re.IGNORECASE)
            delivery_info = delivery_match.group(0).strip() if delivery_match else "Not provided"

            link, ref = await create_paystack_link("customer@example.com", total, chat_id, order_summary, delivery_info, platform=platform)

            await cursor.execute(
                "INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total, reference) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, platform, customer_name, order_summary, delivery_info, total, ref)
            )
            await conn.commit()

            assistant_reply += f"\n\nPlease complete payment here: {link}"

    await send_user_message(platform, chat_id, assistant_reply)
    
    # Check for unpaid orders - This block might be better placed within the DB connection block
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT * FROM orders WHERE chat_id = ? AND paid = 0", (chat_id,))
        unpaid_order = await cursor.fetchone()
        if unpaid_order:
            await send_user_message(platform, chat_id, "⚠️ You have an unpaid order. Reply with 'add' or 'restart'.")
            return
            
    return "ok", 200

# Verify payment status via Paystack
@app.route("/verify", methods=["GET"])
async def verify():
    ref = request.args.get("reference")
    if not ref:
        return "Missing reference", 400

    # Verify payment status via Paystack
    url = f"https://api.paystack.co/transaction/verify/{ref}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    async with httpx.AsyncClient() as http_client:
        r = await http_client.get(url, headers=headers)
        data = r.json()

    if data.get("status") and data["data"].get("status") == "success":
        # Note: The metadata from paystack needs to be updated to include platform
        chat_id = str(data["data"]["metadata"].get("chat_id"))
        delivery = data["data"]["metadata"].get("delivery")
        platform = data["data"]["metadata"].get("platform", "telegram") # Default to telegram for old orders

        async with get_db_conn() as conn:
            cursor = await conn.cursor()

            # Mark order as paid
            await cursor.execute("UPDATE orders SET paid = 1 WHERE reference = ?", (ref,))
            # Get order details
            await cursor.execute("SELECT customer_name, summary, total FROM orders WHERE reference = ?", (ref,))
            order = await cursor.fetchone()

            if not order:
                print(f"Error: No order found for reference {ref}")
                return "failed", 400

            # Clear conversation/cart session
            await cursor.execute("UPDATE conversations SET history = NULL WHERE chat_id = ? AND platform = ?", (chat_id, platform))

            await conn.commit()

        # Notify user and kitchen
        await send_user_message(platform, chat_id, "✅ Order confirmed! Please wait while we prepare your order")
        
        def format_kitchen_order(chat_id, customer_name, summary, total, delivery, platform):
            # Parse items from summary into individual lines
            lines = [f"🍽️ Order for {customer_name or 'N/A'} ({chat_id} on {platform}):"]
            
            # Ensure summary is a string before processing
            order_summary = summary or ""
            for match in re.findall(r"(\*?\s*[\w\s]+)\s*\(₦?([\d,]+)\)", order_summary):
                item = match[0].strip(" *")
                price = match[1].replace(",", "")
                lines.append(f"{item}: ₦{int(price):,}")
            
            lines.append(f"Total: ₦{int(total or 0):,}")
            lines.append(f"Delivery: {delivery or 'Not specified'}")
            return "\n".join(lines)

        kitchen_order = format_kitchen_order(
            chat_id, 
            order['customer_name'], 
            order['summary'], 
            order['total'], 
            delivery, 
            platform
        )
        # Sending kitchen message via Telegram for now
        await send_user_message("telegram", KITCHEN_CHAT_ID, kitchen_order)

        return "confirmed", 200

    # If payment failed
    chat_id = str(data.get("data", {}).get("metadata", {}).get("chat_id"))
    platform = data.get("data", {}).get("metadata", {}).get("platform", "telegram")
    if chat_id:
        await send_user_message(platform, chat_id, "❌ Payment failed. Try again.")
    return "failed", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

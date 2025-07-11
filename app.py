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
IOINTELLIGENCE_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("BASE_URL")
KITCHEN_CHAT_ID = os.getenv("KITCHEN_CHAT_ID")
TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")


async def get_llm_response(history):
    """Calls the IO Intelligence API to get a response."""
    # if not LLM_BASE_URL or not IOINTELLIGENCE_API_KEY:
    #     raise ValueError("LLM_BASE_URL and IOINTELLIGENCE_API_KEY must be set in the environment.")
        
    url = f"{LLM_BASE_URL}/chat/completions"
    
    # FOR DEBUGGING ONLY - using the hardcoded key from the successful test
    api_key = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6Ijg4ZDM2MzI4LTUxMjItNGRhMi1iMGJiLTlkNWM1MmU4NDUxOCIsImV4cCI6NDkwNTg0MDI4Nn0.lXlykZCHVen8hDIwOkQPPuVwjnt-SgF3mh7IOunQ_OPpDuJE_NfgOFn7c1mamKnTpmf_rE2j6yiRmyuI6DFt0A"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [{"role": msg["role"], "content": msg["content"]} for msg in history],
        "temperature": 0.7,
        "max_tokens": 400
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=30.0)
        response.raise_for_status()  # Will raise an exception for 4xx/5xx responses
        return response.json()


async def send_user_message(platform, chat_id, text):
    if platform == "telegram":
        async with httpx.AsyncClient() as http_client:
            url = f"{TELEGRAM_BASE_URL}/sendMessage"
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
                    "You are a friendly and helpful chatbot for a restaurant. Make your replies lively and engaging, but limit your use of 'food' emojis (🍲, 🍛, 🍕, 🌯, etc). Use them thoughtfully to add personality without overwhelming the user. Always prioritize clarity and helpfulness."
                    "You are the JollofAI, an AI-powered assistant for taking orders, handling payments, and guiding customers through our menu. Here is today’s menu:"
                    "Food:"
                    "If you receive questions unrelated to ordering, payments, or the menu, politely reply: 'I'm here to help with orders and our menu. Please let me know what you'd like from our menu.'"
                    "Main Meal: Jollof Rice (₦800), Fried Rice (₦800), WhiteRice/Beans (₦800), Beans Porridge (₦800), Yam Porridge (₦800), Pasta (₦800)"
                    "Soups: Egusi (₦700), Ogbnor (₦700), Vegetable (₦700), Efo Riro (₦700)"
                    "Swallows: Semo (₦200), Apu (₦200), Garri (₦200), Pounded Yam (₦200)"
                    "Local Fridays: Friday Dish (₦1,000)"
                    "Protein: Eggs (₦300), Turkey (₦800), Chicken (₦700), Fish (₦500), Goat Meat (₦700), Beef (₦500)"
                    "Pastries: Meat Pie (₦700), Sausage Roll (₦500), Fish Roll (₦500), Dough Nut (₦500), Cakes (₦700), Cookies (₦500)"
                    "Shawarma: Beef (₦1,500), Chicken (₦1,500), Single Sausage (₦500), Double Sausage (₦800), Combo (₦2,000), Combo with Double Sausage (₦2,500)"
                    "Cocktails: Virgin Daiquiri (₦1,500), Virgin Mojito (₦1,500), Tequila Sunrise (₦1,500), Pinacolada (₦1,500), Chapman (₦1,500), Coffee Boba (₦1,500), Strawberry (₦1,500)"
                    "Milkshake & Dairy: Oreo (₦1,500), Strawberry (₦1,500), Ice Cream (₦1,500), Sweetneded Greek Yogurt (₦1,500), Unsweetneded Greek Yogurt (₦1,500), Strawberry Yogurt (₦1,500), Fura Yogo (₦1,500)"
                    "Fruit Drinks: Pineapple (₦1,000), Orange (₦1,000), Mix Fruit (₦1,000), Carrot (₦1,000), Fruity Zobo (₦1,000), Tiger Nut Milk (₦1,000)"
                    "Soda: Coke (₦600), Fanta (₦600), Sprite (₦600), Schweppes Chapman (₦700), Schweppes Mojito (₦700), Can Malt (₦600), Predator (₦800), 5Alive Berry (₦700), 5Alive Pulpy (₦700), Bottle Water (₦400), Chivita 100% (₦800), Chiexotic (₦700)"
                    "Workflow:"
                    "1. Greet the customer and ask for their name for the order."
                    "2. Offer selections from the menu categories above based on the user's preferences."
                    "3. Guide them to select items, quantities, keep responses short and ask 'Dine in or home delivery? If home delivery, please provide your address.'"
                    "4. When they finish selecting, ask 'Is that everything? Please confirm when you’re done.'"
                    "5. Once confirmed, provide a clear, final summary of the order. Use the heading 'Your Order:' and list each item with its price. Calculate the total and display it clearly at the end. Finally, the structured order details, including delivery information if provided. Format it exactly like this, with no extra text after the closing brace:"
                    "6. After presenting the final bill, DO NOT mention payment. Simply stop and wait for the system to provide a payment link."
                    "7. After payment verification, you will be prompted to send a confirmation and notify the kitchen."
                    "   - Send a confirmation message to the customer with a breakdown of their paid order (receipt)."
                    "   - Notify the kitchen via the kitchen group chat with a summary of the order."
                    "8. If the customer provided a delivery address before or after payment, include it in the notification to the kitchen."
                    "9. Clear the customer session data."
                    "Kitchen message format:"
                    "   🍽️ Order for <Name> (chat_id) on <platform>:"
                    "   Jollof Rice: ₦800"
                    "   Turkey: ₦800"
                    "   Total: ₦1,600"
                    "   Delivery: Table 15"
                    "Recommendations:"
                    "- If unsure, suggest combos dynamically by category and budget."
                    "- Quick-snack: Shawarma and a Soda."
                    "- Surprise Me: Jollof Rice with Chicken."
                    "- Spicy: Egusi Soup with Apu."
                    "- Sweet: A Doughnut and a Milkshake."
                    "Format recommendations as:"
                    "💡 You might enjoy our Pastries: "
                    "🥧 Meat Pie (₦700)"
                    "🥧 Sausage Roll (₦500)"
                    "🥧 Fish Roll (₦500)"
                )
            }]

        history.append({"role": "user", "content": user_text})

        try:
            llm_response = await get_llm_response(history)
            assistant_reply = llm_response['choices'][0]['message']['content'] or ""
        except httpx.HTTPStatusError as e:
            error_details = f"Status: {e.response.status_code}, Response: {e.response.text}"
            log_message = f"LLM API Status Error: {e}. Details: {error_details}"
            print(log_message, flush=True)
            await send_user_message(platform, chat_id, "I'm having trouble thinking right now. Please try again in a moment.")
            return
        except Exception as e:
            log_message = f"An unexpected error occurred when calling LLM API. Type: {type(e).__name__}, Error: {e}"
            print(log_message, flush=True)
            await send_user_message(platform, chat_id, "I'm having trouble thinking right now. Please try again in a moment.")
            return

        history.append({"role": "assistant", "content": assistant_reply})

        # Save conversation history
        await cursor.execute(
            "INSERT INTO conversations (chat_id, platform, history) VALUES (?, ?, ?) ON CONFLICT(chat_id, platform) DO UPDATE SET history = excluded.history",
            (chat_id, platform, json.dumps(history))
        )
        await conn.commit()

        # More robust regex to find the total amount
        json_match = re.search(r"```json\n(.+?)\n```", assistant_reply, re.DOTALL)

        order_data = None
        if json_match:
            json_str = json_match.group(1)
            try:
                order_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from AI response: {e}")
                order_data = None
        
        if order_data:
            total = order_data.get("total")
            order_summary_json = json.dumps(order_data.get("items", []))
            
            delivery_info = order_data.get("delivery_info", "Not provided")

            customer_email = "customer@example.com"

            user_facing_reply = assistant_reply
            try:
                link, ref = await create_paystack_link(customer_email, total, chat_id, order_summary_json, delivery_info, platform=platform)

                await cursor.execute(
                    "INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total, reference) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chat_id, platform, customer_name, order_summary_json, delivery_info, total, ref)
                )
                await conn.commit()

                user_facing_reply = assistant_reply.split("```json")[0].strip()
                user_facing_reply += f"\n\nPlease complete payment here: {link}"

            except Exception as e:
                print(f"Error creating Paystack link: {e}")
                user_facing_reply = assistant_reply + "\n\nSorry, I couldn't create a payment link at the moment. Please try again later."
            
            await send_user_message(platform, chat_id, user_facing_reply)
        else:
            await send_user_message(platform, chat_id, assistant_reply)
            
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
            
            try:
                order_items = json.loads(summary)
                for item in order_items:
                    lines.append(f"{item['name']}: ₦{int(item['price']):,}")
            except (json.JSONDecodeError, TypeError):
                # Fallback for old order format
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

import os
import asyncio
import httpx
from dotenv import load_dotenv
import aiosqlite

# Load environment variables from .env file
load_dotenv()

# Custom imports from your application
from crypto_payment import get_usdt_balance

# --- Configuration ---
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'orders.db')
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
POLL_INTERVAL_SEC = 30  # Poll every 30 seconds

async def get_unpaid_crypto_orders(conn):
    """Fetches all unpaid orders that have a crypto deposit address."""
    cursor = await conn.cursor()
    await cursor.execute(
        "SELECT id, deposit_address, total FROM orders WHERE paid = 0 AND payment_method = 'crypto' AND deposit_address IS NOT NULL"
    )
    orders = await cursor.fetchall()
    return orders

async def mark_order_as_paid(conn, order_id):
    """Updates the order's status to 'paid' in the database."""
    cursor = await conn.cursor()
    await cursor.execute("UPDATE orders SET paid = 1 WHERE id = ?", (order_id,))
    await conn.commit()
    print(f"✅ Marked order {order_id} as paid.")

async def notify_app(order_id):
    """Calls the internal webhook in the main app to trigger user/kitchen notifications."""
    headers = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}
    url = f"{BASE_URL}/internal/order_paid/{order_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            print(f"📲 Notified app about paid order {order_id}. Status: {response.status_code}")
        except httpx.HTTPStatusError as e:
            print(f"❌ Failed to notify app for order {order_id}. Status: {e.response.status_code}, Response: {e.response.text}")
        except httpx.RequestError as e:
            print(f"❌ Could not connect to the app to notify for order {order_id}. Error: {e}")

async def check_payments():
    """The main loop for the payment watcher service."""
    print("🤖 Starting payment watcher service...")
    
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        while True:
            try:
                unpaid_orders = await get_unpaid_crypto_orders(conn)
                
                if not unpaid_orders:
                    await asyncio.sleep(POLL_INTERVAL_SEC)
                    continue

                print(f"🔎 Found {len(unpaid_orders)} unpaid crypto order(s). Checking balances...")

                for order in unpaid_orders:
                    order_id = order['id']
                    address = order['deposit_address']
                    amount_expected = order['total'] / 100

                    try:
                        balance = await asyncio.to_thread(get_usdt_balance, address)
                        print(f"   - Order {order_id} ({address}): Expected ${amount_expected:.2f}, Balance: ${balance:.2f}")

                        if balance >= amount_expected:
                            print(f"💰 Payment detected for order {order_id}!")
                            await mark_order_as_paid(conn, order_id)
                            await notify_app(order_id)
                        
                    except Exception as e:
                        print(f"⚠️ Error checking balance for address {address} (Order {order_id}): {e}")

            except Exception as e:
                print(f"🚨 An unexpected error occurred in the payment watcher: {e}")

            await asyncio.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    if not INTERNAL_API_KEY:
        raise ValueError("INTERNAL_API_KEY environment variable not set. Cannot run watcher.")
    
    try:
        asyncio.run(check_payments())
    except KeyboardInterrupt:
        print("🛑 Payment watcher service stopped.") 
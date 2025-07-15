import os
import uuid
import httpx
from dotenv import load_dotenv

load_dotenv()

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
ADMIN_USDC_ADDRESS = os.getenv("ADMIN_USDC_ADDRESS")

async def create_wallet(chat_id):
    """Creates a new Circle wallet for a user."""
    headers = {
        "Authorization": f"Bearer {CIRCLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "description": f"Telegram-{chat_id}"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post("https://api.circle.com/v1/w3s/users", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["data"]["userId"], res.json()["data"]["walletId"]

async def generate_deposit_address(user_id):
    """Generates a new USDC deposit address for a wallet."""
    headers = {
        "Authorization": f"Bearer {CIRCLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "chain": "MATIC",
        "currency": "USDC"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(f"https://api.circle.com/v1/w3s/users/{user_id}/addresses", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["data"]["address"]

async def forward_to_admin(wallet_id, amount):
    """Forwards a specified amount of USDC to the admin wallet."""
    headers = {
        "Authorization": f"Bearer {CIRCLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "destination": {"address": ADMIN_USDC_ADDRESS},
        "amount": {
            "amount": str(amount),
            "currency": "USDC"
        },
        "walletId": wallet_id
    }
    async with httpx.AsyncClient() as client:
        res = await client.post("https://api.circle.com/v1/w3s/transactions/transfer", headers=headers, json=payload)
        res.raise_for_status()
        return res.json() 
import os
import uuid
import httpx
from typing import Tuple

# --- Configuration ---
CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
ADMIN_USDC_ADDRESS = os.getenv("ADMIN_USDC_ADDRESS")
CIRCLE_BASE_URL = os.getenv("CIRCLE_BASE_URL", "https://api.circle.com/v1/w3s")

# --- Custom Exception ---
class CircleException(Exception):
    """Custom exception for Circle API related errors."""
    pass

# --- Private Helper ---
async def _make_circle_request(method: str, endpoint: str, payload: dict) -> dict:
    """A helper function to make authenticated requests to the Circle API."""
    if not CIRCLE_API_KEY:
        raise CircleException("CIRCLE_API_KEY is not configured.")
    
    headers = {
        "Authorization": f"Bearer {CIRCLE_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CIRCLE_BASE_URL}{endpoint}"
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.request(method, url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()
    except httpx.HTTPStatusError as e:
        # Capture details from the response if available
        error_details = e.response.text
        raise CircleException(f"Circle API request failed: {e.response.status_code} - {error_details}")
    except httpx.RequestError as e:
        raise CircleException(f"Circle API request failed: {e}")

# --- Public API Functions ---
async def create_wallet(chat_id: str) -> Tuple[str, str]:
    """
    Creates a new Circle user and associated wallet.
    Returns a tuple of (user_id, wallet_id).
    """
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "description": f"User-{chat_id}"
    }
    data = await _make_circle_request("POST", "/users", payload)
    return data["data"]["userId"], data["data"]["walletId"]

async def generate_deposit_address(user_id: str) -> str:
    """
    Generates a new USDC deposit address for a user's wallet.
    """
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "chain": "MATIC",
        "currency": "USDC"
    }
    data = await _make_circle_request("POST", f"/users/{user_id}/addresses", payload)
    return data["data"]["address"]

async def forward_to_admin(wallet_id: str, amount_in_cents: int) -> dict:
    """
    Forwards a specified amount of USDC to the admin wallet.
    Amount should be in the smallest unit (e.g., cents for USDC).
    """
    if not ADMIN_USDC_ADDRESS:
        raise CircleException("ADMIN_USDC_ADDRESS is not configured.")

    # Circle API expects the amount as a string float, e.g., "1.23" for $1.23
    amount_float_str = f"{amount_in_cents / 100:.2f}"
    
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "destination": {"address": ADMIN_USDC_ADDRESS},
        "amount": {
            "amount": amount_float_str,
            "currency": "USDC"
        },
        "walletId": wallet_id,
        # TODO: Add fee level configuration if needed
        # "feeLevel": "MEDIUM" 
    }
    return await _make_circle_request("POST", "/transactions/transfer", payload) 
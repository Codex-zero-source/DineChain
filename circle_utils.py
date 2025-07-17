import os, httpx, uuid

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
CIRCLE_API_URL = os.getenv("CIRCLE_API_URL", "https://api-sandbox.circle.com")
HEADERS = {
    "Authorization": f"Bearer {CIRCLE_API_KEY}",
    "Content-Type": "application/json"
}

class CircleException(Exception):
    pass

async def _post(path: str, payload: dict):
    if not CIRCLE_API_KEY:
        raise CircleException("CIRCLE_API_KEY not set")
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{CIRCLE_API_URL}{path}", json=payload, headers=HEADERS, timeout=15)
    if r.status_code >= 300:
        raise CircleException(f"Circle API error {r.status_code}: {r.text}")
    return r.json()

async def create_wallet(chat_id: str):
    """Create a new wallet and return its ID."""
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "description": f"wallet-{chat_id}"
    }
    data = await _post("/v1/wallets", payload)
    # Circle returns the wallet ID under data.id
    wallet_id = data["data"]["id"]
    return wallet_id

async def generate_deposit_address(wallet_id: str):
    """Generate a USDC deposit address on Polygon for the given wallet."""
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "currency": "USD",        # must specify currency
        "chain": "POLYGON"
    }
    data = await _post(f"/v1/wallets/{wallet_id}/addresses", payload)
    # Circle returns the address under data.address
    return data["data"]["address"]

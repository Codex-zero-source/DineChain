import os
import httpx
import uuid

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

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f"{CIRCLE_API_URL}{path}", json=payload, headers=HEADERS)
        if response.status_code >= 300:
            raise CircleException(f"Circle API error {response.status_code}: {response.text}")
        return response.json()

async def _get(path: str):
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{CIRCLE_API_URL}{path}", headers=HEADERS)
        if response.status_code >= 300:
            raise CircleException(f"Circle API GET error {response.status_code}: {response.text}")
        return response.json()

async def create_or_get_wallet(ref_id: str) -> str:
    """
    Create a Circle developer wallet, or return an existing walletId if it already exists for this refId.
    """
    try:
        # Check for existing wallet
        res = await _get("/v1/w3s/developer/wallets")
        for wallet in res.get("data", []):
            if wallet.get("entitySecretCipherText") == ref_id:  # Not official usage, replace if Circle adds refId filter
                return wallet.get("id")

        # If not found, create new wallet
        payload = {
            "idempotencyKey": str(uuid.uuid4()),
            "blockchains": ["MATIC-MUMBAI"],
            "custodyType": "DEVELOPER",
            "entitySecretCipherText": ref_id
        }
        data = await _post("/v1/w3s/developer/wallets", payload)
        return data["data"]["id"]

    except Exception as e:
        raise CircleException(f"Failed to create or retrieve wallet: {e}")

async def generate_deposit_address(wallet_id: str) -> str:
    """
    Create a deposit address on Polygon (MATIC-MUMBAI) chain for given wallet.
    """
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "blockchain": "MATIC-MUMBAI"
    }
    data = await _post(f"/v1/w3s/developer/wallets/{wallet_id}/addresses", payload)
    return data["data"]["address"]

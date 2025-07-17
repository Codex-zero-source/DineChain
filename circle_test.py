import httpx
import uuid

# 🔐 Hardcoded API Key for testing (only use in sandbox/dev)
CIRCLE_API_KEY = "SAND_API_KEY:8ee2eb911933f85c6ea3eb486a2a310c:9bd11e5fbd5d78b9998de264141936b7"
CIRCLE_BASE_URL = "https://api-sandbox.circle.com/v1"
HEADERS = {
    "Authorization": f"Bearer {CIRCLE_API_KEY}",
    "Content-Type": "application/json"
}

async def create_wallet(ref_id: str):
    url = f"{CIRCLE_BASE_URL}/entity/wallets"
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "blockchain": "MATIC-MUMBAI",
        "custodyType": "DEVELOPER",
        "refId": ref_id,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=HEADERS, json=payload)
        if response.status_code != 201:
            raise Exception(f"Wallet creation failed: {response.text}")
        data = response.json()
        return data["data"]["walletId"]

async def generate_deposit_address(wallet_id: str):
    url = f"{CIRCLE_BASE_URL}/entity/wallets/{wallet_id}/addresses"
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "addressType": "DEPOSIT"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=HEADERS, json=payload)
        if response.status_code != 201:
            raise Exception(f"Address generation failed: {response.text}")
        data = response.json()
        return data["data"]["address"]

# Run test flow
import asyncio

async def test():
    print("🧪 Creating wallet and address for test user...")
    wallet_id = await create_wallet("test-user-123")
    print("✅ Wallet ID:", wallet_id)
    address = await generate_deposit_address(wallet_id)
    print("🏦 Deposit Address:", address)

if __name__ == "__main__":
    asyncio.run(test())

import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from httpx import AsyncClient
from app import app
from orders import get_db_conn
import time
import stripe
import os

pytestmark = pytest.mark.asyncio

# --- Mock Data ---
MOCK_LLM_ORDER_CONFIRMATION = {
    "action": "confirm_order",
    "data": {
        "items": [
            {"name": "Jollof Rice", "quantity": 1, "price_in_cents": 80},
            {"name": "Chicken", "quantity": 1, "price_in_cents": 70}
        ],
        "total_in_cents": 150,
        "delivery_info": "Table 5"
    }
}

MOCK_STRIPE_SESSION = MagicMock(
    url="https://checkout.stripe.com/mock_url",
    client_reference_id="mock_stripe_ref_123"
)

# --- Tests ---

@patch('app.get_llm_response')
@patch('stripe_utils.create_stripe_checkout_session', return_value=("https://checkout.stripe.com/mock_url", "mock_stripe_ref_123"))
async def test_stripe_payment_flow(mock_create_stripe_session, mock_get_llm_response, client: AsyncClient):
    """
    Tests the full Stripe payment flow:
    1. User sends a message to start an order.
    2. Mock LLM confirms the order with a JSON response.
    3. App saves the order and asks for payment method.
    4. User replies 'card' to choose Stripe.
    5. App calls Stripe, generates a link, and updates the order.
    6. App sends the Stripe link back to the user.
    """
    # Mock the LLM to return an order confirmation
    mock_get_llm_response.return_value = {
        'choices': [{'message': {'content': json.dumps(MOCK_LLM_ORDER_CONFIRMATION)}}]
    }

    # 1. User starts order
    response = await client.post("/webhook", json={
        "message": {"chat": {"id": "user123"}, "text": "I want to order", "from": {"first_name": "Stripe"}}
    })
    assert response.status_code == 200

    # 2. Verify order was created in DB and user was asked for payment
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT * FROM orders WHERE chat_id = 'user123' AND paid = 0")
        order = await cursor.fetchone()
        assert order is not None
        assert order['total_in_cents'] == 150

    # 3. User chooses 'card'
    with patch('app.send_user_message') as mock_send_message:
        response = await client.post("/webhook", json={
            "message": {"chat": {"id": "user123"}, "text": "pay with card", "from": {"first_name": "Stripe"}}
        })
        assert response.status_code == 200

        # 4. Verify Stripe session was created and link was sent
        mock_create_stripe_session.assert_called_once()
        mock_send_message.assert_called_with(
            "telegram",
            "user123",
            "Please complete your payment here: https://checkout.stripe.com/mock_url"
        )

    # 5. Verify the order in the DB was updated with the Stripe reference
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT reference, payment_method FROM orders WHERE id = ?", (order['id'],))
        updated_order = await cursor.fetchone()
        assert updated_order is not None
        assert updated_order['reference'] is not None
        assert updated_order['payment_method'] == 'card' 

@patch('app.get_llm_response')
@patch('circle_utils.generate_deposit_address', return_value="mock_usdc_address_123")
@patch('circle_utils.create_wallet', return_value=("mock_user_id_456", "mock_wallet_id_789"))
async def test_crypto_payment_flow(mock_create_wallet, mock_generate_address, mock_get_llm_response, client: AsyncClient):
    """
    Tests the full crypto payment flow:
    1. User starts an order, mock LLM confirms it.
    2. App saves the order.
    3. User replies 'crypto'.
    4. App creates a new Circle wallet for the user (since it's their first time).
    5. App generates a deposit address and sends it to the user.
    6. App updates the order in the DB with the payment details.
    """
    # Mock the LLM to return an order confirmation
    mock_get_llm_response.return_value = {
        'choices': [{'message': {'content': json.dumps(MOCK_LLM_ORDER_CONFIRMATION)}}]
    }

    # 1. User starts order
    await client.post("/webhook", json={
        "message": {"chat": {"id": "crypto_user_1"}, "text": "I want to order", "from": {"first_name": "Crypto"}}
    })

    # 2. User chooses 'crypto'
    with patch('app.send_user_message') as mock_send_message:
        response = await client.post("/webhook", json={
            "message": {"chat": {"id": "crypto_user_1"}, "text": "pay with crypto", "from": {"first_name": "Crypto"}}
        })
        assert response.status_code == 200

        # 3. Verify Circle wallet was created, address generated, and message sent
        mock_create_wallet.assert_called_once_with("crypto_user_1")
        mock_generate_address.assert_called_once_with("mock_user_id_456")
        mock_send_message.assert_called_with(
            "telegram",
            "crypto_user_1",
            "Please send `$1.50` USDC to the address below (Polygon network):\n\n`mock_usdc_address_123`\n\nI'll notify you once payment is confirmed."
        )

    # 4. Verify wallet was saved to the DB
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT * FROM circle_wallets WHERE chat_id = 'crypto_user_1'")
        wallet = await cursor.fetchone()
        assert wallet is not None
        assert wallet['user_id'] == "mock_user_id_456"

    # 5. Verify the order was updated correctly
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT deposit_address, payment_method FROM orders WHERE chat_id = 'crypto_user_1'")
        order = await cursor.fetchone()
        assert order is not None
        assert order['deposit_address'] == "mock_usdc_address_123"
        assert order['payment_method'] == 'crypto' 

# --- Test Setup ---
def sign_stripe_payload(payload_str: str, secret: str) -> str:
    """Generates a Stripe signature for a given payload."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_str}"
    signature = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    return f"t={timestamp},v1={signature}"

async def setup_test_order(chat_id: str, platform: str, reference: str, total_cents: int) -> int:
    """Inserts a mock order into the database for testing and returns its ID."""
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            """INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total_in_cents, reference, paid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, platform, "Webhook Customer", '[{"name":"Test Item","price_in_cents":1000,"quantity":1}]', 
             "Test Delivery", total_cents, reference, 0)
        )
        await conn.commit()
        order_id = cursor.lastrowid
        if order_id is None:
            raise RuntimeError("Failed to get lastrowid after inserting test order.")
        return order_id

async def setup_crypto_test_order(chat_id: str, platform: str, deposit_address: str, total_cents: int) -> int:
    """Inserts a mock crypto order into the database for testing and returns its ID."""
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            """INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total_in_cents, payment_method, deposit_address, paid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, platform, "Crypto Customer", '[{"name":"Crypto Item","price_in_cents":2500,"quantity":1}]', 
             "Crypto Delivery", total_cents, "crypto", deposit_address, 0)
        )
        await conn.commit()
        order_id = cursor.lastrowid
        if order_id is None:
            raise RuntimeError("Failed to get lastrowid after inserting crypto test order.")
        return order_id


# --- Webhook Tests ---

@patch('app.send_user_message')
async def test_stripe_webhook_success(mock_send_message, client: AsyncClient):
    """Tests the successful processing of a Stripe webhook event."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    chat_id = "stripe_webhook_user"
    platform = "telegram"
    reference = "test_stripe_webhook_ref_123"
    order_id = await setup_test_order(chat_id, platform, reference, 1500)

    event_payload = {
        "id": "evt_test_webhook", "type": "checkout.session.completed",
        "data": { "object": {
            "id": "cs_test_123", "object": "checkout.session",
            "client_reference_id": reference,
            "metadata": {"chat_id": chat_id, "delivery": "Test Delivery", "platform": platform}
        }}
    }
    payload_str = json.dumps(event_payload)
    headers = {"Stripe-Signature": sign_stripe_payload(payload_str, secret)}

    response = await client.post("/stripe-webhook", content=payload_str, headers=headers)
    assert response.status_code == 200

    # Verify order is marked as paid
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT paid FROM orders WHERE id = ?", (order_id,))
        order = await cursor.fetchone()
        assert order is not None
        assert order['paid'] == 1

    # Verify messages were sent
    assert mock_send_message.call_count == 2
    mock_send_message.assert_any_call(platform, chat_id, "✅ Payment successful! Your order is being prepared.")
    # A more specific check could be done for the kitchen message content if needed
    mock_send_message.assert_any_call("telegram", os.getenv("KITCHEN_CHAT_ID"), ANY) 

@patch('app.send_user_message')
async def test_circle_webhook_success(mock_send_message, client: AsyncClient):
    """Tests the successful processing of a Circle webhook event."""
    chat_id = "circle_webhook_user"
    platform = "telegram"
    address = "test_usdc_address_xyz"
    total_cents = 2500
    order_id = await setup_crypto_test_order(chat_id, platform, address, total_cents)

    event_payload = {
        "notificationType": "AddressDeposits",
        "deposit": {
            "status": "CONFIRMED",
            "address": address,
            "amount": {"amount": "25.00", "currency": "USD"}
        }
    }

    response = await client.post("/circle/webhook", json=event_payload)
    assert response.status_code == 200

    # Verify order is marked as paid
    async with get_db_conn() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT paid FROM orders WHERE id = ?", (order_id,))
        order = await cursor.fetchone()
        assert order is not None
        assert order['paid'] == 1

    # Verify messages were sent
    assert mock_send_message.call_count == 2
    mock_send_message.assert_any_call(
        platform, 
        chat_id, 
        "✅ Payment of $25.00 USDC confirmed. Your order is now processing!"
    )
    mock_send_message.assert_any_call("telegram", os.getenv("KITCHEN_CHAT_ID"), ANY) 
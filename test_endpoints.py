import requests
import json
import os
import sqlite3
import time
import stripe
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:5000"
DB_FILE = "orders.db"
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def setup_test_order(conn):
    """Inserts a mock order into the database for testing."""
    test_ref = f"test_ref_{int(time.time())}"
    chat_id = "test_chat_id"
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total, reference, paid) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, "test_platform", "Test Customer", '{"item": "test"}', "Test Delivery", 1000, test_ref, 0)
    )
    conn.commit()
    return test_ref, chat_id

def construct_stripe_event(event_type, ref, chat_id):
    """Constructs a mock Stripe event payload."""
    return {
        "id": "evt_test_webhook",
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_123",
                "object": "checkout.session",
                "client_reference_id": ref,
                "metadata": {
                    "chat_id": chat_id,
                    "delivery": "Test Delivery",
                    "platform": "test_platform",
                    "reference": ref
                },
            }
        }
    }

def sign_payload(payload_str, secret):
    """Generates a Stripe signature for a given payload."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_str}"
    signature = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    return f"t={timestamp},v1={signature}"

def test_telegram_webhook():
    """Simulates a message from Telegram to the bot."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "message": {
            "chat": {"id": "12345"},
            "text": "Hello, I want to order Jollof Rice",
            "from": {"first_name": "Test User"}
        }
    }
    try:
        r = requests.post(f"{BASE_URL}/webhook", headers=headers, json=payload, timeout=5)
        print(f"POST /webhook -> {r.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"POST /webhook -> Failed to connect: {e}")

def test_stripe_webhook_success():
    """Tests the successful handling of a 'checkout.session.completed' event."""
    if not STRIPE_WEBHOOK_SECRET:
        print("STRIPE_WEBHOOK_SECRET not set, skipping webhook test.")
        return

    conn = sqlite3.connect(DB_FILE)
    test_ref, chat_id = setup_test_order(conn)
    
    try:
        event_payload = construct_stripe_event("checkout.session.completed", test_ref, chat_id)
        payload_str = json.dumps(event_payload, separators=(',', ':'))
        sig_header = sign_payload(payload_str, STRIPE_WEBHOOK_SECRET)
        headers = {"Stripe-Signature": sig_header, "Content-Type": "application/json"}

        print("\n--- Running test_stripe_webhook_success ---")
        r = requests.post(f"{BASE_URL}/stripe-webhook", data=payload_str, headers=headers)
        print(f"POST /stripe-webhook -> {r.status_code}")
        assert r.status_code == 200

        cursor = conn.cursor()
        cursor.execute("SELECT paid FROM orders WHERE reference = ?", (test_ref,))
        result = cursor.fetchone()
        assert result is not None and result[0] == 1
        print("✅ Success: Order was correctly marked as paid.")

    finally:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE reference = ?", (test_ref,))
        conn.commit()
        conn.close()

def test_stripe_webhook_invalid_signature():
    """Tests that the webhook rejects requests with an invalid signature."""
    if not STRIPE_WEBHOOK_SECRET:
        print("STRIPE_WEBHOOK_SECRET not set, skipping webhook test.")
        return

    event_payload = construct_stripe_event("checkout.session.completed", "any_ref", "any_chat_id")
    payload_str = json.dumps(event_payload, separators=(',', ':'))
    headers = {"Stripe-Signature": "t=123,v1=invalid_signature", "Content-Type": "application/json"}

    print("\n--- Running test_stripe_webhook_invalid_signature ---")
    r = requests.post(f"{BASE_URL}/stripe-webhook", data=payload_str, headers=headers)
    print(f"POST /stripe-webhook (invalid signature) -> {r.status_code}")
    assert r.status_code == 400
    print("✅ Success: Correctly returned 400 for invalid signature.")

def test_stripe_webhook_missing_ref():
    """Tests the webhook's handling of an event with a missing client_reference_id."""
    if not STRIPE_WEBHOOK_SECRET:
        print("STRIPE_WEBHOOK_SECRET not set, skipping webhook test.")
        return

    event_payload = construct_stripe_event("checkout.session.completed", None, "any_chat_id")
    payload_str = json.dumps(event_payload, separators=(',', ':'))
    sig_header = sign_payload(payload_str, STRIPE_WEBHOOK_SECRET)
    headers = {"Stripe-Signature": sig_header, "Content-Type": "application/json"}

    print("\n--- Running test_stripe_webhook_missing_ref ---")
    r = requests.post(f"{BASE_URL}/stripe-webhook", data=payload_str, headers=headers)
    print(f"POST /stripe-webhook (missing ref) -> {r.status_code}")
    assert r.status_code == 400
    print("✅ Success: Correctly returned 400 for missing reference ID.")

def test_stripe_webhook_unhandled_event():
    """Tests that the webhook correctly handles an unmanaged event type."""
    if not STRIPE_WEBHOOK_SECRET:
        print("STRIPE_WEBHOOK_SECRET not set, skipping webhook test.")
        return
        
    event_payload = construct_stripe_event("payment_intent.created", "any_ref", "any_chat_id")
    payload_str = json.dumps(event_payload, separators=(',', ':'))
    sig_header = sign_payload(payload_str, STRIPE_WEBHOOK_SECRET)
    headers = {"Stripe-Signature": sig_header, "Content-Type": "application/json"}

    print("\n--- Running test_stripe_webhook_unhandled_event ---")
    r = requests.post(f"{BASE_URL}/stripe-webhook", data=payload_str, headers=headers)
    print(f"POST /stripe-webhook (unhandled event) -> {r.status_code}")
    assert r.status_code == 200
    print("✅ Success: Correctly returned 200 for an unhandled event.")

if __name__ == "__main__":
    test_telegram_webhook()
    test_stripe_webhook_success()
    test_stripe_webhook_invalid_signature()
    test_stripe_webhook_missing_ref()
    test_stripe_webhook_unhandled_event() 
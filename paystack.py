import os
import requests
import uuid

def create_paystack_link(email, amount):
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    domain_url = os.getenv("DOMAIN_URL")
    if not (secret_key or domain_url):
        raise Exception("Missing PAYSTACK_SECRET_KEY in .env")

    reference = str(uuid.uuid4())  # Unique ID

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": amount * 100,  # Paystack uses kobo
        "reference": reference,
        "currency": "NGN",
        "callback_url": f"https://{domain_url}/verify?reference={reference}"
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
    data = response.json()

    if not data.get("status"):
        raise Exception(f"Paystack error: {data}")

    payment_url = data["data"]["authorization_url"]
    return payment_url, reference

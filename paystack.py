import os
import requests
import uuid

def create_paystack_link(email, amount, chat_id, order_summary):
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    reference = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": amount * 100,
        "reference": reference,
        "currency": "NGN",
        "callback_url": f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/verify?reference={reference}",
        "metadata": {
            "chat_id": chat_id,
            "order_summary": order_summary
        }
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
    data = response.json()

    if not data.get("status"):
        raise Exception(f"Paystack error: {data}")

    payment_url = data["data"]["authorization_url"]
    return payment_url, reference

import os
import stripe
import uuid
import json

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_stripe_checkout_session(email, order_items, chat_id, delivery_info, platform="telegram"):
    reference = str(uuid.uuid4())
    success_url = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/cancel"

    line_items = []
    for item in order_items:
        line_items.append({
            'price_data': {
                'currency': 'ngn',
                'product_data': {
                    'name': item.get('name', 'Unnamed Item'),
                },
                'unit_amount': int(item.get('price', 0) * 100),
            },
            'quantity': item.get('quantity', 1),
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=reference,
            customer_email=email,
            metadata={
                "chat_id": chat_id,
                "order_summary": json.dumps(order_items),
                "delivery": delivery_info,
                "platform": platform,
                "reference": reference
            }
        )
        return checkout_session.url, reference
    except Exception as e:
        # Handle Stripe API errors
        raise Exception(f"Stripe error: {e}") 
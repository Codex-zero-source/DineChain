import os
import stripe
import uuid
import json
import asyncio

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_stripe_checkout_session(order_id, email, order_items, chat_id, delivery_info, platform="telegram"):
    success_url = f"{os.getenv('APP_URL')}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{os.getenv('APP_URL')}/cancel"

    line_items = []
    for item in order_items:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item.get('name', 'Unnamed Item'),
                },
                'unit_amount': int(item.get('price', 0) * 100),
            },
            'quantity': item.get('quantity', 1),
        })

    try:
        checkout_session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=email,
            metadata={
                "order_id": order_id,
                "chat_id": chat_id,
                "delivery": delivery_info,
                "platform": platform,
            }
        )
        return checkout_session.url, checkout_session.id
    except Exception as e:
        # Handle Stripe API errors
        raise Exception(f"Stripe error: {e}") 
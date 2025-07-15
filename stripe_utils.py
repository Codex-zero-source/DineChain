import os
import stripe
import uuid
import json
import asyncio
from typing import List, Dict, Any, Tuple

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class StripeException(Exception):
    """Custom exception for Stripe-related errors."""
    pass

async def create_stripe_checkout_session(email: str, order_items: List[Dict[str, Any]], chat_id: str, delivery_info: str, platform: str = "telegram") -> Tuple[str, str]:
    """
    Creates a Stripe Checkout session.
    Args:
        email: The customer's email address.
        order_items: A list of dictionaries, where each dict represents an item in the order.
                     Example: [{'name': 'Jollof Rice', 'price_in_cents': 80, 'quantity': 1}]
        chat_id: The chat ID of the user.
        delivery_info: Delivery information for the order.
        platform: The platform the user is on (e.g., 'telegram').
    Returns:
        A tuple containing the checkout session URL and the internal reference ID.
    Raises:
        StripeException: If there is an error with the Stripe API.
    """
    if not stripe.api_key:
        raise StripeException("Stripe API key is not configured.")

    base_url = os.getenv("BASE_URL", f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com")
    success_url = f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/cancel"
    reference = str(uuid.uuid4())

    line_items = []
    for item in order_items:
        if not all(k in item for k in ['name', 'price_in_cents', 'quantity']):
            # Skip invalid items but log the issue
            print(f"Skipping invalid item in order_items: {item}")
            continue
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item['name'],
                },
                'unit_amount': item['price_in_cents'],
            },
            'quantity': item['quantity'],
        })

    if not line_items:
        raise StripeException("Cannot create a Stripe session with no valid line items.")

    try:
        checkout_session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=reference,
            customer_email=email,
            metadata={
                "chat_id": chat_id,
                "delivery": delivery_info,
                "platform": platform,
                "reference": reference
            }
        )
        if not checkout_session.url:
            raise StripeException("Stripe session was created, but no URL was returned.")
        return checkout_session.url, reference
    except stripe.StripeError as e:
        # Catch specific Stripe errors and re-raise as a custom exception
        raise StripeException(f"Stripe API error: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        raise StripeException(f"An unexpected error occurred during Stripe session creation: {e}") 
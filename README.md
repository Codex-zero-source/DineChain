# JollofAI

JollofAI is an AI-powered WhatsApp and Telegram bot that helps customers of a restaurant to place orders for food and drinks.

## Features

- **Conversational Ordering:** Customers can place orders in a natural, conversational way.
- **Stripe Integration:** Securely process payments using Stripe.
- **Telegram & WhatsApp Integration:** Works with both Telegram and WhatsApp.
- **Order Notifications:** Instantly notifies the kitchen of new orders.

## Getting Started

### Prerequisites

- Python 3.10+
- `pip` for package management
- A Stripe account
- A Telegram bot token
- Twilio account for WhatsApp

### Installation

1.  **Clone the repository:**

```bash
git clone https://github.com/Codex-zero-source/JollofAI
cd JollofAI
```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**

    Create a `.env` file in the root directory and add the following:

    ```env
    TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
    LLM_API_KEY="your_llm_api_key"
    BASE_URL="your_llm_base_url"
    KITCHEN_CHAT_ID="your_kitchen_chat_id"
    STRIPE_SECRET_KEY="your_stripe_secret_key"
    STRIPE_WEBHOOK_SECRET="your_stripe_webhook_secret"
    TWILIO_ACCOUNT_SID="your_twilio_account_sid"
    TWILIO_AUTH_TOKEN="your_twilio_auth_token"
    TWILIO_WHATSAPP_NUMBER="your_twilio_whatsapp_number"
    ```

### Running the App

1.  **Initialize the database:**

    The database is initialized automatically when the app starts.

2.  **Run the Flask app:**

    ```bash
    flask run
    ```

3.  **Set up webhooks:**

    -   **Telegram:** You'll need to set up a webhook to point to your server's `/webhook` endpoint. You can use a tool like `ngrok` for local development.

        ```bash
        curl -F "url=https://your-domain.com/webhook" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
        ```

    -   **Twilio (WhatsApp):** Configure the webhook URL in your Twilio dashboard to point to `/twilio_webhook`.

## 🪙 Crypto Payments (USDC via Circle)

Set the following environment variables (see `env.example`):

| Variable | Description |
|----------|-------------|
| `CIRCLE_API_KEY` | Circle sandbox / prod API key |
| `CIRCLE_API_URL` | `https://api-sandbox.circle.com` for testing |
| `CIRCLE_ADMIN_WALLET` | Wallet ID that ultimately receives funds |

Flow:
1. After order confirmation bot asks **Card / Crypto**.
2. If **Crypto** selected it creates a Circle customer wallet and deposit address, replies with USDC amount & address (Polygon).
3. When Circle webhook `AddressDeposits` reports `CONFIRMED`, order is marked paid, user & kitchen notified.

> For production switch `CIRCLE_API_URL` to Circle mainnet endpoint and update your webhook URL in Circle console to `https://your-domain/circle/webhook`.

## Project Structure

```
.
├── app.py           # Main Flask application
├── admin.py         # Admin routes and logic
├── orders.py        # Database schema and order management
├── stripe.py        # Stripe integration logic
├── set_webhook.py   # Script to set the Telegram webhook
├── requirements.txt # Python dependencies
├── .env             # Example environment variables
└── README.md
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
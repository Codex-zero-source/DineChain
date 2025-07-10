# JollofAI

JollofAI is an AI-driven chatbot that simplifies ordering food wherever you are. Whether your customers prefer Telegram or WhatsApp, JollofAI handles everything: greeting them, guiding them through the menu, processing payments, and notifying the kitchen once orders are confirmed.

## 🚀 Key Features

- **Natural Conversations**: Powered by a state-of-the-art LLM (meta-llama/Llama-3.3-70B-Instruct) to make chats feel smooth and intuitive.
- **Multiple Channels**: Works seamlessly on both Telegram and WhatsApp.
- **Interactive Menu**: Presents a dynamic menu, suggests popular dishes, and adapts to customer preferences.
- **Order Management**: Guides users through choosing items, confirming details, and calculating totals automatically.
- **Secure Payments**: Generates Paystack payment links and verifies transactions in real time.
- **Kitchen Notifications**: Once payment clears, JollofAI sends a concise order summary to your kitchen’s Telegram group.
- **Asynchronous & Scalable**: Built with asyncio, httpx, and aiosqlite for high performance under load.
- **Admin Dashboard**: A simple web interface lets you view and manage all orders in one place.

## ⚙️ Architecture Overview

### Messaging Layer

- Telegram Bot API
- Twilio WhatsApp API

### Business Logic

- Flask (with async support) to handle incoming messages and webhooks.
- IO.net API for LLM-driven chat intelligence.

### Payments

- Paystack for secure, seamless transactions.

### Data Storage

- SQLite (via aiosqlite) for lightweight, file-based storage.

### Web Interface

- An admin dashboard to track and manage orders.

## 🔧 Getting Started

- [Test a running version](https://t.me/IO_agent_bot)

### Clone the repo

```bash
git clone https://github.com/Codex-zero-source/JollofAI
cd JollofAI
```

### Set up a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file at the project root and add:

```
# Telegram
TELEGRAM_BOT_TOKEN=...
LLM_API_KEY=...
KITCHEN_CHAT_ID=...
BASE_URL=...  # LLM API endpoint

# Paystack
PAYSTACK_SECRET_KEY=...

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=...

# Deployment (e.g., Render service)
RENDER_SERVICE_NAME=...
```

### Initialize the database

```bash
python orders.py
```

### Run the server

```bash
flask run --app app.py
```

### Expose your webhook (for development)

```bash
ngrok http 5000
```

This will give you a public HTTPS URL. Copy it, as you'll need it for the next step.

## Webhook Configuration

For the bot to receive messages, you need to configure webhooks for Telegram and Twilio to point to your running application.

### Telegram Webhook

Telegram sends message updates to a webhook URL you specify.

-   **URL**: `https://<your-public-url>/webhook`
-   **Method**: `POST`


-  **Using the provided script**:
    The `set_webhook.py` script uses the `RENDER_SERVICE_NAME` environment variable to construct the full URL and register it.
    ```bash
    python set_webhook.py
    ```

### Twilio (WhatsApp) Webhook

1.  Go to your **Twilio Console**.
2.  Navigate to **Messaging > Senders > WhatsApp Senders**.
3.  Select your WhatsApp number.
4.  Find the webhook configuration section. In the field labeled **"WHEN A MESSAGE COMES IN"**, enter your public URL with the `/twilio_webhook` endpoint.
    -   **URL**: `https://<your-public-url>/twilio_webhook`
    -   **Method**: `HTTP POST`
5.  Save your changes.
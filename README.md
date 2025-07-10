# JollofAI - The Multichannel Food Ordering Bot

JollofAI is an intelligent, AI-powered chatbot designed to streamline the food ordering process. It can handle customer interactions, take orders, process payments, and send notifications to the kitchen, all through familiar messaging platforms like Telegram and WhatsApp.

## Features

- **AI-Powered Conversations:** Uses a meta-llama/Llama-3.3-70B-Instruct to provide natural and helpful interactions.
- **Multi-Platform Support:** Seamlessly integrated with both Telegram and WhatsApp.
- **Dynamic Menu:** Can present a full menu with recommendations to customers.
- **Order Management:** Guides users through selecting items, confirming orders, and calculating totals.
- **Integrated Payments:** Generates Paystack payment links for secure transactions.
- **Kitchen Notifications:** Automatically sends order details to the kitchen's Telegram group upon successful payment.
- **Asynchronous Architecture:** Built with `asyncio`, `httpx`, and `aiosqlite` for high performance and scalability.
- **Admin Dashboard:** A simple web interface to view all orders.

## How It Works

The bot interacts with users on their preferred platform (Telegram or WhatsApp):

1.  **Greeting & Menu:** The bot greets the user, asks for their name, and presents the menu.
2.  **Order Taking:** The user selects items, and the AI assistant confirms the selections.
3.  **Payment:** Once the order is confirmed, the bot calculates the total and provides a Paystack link.
4.  **Verification & Confirmation:** After payment, the system verifies the transaction, confirms the order with the user, and sends the order details to the kitchen's Telegram group.

## Architecture

- **Backend:** Flask (with async support)
- **Messaging Platforms:**
    - Telegram (via Telegram Bot API)
    - WhatsApp (via Twilio API for WhatsApp)
- **AI:** IO.net API (for Large Language Model access)
- **Payments:** Paystack
- **Database:** SQLite (with `aiosqlite` for async operations)
- **HTTP Client:** `httpx` for asynchronous API calls

## Setup and Deployment Guide

### 1. Prerequisites

- Python 3.11+
- A [Render](https://render.com/) account (or another deployment platform)
- API keys and credentials from:
    - Telegram (for a bot)
    - An LLM provider (like OpenAI)
    - Paystack
    - Twilio

### 2. Clone the Repository

```bash
git clone repo
cd repo
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set Up Environment Variables

Create a `.env` file in the root of the project and add the following variables.

```
# Telegram
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
LLM_API_KEY=YOUR_LLM_API_KEY
KITCHEN_CHAT_ID=YOUR_KITCHEN_TELEGRAM_CHAT_ID
BASE_URL=YOUR_IO.NET_API_ENDPOINT # The API endpoint for the IO.net LLM

# Paystack
PAYSTACK_SECRET_KEY=YOUR_PAYSTACK_SECRET_KEY

# Twilio (for WhatsApp)
TWILIO_ACCOUNT_SID=YOUR_TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN=YOUR_TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER=YOUR_TWILIO_WHATSAPP_NUMBER

# Deployment (e.g., Render service name)
RENDER_SERVICE_NAME=your-service-name-on-render
```

### 6. Initialize the Database

Run the `orders.py` script to create the initial database file (`orders.db`).

```bash
python orders.py
```
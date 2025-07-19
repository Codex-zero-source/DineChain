# DineChain API

DineChain is an AI-powered chatbot designed to streamline the food ordering process for restaurants. It allows users to place orders, make payments via card or cryptocurrency, and receive real-time updates through a conversational interface on platforms like Telegram and WhatsApp.

## Features

-   **Conversational Ordering**: A natural language interface for placing food and drink orders.
-   **Multi-Platform Support**: Works with both Telegram and WhatsApp.
-   **Dual Payment Options**: Supports payments via Stripe (credit/debit cards) and cryptocurrency (USDC on the Fuji testnet).
-   **Real-Time Notifications**: Keeps the user and kitchen updated on the order status.
-   **Admin Dashboard**: A simple web interface to view all orders.

## Project Structure

The project is organized into the following structure:

```
.
├── dinechain_api
│   ├── __init__.py
│   ├── app.py
│   ├── blueprints
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   └── orders.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── crypto_payment.py
│   │   └── llm.py
│   └── utils
│       ├── __init__.py
│       ├── set_webhook.py
│       └── stripe_utils.py
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

## Setup and Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/Codex-zero-source/JollofAI.git
    cd JollofAI
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**

    Create a `.env` file in the root directory and copy the contents of `.env.example`. Fill in the required API keys and tokens.

5.  **Run the application:**

    ```bash
    python main.py
    ```

## How It Works

The application's core is a **Flask** web server that processes incoming messages and manages the order lifecycle. Here’s a step-by-step breakdown of the process:

1.  **Webhook Listeners**: The application exposes webhook endpoints (`/webhook` for Telegram and `/twilio_webhook` for WhatsApp) to receive incoming user messages.

2.  **Message Processing**: The `process_message` function is the central hub for handling user input. It uses a locking mechanism to ensure that messages from the same user are processed sequentially, preventing race conditions.

3.  **Conversational AI**:
    *   The user's conversation history is passed to a Large Language Model (LLM).
    *   The LLM interprets the user's intent, guides them through menu selection, and confirms order details.

4.  **Order Creation**:
    *   Once the user confirms their order, the LLM generates a JSON summary.
    *   This summary is parsed, and a new order is created in the database with an "unpaid" status.
    -   The user is then prompted to choose a payment method: Card or Crypto.

5.  **Payment Flows**:
    *   **Card (Stripe)**: If the user selects "Card," a Stripe Checkout session is created, and a payment link is sent to the user. A dedicated `/stripe-webhook` endpoint listens for payment confirmation from Stripe.
    *   **Crypto (USDC)**: If the user selects "Crypto," a new wallet on the Fuji testnet is generated, and the user is asked to send the required amount of USDC to that address.

6.  **Payment Verification**:
    *   A background thread (`payment_watcher_thread`) runs continuously to monitor crypto payments.
    *   It periodically queries the Snowtrace API to check for incoming transactions to the generated deposit addresses.
    *   When a valid crypto payment is detected or a Stripe payment is confirmed, the order's status in the database is updated to "paid."

7.  **Final Confirmation**: Once an order is marked as paid, the `_notify_user_and_kitchen` function is triggered, sending a final confirmation receipt to the customer and a notification to the kitchen.

8.  **Admin Dashboard**: A simple web interface at the `/admin` route allows for viewing all orders and their current status.
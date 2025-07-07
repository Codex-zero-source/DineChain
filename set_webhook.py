# set_webhook.py
import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SERVICE_NAME = os.getenv("RENDER_SERVICE_NAME")  # e.g. telegram-bot

PRODUCTION_URL = f"https://{SERVICE_NAME}.onrender.com/webhook"

def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    res = requests.post(url, data={"url": PRODUCTION_URL})
    print("Webhook set:", res.json())

if __name__ == "__main__":
    set_webhook()

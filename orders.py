import json
import re

# Menu database
MENU = {
    "food": {
        "jollof rice": 1500,
        "fried rice": 1500,
        "pizza": 2500,
        "shawarma": 1800
    },
    "drinks": {
        "mojitos": 1000,
        "tequila": 2000,
        "hollandia": 800,
        "pepsi": 500,
        "coca cola": 500
    }
}

def calculate_total(order_text):
    total = 0
    items = []

    text = order_text.lower()

    for category in MENU:
        for item, price in MENU[category].items():
            if re.search(rf"\b{re.escape(item)}\b", text):
                total += price
                items.append((item.title(), price))

    return total, items

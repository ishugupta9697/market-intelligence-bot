import requests
import os

token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

message = "✅ Market Intelligence Bot is LIVE.\nYou will receive alerts here."

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": message
}

requests.post(url, json=payload)

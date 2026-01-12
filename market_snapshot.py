import yfinance as yf
import requests
import os
from datetime import datetime, timedelta

# Telegram credentials
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, json=payload)

# Market symbols
symbols = {
    "NIFTY 50": "^NSEI",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "ITC": "ITC.NS",
    "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS",
    "MARUTI": "MARUTI.NS",
    "GOLD ETF": "GOLDBEES.NS",
    "USD-INR": "USDINR=X"
}

# IST time using reliable UTC offset
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)
current_time = ist_now.strftime("%d %b %Y | %I:%M %p IST")

lines = []

for name, ticker in symbols.items():
    data = yf.Ticker(ticker).history(period="1d")
    if not data.empty:
        price = round(data["Close"].iloc[-1], 2)
        lines.append(f"{name}: {price}")
    else:
        lines.append(f"{name}: data unavailable")

message = (
    "📊 Market Snapshot\n"
    f"{current_time}\n\n" +
    "\n".join(lines)
)

send_telegram(message)

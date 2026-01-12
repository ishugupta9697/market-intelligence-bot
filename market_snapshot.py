import yfinance as yf
import requests
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=payload)

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

lines = []
now = datetime.now().strftime("%d %b %Y | %I:%M %p")

for name, ticker in symbols.items():
    data = yf.Ticker(ticker).history(period="1d")
    if not data.empty:
        price = round(data["Close"].iloc[-1], 2)
        lines.append(f"{name}: {price}")
    else:
        lines.append(f"{name}: data unavailable")

message = "📊 Market Snapshot\n" + now + "\n\n" + "\n".join(lines)

send_telegram(message)

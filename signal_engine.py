import yfinance as yf
import requests
import os
import json
from datetime import datetime, timedelta, time
import pandas as pd

from performance_tracker import log_trade

# ================= TELEGRAM =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

# ================= TIME CONTROL =================
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)
weekday = ist_now.weekday()
now_time = ist_now.time()

MARKET_OPEN = time(9, 20)
INTRADAY_ENTRY_CUTOFF = time(13, 30)
MARKET_CLOSE = time(15, 10)

if weekday > 4 or now_time < MARKET_OPEN or now_time > MARKET_CLOSE:
    exit()

time_now = ist_now.strftime("%d %b %Y | %I:%M %p IST")

# ================= STATE =================
STATE_FILE = "active_trades.json"
DAY_FILE = "intraday_count.json"

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

state = load_json(STATE_FILE, {})
intraday_count = load_json(DAY_FILE, {"date": ist_now.strftime("%Y-%m-%d"), "count": 0})

# Reset intraday counter daily
if intraday_count["date"] != ist_now.strftime("%Y-%m-%d"):
    intraday_count = {"date": ist_now.strftime("%Y-%m-%d"), "count": 0}

# ================= SYMBOLS =================
symbols = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN"

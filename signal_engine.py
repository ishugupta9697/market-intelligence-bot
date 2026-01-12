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
    "SBIN": "SBIN.NS",
    "ITC": "ITC.NS",
    "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS",
    "MARUTI": "MARUTI.NS"
}

# ================= INDICATORS =================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def vwap(high, low, close, volume):
    typical_price = (high + low + close) / 3
    return (typical_price * volume).cumsum() / volume.cumsum()

# ================= INTRADAY ENTRY =================
if now_time <= INTRADAY_ENTRY_CUTOFF and intraday_count["count"] < 3:

    for name, ticker in symbols.items():
        if name in state:
            continue

        data = yf.download(
            ticker, period="5d", interval="15m", progress=False, auto_adjust=True
        )
        if data.empty or len(data) < 50:
            continue

        close = data["Close"].astype(float)
        high = data["High"].astype(float)
        low = data["Low"].astype(float)
        volume = data["Volume"].astype(float)

        ema9 = close.ewm(span=9).mean()
        ema21 = close.ewm(span=21).mean()
        rsi_val = rsi(close)
        vwap_val = vwap(high, low, close, volume)

        entry = float(close.iloc[-1])
        last_rsi = float(rsi_val.iloc[-1])

        score = 0
        reasons = []

        if entry > ema9.iloc[-1] > ema21.iloc[-1]:
            score += 40
            reasons.append("EMA 9 > EMA 21")

        if entry > vwap_val.iloc[-1]:
            score += 30
            reasons.append("Above VWAP")

        if 50 <= last_rsi <= 65:
            score += 30
            reasons.append(f"RSI healthy ({round(last_rsi,1)})")

        if score >= 80:
            sl = entry * 0.995   # ~0.5% SL
            target = entry * 1.01

            state[name] = {
                "ticker": ticker,
                "entry": entry,
                "stop_loss": sl,
                "risk": entry - sl,
                "strategy": "INTRADAY"
            }

            intraday_count["count"] += 1

            send_telegram(
                "📈 BUY — INTRADAY\n"
                f"{name}\n"
                f"Time: {time_now}\n\n"
                f"Entry: ₹{round(entry,2)}\n"
                f"SL: ₹{round(sl,2)}\n"
                f"Target: ₹{round(target,2)}\n\n"
                f"Risk: 0.5%\n"
                f"Confidence: {score}%\n"
                "Why:\n• " + "\n• ".join(reasons)
            )

            save_json(STATE_FILE, state)
            save_json(DAY_FILE, intraday_count)

# ================= INTRADAY EXIT =================
for name, trade in list(state.items()):
    if trade.get("strategy") != "INTRADAY":
        continue

    ticker = trade["ticker"]
    entry = trade["entry"]
    sl = trade["stop_loss"]

    data = yf.download(
        ticker, period="1d", interval="5m", progress=False, auto_adjust=True
    )
    if data.empty:
        continue

    price = float(data["Close"].iloc[-1])

    # SL Hit
    if price <= sl:
        send_telegram(
            f"🔴 EXIT — {name} | Intraday\n"
            f"Time: {time_now}\n"
            f"Exit: ₹{round(price,2)}\nReason: SL hit"
        )
        log_trade(name, entry, price, trade["risk"], "Intraday SL hit")
        del state[name]

    # Forced square-off
    elif now_time >= MARKET_CLOSE:
        send_telegram(
            f"🔵 SQUARE-OFF — {name} | Intraday\n"
            f"Time: {time_now}\n"
            f"Exit: ₹{round(price,2)}\nReason: Market close"
        )
        log_trade(name, entry, price, trade["risk"], "Intraday square-off")
        del state[name]

save_json(STATE_FILE, state)

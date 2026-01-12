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
BTST_ENTRY_START = time(14, 15)     # last 60 minutes window
MARKET_CLOSE = time(15, 10)

if weekday > 4 or now_time < MARKET_OPEN or now_time > MARKET_CLOSE:
    exit()

time_now = ist_now.strftime("%d %b %Y | %I:%M %p IST")
today_str = ist_now.strftime("%Y-%m-%d")

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
intraday_count = load_json(DAY_FILE, {"date": today_str, "count": 0})

if intraday_count["date"] != today_str:
    intraday_count = {"date": today_str, "count": 0}

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

def atr_from_ohlc(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ================= INTRADAY ENTRY (UNCHANGED) =================
if now_time <= INTRADAY_ENTRY_CUTOFF and intraday_count["count"] < 3:
    for name, ticker in symbols.items():
        if name in state:
            continue

        data = yf.download(ticker, period="5d", interval="15m", progress=False, auto_adjust=True)
        if data.empty or len(data) < 50:
            continue

        close = data["Close"].astype(float)
        high = data["High"].astype(float)
        low = data["Low"].astype(float)
        volume = data["Volume"].astype(float)

        ema9 = close.ewm(span=9).mean()
        ema21 = close.ewm(span=21).mean()
        rsi_val = rsi(close)
        vwap = ((high + low + close) / 3 * volume).cumsum() / volume.cumsum()

        entry = float(close.iloc[-1])
        last_rsi = float(rsi_val.iloc[-1])

        score = 0
        reasons = []

        if entry > ema9.iloc[-1] > ema21.iloc[-1]:
            score += 40; reasons.append("EMA 9 > EMA 21")
        if entry > vwap.iloc[-1]:
            score += 30; reasons.append("Above VWAP")
        if 50 <= last_rsi <= 65:
            score += 30; reasons.append(f"RSI healthy ({round(last_rsi,1)})")

        if score >= 80:
            sl = entry * 0.995
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
                f"{name}\nTime: {time_now}\n\n"
                f"Entry: ₹{round(entry,2)}\nSL: ₹{round(sl,2)}\nTarget: ₹{round(target,2)}\n"
                f"Risk: 0.5%\nConfidence: {score}%\nWhy:\n• " + "\n• ".join(reasons)
            )

            save_json(STATE_FILE, state)
            save_json(DAY_FILE, intraday_count)

# ================= BTST ENTRY =================
if now_time >= BTST_ENTRY_START:
    for name, ticker in symbols.items():
        if name in state:
            continue

        data = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if data.empty or len(data) < 50:
            continue

        close = data["Close"].astype(float)
        high = data["High"].astype(float)
        low = data["Low"].astype(float)

        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        rsi_val = rsi(close)
        atr = atr_from_ohlc(high, low, close)

        entry = float(close.iloc[-1])
        last_rsi = float(rsi_val.iloc[-1])
        last_atr = float(atr.iloc[-1])

        score = 0
        reasons = []

        if entry > ema20.iloc[-1] and entry > ema50.iloc[-1]:
            score += 40; reasons.append("Strong EOD close above EMA 20 & 50")
        if 50 <= last_rsi <= 65:
            score += 30; reasons.append(f"RSI healthy ({round(last_rsi,1)})")

        candle_range = float(high.iloc[-1] - low.iloc[-1])
        avg_range = float((high - low).rolling(10).mean().iloc[-1])
        if candle_range <= 1.5 * avg_range:
            score += 30; reasons.append("No abnormal volatility")

        if score >= 80:
            sl = entry - (1.5 * last_atr)
            target = entry + (1.8 * (entry - sl))

            state[name] = {
                "ticker": ticker,
                "entry": entry,
                "stop_loss": sl,
                "risk": entry - sl,
                "strategy": "BTST",
                "btst_date": today_str
            }

            send_telegram(
                "📈 BUY — BTST\n"
                f"{name}\nTime: {time_now}\n\n"
                f"Entry: ₹{round(entry,2)}\nSL: ₹{round(sl,2)}\nTarget: ₹{round(target,2)}\n"
                f"Confidence: {score}%\nWhy:\n• " + "\n• ".join(reasons)
            )

            save_json(STATE_FILE, state)

# ================= BTST EXIT (NEXT DAY MORNING) =================
for name, trade in list(state.items()):
    if trade.get("strategy") != "BTST":
        continue
    if trade.get("btst_date") == today_str:
        continue  # exit only next trading day

    ticker = trade["ticker"]
    entry = trade["entry"]
    sl = trade["stop_loss"]

    data = yf.download(ticker, period="1d", interval="5m", progress=False, auto_adjust=True)
    if data.empty:
        continue

    price = float(data["Close"].iloc[-1])

    # SL protection
    if price <= sl:
        send_telegram(
            f"🔴 EXIT — {name} | BTST\n"
            f"Time: {time_now}\nExit: ₹{round(price,2)}\nReason: SL hit"
        )
        log_trade(name, entry, price, trade["risk"], "BTST SL hit")
        del state[name]
        save_json(STATE_FILE, state)
        continue

    # Morning exit (book or trail later if we add)
    if now_time >= time(9, 30):
        send_telegram(
            f"🟢 EXIT — {name} | BTST\n"
            f"Time: {time_now}\nExit: ₹{round(price,2)}\nReason: BTST morning exit"
        )
        log_trade(name, entry, price, trade["risk"], "BTST morning exit")
        del state[name]
        save_json(STATE_FILE, state)

save_json(STATE_FILE, state)

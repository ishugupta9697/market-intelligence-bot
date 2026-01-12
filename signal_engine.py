import yfinance as yf
import requests
import os
import json
from datetime import datetime, timedelta
import pandas as pd

from performance_tracker import log_trade

# ================= TELEGRAM =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

# ================= MARKET TIME CONTROL =================
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)

weekday = ist_now.weekday()
current_time = ist_now.time()

MARKET_OPEN = datetime.strptime("09:20", "%H:%M").time()
MARKET_CLOSE = datetime.strptime("15:10", "%H:%M").time()

if weekday > 4 or current_time < MARKET_OPEN or current_time > MARKET_CLOSE:
    exit()

time_now = ist_now.strftime("%d %b %Y | %I:%M %p IST")

# ================= FILE STATE =================
STATE_FILE = "active_trades.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_state()

# ================= ASSETS =================
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
    "MARUTI": "MARUTI.NS",
    "GOLD ETF": "GOLDBEES.NS"
}

# ================= INDICATORS =================
def calculate_rsi(series, period=14):
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

# ================= MONITOR ACTIVE TRADES =================
for name, trade in list(state.items()):
    ticker = trade["ticker"]
    entry = trade["entry"]
    stop_loss = trade["stop_loss"]
    target = trade["target"]
    risk = trade["risk"]
    trailing_active = trade["trailing_active"]
    highest = trade["highest"]

    data = yf.download(ticker, period="2mo", interval="5m", progress=False, auto_adjust=True)
    if data.empty:
        continue

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)

    ema20 = close.ewm(span=20).mean()
    rsi = calculate_rsi(close)
    atr = atr_from_ohlc(high, low, close)

    price = float(close.iloc[-1])
    ema20_last = float(ema20.iloc[-1])
    rsi_last = float(rsi.iloc[-1])
    atr_last = float(atr.iloc[-1])

    if price > highest:
        highest = price

    if not trailing_active and price >= entry + risk:
        stop_loss = entry
        trailing_active = True
        send_telegram(f"🔄 TRAILING ACTIVATED — {name}\nTime: {time_now}\nNew SL: ₹{round(stop_loss,2)}")

    if trailing_active:
        trail_sl = max(stop_loss, highest - (1.2 * atr_last))
        if trail_sl > stop_loss:
            stop_loss = trail_sl
            send_telegram(f"🔄 TRAILING UPDATED — {name}\nTime: {time_now}\nNew SL: ₹{round(stop_loss,2)}")

    # EXIT: Stop-loss
    if price <= stop_loss:
        send_telegram(f"🔴 EXIT — {name}\nTime: {time_now}\nExit: ₹{round(price,2)}\nReason: SL hit")
        log_trade(name, entry, price, risk, "SL hit")
        del state[name]
        save_state(state)
        continue

    # EXIT: Momentum weakness
    if rsi_last < 40 or price < ema20_last:
        send_telegram(f"⚠️ EXIT — {name}\nTime: {time_now}\nExit: ₹{round(price,2)}\nReason: Momentum weak")
        log_trade(name, entry, price, risk, "Momentum weak")
        del state[name]
        save_state(state)
        continue

    state[name].update({
        "stop_loss": stop_loss,
        "trailing_active": trailing_active,
        "highest": highest
    })

save_state(state)

# ================= ENTRY ENGINE (UNCHANGED) =================
signals_sent = 0

for name, ticker in symbols.items():
    if name in state or len(state) >= 3:
        continue

    data = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 50:
        continue

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    rsi = calculate_rsi(close)
    atr = atr_from_ohlc(high, low, close)

    entry = float(close.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_atr = float(atr.iloc[-1])

    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_signal = macd.ewm(span=9).mean()

    score = 0
    reasons = []

    if entry > last_ema20 and entry > last_ema50: score += 25
    if 45 <= last_rsi <= 65: score += 20
    if float(macd.iloc[-1]) > float(macd_signal.iloc[-1]): score += 25
    if last_ema20 > last_ema50: score += 15

    candle_range = float(high.iloc[-1] - low.iloc[-1])
    avg_range = float((high - low).rolling(10).mean().iloc[-1])
    if candle_range <= 1.5 * avg_range: score += 15

    if last_rsi > 75 or last_rsi < 25:
        continue

    if score >= 80 and signals_sent < 3:
        stop_loss = entry - (1.2 * last_atr)
        risk = entry - stop_loss
        target = entry + (1.8 * risk)

        state[name] = {
            "ticker": ticker,
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "risk": risk,
            "trailing_active": False,
            "highest": entry
        }

        send_telegram(
            "📈 BUY SIGNAL — HIGH CONFIDENCE\n"
            f"{name}\nTime: {time_now}\n\n"
            f"Entry: ₹{round(entry,2)}\nSL: ₹{round(stop_loss,2)}\nTarget: ₹{round(target,2)}\n"
            f"Confidence: {score}%"
        )
        signals_sent += 1

save_state(state)

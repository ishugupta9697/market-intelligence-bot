import yfinance as yf
import requests
import os
import json
from datetime import datetime, timedelta, time
import pandas as pd

# ================= TELEGRAM =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

# ================= TIME =================
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)
weekday = ist_now.weekday()
now_time = ist_now.time()

MARKET_OPEN = time(9, 20)
MARKET_CLOSE = time(15, 10)

if weekday > 4 or now_time < MARKET_OPEN or now_time > MARKET_CLOSE:
    exit()

time_str = ist_now.strftime("%d %b %Y | %I:%M %p IST")
today = ist_now.strftime("%Y-%m-%d")

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

# ================= WATCHLIST =================
equity_symbols = {
    "RELIANCE": "RELIANCE.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "ITC": "ITC.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HCLTECH": "HCLTECH.NS",
    "LTIM": "LTIM.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "TITAN": "TITAN.NS",
    "ASIANPAINT": "ASIANPAINT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "MARUTI": "MARUTI.NS",
    "M&M": "M&M.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "CIPLA": "CIPLA.NS",
    "DRREDDY": "DRREDDY.NS",
    "NTPC": "NTPC.NS",
    "POWERGRID": "POWERGRID.NS",
    "ONGC": "ONGC.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "HINDALCO": "HINDALCO.NS",
    "BANKBARODA": "BANKBARODA.NS",
    "PNB": "PNB.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "JSWSTEEL": "JSWSTEEL.NS",
    "VEDL": "VEDL.NS",
    "COALINDIA": "COALINDIA.NS",
    "BEL": "BEL.NS",
    "HAL": "HAL.NS",
    "IRFC": "IRFC.NS",
    "IRCTC": "IRCTC.NS",
    "JIOFIN": "JIOFIN.NS",
    "ZOMATO": "ZOMATO.NS",
    "DLF": "DLF.NS"
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

# ================= ENTRY — SWING ONLY =================
for name, ticker in equity_symbols.items():
    if name in state:
        continue

    data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 120:
        continue

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    volume = data["Volume"].astype(float)

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    ema200 = close.ewm(span=200).mean()
    rsi_series = rsi(close)

    entry = float(close.iloc[-1])
    ema20_v = float(ema20.iloc[-1])
    ema50_v = float(ema50.iloc[-1])
    ema200_v = float(ema200.iloc[-1])
    rsi_v = float(rsi_series.iloc[-1])

    score = 0
    reasons = []

    if entry > ema20_v and entry > ema50_v and entry > ema200_v:
        score += 40; reasons.append("Price above EMA 20/50/200")
    if 45 <= rsi_v <= 65:
        score += 30; reasons.append(f"RSI healthy ({round(rsi_v,1)})")

    avg_vol = volume.rolling(20).mean().iloc[-1]
    if volume.iloc[-1] > 1.5 * avg_vol:
        score += 30; reasons.append("Volume expansion")

    if score >= 70:
        sl = entry * 0.9
        t1 = entry * 1.1
        t2 = entry * 1.2

        state[name] = {
            "ticker": ticker,
            "entry": entry,
            "stop_loss": sl,
            "t1": t1,
            "t2": t2,
            "t1_hit": False,
            "strategy": "SWING"
        }

        send_telegram(
            "📈 BUY — SWING\n"
            f"{name}\nTime: {time_str}\n\n"
            f"Entry: ₹{round(entry,2)}\n"
            f"SL: ₹{round(sl,2)}\n"
            f"Target 1: ₹{round(t1,2)}\n"
            f"Target 2: ₹{round(t2,2)}\n"
            f"Confidence: {score}%\nWhy:\n• " + "\n• ".join(reasons) +
            "\n\nNews Check (MANDATORY):\n• Verify no negative news before entry"
        )

# ================= MONITORING =================
for name in list(state.keys()):
    trade = state[name]
    ticker = trade["ticker"]

    data = yf.download(ticker, period="10d", interval="1d", progress=False, auto_adjust=True)
    if data.empty:
        continue

    price = float(data["Close"].iloc[-1])

    # SL HIT
    if price <= trade["stop_loss"]:
        send_telegram(
            f"🔴 EXIT — {name} (SWING)\n"
            f"Reason: Stop Loss hit\nAction: SELL"
        )
        del state[name]
        continue

    # T1 HIT
    if not trade["t1_hit"] and price >= trade["t1"]:
        trade["t1_hit"] = True
        trade["stop_loss"] = trade["entry"] * 1.05  # profit lock

        send_telegram(
            f"🟢 UPDATE — {name} (SWING)\n\n"
            f"Target 1 Achieved: ₹{round(trade['t1'],2)} ✅\n\n"
            "Suggested Actions:\n"
            "• Book 50% quantity\n"
            "• Hold remaining position\n\n"
            f"SL moved to: ₹{round(trade['stop_loss'],2)} (PROFIT LOCKED)\n"
            f"Next Target: ₹{round(trade['t2'],2)}"
        )

    # FINAL TARGET
    if price >= trade["t2"]:
        send_telegram(
            f"🟢 EXIT — {name} (SWING)\n"
            f"Reason: Final Target achieved\nAction: SELL"
        )
        del state[name]

save_state(state)

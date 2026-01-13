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
BTST_START = time(14, 15)
BTST_END = time(15, 10)

if weekday > 4 or now_time < MARKET_OPEN or now_time > MARKET_CLOSE:
    exit()

time_str = ist_now.strftime("%d %b %Y | %I:%M %p IST")
today = ist_now.strftime("%Y-%m-%d")
yesterday = (ist_now - timedelta(days=1)).strftime("%Y-%m-%d")

# ================= FILE STATE =================
SWING_STATE_FILE = "active_trades.json"
BTST_STATE_FILE = "btst_state.json"

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

swing_state = load_json(SWING_STATE_FILE, {})
btst_state = load_json(BTST_STATE_FILE, {"date": today, "count": 0, "trades": {}})

# reset BTST daily counter
if btst_state.get("date") != today:
    btst_state = {"date": today, "count": 0, "trades": {}}

# ================= WATCHLIST =================
equity_symbols = {
    "RELIANCE": "RELIANCE.NS", "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS", "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS", "ITC": "ITC.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HCLTECH": "HCLTECH.NS", "LTIM": "LTIM.NS", "BHARTIARTL": "BHARTIARTL.NS",
    "TITAN": "TITAN.NS", "ASIANPAINT": "ASIANPAINT.NS", "ULTRACEMCO": "ULTRACEMCO.NS",
    "TATAMOTORS": "TATAMOTORS.NS", "MARUTI": "MARUTI.NS", "M&M": "M&M.NS",
    "BAJFINANCE": "BAJFINANCE.NS", "BAJAJFINSV": "BAJAJFINSV.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "CIPLA": "CIPLA.NS", "DRREDDY": "DRREDDY.NS",
    "NTPC": "NTPC.NS", "POWERGRID": "POWERGRID.NS", "ONGC": "ONGC.NS",
    "ADANIPORTS": "ADANIPORTS.NS", "TATASTEEL": "TATASTEEL.NS",
    "HINDALCO": "HINDALCO.NS", "BANKBARODA": "BANKBARODA.NS", "PNB": "PNB.NS",
    "INDUSINDBK": "INDUSINDBK.NS", "JSWSTEEL": "JSWSTEEL.NS",
    "VEDL": "VEDL.NS", "COALINDIA": "COALINDIA.NS", "BEL": "BEL.NS",
    "HAL": "HAL.NS", "IRFC": "IRFC.NS", "IRCTC": "IRCTC.NS",
    "JIOFIN": "JIOFIN.NS", "ZOMATO": "ZOMATO.NS", "DLF": "DLF.NS"
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

# =========================
# ===== SWING ENGINE ======
# =========================

for name, ticker in equity_symbols.items():
    if name in swing_state:
        continue

    data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 200:
        continue

    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    ema200 = close.ewm(span=200).mean()
    rsi_series = rsi(close)

    entry = float(close.iloc[-1])
    score = 0
    reasons = []

    if entry > ema20.iloc[-1] and entry > ema50.iloc[-1] and entry > ema200.iloc[-1]:
        score += 40; reasons.append("Price above EMA 20/50/200")
    if 45 <= rsi_series.iloc[-1] <= 65:
        score += 30; reasons.append(f"RSI healthy ({round(rsi_series.iloc[-1],1)})")
    if volume.iloc[-1] > 1.5 * volume.rolling(20).mean().iloc[-1]:
        score += 30; reasons.append("Volume expansion")

    if score >= 70:
        swing_state[name] = {
            "ticker": ticker,
            "entry": entry,
            "stop_loss": entry * 0.9,
            "t1": entry * 1.1,
            "t2": entry * 1.2,
            "t1_hit": False,
            "dynamic": False,
            "strategy": "SWING"
        }

        send_telegram(
            "📈 BUY — SWING\n"
            f"{name}\nTime: {time_str}\n\n"
            f"Entry: ₹{round(entry,2)}\n"
            f"SL: ₹{round(entry*0.9,2)}\n"
            f"Target 1: ₹{round(entry*1.1,2)}\n"
            f"Target 2: ₹{round(entry*1.2,2)}\n"
            f"Confidence: {score}%\nWhy:\n• " + "\n• ".join(reasons) +
            "\n\nNews Check (MANDATORY):\n• Verify no negative news before entry"
        )

# ===== SWING MONITORING =====
for name in list(swing_state.keys()):
    trade = swing_state[name]
    ticker = trade["ticker"]

    data = yf.download(ticker, period="15d", interval="1d", progress=False, auto_adjust=True)
    if data.empty:
        continue

    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    price = float(close.iloc[-1])

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    rsi_series = rsi(close)

    # SL HIT
    if price <= trade["stop_loss"]:
        send_telegram(f"🔴 EXIT — {name} (SWING)\nReason: Stop Loss hit\nAction: SELL")
        del swing_state[name]
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

    # MOMENTUM EXTENSION
    if trade["t1_hit"] and not trade["dynamic"]:
        last3 = close.iloc[-3:]
        momentum = (
            price > ema20.iloc[-1] and
            price > ema50.iloc[-1] and
            55 <= rsi_series.iloc[-1] <= 70 and
            last3.is_monotonic_increasing and
            volume.iloc[-1] >= volume.rolling(20).mean().iloc[-1]
        )

        if momentum:
            trade["dynamic"] = True
            trade["t1"] = trade["t2"]
            trade["t2"] = trade["t2"] * 1.125
            trade["stop_loss"] = trade["t1"] * 0.95

            send_telegram(
                f"🔵 MOMENTUM UPDATE — {name} (SWING)\n\n"
                f"Targets revised:\n"
                f"• New Target 1: ₹{round(trade['t1'],2)}\n"
                f"• New Target 2: ₹{round(trade['t2'],2)}\n"
                f"• Trailing SL: ₹{round(trade['stop_loss'],2)}\n\n"
                "Action: Hold remaining position"
            )

    # FINAL TARGET
    if price >= trade["t2"]:
        send_telegram(f"🟢 EXIT — {name} (SWING)\nReason: Final Target achieved\nAction: SELL")
        del swing_state[name]

# =========================
# ===== BTST MODULE =======
# =========================

# NEXT-DAY MANDATORY EXIT
for name in list(btst_state["trades"].keys()):
    t = btst_state["trades"][name]
    ticker = t["ticker"]

    data = yf.download(ticker, period="2d", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 2:
        continue

    price = float(data["Close"].iloc[-1])

    if price <= t["sl"]:
        send_telegram(f"🔴 EXIT — {name} (BTST)\nReason: SL hit / Gap-down\nAction: SELL")
        del btst_state["trades"][name]
        continue

    if price >= t["t2"]:
        send_telegram(f"🟢 EXIT — {name} (BTST)\nReason: Target 2 achieved\nAction: SELL")
        del btst_state["trades"][name]
        continue

    # Time-based exit (mandatory)
    send_telegram(f"🔴 EXIT — {name} (BTST)\nReason: Time-based exit\nAction: SELL")
    del btst_state["trades"][name]

# BTST ENTRY (STRICT WINDOW)
if BTST_START <= now_time <= BTST_END and btst_state["count"] < 4:
    for name, ticker in equity_symbols.items():
        if btst_state["count"] >= 4 or name in btst_state["trades"]:
            break

        data = yf.download(ticker, period="2mo", interval="1d", progress=False, auto_adjust=True)
        if data.empty or len(data) < 30:
            continue

        close = data["Close"].astype(float)
        high = data["High"].astype(float)
        low = data["Low"].astype(float)
        volume = data["Volume"].astype(float)

        candle_range = high.iloc[-1] - low.iloc[-1]
        if close.iloc[-1] < (low.iloc[-1] + 0.75 * candle_range):
            continue

        if volume.iloc[-1] < 2 * volume.rolling(10).mean().iloc[-1]:
            continue

        entry = float(close.iloc[-1])
        sl = entry * 0.993
        t1 = entry * 1.02
        t2 = entry * 1.035

        btst_state["trades"][name] = {
            "ticker": ticker,
            "entry": entry,
            "sl": sl,
            "t1": t1,
            "t2": t2,
            "date": today
        }
        btst_state["count"] += 1

        send_telegram(
            "📈 BUY — BTST (CONSERVATIVE)\n"
            f"{name}\nTime: {time_str}\n\n"
            f"Entry: ₹{round(entry,2)}\n"
            f"SL: ₹{round(sl,2)}\n"
            f"T1: ₹{round(t1,2)}\n"
            f"T2: ₹{round(t2,2)}\n"
            "Action: Hold overnight (mandatory exit next day)"
        )

# ================= SAVE STATES =================
save_json(SWING_STATE_FILE, swing_state)
save_json(BTST_STATE_FILE, btst_state)

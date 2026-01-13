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
BTST_ENTRY_START = time(14, 15)
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

gold_etfs = {
    "GOLDBEES": "GOLDBEES.NS"
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

# ================= INTRADAY =================
if now_time <= INTRADAY_ENTRY_CUTOFF and intraday_count["count"] < 3:
    for name, ticker in equity_symbols.items():
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
        rsi_series = rsi(close)
        vwap = ((high + low + close) / 3 * volume).cumsum() / volume.cumsum()

        entry = float(close.iloc[-1])
        ema9_val = float(ema9.iloc[-1])
        ema21_val = float(ema21.iloc[-1])
        vwap_val = float(vwap.iloc[-1])
        last_rsi = float(rsi_series.iloc[-1])

        score = 0
        reasons = []

        if entry > ema9_val and ema9_val > ema21_val:
            score += 40; reasons.append("EMA 9 > EMA 21")
        if entry > vwap_val:
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

# ================= BTST =================
if now_time >= BTST_ENTRY_START:
    for name, ticker in equity_symbols.items():
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
        rsi_series = rsi(close)
        atr = atr_from_ohlc(high, low, close)

        entry = float(close.iloc[-1])
        ema20_val = float(ema20.iloc[-1])
        ema50_val = float(ema50.iloc[-1])
        last_rsi = float(rsi_series.iloc[-1])
        last_atr = float(atr.iloc[-1])

        score = 0
        reasons = []

        if entry > ema20_val and entry > ema50_val:
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

# ================= GOLD ETF =================
for name, ticker in gold_etfs.items():
    if name in state:
        continue

    data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 80:
        continue

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    rsi_series = rsi(close)
    atr = atr_from_ohlc(high, low, close)

    entry = float(close.iloc[-1])
    ema20_val = float(ema20.iloc[-1])
    ema50_val = float(ema50.iloc[-1])
    last_rsi = float(rsi_series.iloc[-1])
    last_atr = float(atr.iloc[-1])

    score = 0
    reasons = []

    if entry > ema20_val and entry > ema50_val:
        score += 40; reasons.append("Price above EMA 20 & 50")
    if 45 <= last_rsi <= 65:
        score += 30; reasons.append(f"RSI healthy ({round(last_rsi,1)})")

    candle_range = float(high.iloc[-1] - low.iloc[-1])
    avg_range = float((high - low).rolling(10).mean().iloc[-1])
    if candle_range <= 1.5 * avg_range:
        score += 30; reasons.append("Stable gold volatility")

    if score >= 80:
        sl = entry - (1.8 * last_atr)
        target = entry + (2.0 * (entry - sl))

        state[name] = {
            "ticker": ticker,
            "entry": entry,
            "stop_loss": sl,
            "risk": entry - sl,
            "strategy": "GOLD_ETF"
        }

        send_telegram(
            "🟡 BUY — GOLD ETF (Swing)\n"
            f"{name}\nTime: {time_now}\n\n"
            f"Entry: ₹{round(entry,2)}\nSL: ₹{round(sl,2)}\nTarget: ₹{round(target,2)}\n"
            f"Risk: 1%\nConfidence: {score}%\nWhy:\n• " + "\n• ".join(reasons)
        )

        save_json(STATE_FILE, state)

save_json(STATE_FILE, state)

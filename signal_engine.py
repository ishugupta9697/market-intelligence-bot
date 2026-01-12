import yfinance as yf
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

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

weekday = ist_now.weekday()  # Mon=0
current_time = ist_now.time()

MARKET_OPEN = datetime.strptime("09:20", "%H:%M").time()
MARKET_CLOSE = datetime.strptime("15:10", "%H:%M").time()

# Exit silently if market is closed
if weekday > 4 or current_time < MARKET_OPEN or current_time > MARKET_CLOSE:
    exit()

time_now = ist_now.strftime("%d %b %Y | %I:%M %p IST")

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

signals_sent = 0

# ================= SIGNAL ENGINE =================
for name, ticker in symbols.items():
    data = yf.download(
        ticker,
        period="3mo",
        interval="1d",
        progress=False,
        auto_adjust=True
    )

    if data.empty or len(data) < 50:
        continue

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)

    # Indicators
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    rsi = calculate_rsi(close)

    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_signal = macd.ewm(span=9).mean()

    # ATR (14)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # Latest values
    entry = float(close.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_atr = float(atr.iloc[-1])

    score = 0
    reasons = []

    # Conditions
    if entry > last_ema20 and entry > last_ema50:
        score += 25
        reason

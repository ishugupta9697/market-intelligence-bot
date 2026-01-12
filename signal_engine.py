import yfinance as yf
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# Telegram credentials
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)


# Assets to scan
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

# IST time (manual UTC offset – safe)
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)
time_now = ist_now.strftime("%d %b %Y | %I:%M %p IST")


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


signals_sent = 0

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

    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    rsi = calculate_rsi(close)

    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_signal = macd.ewm(span=9).mean()

    # Safely extract LAST values as floats
    last_close = float(close.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])

    score = 0
    reasons = []

    # Trend condition
    if last_close > last_ema20 and last_close > last_ema50:
        score += 25
        reasons.append("Price above EMA 20 & 50")

    # RSI condition
    if 45 <= last_rsi <= 65:
        score += 20
        reasons.append(f"RSI healthy ({round(last_rsi, 1)})")

    # MACD condition
    if last_macd > last_macd_signal:
        score += 25
        reasons.append("MACD bullish crossover")

    # EMA alignment
    if last_ema20 > last_ema50:
        score += 15
        reasons.append("Trend alignment positive")

    # Volatility filter
    candle_range = float(high.iloc[-1] - low.iloc[-1])
    avg_range = float((high - low).rolling(10).mean().iloc[-1])

    if candle_range <= 1.5 * avg_range:
        score += 15
        reasons.append("No abnormal volatility")

    # Hard safety filters
    if last_rsi > 75 or last_rsi < 25:
        continue

    # Final decision (≥80% only)
    if score >= 80 and signals_sent < 3:
        message = (
            "📈 HIGH-CONFIDENCE BUY SIGNAL\n"
            f"{name}\n"
            f"Time: {time_now}\n\n"
            f"Confidence: {score}%\n\n"
            "Why:\n• " + "\n• ".join(reasons) +
            "\n\nRisk Note:\n• Use strict stop-loss\n• Risk ≤ 1% capital"
        )

        send_telegram(message)
        signals_sent += 1

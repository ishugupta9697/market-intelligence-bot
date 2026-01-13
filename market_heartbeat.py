import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, time
import json

# ============== TELEGRAM ==============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

# ============== TIME (IST) ==============
utc_now = datetime.utcnow()
ist_now = utc_now + timedelta(hours=5, minutes=30)
weekday = ist_now.weekday()
now_time = ist_now.time()

# Only on trading days
if weekday > 4:
    exit()

PRE_MARKET_TIME = time(9, 15)
POST_MARKET_TIME = time(15, 30)

# ============== MARKET DATA (FREE) ==============
def pct_change(ticker):
    d = yf.download(ticker, period="2d", interval="1d", progress=False)
    if d.empty or len(d) < 2:
        return None
    prev, last = float(d["Close"].iloc[-2]), float(d["Close"].iloc[-1])
    return round(((last - prev) / prev) * 100, 2)

nifty = pct_change("^NSEI")
banknifty = pct_change("^NSEBANK")
vix = pct_change("^INDIAVIX")

# ============== STRATEGY COUNTS (OPTIONAL) ==============
def count_today_alerts():
    # Non-intrusive: reads local log if present
    if not os.path.exists("trade_log.csv"):
        return {"Intraday": 0, "Swing": 0, "BTST": 0, "Gold ETF": 0}
    counts = {"Intraday": 0, "Swing": 0, "BTST": 0, "Gold ETF": 0}
    today = ist_now.strftime("%Y-%m-%d")
    with open("trade_log.csv", "r") as f:
        lines = f.readlines()[1:]
        for l in lines:
            if today in l:
                if "INTRADAY" in l: counts["Intraday"] += 1
                if "BTST" in l: counts["BTST"] += 1
                if "GOLD_ETF" in l: counts["Gold ETF"] += 1
                if "Swing" in l: counts["Swing"] += 1
    return counts

# ============== PRE-MARKET ==============
if now_time == PRE_MARKET_TIME:
    mood = "Mixed"
    if nifty is not None and nifty > 0.3:
        mood = "Positive"
    elif nifty is not None and nifty < -0.3:
        mood = "Cautious"

    send_telegram(
        "🟢 PRE-MARKET UPDATE | 9:15 AM IST\n\n"
        "System Status: ACTIVE ✅\n\n"
        "Market Mood (Early Cues):\n"
        f"• NIFTY: {nifty}%\n"
        f"• BANK NIFTY: {banknifty}%\n"
        f"• INDIA VIX: {vix}%\n\n"
        f"Overall Tone: {mood}\n\n"
        "Strategies Active Today:\n"
        "• Intraday\n• Swing\n• BTST\n• Gold ETF\n\n"
        "Note: Alerts only if conditions qualify (≥80% confidence)."
    )

# ============== POST-MARKET ==============
if now_time == POST_MARKET_TIME:
    counts = count_today_alerts()
    send_telegram(
        "🔵 POST-MARKET SUMMARY | 3:30 PM IST\n\n"
        "Market Summary:\n"
        f"• NIFTY: {nifty}%\n"
        f"• BANK NIFTY: {banknifty}%\n"
        f"• INDIA VIX: {vix}%\n\n"
        "System Activity Today:\n"
        f"• Intraday alerts: {counts['Intraday']}\n"
        f"• Swing alerts: {counts['Swing']}\n"
        f"• BTST alerts: {counts['BTST']}\n"
        f"• Gold ETF alerts: {counts['Gold ETF']}\n\n"
        "Status:\n• Monitoring paused till next market day.\n"
        "Have a good evening."
    )

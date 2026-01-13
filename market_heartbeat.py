import os
import json
import requests
from datetime import datetime, timedelta, time

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

# Market days only (Mon–Fri)
if weekday > 4:
    exit()

# Heartbeat times
PRE_MARKET_TIME = time(9, 15)
POST_MARKET_TIME = time(15, 40)

# ================= STATE FILES =================
SWING_STATE_FILE = "active_trades.json"
BTST_STATE_FILE = "btst_state.json"

def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r") as f:
                return json.load(f)
    except:
        pass
    return default

swing_state = load_json(SWING_STATE_FILE, {})
btst_state = load_json(BTST_STATE_FILE, {"count": 0})

date_str = ist_now.strftime("%d %b %Y")
time_str = ist_now.strftime("%I:%M %p IST")

# ================= PRE-MARKET HEARTBEAT =================
if now_time.hour == PRE_MARKET_TIME.hour and now_time.minute == PRE_MARKET_TIME.minute:
    send_telegram(
        "🔔 MARKET OPEN — SYSTEM CHECK\n"
        f"Date: {date_str} | {time_str}\n\n"
        "System Status:\n"
        f"• Swing Engine: ACTIVE ({len(swing_state)} open trades)\n"
        "• BTST Engine: ACTIVE\n"
        "• Risk/Trade: 1% max\n\n"
        "Reminder:\n"
        "• Trades only on high-confidence alerts\n"
        "• No action required now"
    )
    exit()

# ================= POST-MARKET HEARTBEAT =================
if now_time.hour == POST_MARKET_TIME.hour and now_time.minute == POST_MARKET_TIME.minute:
    btst_count = btst_state.get("count", 0)

    send_telegram(
        "🔔 MARKET CLOSED — DAILY SUMMARY\n"
        f"Date: {date_str} | {time_str}\n\n"
        "Today’s Activity:\n"
        f"• Swing Trades Active: {len(swing_state)}\n"
        f"• BTST Trades Taken: {btst_count}\n\n"
        "System Health:\n"
        "• All workflows executed\n"
        "• No manual action required\n\n"
        "Note:\n"
        "• Silence = discipline\n"
        "• Capital protection comes first"
    )
    exit()

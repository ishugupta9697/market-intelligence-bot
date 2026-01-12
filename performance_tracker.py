import csv
import os
from datetime import datetime

LOG_FILE = "trade_log.csv"

FIELDS = [
    "date",
    "symbol",
    "side",
    "entry",
    "exit",
    "risk",
    "pnl",
    "r_multiple",
    "exit_reason"
]

def ensure_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()

def log_trade(symbol, entry, exit_price, risk, exit_reason, side="BUY"):
    ensure_log()
    pnl = exit_price - entry if side == "BUY" else entry - exit_price
    r_multiple = pnl / risk if risk != 0 else 0

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow({
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "side": side,
            "entry": round(entry, 2),
            "exit": round(exit_price, 2),
            "risk": round(risk, 2),
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "exit_reason": exit_reason
        })

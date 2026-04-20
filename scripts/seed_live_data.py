"""Seed Neon DB with realistic demo live-trading data.

Writes:
- 30 daily performance snapshots (equity curve, sharpe, drawdown)
- ~60 trades across AAPL / MSFT / GOOG (buy/sell, last 30 days)
- 15 agent_logs entries from TradingExecutor / MonitorAgent / ResearchAgent

Usage:
    DATABASE_URL=postgresql://neondb_owner:...@.../neondb python scripts/seed_live_data.py
"""

import os
import sys
import random
import math
from datetime import datetime, timedelta

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage.data_manager import DataStorageManager


def main():
    db = DataStorageManager()
    rng = random.Random(42)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 1. Performance snapshots (30 days) ───────────────────────────────────
    print("Seeding performance snapshots…")
    equity = 10_000.0
    peak = equity
    for i in range(30):
        day = today - timedelta(days=29 - i)
        # Gentle random walk with upward bias
        drift = rng.gauss(0.0008, 0.012)
        equity = max(8_000, equity * (1 + drift))
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak
        total_return = (equity / 10_000) - 1
        sharpe = rng.gauss(0.9, 0.3)
        win_rate = rng.gauss(0.54, 0.06)
        num_trades = rng.randint(2, 8)

        db.save_performance({
            "timestamp": day.isoformat(),
            "model_name": "LivePortfolio",
            "equity": round(equity, 2),
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(drawdown, 4),
            "win_rate": round(min(max(win_rate, 0.3), 0.75), 3),
            "num_trades": num_trades,
        })
    print(f"  → equity final: ${equity:,.2f}")

    # ── 2. Trades ─────────────────────────────────────────────────────────────
    print("Seeding trades…")
    symbols = {
        "AAPL": {"price": 220.0, "vol": 0.015},
        "MSFT": {"price": 415.0, "vol": 0.012},
        "GOOG": {"price": 172.0, "vol": 0.018},
    }
    qty_map = {"AAPL": 0.0, "MSFT": 0.0, "GOOG": 0.0}
    trade_count = 0

    for i in range(60):
        day = today - timedelta(days=29 - (i // 2))
        hour = rng.randint(9, 15)
        minute = rng.randint(0, 59)
        ts = day.replace(hour=hour, minute=minute).isoformat()

        sym = rng.choice(list(symbols.keys()))
        info = symbols[sym]

        # Random walk price
        info["price"] *= (1 + rng.gauss(0, info["vol"]))
        price = round(info["price"], 2)

        # Alternate buy/sell; always hold at least a small position
        if qty_map[sym] <= 0.5:
            action = "BUY"
        elif qty_map[sym] >= 8:
            action = "SELL"
        else:
            action = rng.choice(["BUY", "BUY", "SELL"])

        qty = round(rng.uniform(0.5, 3.0), 2)
        if action == "SELL":
            qty = min(qty, round(qty_map[sym] * 0.6, 2))
            if qty <= 0:
                continue

        qty_map[sym] += qty if action == "BUY" else -qty
        value = round(price * qty, 2)

        db.save_trade({
            "timestamp": ts,
            "symbol": sym,
            "action": action,
            "quantity": qty,
            "price": price,
            "value": value,
            "model_name": "LivePortfolio",
            "status": "executed",
        })
        trade_count += 1

    print(f"  → {trade_count} trades written")
    print(f"  → open positions: { {k: round(v,2) for k,v in qty_map.items() if v > 0} }")

    # ── 3. Agent logs ─────────────────────────────────────────────────────────
    print("Seeding agent logs…")
    log_entries = [
        ("TradingExecutor", "active",   "Paper trading loop started — equity $10,000"),
        ("TradingExecutor", "active",   "Signal BUY AAPL @ market — qty 1.5"),
        ("TradingExecutor", "active",   "Mark-to-market complete — unrealized P&L +$142"),
        ("TradingExecutor", "active",   "Signal SELL MSFT — risk limit triggered"),
        ("MonitorAgent",    "active",   "Portfolio VaR(95%) = $198 — within $500 limit"),
        ("MonitorAgent",    "active",   "System health check: all components nominal"),
        ("MonitorAgent",    "warning",  "Momentum Sharpness drawdown 4.7% — approaching 5% limit"),
        ("MonitorAgent",    "active",   "Rebalance check: portfolio drift within tolerance"),
        ("ResearchAgent",   "active",   "arXiv scan complete — 3 relevant papers found"),
        ("ResearchAgent",   "active",   "Scheduled next run in 6h"),
        ("ValidationAgent", "active",   "LivePortfolio validation step 1/3 passed"),
        ("ValidationAgent", "active",   "Sharpe 0.91 > 0.5 threshold — APPROVED"),
        ("TradingExecutor", "active",   "Daily P&L snapshot saved — return +0.8%"),
        ("MonitorAgent",    "active",   "End-of-day report: 4 trades, win rate 75%"),
        ("TradingExecutor", "active",   "Session closed — positions carried overnight"),
    ]
    for j, (agent, status, msg) in enumerate(log_entries):
        ts = (today - timedelta(hours=len(log_entries) - j)).isoformat()
        db.log_agent_activity(agent, status, msg)

    print(f"  → {len(log_entries)} log entries written")
    print("Done. DB seeded successfully.")


if __name__ == "__main__":
    main()

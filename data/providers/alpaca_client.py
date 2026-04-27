"""Alpaca REST client for real-time quotes and historical bars.

Requires env vars: ALPACA_API_KEY, ALPACA_SECRET_KEY.
Falls back gracefully if credentials are absent (returns empty dict / None).
Paper trading base: https://paper-api.alpaca.markets
Data base:         https://data.alpaca.markets
"""
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_DATA_BASE = "https://data.alpaca.markets"
_PAPER_BASE = "https://paper-api.alpaca.markets"


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
    }


def _configured() -> bool:
    return bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))


def get_latest_quote(symbol: str) -> Optional[float]:
    """Return latest trade price for symbol via Alpaca REST. Returns None on error."""
    if not _configured():
        return None
    try:
        url = f"{_DATA_BASE}/v2/stocks/{symbol}/trades/latest"
        r = httpx.get(url, headers=_headers(), params={"feed": "iex"}, timeout=5)
        r.raise_for_status()
        return float(r.json()["trade"]["p"])
    except Exception as e:
        logger.debug(f"Alpaca quote {symbol}: {e}")
        return None


def get_bars(symbol: str, timeframe: str = "1Min", limit: int = 50) -> list[dict]:
    """Return list of OHLCV bar dicts for signal generation."""
    if not _configured():
        return []
    try:
        url = f"{_DATA_BASE}/v2/stocks/{symbol}/bars"
        params = {"timeframe": timeframe, "limit": limit, "feed": "iex", "sort": "asc"}
        r = httpx.get(url, headers=_headers(), params=params, timeout=8)
        r.raise_for_status()
        bars = r.json().get("bars") or []
        return [
            {
                "datetime": b["t"],
                "open": b["o"], "high": b["h"], "low": b["l"],
                "close": b["c"], "volume": b["v"],
            }
            for b in bars
        ]
    except Exception as e:
        logger.debug(f"Alpaca bars {symbol}: {e}")
        return []


def get_account() -> dict:
    """Return Alpaca paper account snapshot (equity, cash, buying_power)."""
    if not _configured():
        return {}
    try:
        r = httpx.get(f"{_PAPER_BASE}/v2/account", headers=_headers(), timeout=5)
        r.raise_for_status()
        d = r.json()
        return {
            "equity": float(d.get("equity", 0)),
            "cash": float(d.get("cash", 0)),
            "buying_power": float(d.get("buying_power", 0)),
            "portfolio_value": float(d.get("portfolio_value", 0)),
            "currency": d.get("currency", "USD"),
        }
    except Exception as e:
        logger.debug(f"Alpaca account: {e}")
        return {}


def submit_paper_order(symbol: str, qty: float, side: str) -> dict:
    """Submit a paper market order. side: 'buy' | 'sell'."""
    if not _configured():
        return {"error": "ALPACA_API_KEY not set"}
    try:
        payload = {
            "symbol": symbol, "qty": str(qty),
            "side": side, "type": "market", "time_in_force": "day",
        }
        r = httpx.post(f"{_PAPER_BASE}/v2/orders", headers=_headers(), json=payload, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"Alpaca order {side} {symbol}: {e}")
        return {"error": str(e)}

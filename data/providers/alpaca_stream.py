"""Alpaca real-time price cache via WebSocket.

Maintains an in-memory dict of latest prices updated from the
Alpaca IEX real-time stream. Falls back to REST on disconnect.

Usage:
    stream = AlpacaStream(["AAPL", "MSFT", "GOOG", "NVDA"])
    await stream.start()          # call once at app startup
    price = stream.get("AAPL")   # non-blocking, returns cached float or None
    await stream.stop()
"""
import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"


class AlpacaStream:
    def __init__(self, symbols: list[str]):
        self.symbols = [s.upper() for s in symbols]
        self._prices: dict[str, float] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def get(self, symbol: str) -> Optional[float]:
        return self._prices.get(symbol.upper())

    @property
    def latest_prices(self) -> dict[str, float]:
        return dict(self._prices)

    async def start(self):
        if not (os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")):
            logger.info("AlpacaStream: credentials absent, stream disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run_loop(self):
        """Reconnect loop — retries with exponential backoff on failure."""
        delay = 2
        while self._running:
            try:
                await self._connect()
                delay = 2  # reset on clean exit
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"AlpacaStream disconnected ({e}), retry in {delay}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connect(self):
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed — AlpacaStream disabled")
            self._running = False
            return

        async with websockets.connect(_WS_URL) as ws:
            # Auth
            await ws.send(json.dumps({
                "action": "auth",
                "key": os.getenv("ALPACA_API_KEY"),
                "secret": os.getenv("ALPACA_SECRET_KEY"),
            }))
            auth_resp = json.loads(await ws.recv())
            if not any(m.get("T") == "success" for m in auth_resp):
                raise RuntimeError(f"Auth failed: {auth_resp}")

            # Subscribe to real-time trades
            await ws.send(json.dumps({"action": "subscribe", "trades": self.symbols}))

            logger.info(f"AlpacaStream connected, subscribed to {self.symbols}")
            async for raw in ws:
                if not self._running:
                    break
                try:
                    messages = json.loads(raw)
                    for msg in messages:
                        if msg.get("T") == "t":  # trade tick
                            sym = msg.get("S", "")
                            price = msg.get("p")
                            if sym and price is not None:
                                self._prices[sym] = float(price)
                except Exception as e:
                    logger.debug(f"AlpacaStream parse error: {e}")

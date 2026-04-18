"""StrategyRunner — compiles and executes a strategy's run() function.

Accepts strategy code as a string, generates synthetic or
seeded price data, and returns raw signals + position sizes.
No external data fetches — everything is deterministic.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any


class StrategyRunner:
    """Compiles strategy code and runs it against synthetic price data."""

    def run(
        self,
        strategy_code: str,
        parameters: dict,
        symbols: list[str],
        start: str,
        end: str,
        seed: int = 42,
    ) -> dict:
        """Execute strategy code and return raw output.

        Returns:
            {
                "signals": list[str],
                "position_sizes": list[float],
                "prices": list[float],
                "dates": list[str],
            }
        """
        prices, dates = self._generate_prices(symbols[0] if symbols else "AAPL", start, end, seed)
        run_fn = self._compile(strategy_code)
        data = {
            "prices": prices,
            "dates": dates,
            "volume": [1_000_000.0] * len(prices),
            "symbols": symbols,
        }
        output = run_fn(data, parameters)
        signals = output.get("signals", ["hold"] * len(prices))
        sizes = output.get("position_sizes", [0.0] * len(prices))
        return {"signals": signals, "position_sizes": sizes, "prices": prices, "dates": dates}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _compile(self, code: str):
        """Compile strategy code and return the run() callable."""
        namespace: dict[str, Any] = {}
        exec(compile(code, "<strategy>", "exec"), namespace)  # noqa: S102
        run_fn = namespace.get("run")
        if run_fn is None:
            raise ValueError("Strategy code must define a 'run(data, params)' function")
        return run_fn

    def _generate_prices(self, symbol: str, start: str, end: str, seed: int) -> tuple[list[float], list[str]]:
        """Generate deterministic synthetic OHLC-close prices via seeded GBM."""
        n_days = self._count_trading_days(start, end)
        sym_seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        combined_seed = (seed ^ sym_seed) & 0xFFFFFFFF

        base_price = 100.0 + (sym_seed % 400)
        mu = 0.0002
        sigma = 0.015
        prices: list[float] = [base_price]

        # LCG pseudo-random for determinism without numpy dependency
        state = combined_seed
        for _ in range(n_days - 1):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            u = state / 0xFFFFFFFF
            # Box-Muller (half — use sin branch)
            state2 = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            u2 = state2 / 0xFFFFFFFF
            state = state2
            z = math.sqrt(-2 * math.log(max(u, 1e-10))) * math.sin(2 * math.pi * u2)
            ret = mu + sigma * z
            prices.append(max(0.01, prices[-1] * (1 + ret)))

        # Generate date strings (simplified — no calendar, just sequential)
        dates = [f"day_{i}" for i in range(n_days)]
        return prices, dates

    def _count_trading_days(self, start: str, end: str) -> int:
        """Estimate trading days between two ISO date strings."""
        try:
            from datetime import date
            y1, m1, d1 = (int(x) for x in start.split("-"))
            y2, m2, d2 = (int(x) for x in end.split("-"))
            delta = date(y2, m2, d2) - date(y1, m1, d1)
            return max(30, int(delta.days * 5 / 7))
        except Exception:
            return 252

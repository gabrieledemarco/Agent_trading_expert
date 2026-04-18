"""MetricsCalculator — computes backtest performance metrics from raw signals.

Pure numerical module. No agents, no I/O, no external deps beyond stdlib.
"""

from __future__ import annotations

import math
from typing import Sequence


class MetricsCalculator:
    """Computes Sharpe, drawdown, win-rate etc. from prices + signals."""

    def compute(
        self,
        prices: Sequence[float],
        signals: Sequence[str],
        position_sizes: Sequence[float],
        initial_capital: float = 10_000.0,
        transaction_cost: float = 0.001,
    ) -> dict:
        """Return full performance metrics dict."""
        equity, trades = self._simulate(prices, signals, position_sizes, initial_capital, transaction_cost)
        returns = self._daily_returns(equity)

        total_return = (equity[-1] / initial_capital) - 1 if equity else 0.0
        n = len(returns)
        annual_factor = 252
        annual_return = (1 + total_return) ** (annual_factor / max(n, 1)) - 1 if n > 0 else 0.0

        mean_r = sum(returns) / n if n else 0.0
        var = sum((r - mean_r) ** 2 for r in returns) / n if n > 1 else 0.0
        annual_vol = math.sqrt(var * annual_factor) if var > 0 else 0.0
        sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0.0

        peak = initial_capital
        max_dd = 0.0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        win_rate = sum(1 for r in returns if r > 0) / n if n > 0 else 0.0

        # Sortino
        neg_returns = [r for r in returns if r < 0]
        downside_var = sum(r ** 2 for r in neg_returns) / len(neg_returns) if neg_returns else 0.0
        downside_vol = math.sqrt(downside_var * annual_factor) if downside_var > 0 else 0.0
        sortino = (annual_return - 0.02) / downside_vol if downside_vol > 0 else 0.0

        calmar = annual_return / max_dd if max_dd > 0 else 0.0

        return {
            "sharpe_ratio":   round(sharpe, 4),
            "sortino_ratio":  round(sortino, 4),
            "calmar_ratio":   round(calmar, 4),
            "total_return":   round(total_return, 4),
            "annual_return":  round(annual_return, 4),
            "volatility":     round(annual_vol, 4),
            "max_drawdown":   round(max_dd, 4),
            "win_rate":       round(win_rate, 4),
            "num_trades":     len(trades),
            "risk_score":     self._risk_score(max_dd, sharpe, annual_vol),
            "return_score":   self._return_score(annual_return, sharpe),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _simulate(
        self,
        prices: Sequence[float],
        signals: Sequence[str],
        sizes: Sequence[float],
        capital: float,
        cost: float,
    ) -> tuple[list[float], list[dict]]:
        equity = [capital]
        trades = []
        position = 0.0
        cash = capital

        for i in range(1, len(prices)):
            sig = signals[i] if i < len(signals) else "hold"
            size = max(0.0, min(1.0, sizes[i])) if i < len(sizes) else 0.0
            price = prices[i]
            prev = prices[i - 1]

            if sig == "buy" and position == 0.0 and size > 0:
                qty = (cash * size) / price
                fee = qty * price * cost
                cash -= qty * price + fee
                position = qty
                trades.append({"action": "buy", "price": price, "qty": qty})

            elif sig == "sell" and position > 0.0:
                proceeds = position * price
                fee = proceeds * cost
                cash += proceeds - fee
                trades.append({"action": "sell", "price": price, "qty": position})
                position = 0.0

            equity.append(cash + position * price)

        return equity, trades

    def _daily_returns(self, equity: list[float]) -> list[float]:
        return [(equity[i] - equity[i - 1]) / equity[i - 1]
                for i in range(1, len(equity)) if equity[i - 1] != 0]

    def _risk_score(self, max_drawdown: float, sharpe: float, vol: float) -> str:
        if max_drawdown > 0.3 or vol > 0.3:
            return "HIGH"
        if max_drawdown > 0.15 or vol > 0.15:
            return "MEDIUM"
        return "LOW"

    def _return_score(self, annual_return: float, sharpe: float) -> str:
        if annual_return > 0.15 and sharpe > 1.5:
            return "EXCELLENT"
        if annual_return > 0.08 and sharpe > 1.0:
            return "GOOD"
        if annual_return > 0.03:
            return "MODERATE"
        return "POOR"

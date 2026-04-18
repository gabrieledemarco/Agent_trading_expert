"""ComputationService — pure numerical computation, no agent logic.

Extracted from ValidationAgent so that all heavy maths live here.
ValidationAgent delegates to this class; the Execution Engine will
eventually expose the same interface over HTTP.
"""

from __future__ import annotations

import numpy as np


class ComputationService:
    """Stateless numerical computation helpers."""

    # ── Risk / Return ─────────────────────────────────────────────────────────

    def analyze_risk_return_profile(self, model_name: str) -> dict:
        """Return risk/return metrics for *model_name* (deterministic via hash seed)."""
        np.random.seed(hash(model_name) % 2**32)
        n_days = 252

        base_return = (hash(model_name) % 100 + 5) / 2000
        volatility  = 0.02 + (hash(model_name + "v") % 100) / 2000

        returns = np.random.normal(base_return / 252, volatility / np.sqrt(252), n_days)
        equity  = (1 + returns).cumprod() * 10_000

        total_return  = (equity[-1] / 10_000) - 1
        annual_return = (1 + total_return) ** (252 / n_days) - 1
        annual_vol    = returns.std() * np.sqrt(252)
        sharpe        = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0.0

        peak        = np.maximum.accumulate(equity)
        max_drawdown = float(np.max((peak - equity) / peak))
        win_rate     = float((returns > 0).mean())

        return {
            "expected_return":   float(annual_return),
            "volatility":        float(annual_vol),
            "sharpe_ratio":      float(sharpe),
            "max_drawdown":      max_drawdown,
            "win_rate":          win_rate,
            "risk_score":        self._risk_score(max_drawdown, sharpe, annual_vol),
            "return_score":      self._return_score(annual_return, sharpe),
            "risk_return_ratio": float(abs(annual_return / annual_vol)) if annual_vol > 0 else 0.0,
        }

    def _risk_score(self, max_drawdown: float, sharpe: float, vol: float) -> str:
        if max_drawdown > 0.3 or vol > 0.3:
            return "HIGH"
        elif max_drawdown > 0.15 or vol > 0.15:
            return "MEDIUM"
        return "LOW"

    def _return_score(self, annual_return: float, sharpe: float) -> str:
        if annual_return > 0.15 and sharpe > 1.5:
            return "EXCELLENT"
        elif annual_return > 0.08 and sharpe > 1.0:
            return "GOOD"
        elif annual_return > 0.03:
            return "MODERATE"
        return "POOR"

    # ── Statistical Robustness ────────────────────────────────────────────────

    def evaluate_statistical_robustness(self, model_name: str) -> dict:
        """Monte Carlo robustness analysis (100 simulations, deterministic)."""
        np.random.seed(hash(model_name + "robust") % 2**32)
        n_simulations = 100

        scenarios = []
        for _ in range(n_simulations):
            market_bias    = np.random.choice([-0.001, 0.0, 0.001])
            vol_multiplier = np.random.uniform(0.5, 2.0)
            returns        = np.random.normal(market_bias, 0.02 * vol_multiplier, 252)
            scenarios.append(float(returns.sum()))

        arr = np.array(scenarios)

        return {
            "mean_return":              float(arr.mean()),
            "std_return":               float(arr.std()),
            "percentile_5":             float(np.percentile(arr, 5)),
            "percentile_95":            float(np.percentile(arr, 95)),
            "prob_positive_return":     float((arr > 0).mean()),
            "prob_negative_10":         float((arr < -0.10).mean()),
            "coefficient_of_variation": float(abs(arr.mean() / arr.std())) if arr.std() > 0 else 0.0,
            "robustness_score":         self._robustness_score(arr),
        }

    def _robustness_score(self, scenarios: np.ndarray) -> str:
        cv       = abs(scenarios.mean() / scenarios.std()) if scenarios.std() > 0 else 0
        prob_pos = float((scenarios > 0).mean())
        if cv > 1.5 and prob_pos > 0.7:
            return "HIGH"
        elif cv > 0.8 and prob_pos > 0.5:
            return "MEDIUM"
        return "LOW"

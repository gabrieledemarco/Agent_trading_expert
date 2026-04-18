"""Parity tests: ComputationService output == pre-extraction inline logic.

These tests lock the numerical results so any future refactor that breaks
determinism is caught immediately.
"""

import numpy as np
import pytest
from execution_engine.computation_service import ComputationService

MODEL_NAMES = [
    "model_dynamic_time_window_optimization_for",
    "model_hierarchical_temporal_memory_for_fina",
    "model_hybrid_wavelet_lstm_for_multi_timescal",
    "model_regime_adaptive_portfolio_optimization",
]


def _reference_risk_return(model_name: str) -> dict:
    """Original inline implementation, kept here for parity comparison."""
    np.random.seed(hash(model_name) % 2**32)
    n_days = 252
    base_return = (hash(model_name) % 100 + 5) / 2000
    volatility  = 0.02 + (hash(model_name + "v") % 100) / 2000
    returns = np.random.normal(base_return / 252, volatility / np.sqrt(252), n_days)
    equity  = (1 + returns).cumprod() * 10000

    total_return  = (equity[-1] / 10000) - 1
    annual_return = (1 + total_return) ** (252 / n_days) - 1
    annual_vol    = returns.std() * np.sqrt(252)
    sharpe        = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

    peak         = np.maximum.accumulate(equity)
    max_drawdown = float(np.max((peak - equity) / peak))
    win_rate     = float((returns > 0).mean())

    return {
        "expected_return":   float(annual_return),
        "volatility":        float(annual_vol),
        "sharpe_ratio":      float(sharpe),
        "max_drawdown":      max_drawdown,
        "win_rate":          win_rate,
        "risk_return_ratio": float(abs(annual_return / annual_vol)) if annual_vol > 0 else 0.0,
    }


def _reference_robustness(model_name: str) -> dict:
    np.random.seed(hash(model_name + "robust") % 2**32)
    scenarios = []
    for _ in range(100):
        market_bias    = np.random.choice([-0.001, 0.0, 0.001])
        vol_multiplier = np.random.uniform(0.5, 2.0)
        returns        = np.random.normal(market_bias, 0.02 * vol_multiplier, 252)
        scenarios.append(float(returns.sum()))
    arr = np.array(scenarios)
    return {
        "mean_return":          float(arr.mean()),
        "std_return":           float(arr.std()),
        "percentile_5":         float(np.percentile(arr, 5)),
        "percentile_95":        float(np.percentile(arr, 95)),
        "prob_positive_return": float((arr > 0).mean()),
        "prob_negative_10":     float((arr < -0.10).mean()),
    }


@pytest.fixture(scope="module")
def svc():
    return ComputationService()


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_risk_return_parity(svc, model_name):
    got = svc.analyze_risk_return_profile(model_name)
    ref = _reference_risk_return(model_name)
    for key, ref_val in ref.items():
        assert abs(got[key] - ref_val) < 1e-12, f"{key} mismatch for {model_name}"


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_robustness_parity(svc, model_name):
    got = svc.evaluate_statistical_robustness(model_name)
    ref = _reference_robustness(model_name)
    for key, ref_val in ref.items():
        assert abs(got[key] - ref_val) < 1e-12, f"{key} mismatch for {model_name}"

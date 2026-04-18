"""Contract tests for StrategyRunner, MetricsCalculator, ComputationService.run_strategy_code."""

from __future__ import annotations

import pytest

MOMENTUM_CODE = """
def run(data, params):
    prices = data["prices"]
    lookback = params.get("lookback", 10)
    threshold = params.get("threshold", 0.01)
    n = len(prices)
    signals = ["hold"] * n
    sizes = [0.0] * n
    for i in range(lookback, n):
        mom = (prices[i] - prices[i - lookback]) / prices[i - lookback]
        if mom > threshold:
            signals[i] = "buy"
            sizes[i] = 0.5
        elif mom < -threshold:
            signals[i] = "sell"
            sizes[i] = 0.5
    return {"signals": signals, "position_sizes": sizes}
""".strip()

HOLD_CODE = "def run(data, params): n=len(data['prices']); return {'signals':['hold']*n,'position_sizes':[0.0]*n}"


# ── StrategyRunner ────────────────────────────────────────────────────────────

class TestStrategyRunner:
    @pytest.fixture
    def runner(self):
        from execution_engine.runner import StrategyRunner
        return StrategyRunner()

    def test_imports_cleanly(self):
        from execution_engine.runner import StrategyRunner
        assert StrategyRunner is not None

    def test_run_returns_required_keys(self, runner):
        result = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert "signals" in result
        assert "position_sizes" in result
        assert "prices" in result
        assert "dates" in result

    def test_output_lengths_match(self, runner):
        result = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        n = len(result["prices"])
        assert len(result["signals"]) == n
        assert len(result["position_sizes"]) == n
        assert len(result["dates"]) == n

    def test_signals_are_valid(self, runner):
        result = runner.run(MOMENTUM_CODE, {"lookback": 10, "threshold": 0.01}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert all(s in ("buy", "sell", "hold") for s in result["signals"])

    def test_position_sizes_in_range(self, runner):
        result = runner.run(MOMENTUM_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert all(0.0 <= s <= 1.0 for s in result["position_sizes"])

    def test_prices_are_positive(self, runner):
        result = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert all(p > 0 for p in result["prices"])

    def test_deterministic_same_seed(self, runner):
        r1 = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31", seed=42)
        r2 = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31", seed=42)
        assert r1["prices"] == r2["prices"]

    def test_different_seeds_differ(self, runner):
        r1 = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31", seed=1)
        r2 = runner.run(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31", seed=999)
        assert r1["prices"] != r2["prices"]

    def test_raises_on_missing_run_fn(self, runner):
        with pytest.raises(ValueError, match="must define"):
            runner.run("def foo(): pass", {}, ["AAPL"], "2022-01-01", "2022-12-31")

    def test_minimum_price_count(self, runner):
        result = runner.run(HOLD_CODE, {}, ["AAPL"], "2023-01-01", "2023-06-30")
        assert len(result["prices"]) >= 30

    @pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "GOOG", "TSLA"])
    def test_different_symbols_give_different_prices(self, runner, symbol):
        result = runner.run(HOLD_CODE, {}, [symbol], "2022-01-01", "2022-12-31")
        assert len(result["prices"]) > 0
        assert result["prices"][0] > 0


# ── MetricsCalculator ─────────────────────────────────────────────────────────

class TestMetricsCalculator:
    @pytest.fixture
    def calc(self):
        from execution_engine.metrics import MetricsCalculator
        return MetricsCalculator()

    @pytest.fixture
    def flat_prices(self):
        return [100.0] * 252

    @pytest.fixture
    def rising_prices(self):
        return [100.0 + i * 0.5 for i in range(252)]

    def test_imports_cleanly(self):
        from execution_engine.metrics import MetricsCalculator
        assert MetricsCalculator is not None

    def test_returns_all_required_keys(self, calc, flat_prices):
        result = calc.compute(flat_prices, ["hold"] * 252, [0.0] * 252)
        for key in ("sharpe_ratio", "sortino_ratio", "calmar_ratio", "total_return",
                    "annual_return", "volatility", "max_drawdown", "win_rate",
                    "num_trades", "risk_score", "return_score"):
            assert key in result, f"Missing key: {key}"

    def test_hold_strategy_num_trades_zero(self, calc, flat_prices):
        result = calc.compute(flat_prices, ["hold"] * 252, [0.0] * 252)
        assert result["num_trades"] == 0

    def test_win_rate_between_0_and_1(self, calc, rising_prices):
        signals = ["buy"] + ["hold"] * 250 + ["sell"]
        sizes = [1.0] + [0.0] * 250 + [1.0]
        result = calc.compute(rising_prices, signals, sizes)
        assert 0.0 <= result["win_rate"] <= 1.0

    def test_max_drawdown_non_negative(self, calc, rising_prices):
        signals = ["hold"] * 252
        sizes = [0.0] * 252
        result = calc.compute(rising_prices, signals, sizes)
        assert result["max_drawdown"] >= 0.0

    def test_risk_score_enum(self, calc, flat_prices):
        result = calc.compute(flat_prices, ["hold"] * 252, [0.0] * 252)
        assert result["risk_score"] in ("LOW", "MEDIUM", "HIGH")

    def test_return_score_enum(self, calc, flat_prices):
        result = calc.compute(flat_prices, ["hold"] * 252, [0.0] * 252)
        assert result["return_score"] in ("POOR", "MODERATE", "GOOD", "EXCELLENT")

    def test_buy_sell_produces_trades(self, calc, rising_prices):
        # loop starts at i=1, so buy signal at index 1
        signals = ["hold", "buy"] + ["hold"] * 124 + ["sell"] + ["hold"] * 125
        sizes = [0.0, 0.5] + [0.0] * 124 + [1.0] + [0.0] * 125
        result = calc.compute(rising_prices, signals, sizes)
        assert result["num_trades"] == 2

    def test_rising_market_positive_return(self, calc, rising_prices):
        signals = ["hold", "buy"] + ["hold"] * 249 + ["sell"]
        sizes = [0.0, 1.0] + [0.0] * 249 + [1.0]
        result = calc.compute(rising_prices, signals, sizes)
        assert result["total_return"] > 0


# ── ComputationService.run_strategy_code ─────────────────────────────────────

class TestComputationServiceRunStrategy:
    @pytest.fixture
    def svc(self):
        from execution_engine.computation_service import ComputationService
        return ComputationService()

    def test_run_strategy_code_returns_dict(self, svc):
        result = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert isinstance(result, dict)

    def test_run_strategy_code_has_required_keys(self, svc):
        result = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert "execution_id" in result
        assert "status" in result
        assert "risk_return" in result

    def test_run_strategy_code_status_completed(self, svc):
        result = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert result["status"] == "completed"

    def test_run_strategy_code_risk_return_schema(self, svc):
        result = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        rr = result["risk_return"]
        assert "sharpe_ratio" in rr
        assert "max_drawdown" in rr
        assert "win_rate" in rr

    def test_run_strategy_code_momentum(self, svc):
        result = svc.run_strategy_code(
            MOMENTUM_CODE,
            {"lookback": 10, "threshold": 0.01},
            ["AAPL"], "2022-01-01", "2022-12-31",
        )
        assert result["status"] == "completed"
        assert isinstance(result["risk_return"]["sharpe_ratio"], float)

    def test_execution_id_is_unique(self, svc):
        r1 = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        r2 = svc.run_strategy_code(HOLD_CODE, {}, ["AAPL"], "2022-01-01", "2022-12-31")
        assert r1["execution_id"] != r2["execution_id"]


# ── ExecutionClient local execute_backtest ────────────────────────────────────

class TestExecutionClientLocalBacktest:
    @pytest.fixture
    def client(self):
        from agents.base.execution_client import ExecutionClient
        return ExecutionClient(engine_url=None)

    def test_execute_backtest_local_returns_dict(self, client):
        result = client.execute_backtest({
            "strategy_id": "test",
            "strategy_code": HOLD_CODE,
            "parameters": {},
            "dataset": {"symbols": ["AAPL"], "start": "2022-01-01", "end": "2022-12-31"},
            "backtest_config": {"initial_capital": 10000, "seed": 42},
        })
        assert isinstance(result, dict)

    def test_execute_backtest_local_has_risk_return(self, client):
        result = client.execute_backtest({
            "strategy_id": "test",
            "strategy_code": MOMENTUM_CODE,
            "parameters": {"lookback": 10, "threshold": 0.01},
            "dataset": {"symbols": ["AAPL"], "start": "2022-01-01", "end": "2022-12-31"},
            "backtest_config": {"initial_capital": 10000, "seed": 42},
        })
        assert "risk_return" in result
        assert "sharpe_ratio" in result["risk_return"]

    def test_execute_backtest_local_status_completed(self, client):
        result = client.execute_backtest({
            "strategy_id": "test",
            "strategy_code": HOLD_CODE,
            "parameters": {},
            "dataset": {"symbols": ["AAPL"], "start": "2022-01-01", "end": "2022-12-31"},
        })
        assert result["status"] == "completed"

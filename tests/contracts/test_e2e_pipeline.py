"""End-to-end pipeline test: Research → Strategy → Backtest → Validation → Improvement.

Uses only local/mock components — no external services required.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dirs(tmp_path):
    dirs = {
        "specs": tmp_path / "specs",
        "versions": tmp_path / "versions",
        "validated": tmp_path / "validated",
        "logs": tmp_path / "logs",
    }
    for d in dirs.values():
        d.mkdir(parents=True)
    return dirs


@pytest.fixture
def sample_spec(tmp_dirs):
    spec = {
        "model": {
            "name": "e2e_momentum_v1",
            "type": "momentum",
            "description": "End-to-end test momentum strategy",
        },
        "architecture": {"type": "rule_based"},
        "training": {
            "hyperparameters": {
                "lookback_period": 10,
                "signal_threshold": 0.015,
            }
        },
        "data_requirements": {"sources": ["AAPL"]},
        "source_paper": {"title": "E2E Test Paper"},
    }
    spec_file = tmp_dirs["specs"] / "e2e_momentum_v1.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec, f)
    return spec


@pytest.fixture
def mock_backtest_result():
    return {
        "execution_id": "e2e-exec-001",
        "risk_return": {
            "sharpe_ratio": 0.95,
            "max_drawdown": -0.12,
            "win_rate": 0.52,
            "risk_score": "MEDIUM",
        },
    }


@pytest.fixture
def strategy_agent(tmp_dirs):
    from agents.strategy.strategy_agent import StrategyAgent
    return StrategyAgent(
        specs_dir=str(tmp_dirs["specs"]),
        output_dir=str(tmp_dirs["versions"]),
    )


@pytest.fixture
def improvement_agent(tmp_dirs):
    from agents.improvement.improvement_agent import ImprovementAgent
    return ImprovementAgent(
        validated_dir=str(tmp_dirs["validated"]),
        output_dir=str(tmp_dirs["versions"]),
        max_iterations=2,
    )


# ── Stage 1: Strategy generation ─────────────────────────────────────────────

class TestStage1StrategyGeneration:
    """Strategy code must be generated from spec and saved to disk."""

    def test_generates_strategy_file(self, strategy_agent, sample_spec, mock_backtest_result, tmp_dirs):
        with patch.object(strategy_agent.execution_client, "execute_backtest", return_value=mock_backtest_result):
            result = strategy_agent.generate_strategy(sample_spec)

        assert result["status"] == "generated"
        output = Path(result["output_file"])
        assert output.exists()
        content = output.read_text()
        assert "def run(data" in content

    def test_generated_strategy_is_valid_python(self, strategy_agent, sample_spec, mock_backtest_result):
        with patch.object(strategy_agent.execution_client, "execute_backtest", return_value=mock_backtest_result):
            result = strategy_agent.generate_strategy(sample_spec)

        code_path = Path(result["output_file"])
        code = code_path.read_text()
        # Strip header comments before compile check
        code_lines = [ln for ln in code.splitlines() if not ln.startswith("#")]
        fn_code = "\n".join(code_lines)
        namespace = {}
        exec(compile(fn_code, "<test>", "exec"), namespace)
        assert "run" in namespace

    def test_run_fn_produces_correct_schema(self, strategy_agent, sample_spec, mock_backtest_result):
        with patch.object(strategy_agent.execution_client, "execute_backtest", return_value=mock_backtest_result):
            result = strategy_agent.generate_strategy(sample_spec)

        code_path = Path(result["output_file"])
        code = code_path.read_text()
        code_lines = [ln for ln in code.splitlines() if not ln.startswith("#")]
        namespace = {}
        exec(compile("\n".join(code_lines), "<test>", "exec"), namespace)

        prices = [100.0 + i for i in range(30)]
        output = namespace["run"](
            {"prices": prices, "dates": [str(i) for i in range(30)], "volume": [1e6] * 30},
            {"lookback": 10, "threshold": 0.015},
        )
        assert "signals" in output
        assert "position_sizes" in output
        assert len(output["signals"]) == 30
        assert all(s in ("buy", "sell", "hold") for s in output["signals"])
        assert all(0.0 <= sz <= 1.0 for sz in output["position_sizes"])


# ── Stage 2: Validation integration ──────────────────────────────────────────

class TestStage2ValidationIntegration:
    """Validation results drive the improvement stage."""

    def test_rejected_validation_triggers_improvement(self, improvement_agent, tmp_dirs, mock_backtest_result):
        validation = {
            "model_name": "e2e_momentum_v1",
            "validation_status": "REJECTED",
            "risk_return_profile": {
                "sharpe_ratio": 0.3,
                "max_drawdown": -0.30,
                "win_rate": 0.44,
            },
            "anomalies": [],
        }
        vpath = tmp_dirs["validated"] / "e2e_momentum_v1_validation.json"
        vpath.write_text(json.dumps(validation))

        improved_result = {"risk_return": {"sharpe_ratio": 1.1}, "execution_id": "e2e-imp-001"}
        with patch.object(improvement_agent.execution_client, "execute_backtest", return_value=improved_result):
            results = improvement_agent.run()

        assert len(results) == 1
        r = results[0]
        assert r["model_name"] == "e2e_momentum_v1"
        assert r["status"] == "improved"
        assert r["best_sharpe"] > validation["risk_return_profile"]["sharpe_ratio"]

    def test_approved_strategy_not_targeted(self, improvement_agent, tmp_dirs):
        validation = {
            "model_name": "e2e_approved",
            "validation_status": "APPROVED",
            "risk_return_profile": {"sharpe_ratio": 1.8},
            "anomalies": [],
        }
        vpath = tmp_dirs["validated"] / "e2e_approved_validation.json"
        vpath.write_text(json.dumps(validation))

        results = improvement_agent.run()
        assert results == []


# ── Stage 3: TradingAgentsWrapper integration ─────────────────────────────────

class TestStage3OrchestrationIntegration:
    """Wrapper must route decisions correctly and handle local fallback."""

    def test_local_pipeline_decision_schema(self):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper, AgentDecision

        wrapper = TradingAgentsWrapper()
        with patch("agents.orchestration.trading_agents_wrapper.USE_TRADING_AGENTS", False):
            mock_exec = MagicMock()
            mock_exec.fetch_realtime_data.return_value = {"prices": [100.0, 101.0, 102.0]}
            mock_exec.generate_signal.return_value = "buy"
            with patch("agents.trading.trading_executor.TradingExecutorAgent", return_value=mock_exec):
                decision = wrapper.propagate("AAPL", "2024-01-15")

        assert isinstance(decision, AgentDecision)
        assert decision.ticker == "AAPL"
        assert decision.date == "2024-01-15"
        assert decision.action in ("buy", "sell", "hold")
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.source in ("trading_agents", "local_pipeline")

    def test_propagate_fallback_on_local_error(self):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper, AgentDecision

        wrapper = TradingAgentsWrapper()
        with patch("agents.orchestration.trading_agents_wrapper.USE_TRADING_AGENTS", False):
            with patch("agents.trading.trading_executor.TradingExecutorAgent", side_effect=ImportError("no module")):
                decision = wrapper.propagate("AAPL", "2024-01-15")

        assert isinstance(decision, AgentDecision)
        assert decision.action == "hold"

    def test_reflect_and_remember_no_crash(self):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper

        wrapper = TradingAgentsWrapper()
        wrapper.reflect_and_remember("AAPL", 250.75)
        wrapper.reflect_and_remember("MSFT", -50.0)


# ── Full pipeline: Research → Strategy → Improvement → Decision ───────────────

class TestFullPipeline:
    """Smoke test: all three stages chain together without errors."""

    def test_full_pipeline_no_exceptions(self, strategy_agent, improvement_agent, sample_spec, tmp_dirs, mock_backtest_result):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper

        # Stage 1: Generate strategy
        with patch.object(strategy_agent.execution_client, "execute_backtest", return_value=mock_backtest_result):
            gen_result = strategy_agent.generate_strategy(sample_spec)
        assert gen_result["status"] == "generated"

        # Stage 2: Simulate rejection and improve
        validation = {
            "model_name": "e2e_momentum_v1",
            "validation_status": "REJECTED",
            "risk_return_profile": {"sharpe_ratio": 0.4, "max_drawdown": -0.2, "win_rate": 0.48},
            "anomalies": [],
        }
        vpath = tmp_dirs["validated"] / "e2e_momentum_v1_validation.json"
        vpath.write_text(json.dumps(validation))

        improved = {"risk_return": {"sharpe_ratio": 1.2}, "execution_id": "imp-001"}
        with patch.object(improvement_agent.execution_client, "execute_backtest", return_value=improved):
            imp_results = improvement_agent.run()
        assert imp_results[0]["status"] == "improved"

        # Stage 3: Get trade decision
        wrapper = TradingAgentsWrapper()
        with patch("agents.orchestration.trading_agents_wrapper.USE_TRADING_AGENTS", False):
            with patch("agents.trading.trading_executor.TradingExecutorAgent", side_effect=ImportError):
                decision = wrapper.propagate("AAPL", "2024-01-15")
        assert decision.action in ("buy", "sell", "hold")

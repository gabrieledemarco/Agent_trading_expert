"""Contract tests for StrategyAgent, ImprovementAgent, TradingAgentsWrapper, QueueWorker."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── StrategyAgent contracts ───────────────────────────────────────────────────

class TestStrategyAgentContracts:
    """StrategyAgent must produce valid strategy output without numerical computation."""

    @pytest.fixture
    def agent(self, tmp_path):
        from agents.strategy.strategy_agent import StrategyAgent
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        output_dir = tmp_path / "versions"
        output_dir.mkdir()
        return StrategyAgent(specs_dir=str(specs_dir), output_dir=str(output_dir))

    def test_imports_cleanly(self):
        from agents.strategy.strategy_agent import StrategyAgent
        assert StrategyAgent is not None

    def test_inherits_base_agent(self):
        from agents.strategy.strategy_agent import StrategyAgent
        from agents.base.base_agent import BaseAgent
        assert issubclass(StrategyAgent, BaseAgent)

    def test_run_returns_list(self, agent):
        result = agent.run()
        assert isinstance(result, list)

    def test_generate_strategy_calls_execution_client(self, agent):
        spec = {
            "model": {"name": "test_momentum", "type": "momentum", "description": "test"},
            "architecture": {},
            "training": {"hyperparameters": {"lookback_period": 20, "signal_threshold": 0.02}},
            "data_requirements": {"sources": ["AAPL"]},
            "source_paper": {"title": "Test Paper"},
        }
        mock_result = {
            "execution_id": "test-exec-001",
            "risk_return": {"sharpe_ratio": 1.2, "risk_score": "LOW"},
        }
        with patch.object(agent.execution_client, "execute_backtest", return_value=mock_result) as mock_exec:
            result = agent.generate_strategy(spec)
            mock_exec.assert_called_once()
            assert result["model_name"] == "test_momentum"
            assert result["status"] == "generated"
            assert "output_file" in result
            assert "execution_id" in result

    def test_template_generates_valid_python(self, agent):
        for model_type in ["momentum", "mean_reversion", "lstm"]:
            spec = {
                "model": {"name": f"test_{model_type}", "type": model_type},
                "architecture": {},
                "training": {"hyperparameters": {"lookback_period": 10, "signal_threshold": 0.01}},
            }
            code = agent._template_generate(spec)
            assert "def run(data" in code
            assert "signals" in code
            assert "position_sizes" in code

    def test_generated_code_is_executable(self, agent):
        spec = {
            "model": {"name": "exec_test", "type": "momentum"},
            "training": {"hyperparameters": {"lookback_period": 5, "signal_threshold": 0.01}},
        }
        code = agent._template_generate(spec)
        namespace = {}
        exec(compile(code, "<test>", "exec"), namespace)
        run_fn = namespace["run"]
        prices = [100.0 + i * 0.5 for i in range(20)]
        result = run_fn({"prices": prices, "dates": [], "volume": []}, {})
        assert "signals" in result
        assert "position_sizes" in result
        assert len(result["signals"]) == len(prices)
        assert all(s in ("buy", "sell", "hold") for s in result["signals"])

    def test_no_numerical_computation_in_agent(self, agent):
        """Agent must not do numerical math — that's ExecutionClient's job."""
        import inspect
        source = inspect.getsource(type(agent))
        # Template methods are allowed to have simple arithmetic for code generation
        # but the agent itself must not call numpy/pandas
        assert "import numpy" not in source
        assert "import pandas" not in source

    @pytest.mark.parametrize("model_type,expected_fn", [
        ("momentum", "_momentum_template"),
        ("mean_reversion", "_mean_reversion_template"),
        ("lstm", "_ml_template"),
        ("neural_net", "_ml_template"),
        ("arbitrage", "_mean_reversion_template"),
        ("unknown_type", "_momentum_template"),  # default fallback
    ])
    def test_template_routing(self, agent, model_type, expected_fn):
        spec = {
            "model": {"type": model_type},
            "training": {"hyperparameters": {}},
        }
        with patch.object(agent, expected_fn, wraps=getattr(agent, expected_fn)) as mock_fn:
            agent._template_generate(spec)
            mock_fn.assert_called_once()


# ── ImprovementAgent contracts ────────────────────────────────────────────────

class TestImprovementAgentContracts:
    """ImprovementAgent must iterate over REJECTED strategies and propose improvements."""

    @pytest.fixture
    def agent(self, tmp_path):
        from agents.improvement.improvement_agent import ImprovementAgent
        validated_dir = tmp_path / "validated"
        validated_dir.mkdir()
        output_dir = tmp_path / "versions"
        output_dir.mkdir()
        return ImprovementAgent(
            validated_dir=str(validated_dir),
            output_dir=str(output_dir),
            max_iterations=2,
        )

    @pytest.fixture
    def rejected_validation(self, agent):
        v = {
            "model_name": "test_strategy",
            "validation_status": "REJECTED",
            "risk_return_profile": {"sharpe_ratio": 0.3, "max_drawdown": -0.25, "win_rate": 0.45},
            "anomalies": [{"type": "high_drawdown", "severity": "high"}],
        }
        path = Path(agent.validated_dir) / "test_strategy_validation.json"
        path.write_text(json.dumps(v))
        return v

    def test_imports_cleanly(self):
        from agents.improvement.improvement_agent import ImprovementAgent
        assert ImprovementAgent is not None

    def test_inherits_base_agent(self):
        from agents.improvement.improvement_agent import ImprovementAgent
        from agents.base.base_agent import BaseAgent
        assert issubclass(ImprovementAgent, BaseAgent)

    def test_run_returns_list(self, agent):
        result = agent.run()
        assert isinstance(result, list)

    def test_improve_calls_execution_client(self, agent, rejected_validation):
        mock_result = {"risk_return": {"sharpe_ratio": 0.8}, "execution_id": "iter-001"}
        with patch.object(agent.execution_client, "execute_backtest", return_value=mock_result):
            result = agent.improve(rejected_validation)
            assert result["model_name"] == "test_strategy"
            assert "status" in result
            assert "best_sharpe" in result
            assert "iterations" in result
            assert len(result["iterations"]) == agent.max_iterations

    def test_improve_detects_improvement(self, agent, rejected_validation):
        mock_result = {"risk_return": {"sharpe_ratio": 1.5}, "execution_id": "x"}
        with patch.object(agent.execution_client, "execute_backtest", return_value=mock_result):
            result = agent.improve(rejected_validation)
            assert result["status"] == "improved"
            assert result["best_sharpe"] > rejected_validation["risk_return_profile"]["sharpe_ratio"]

    def test_improve_handles_no_improvement(self, agent, rejected_validation):
        mock_result = {"risk_return": {"sharpe_ratio": 0.1}, "execution_id": "x"}
        with patch.object(agent.execution_client, "execute_backtest", return_value=mock_result):
            result = agent.improve(rejected_validation)
            assert result["status"] == "no_improvement"

    def test_heuristic_propose_first_iter(self, agent):
        params = {"lookback": 20, "threshold": 0.02}
        new = agent._heuristic_propose(params, [])
        assert new["lookback"] > params["lookback"]
        assert new["threshold"] < params["threshold"]

    def test_heuristic_propose_no_improvement(self, agent):
        params = {"lookback": 20, "threshold": 0.02}
        history = [{"iteration": 1, "params": params, "sharpe": 0.2, "improved": False}]
        new = agent._heuristic_propose(params, history)
        assert new["threshold"] > params["threshold"]

    def test_find_targets_only_rejected(self, agent, rejected_validation):
        approved_v = {
            "model_name": "approved_strat",
            "validation_status": "APPROVED",
            "risk_return_profile": {"sharpe_ratio": 1.5},
        }
        approved_path = Path(agent.validated_dir) / "approved_strat_validation.json"
        approved_path.write_text(json.dumps(approved_v))

        targets = agent._find_targets(None)
        names = [t["model_name"] for t in targets]
        assert "test_strategy" in names
        assert "approved_strat" not in names

    def test_find_specific_model(self, agent, rejected_validation):
        targets = agent._find_targets("test_strategy")
        assert len(targets) == 1
        assert targets[0]["model_name"] == "test_strategy"


# ── TradingAgentsWrapper contracts ────────────────────────────────────────────

class TestTradingAgentsWrapperContracts:
    """TradingAgentsWrapper must return AgentDecision with correct schema."""

    @pytest.fixture
    def wrapper(self):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper
        return TradingAgentsWrapper()

    def test_imports_cleanly(self):
        from agents.orchestration.trading_agents_wrapper import TradingAgentsWrapper, AgentDecision
        assert TradingAgentsWrapper is not None
        assert AgentDecision is not None

    def test_propagate_returns_agent_decision(self, wrapper):
        from agents.orchestration.trading_agents_wrapper import AgentDecision
        with patch("agents.orchestration.trading_agents_wrapper.USE_TRADING_AGENTS", False):
            with patch.object(wrapper, "_propagate_local") as mock_local:
                mock_local.return_value = AgentDecision(
                    ticker="AAPL", date="2024-01-01",
                    action="buy", confidence=0.7,
                    reasoning="test", source="local_pipeline",
                )
                result = wrapper.propagate("AAPL", "2024-01-01")
                assert isinstance(result, AgentDecision)
                assert result.ticker == "AAPL"
                assert result.action in ("buy", "sell", "hold")
                assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.parametrize("action", ["buy", "sell", "hold"])
    def test_agent_decision_action_values(self, action):
        from agents.orchestration.trading_agents_wrapper import AgentDecision
        d = AgentDecision(
            ticker="MSFT", date="2024-01-01",
            action=action, confidence=0.6,
            reasoning="test", source="local_pipeline",
        )
        assert d.action == action

    def test_agent_decision_has_required_fields(self):
        from agents.orchestration.trading_agents_wrapper import AgentDecision
        d = AgentDecision(
            ticker="GOOG", date="2024-06-15",
            action="hold", confidence=0.5,
            reasoning="neutral", source="trading_agents",
        )
        assert hasattr(d, "ticker")
        assert hasattr(d, "date")
        assert hasattr(d, "action")
        assert hasattr(d, "confidence")
        assert hasattr(d, "reasoning")
        assert hasattr(d, "source")
        assert hasattr(d, "metadata")

    def test_agent_decision_metadata_defaults_empty(self):
        from agents.orchestration.trading_agents_wrapper import AgentDecision
        d = AgentDecision(
            ticker="X", date="2024-01-01", action="buy",
            confidence=0.8, reasoning="r", source="s",
        )
        assert d.metadata == {}

    def test_parse_graph_result_string_buy(self, wrapper):
        result = wrapper._parse_graph_result("AAPL", "2024-01-01", "The signal is buy based on momentum")
        assert result.action == "buy"
        assert result.source == "trading_agents"

    def test_parse_graph_result_string_sell(self, wrapper):
        result = wrapper._parse_graph_result("AAPL", "2024-01-01", "sell pressure detected")
        assert result.action == "sell"

    def test_parse_graph_result_string_hold(self, wrapper):
        result = wrapper._parse_graph_result("AAPL", "2024-01-01", "neutral market conditions")
        assert result.action == "hold"

    def test_parse_graph_result_dict(self, wrapper):
        raw = {"action": "sell", "confidence": 0.85, "reasoning": "overbought"}
        result = wrapper._parse_graph_result("TSLA", "2024-01-01", raw)
        assert result.action == "sell"
        assert result.confidence == 0.85
        assert result.reasoning == "overbought"

    def test_parse_graph_result_unknown_type(self, wrapper):
        result = wrapper._parse_graph_result("AAPL", "2024-01-01", 42)
        assert result.action == "hold"
        assert result.confidence == 0.5

    def test_reflect_and_remember_no_graph(self, wrapper):
        """Should not raise when no graph loaded."""
        wrapper.reflect_and_remember("AAPL", 150.0)  # must not raise

    def test_local_propagate_returns_decision(self, wrapper):
        from agents.orchestration.trading_agents_wrapper import AgentDecision
        mock_executor = MagicMock()
        mock_executor.fetch_realtime_data.return_value = {"prices": [100, 101, 102]}
        mock_executor.generate_signal.return_value = "buy"

        with patch("agents.orchestration.trading_agents_wrapper.USE_TRADING_AGENTS", False):
            with patch("agents.trading.trading_executor.TradingExecutorAgent", return_value=mock_executor):
                decision = wrapper._propagate_local("AAPL", "2024-01-01")
                assert isinstance(decision, AgentDecision)
                assert decision.source == "local_pipeline"


# ── QueueWorker contracts ─────────────────────────────────────────────────────

class TestQueueWorkerContracts:
    """QueueWorker must handle jobs and results correctly (Redis mocked)."""

    @pytest.fixture
    def worker(self):
        from execution_engine.queue_worker import QueueWorker
        return QueueWorker()

    def test_imports_cleanly(self):
        from execution_engine.queue_worker import QueueWorker
        assert QueueWorker is not None

    def test_start_skips_when_disabled(self, worker):
        with patch("execution_engine.queue_worker.ENABLE_QUEUE_WORKER", False):
            worker.start()  # should return immediately without error

    def test_enqueue_raises_without_redis(self, worker):
        with patch.object(worker, "_connect_redis", return_value=None):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                worker.enqueue({"strategy_id": "test"})

    def test_enqueue_assigns_job_id(self, worker):
        mock_redis = MagicMock()
        with patch.object(worker, "_connect_redis", return_value=mock_redis):
            job_id = worker.enqueue({"strategy_id": "test_strategy"})
            assert isinstance(job_id, str)
            assert len(job_id) > 0
            mock_redis.rpush.assert_called_once()

    def test_enqueue_uses_provided_job_id(self, worker):
        mock_redis = MagicMock()
        with patch.object(worker, "_connect_redis", return_value=mock_redis):
            job_id = worker.enqueue({"job_id": "my-custom-id", "strategy_id": "s"})
            assert job_id == "my-custom-id"

    def test_get_result_returns_none_on_timeout(self, worker):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch.object(worker, "_connect_redis", return_value=mock_redis):
            result = worker.get_result("nonexistent-id", timeout=0)
            assert result is None

    def test_get_result_returns_parsed_json(self, worker):
        payload = {"job_id": "abc", "status": "completed", "risk_return": {"sharpe_ratio": 1.5}}
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(payload)
        with patch.object(worker, "_connect_redis", return_value=mock_redis):
            result = worker.get_result("abc", timeout=5)
            assert result == payload

    def test_compile_strategy_extracts_run_fn(self, worker):
        code = "def run(data, params):\n    return {'signals': ['hold'], 'position_sizes': [0.0]}"
        fn = worker._compile_strategy(code)
        assert callable(fn)
        out = fn({"prices": [100.0], "dates": [], "volume": []}, {})
        assert "signals" in out

    def test_compile_strategy_raises_on_missing_run(self, worker):
        code = "def not_run(data, params): pass"
        with pytest.raises(ValueError, match="must define a 'run' function"):
            worker._compile_strategy(code)

    def test_connect_redis_returns_none_without_redis(self, worker):
        with patch.dict(os.environ, {"REDIS_URL": "redis://nonexistent:6379/0"}):
            client = worker._connect_redis()
            assert client is None

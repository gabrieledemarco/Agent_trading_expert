"""Phase 3 tests: formal split MLEngineer model gates vs ValidationAgent strategy checks."""

from unittest.mock import MagicMock

from agents.ml_engineer.ml_engineer_agent import MLEngineerAgent
from agents.validation.validation_agent import ValidationAgent


def test_mlengineer_rejects_random_like_metrics():
    agent = MLEngineerAgent()
    gate = agent.evaluate_model_gates(
        {
            "mse": 1.0,
            "r2_score": 0.0,
            "directional_accuracy": 0.50,
            "train_test_gap": 0.30,
        }
    )
    assert gate["passed"] is False
    assert any("directional_accuracy" in r for r in gate["reasons"])
    assert any("r2_score" in r for r in gate["reasons"])
    assert any("train_test_gap" in r for r in gate["reasons"])


def test_mlengineer_persists_v2_model_status_rejected(tmp_path):
    agent = MLEngineerAgent(specs_dir=str(tmp_path), models_dir=str(tmp_path))
    mock_db = MagicMock()
    mock_db.get_specs.return_value = [{"id": 1, "model_name": "model_demo"}]
    mock_db.save_model.return_value = 1
    mock_db.save_model_v2.return_value = "v2-1"
    agent._db = mock_db

    spec = {
        "strategy_id": "strategy-1",
        "model": {"name": "model_demo", "type": "time_series_forecasting"},
        "training": {},
        "model_validation_metrics": {
            "mse": 1.0,
            "r2_score": 0.01,
            "directional_accuracy": 0.49,
            "train_test_gap": 0.25,
        },
        "architecture": {"input_features": []},
    }
    agent.implement_model(spec)

    kwargs = mock_db.save_model_v2.call_args[0][0]
    assert kwargs["status"] == "rejected"
    assert kwargs["directional_accuracy"] < 0.52


def test_validation_agent_rejects_high_drawdown_and_persists_v2():
    agent = ValidationAgent()
    mock_db = MagicMock()
    mock_db.get_backtest_reports.return_value = [
        {
            "id": "report-1",
            "strategy_id": "strategy-1",
            "method": "rolling_window",
            "sharpe_ratio": 1.0,
            "max_drawdown": 0.35,  # should fail L4
            "monte_carlo_pvalue": 0.01,
            "trades": [],
        }
    ]
    agent._db = mock_db

    statuses = agent.run_validation()

    assert statuses == ["REJECTED"]
    assert mock_db.save_validation_v2.called
    saved = mock_db.save_validation_v2.call_args[0][0]
    assert saved["level"] == "L4"
    assert saved["metric_name"] == "max_drawdown"

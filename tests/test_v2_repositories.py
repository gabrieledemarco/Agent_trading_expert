"""Tests for V2 repository layer abstractions."""

from unittest.mock import MagicMock

from data.repositories import (
    BacktestRepository,
    ModelRepositoryV2,
    StrategyRepository,
    ValidationRepositoryV2,
)


def test_strategy_repository_create_and_list():
    db = MagicMock()
    db.save_strategy.return_value = "strategy-1"
    db.get_strategies_v2.return_value = [{"id": "strategy-1", "name": "s1"}]

    repo = StrategyRepository(db=db)
    assert repo.create({"name": "s1", "spec": {}}) == "strategy-1"
    rows = repo.list(limit=10)
    assert len(rows) == 1
    db.save_strategy.assert_called_once()
    db.get_strategies_v2.assert_called_once()


def test_model_repository_v2_create_and_list():
    db = MagicMock()
    db.save_model_v2.return_value = "model-1"
    db.get_models_v2.return_value = [{"id": "model-1"}]

    repo = ModelRepositoryV2(db=db)
    assert repo.create({"strategy_id": "strategy-1"}) == "model-1"
    assert repo.list(status="validated")[0]["id"] == "model-1"
    db.save_model_v2.assert_called_once()
    db.get_models_v2.assert_called_once()


def test_backtest_repository_create_and_list():
    db = MagicMock()
    db.save_backtest_report.return_value = "report-1"
    db.get_backtest_reports.return_value = [{"id": "report-1"}]

    repo = BacktestRepository(db=db)
    assert repo.create({"strategy_id": "strategy-1"}) == "report-1"
    assert repo.list(strategy_id="strategy-1")[0]["id"] == "report-1"
    db.save_backtest_report.assert_called_once()
    db.get_backtest_reports.assert_called_once()


def test_validation_repository_v2_create_and_list():
    db = MagicMock()
    db.save_validation_v2.return_value = "validation-1"
    db.get_validations_v2.return_value = [{"id": "validation-1"}]

    repo = ValidationRepositoryV2(db=db)
    assert repo.create({"strategy_id": "strategy-1"}) == "validation-1"
    assert repo.list(strategy_id="strategy-1")[0]["id"] == "validation-1"
    db.save_validation_v2.assert_called_once()
    db.get_validations_v2.assert_called_once()

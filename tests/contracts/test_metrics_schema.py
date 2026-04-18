"""Contract tests for PerformanceMetrics JSONL schema.

Guards the TradingExecutor → MonitoringAgent file-based contract.
"""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

METRICS_FIELDS = {
    "timestamp": str,
    "model_name": str,
    "current_equity": (int, float),
    "total_return": (int, float),
    "sharpe_ratio": (int, float),
    "max_drawdown": (int, float),
    "win_rate": (int, float),
    "num_trades": int,
    "risk_profile": str,
}

TRADE_FIELDS = {
    "timestamp": str,
    "symbol": str,
    "action": str,
    "quantity": (int, float),
    "price": (int, float),
    "value": (int, float),
    "model_name": str,
}

VALID_ACTIONS = {"buy", "sell", "hold"}


def _load_jsonl(path: Path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@pytest.fixture()
def metrics_records():
    return _load_jsonl(FIXTURES_DIR / "metrics_snapshot_v0.jsonl")


@pytest.fixture()
def trade_records():
    return _load_jsonl(FIXTURES_DIR / "trade_snapshot_v0.jsonl")


class TestMetricsSchema:

    def test_metrics_records_not_empty(self, metrics_records):
        assert len(metrics_records) > 0

    def test_metrics_required_fields(self, metrics_records):
        for i, record in enumerate(metrics_records):
            for field, expected_type in METRICS_FIELDS.items():
                assert field in record, f"metrics[{i}] missing field '{field}'"
                assert isinstance(record[field], expected_type), (
                    f"metrics[{i}].{field} wrong type: {type(record[field])}"
                )

    def test_metrics_equity_positive(self, metrics_records):
        for record in metrics_records:
            assert record["current_equity"] > 0

    def test_metrics_win_rate_range(self, metrics_records):
        for record in metrics_records:
            assert 0.0 <= record["win_rate"] <= 1.0

    def test_metrics_max_drawdown_non_negative(self, metrics_records):
        for record in metrics_records:
            assert record["max_drawdown"] >= 0.0

    def test_metrics_num_trades_non_negative(self, metrics_records):
        for record in metrics_records:
            assert record["num_trades"] >= 0


class TestTradeSchema:

    def test_trade_records_not_empty(self, trade_records):
        assert len(trade_records) > 0

    def test_trade_required_fields(self, trade_records):
        for i, record in enumerate(trade_records):
            for field, expected_type in TRADE_FIELDS.items():
                assert field in record, f"trade[{i}] missing field '{field}'"
                assert isinstance(record[field], expected_type), (
                    f"trade[{i}].{field} wrong type"
                )

    def test_trade_action_enum(self, trade_records):
        for record in trade_records:
            assert record["action"] in VALID_ACTIONS, (
                f"Invalid trade action: '{record['action']}'"
            )

    def test_trade_positive_values(self, trade_records):
        for record in trade_records:
            assert record["quantity"] > 0
            assert record["price"] > 0
            assert record["value"] > 0

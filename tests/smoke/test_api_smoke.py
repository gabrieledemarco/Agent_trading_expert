"""Smoke tests for FastAPI endpoints.

Starts the app with a mocked DB and verifies HTTP 200 + response shape.
Requires: httpx, anyio (pip install httpx anyio).
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent.parent

_MOCK_SUMMARY = {
    "research_papers": 4, "specs_created": 4, "models_implemented": 4,
    "models_validated": 4, "total_trades": 10,
    "current_equity": 10000.0, "total_return": 0.05, "sharpe_ratio": 1.2,
}
_MOCK_AGENT_STATUS = {"agents": [{"agent_name": "ResearchAgent", "last_status": "idle"}]}
_MOCK_PERF = [{"equity": 10000.0, "total_return": 0.05, "sharpe_ratio": 1.2, "max_drawdown": 0.05}]


@pytest.fixture(scope="module")
def client():
    try:
        from httpx import Client
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("httpx not installed")

    mock_db = MagicMock()
    mock_db.get_dashboard_summary.return_value = _MOCK_SUMMARY
    mock_db.get_strategies_v2.return_value = []
    mock_db.get_agent_status.return_value = [{"agent_name": "ResearchAgent", "status": "idle"}]
    mock_db.get_performance.return_value = _MOCK_PERF
    mock_db.get_trades.return_value = []
    mock_db.get_strategies.return_value = []
    mock_db.get_agent_logs.return_value = []

    import sys, types
    sys.path.insert(0, str(ROOT))

    # data.storage.data_manager needs psycopg2 to import; inject a stub so
    # patch() can resolve the target without a real DB driver installed.
    if "data.storage.data_manager" not in sys.modules:
        _stub = types.ModuleType("data.storage.data_manager")
        _stub.DataStorageManager = type("DataStorageManager", (), {})
        sys.modules["data.storage.data_manager"] = _stub
        import data.storage as _ds_pkg
        _ds_pkg.data_manager = _stub

    with patch("data.storage.data_manager.DataStorageManager", return_value=mock_db):
        with patch("api.main.get_db", return_value=mock_db):
            from api.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c


class TestApiSmoke:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_api_dashboard_summary_shape(self, client):
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 200
        body = r.json()
        for key in ("portfolio", "strategies", "models", "research", "agents", "trades", "last_updated"):
            assert key in body, f"Missing key: {key}"

    def test_dashboard_summary_legacy(self, client):
        r = client.get("/dashboard/summary")
        assert r.status_code == 200

    def test_strategies_list(self, client):
        r = client.get("/strategies")
        assert r.status_code == 200
        assert "strategies" in r.json()

    def test_pipeline_overview(self, client):
        r = client.get("/api/pipeline/overview")
        assert r.status_code == 200
        body = r.json()
        assert "by_status" in body
        assert "total_strategies" in body

    def test_agents_status(self, client):
        r = client.get("/api/agents/status")
        assert r.status_code == 200
        assert "agents" in r.json()

    def test_risk_summary(self, client):
        r = client.get("/api/risk/summary")
        assert r.status_code == 200
        body = r.json()
        for key in ("current_equity", "sharpe_ratio", "max_drawdown_pct"):
            assert key in body

    def test_pipeline_kanban(self, client):
        r = client.get("/api/pipeline/kanban")
        assert r.status_code == 200
        body = r.json()
        assert "columns" in body

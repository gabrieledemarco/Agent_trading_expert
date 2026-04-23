"""Contract tests for internal V2 strategy endpoints."""

from unittest.mock import patch


from fastapi.testclient import TestClient

from api.main import app


class _FakeRepo:
    def __init__(self):
        self._rows = [
            {"id": "strategy-1", "name": "demo", "status": "draft", "spec": {"model": {"type": "lstm"}}}
        ]

    def create(self, strategy: dict) -> str:
        return "strategy-1"

    def list(self, status=None, limit=100):
        if status:
            return [r for r in self._rows if r.get("status") == status][:limit]
        return self._rows[:limit]


def test_create_strategy_v2_endpoint():
    with patch("data.repositories.StrategyRepository", return_value=_FakeRepo()):
        client = TestClient(app)
        payload = {"name": "demo", "spec": {"model": {"type": "lstm"}}, "status": "draft"}
        response = client.post("/internal/v2/strategies", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["strategy_id"] == "strategy-1"


def test_list_strategy_v2_endpoint():
    with patch("data.repositories.StrategyRepository", return_value=_FakeRepo()):
        client = TestClient(app)
        response = client.get("/internal/v2/strategies?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert isinstance(body["strategies"], list)


def test_v2_orchestration_metrics_endpoint_disabled_by_default():
    client = TestClient(app)
    response = client.get("/internal/v2/orchestration/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False


def test_v2_orchestration_metrics_endpoint_enabled(monkeypatch):
    monkeypatch.setenv("V2_EVENT_DRIVEN", "true")

    class _FakeOrch:
        def snapshot_metrics(self):
            return {"processed_events": 7, "failed_events": 1}

    with patch("api.main.get_event_orchestrator", return_value=_FakeOrch()):
        client = TestClient(app)
        response = client.get("/internal/v2/orchestration/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["metrics"]["processed_events"] == 7


def test_pipeline_overview_endpoint():
    class _FakeDB:
        def get_strategies_v2(self, limit=500):
            return [
                {"id": "s1", "name": "Momentum", "status": "approved"},
                {"id": "s2", "name": "Breakout", "status": "human_review"},
            ]

        def get_agent_logs(self, limit=20):
            return [{"timestamp": "2026-04-23T10:00:00", "agent_name": "ValidationAgent", "status": "warning", "message": "L4 fail"}]

    with patch("api.main.get_db", return_value=_FakeDB()):
        client = TestClient(app)
        response = client.get("/api/pipeline/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["approved"] == 1
    assert body["human_review_count"] == 1
    assert len(body["recent_events"]) == 1


def test_pipeline_kanban_and_backtest_endpoints():
    class _FakeDB:
        def get_strategies_v2(self, limit=300):
            return [{"id": "s1", "name": "MeanRev", "status": "validation_pending", "retry_count": 1, "updated_at": "2026-04-23"}]

        def get_backtest_reports(self, strategy_id=None, limit=50):
            return [{"id": "r1", "strategy_id": strategy_id, "method": "rolling_window"}]

    with patch("api.main.get_db", return_value=_FakeDB()):
        client = TestClient(app)
        kanban = client.get("/api/pipeline/kanban")
        backtest = client.get("/api/strategies/s1/backtest")

    assert kanban.status_code == 200
    assert "validation_pending" in kanban.json()["columns"]
    assert backtest.status_code == 200
    assert backtest.json()["count"] == 1

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

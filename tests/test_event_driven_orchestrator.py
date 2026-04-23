"""Tests for V2 event-driven orchestration flow."""

from agents.orchestration.event_listener import EventDrivenOrchestrator


class _FakeDB:
    def __init__(self):
        self.status_updates = []
        self.retries = {}

    def update_strategy_status(self, strategy_id: str, status: str):
        self.status_updates.append((strategy_id, status))

    def increment_strategy_retry(self, strategy_id: str) -> dict:
        self.retries[strategy_id] = self.retries.get(strategy_id, 0) + 1
        return {
            "retry_count": self.retries[strategy_id],
            "max_retries": 3,
            "reached_max": self.retries[strategy_id] >= 3,
        }


class _FakeML:
    def __init__(self):
        self.called = 0

    def run_implementation(self):
        self.called += 1
        return ["model.py"]


class _FakeSE:
    def __init__(self):
        self.args = None

    def run_for_strategy(self, strategy_id: str, model_id: str | None = None):
        self.args = (strategy_id, model_id)
        return {"strategy_id": strategy_id, "status": "backtest.completed"}


class _FakeVA:
    def run_validation(self):
        return ["APPROVED"]


class _FakeTrading:
    def __init__(self):
        self.called = 0

    def run_trading_loop(self, **kwargs):
        self.called += 1
        return {"ok": True}


def _build_orchestrator():
    return EventDrivenOrchestrator(
        db=_FakeDB(),
        ml_engineer=_FakeML(),
        strategy_engineer=_FakeSE(),
        validation_agent=_FakeVA(),
        trading_executor=_FakeTrading(),
        enable_v2=True,
    )


def test_dispatches_core_events_and_deduplicates():
    orch = _build_orchestrator()

    r1 = orch.process_event({"event": "spec.created", "strategy_id": "s1", "event_id": "e1"})
    assert r1["status"] == "ok"
    assert orch.ml_engineer.called == 1

    # duplicate same event_id should not be processed twice
    r2 = orch.process_event({"event": "spec.created", "strategy_id": "s1", "event_id": "e1"})
    assert r2["status"] == "deduplicated"
    assert orch.ml_engineer.called == 1


def test_validation_rejected_retries_then_human_review():
    orch = _build_orchestrator()

    for _ in range(3):
        orch.process_event({"event": "validation.rejected", "strategy_id": "s2"})

    # last transition should be human_review at retry limit
    assert orch.db.status_updates[-1] == ("s2", "human_review")


def test_validation_approved_deploys_paper_trading():
    orch = _build_orchestrator()

    res = orch.process_event({"event": "validation.approved", "strategy_id": "s3"})

    assert res["status"] == "ok"
    assert orch.trading_executor.called == 1
    assert ("s3", "deployed") in orch.db.status_updates

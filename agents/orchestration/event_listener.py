"""Event-driven V2 orchestrator backed by PostgreSQL LISTEN/NOTIFY."""

from __future__ import annotations

import json
import logging
import os
import select
import time
from dataclasses import dataclass, asdict
from typing import Optional

import psycopg2

from agents.ml_engineer.ml_engineer_agent import MLEngineerAgent
from agents.strategy import StrategyEngineer
from agents.trading.trading_executor import TradingExecutorAgent
from agents.validation.validation_agent import ValidationAgent
from data.storage.data_manager import DataStorageManager

logger = logging.getLogger(__name__)


@dataclass
class EventOrchestrationMetrics:
    processed_events: int = 0
    failed_events: int = 0
    deduplicated_events: int = 0
    total_retries: int = 0
    last_event: Optional[str] = None
    last_latency_ms: int = 0


class EventDrivenOrchestrator:
    """Consumes domain events and executes V2 phase transitions with retry policies."""

    def __init__(
        self,
        db: Optional[DataStorageManager] = None,
        ml_engineer: Optional[MLEngineerAgent] = None,
        strategy_engineer: Optional[StrategyEngineer] = None,
        validation_agent: Optional[ValidationAgent] = None,
        trading_executor: Optional[TradingExecutorAgent] = None,
        enable_v2: Optional[bool] = None,
    ):
        self.db = db or DataStorageManager()
        self.ml_engineer = ml_engineer or MLEngineerAgent()
        self.strategy_engineer = strategy_engineer or StrategyEngineer(db=self.db)
        self.validation_agent = validation_agent or ValidationAgent()
        self.trading_executor = trading_executor or TradingExecutorAgent(paper_trading=True)
        self.metrics = EventOrchestrationMetrics()

        if enable_v2 is None:
            enable_v2 = str(os.getenv("V2_EVENT_DRIVEN", "false")).lower() in {"1", "true", "yes", "on"}
        self.enable_v2 = enable_v2
        self._seen_event_ids: set[str] = set()

    def snapshot_metrics(self) -> dict:
        return asdict(self.metrics)

    def listen_forever(self, poll_seconds: float = 1.0):
        """Start LISTEN/NOTIFY loop on channel `events`."""
        if not self.enable_v2:
            logger.info("Event-driven orchestrator disabled by V2_EVENT_DRIVEN flag")
            return

        conn = psycopg2.connect(self.db.db_url)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("LISTEN events;")
        logger.info("Listening on PostgreSQL channel 'events'")

        while True:
            if select.select([conn], [], [], poll_seconds) == ([], [], []):
                continue
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    payload = json.loads(notify.payload)
                except Exception:
                    logger.warning("Received non-JSON payload from events channel: %s", notify.payload)
                    continue
                self.process_event(payload)

    def process_event(self, payload: dict) -> dict:
        start = time.perf_counter()
        event_name = payload.get("event", "unknown")
        event_id = payload.get("event_id")
        if event_id is not None:
            event_id = str(event_id)
            if event_id in self._seen_event_ids:
                self.metrics.deduplicated_events += 1
                return {"status": "deduplicated", "event_id": event_id}
            self._seen_event_ids.add(event_id)
        self.metrics.last_event = event_name

        try:
            result = self._dispatch_event(event_name, payload)
            self.metrics.processed_events += 1
            return {"status": "ok", "event": event_name, "result": result}
        except Exception as exc:
            self.metrics.failed_events += 1
            logger.exception("Event handling failed for %s", event_name)
            return {"status": "error", "event": event_name, "error": str(exc)}
        finally:
            self.metrics.last_latency_ms = int((time.perf_counter() - start) * 1000)

    def _dispatch_event(self, event_name: str, payload: dict) -> dict:
        strategy_id = payload.get("strategy_id")

        if event_name == "spec.created":
            result = self.ml_engineer.run_implementation()
            return {"model_files": len(result)}

        if event_name == "model.validated":
            return self.strategy_engineer.run_for_strategy(
                strategy_id=strategy_id,
                model_id=payload.get("model_id"),
            )

        if event_name == "backtest.completed":
            statuses = self.validation_agent.run_validation()
            return {"statuses": statuses}

        if event_name == "validation.approved":
            self.db.update_strategy_status(strategy_id, "execution.pending")
            deploy_res = self._deploy_paper_trading(strategy_id)
            return {"deployment": deploy_res}

        if event_name in {"validation.warning", "validation.rejected"}:
            retry = self.db.increment_strategy_retry(strategy_id)
            self.metrics.total_retries += 1
            if retry["reached_max"]:
                self.db.update_strategy_status(strategy_id, "human_review")
                return {"status": "human_review", "retry_count": retry["retry_count"]}
            self.db.update_strategy_status(strategy_id, "backtest_pending")
            return {"status": "retry", "retry_count": retry["retry_count"]}

        if event_name == "validation.max_retries":
            self.db.update_strategy_status(strategy_id, "human_review")
            return {"status": "human_review"}

        return {"status": "ignored", "event": event_name}

    def _deploy_paper_trading(self, strategy_id: str) -> dict:
        """Deploy approved strategy in paper mode and persist state transitions."""
        self.db.update_strategy_status(strategy_id, "execution.pending")

        try:
            self.trading_executor.run_trading_loop(
                symbols=["AAPL"],
                interval_seconds=1,
                max_iterations=1,
            )
            self.db.update_strategy_status(strategy_id, "deployed")
            return {"status": "deployed", "mode": "paper"}
        except Exception as exc:
            self.db.update_strategy_status(strategy_id, "human_review")
            return {"status": "deployment_failed", "error": str(exc)}

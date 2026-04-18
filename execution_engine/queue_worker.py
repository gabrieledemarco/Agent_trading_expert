"""QueueWorker — optional Redis consumer for async backtest jobs.

Requires:
  - Redis running (REDIS_URL env var, default redis://localhost:6379/0)
  - ENABLE_QUEUE_WORKER=true

When disabled (default), all backtests run synchronously via ExecutionClient.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

ENABLE_QUEUE_WORKER = os.getenv("ENABLE_QUEUE_WORKER", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BACKTEST_QUEUE = "backtest_jobs"
RESULT_PREFIX = "backtest_result:"
JOB_TIMEOUT = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))


class QueueWorker:
    """Polls a Redis list for backtest jobs and executes them.

    Job schema (JSON pushed to BACKTEST_QUEUE):
    {
        "job_id": str,
        "strategy_id": str,
        "strategy_code": str,
        "parameters": dict,
        "dataset": {"symbols": list, "start": str, "end": str},
        "backtest_config": {"initial_capital": float, ...}
    }

    Result stored at RESULT_PREFIX + job_id as JSON.
    """

    def __init__(self):
        self._redis = None
        self._running = False
        self._computation = None

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the blocking poll loop. Handles SIGINT/SIGTERM gracefully."""
        if not ENABLE_QUEUE_WORKER:
            logger.info("QueueWorker disabled (ENABLE_QUEUE_WORKER=false)")
            return

        self._redis = self._connect_redis()
        if self._redis is None:
            logger.error("Cannot start QueueWorker: Redis unavailable")
            return

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self._running = True
        logger.info("QueueWorker started — listening on queue '%s'", BACKTEST_QUEUE)

        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                logger.error("Poll error: %s", e)
                time.sleep(1)

    def enqueue(self, job: dict) -> str:
        """Push a job onto the Redis queue. Returns job_id."""
        import uuid
        job_id = job.get("job_id") or str(uuid.uuid4())
        job["job_id"] = job_id

        redis = self._connect_redis()
        if redis is None:
            raise RuntimeError("Redis unavailable — cannot enqueue job")

        redis.rpush(BACKTEST_QUEUE, json.dumps(job))
        logger.info("Enqueued job %s (strategy=%s)", job_id, job.get("strategy_id"))
        return job_id

    def get_result(self, job_id: str, timeout: int = JOB_TIMEOUT) -> Optional[dict]:
        """Poll for a result by job_id. Returns None on timeout."""
        redis = self._connect_redis()
        if redis is None:
            return None

        key = RESULT_PREFIX + job_id
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = redis.get(key)
            if raw:
                return json.loads(raw)
            time.sleep(0.5)
        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _poll_once(self) -> None:
        """Block-pop one job and process it."""
        item = self._redis.blpop(BACKTEST_QUEUE, timeout=2)
        if item is None:
            return

        _, raw = item
        try:
            job = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Invalid job JSON: %s", e)
            return

        job_id = job.get("job_id", "unknown")
        logger.info("Processing job %s", job_id)

        try:
            result = self._execute_job(job)
            result["job_id"] = job_id
            result["status"] = "completed"
        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e)
            result = {"job_id": job_id, "status": "failed", "error": str(e)}

        self._redis.setex(RESULT_PREFIX + job_id, JOB_TIMEOUT * 2, json.dumps(result))
        logger.info("Job %s → %s", job_id, result["status"])

    def _execute_job(self, job: dict) -> dict:
        """Run the backtest via ComputationService."""
        from execution_engine.computation_service import ComputationService
        if self._computation is None:
            self._computation = ComputationService()

        dataset = job.get("dataset", {})
        config = job.get("backtest_config", {})

        result = self._computation.run_strategy_code(
            strategy_code=job.get("strategy_code", "def run(data,params): return {'signals':['hold']*len(data['prices']),'position_sizes':[0.0]*len(data['prices'])}"),
            parameters=job.get("parameters", {}),
            symbols=dataset.get("symbols", ["AAPL"]),
            start=dataset.get("start", "2022-01-01"),
            end=dataset.get("end", "2023-12-31"),
            initial_capital=config.get("initial_capital", 10_000.0),
            transaction_cost=config.get("transaction_cost", 0.001),
            seed=config.get("seed", 42),
        )
        result["job_id"] = job.get("job_id")
        result["strategy_id"] = job.get("strategy_id", result.get("strategy_id"))
        return result

    def _compile_strategy(self, code: str):
        """Compile and return the run() function from strategy code."""
        namespace: dict[str, Any] = {}
        exec(compile(code, "<strategy>", "exec"), namespace)  # noqa: S102
        run_fn = namespace.get("run")
        if run_fn is None:
            raise ValueError("Strategy code must define a 'run' function")
        return run_fn

    def _connect_redis(self):
        """Lazy-connect to Redis. Returns client or None."""
        if self._redis is not None:
            return self._redis
        try:
            import redis as redis_lib
            client = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
            client.ping()
            return client
        except Exception as e:
            logger.warning("Redis connection failed (%s): %s", REDIS_URL, e)
            return None

    def _shutdown(self, signum, frame) -> None:
        logger.info("QueueWorker shutting down (signal %d)…", signum)
        self._running = False


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    worker = QueueWorker()
    worker.start()

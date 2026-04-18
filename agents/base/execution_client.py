"""ExecutionClient — HTTP client for the Execution Engine (port 8001).

Agents call this instead of computing numerics directly.
When engine_url is None, falls back to ComputationService locally.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionClient:
    """Thin HTTP wrapper around the Execution Engine API.

    Falls back transparently to local ComputationService when
    the engine URL is not configured (development mode).
    """

    def __init__(self, engine_url: Optional[str] = None):
        import os
        self.engine_url = engine_url or os.getenv("EXECUTION_ENGINE_URL")
        self._local = None  # lazy-loaded ComputationService

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze_risk_return(self, model_name: str) -> dict:
        if self.engine_url:
            return self._remote_risk_return(model_name)
        return self._local_svc().analyze_risk_return_profile(model_name)

    def evaluate_robustness(self, model_name: str) -> dict:
        if self.engine_url:
            return self._remote_robustness(model_name)
        return self._local_svc().evaluate_statistical_robustness(model_name)

    def execute_backtest(self, request: dict) -> dict:
        """Submit a full backtest request to the Execution Engine."""
        if self.engine_url:
            return self._post("/execute", request)
        # Local fallback: return computation-only result
        model_name = request.get("strategy_id", "unknown")
        return {
            "execution_id": f"local-{model_name[:8]}",
            "strategy_id": model_name,
            "status": "completed",
            "risk_return": self._local_svc().analyze_risk_return_profile(model_name),
            "robustness": self._local_svc().evaluate_statistical_robustness(model_name),
            "backtest_config": request.get("backtest_config", {}),
        }

    def health(self) -> dict:
        if self.engine_url:
            try:
                import urllib.request, json
                with urllib.request.urlopen(f"{self.engine_url}/health", timeout=3) as r:
                    return json.loads(r.read())
            except Exception as e:
                return {"status": "unreachable", "error": str(e)}
        return {"status": "local", "engine_url": None}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _local_svc(self):
        if self._local is None:
            from execution_engine.computation_service import ComputationService
            self._local = ComputationService()
        return self._local

    def _post(self, path: str, payload: dict) -> dict:
        import urllib.request, urllib.error, json
        url = f"{self.engine_url}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            logger.error("ExecutionEngine %s %s → %s: %s", "POST", path, e.code, body)
            raise RuntimeError(f"Execution Engine error {e.code}: {body}") from e
        except Exception as e:
            logger.error("ExecutionEngine unreachable: %s", e)
            raise

    def _remote_risk_return(self, model_name: str) -> dict:
        result = self.execute_backtest({
            "strategy_id": model_name,
            "strategy_code": "# placeholder",
            "parameters": {},
            "dataset": {"symbols": ["AAPL"], "start": "2023-01-01", "end": "2023-12-31"},
        })
        return result.get("risk_return", {})

    def _remote_robustness(self, model_name: str) -> dict:
        result = self.execute_backtest({
            "strategy_id": model_name,
            "strategy_code": "# placeholder",
            "parameters": {},
            "dataset": {"symbols": ["AAPL"], "start": "2023-01-01", "end": "2023-12-31"},
        })
        return result.get("robustness", {})

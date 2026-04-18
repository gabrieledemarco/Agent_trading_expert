"""Execution Engine — FastAPI stub (port 8001).

Agents submit an ExecutionRequest; the engine runs the backtest
inside a RestrictedPython sandbox and returns results.

Current state: stub that validates the request and returns a
deterministic result via ComputationService (no live sandbox yet).
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data.contracts.models import ExecutionRequest
from execution_engine.computation_service import ComputationService

app = FastAPI(
    title="Execution Engine",
    description="Numerical computation layer for the Agent Trading Expert system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_computation = ComputationService()
_STARTED_AT  = datetime.utcnow().isoformat()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "started_at": _STARTED_AT, "version": "0.1.0"}


# ── Execute ───────────────────────────────────────────────────────────────────

class ExecutionResult(BaseModel):
    execution_id:    str
    strategy_id:     str
    status:          str
    started_at:      str
    completed_at:    str
    risk_return:     Dict[str, Any]
    robustness:      Dict[str, Any]
    backtest_config: Dict[str, Any]


@app.post("/execute", response_model=ExecutionResult)
def execute(request: ExecutionRequest) -> ExecutionResult:
    """Run a backtest for the submitted strategy.

    Stub behaviour: delegates to ComputationService using strategy_id as
    the model name seed. A full sandbox runner will replace this later.
    """
    started = datetime.utcnow().isoformat()

    # Validate the code field is non-empty
    if not request.strategy_code.strip():
        raise HTTPException(status_code=422, detail="strategy_code must not be empty")

    # Deterministic execution_id from strategy_id + parameters hash
    params_hash = hashlib.sha256(
        (request.strategy_id + str(sorted(request.parameters.items()))).encode()
    ).hexdigest()[:12]
    execution_id = f"exec-{params_hash}"

    risk_return = _computation.analyze_risk_return_profile(request.strategy_id)
    robustness  = _computation.evaluate_statistical_robustness(request.strategy_id)

    completed = datetime.utcnow().isoformat()

    return ExecutionResult(
        execution_id=execution_id,
        strategy_id=request.strategy_id,
        status="completed",
        started_at=started,
        completed_at=completed,
        risk_return=risk_return,
        robustness=robustness,
        backtest_config=request.backtest_config.model_dump(),
    )


# ── Strategies list (mirror of validated dir) ─────────────────────────────────

@app.get("/strategies")
def list_strategies() -> dict:
    """Return all validated strategies with their risk/return summary."""
    import json
    from pathlib import Path
    from configs.paths import Paths

    strategies = []
    if Paths.VALIDATED_DIR.exists():
        for f in Paths.VALIDATED_DIR.glob("*_validation.json"):
            try:
                data = json.loads(f.read_text())
                strategies.append({
                    "model_name":         data.get("model_name"),
                    "validation_status":  data.get("validation_status"),
                    "risk_score":         data.get("risk_return_profile", {}).get("risk_score"),
                    "sharpe_ratio":       data.get("risk_return_profile", {}).get("sharpe_ratio"),
                    "robustness_score":   data.get("statistical_robustness", {}).get("robustness_score"),
                })
            except Exception:
                pass

    return {"count": len(strategies), "strategies": strategies}


# ── Dashboard summary ─────────────────────────────────────────────────────────

@app.get("/dashboard/summary")
def dashboard_summary() -> dict:
    """Lightweight summary for the dashboard frontend."""
    from data.storage.data_manager import DataStorageManager
    mgr = DataStorageManager()
    return mgr.get_dashboard_summary()

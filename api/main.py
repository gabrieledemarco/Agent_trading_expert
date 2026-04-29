"""Trading Agents API — data served exclusively from Neon PostgreSQL."""

import asyncio
import json
import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel

from configs.paths import Paths
from data.providers.alpaca_stream import AlpacaStream
from data.providers.alpaca_client import get_latest_quote, get_account

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB singleton — created once at startup, shared across all requests.
_db = None
_event_orchestrator = None

# Alpaca real-time price cache (populated by WebSocket stream at startup)
_SSE_SYMBOLS = ["AAPL", "MSFT", "GOOG", "NVDA"]
_alpaca_stream = AlpacaStream(_SSE_SYMBOLS)


def is_v2_event_driven_enabled() -> bool:
    return str(os.getenv("V2_EVENT_DRIVEN", "false")).lower() in {"1", "true", "yes", "on"}


def _env_flag(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).lower() in {"1", "true", "yes", "on"}


def is_background_jobs_enabled() -> bool:
    """Global switch for background loops (off-by-default in deploys)."""
    return _env_flag("ENABLE_BACKGROUND_LOOPS", "false")


def can_connect_db() -> bool:
    """Best-effort DB readiness check used to avoid noisy failing loops at startup."""
    try:
        get_db().get_dashboard_summary()
        return True
    except Exception as e:
        logger.warning("Skipping background jobs: database is not reachable (%s)", e)
        return False


def get_event_orchestrator():
    global _event_orchestrator
    if _event_orchestrator is None:
        from agents.orchestration import EventDrivenOrchestrator
        _event_orchestrator = EventDrivenOrchestrator(enable_v2=is_v2_event_driven_enabled())
    return _event_orchestrator

def get_db():
    global _db
    if _db is None:
        from data.storage.data_manager import DataStorageManager
        _db = DataStorageManager()
    return _db


def _run_pipeline_if_due():
    """Avvia il pipeline chain se ResearchAgent non ha girato negli ultimi 7 giorni."""
    if not _env_flag("ENABLE_PIPELINE_AUTORUN", "false"):
        logger.info("Pipeline autorun disabled (ENABLE_PIPELINE_AUTORUN=false)")
        return
    try:
        from agents.research.research_agent import ResearchAgent
        if not ResearchAgent().should_run_now(min_interval_days=7):
            logger.info("Pipeline: last run recent, skipping auto-run")
            return
        logger.info("Pipeline: auto-starting weekly chain")
        from agents.orchestration.pipeline_orchestrator import PipelineOrchestrator
        PipelineOrchestrator().run_pipeline_chain()
    except Exception as e:
        logger.warning(f"Auto pipeline run failed: {e}")


def _run_monitoring_loop():
    """Monitoring in background thread continuo (ogni ora)."""
    if not _env_flag("ENABLE_MONITORING_LOOP", "false"):
        logger.info("Monitoring loop disabled (ENABLE_MONITORING_LOOP=false)")
        return
    import time
    while True:
        try:
            from agents.monitoring.monitoring_agent import MonitoringAgent
            MonitoringAgent().run()
        except Exception as e:
            logger.warning(f"Monitoring cycle failed: {e}")
        time.sleep(3600)


def _run_event_listener_loop():
    """Event listener for V2 LISTEN/NOTIFY orchestration."""
    try:
        orchestrator = get_event_orchestrator()
        orchestrator.listen_forever()
    except Exception as e:
        logger.warning(f"Event listener loop failed: {e}")


def _run_trading_loop():
    """Trading in background thread continuo (ogni 5 minuti, paper trading)."""
    if not _env_flag("ENABLE_TRADING_LOOP", "false"):
        logger.info("Trading loop disabled (ENABLE_TRADING_LOOP=false)")
        return
    import time
    while True:
        try:
            from agents.trading.trading_executor import TradingExecutorAgent
            agent = TradingExecutorAgent(paper_trading=True)
            agent.run_trading_loop(
                symbols=["AAPL", "MSFT", "GOOG"],
                interval_seconds=0,  # outer loop already sleeps 300s; avoid double wait
                max_iterations=1,
            )
        except Exception as e:
            logger.warning(f"Trading cycle failed: {e}")
        time.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()

    # Always start Alpaca WebSocket stream (independent of background loops flag).
    # Silently skips if ALPACA_API_KEY is absent.
    await _alpaca_stream.start()

    if not is_background_jobs_enabled():
        logger.info("Background jobs disabled (ENABLE_BACKGROUND_LOOPS=false)")
        yield
        await _alpaca_stream.stop()
        return

    if not can_connect_db():
        logger.warning("Background jobs not started: no DB connectivity at startup")
        yield
        return

    if is_v2_event_driven_enabled():
        logger.info("Starting API in V2 event-driven mode")
        loop.run_in_executor(None, _run_event_listener_loop)
    else:
        logger.info("Starting API in legacy scheduler mode")
        # Thread 1: pipeline chain settimanale (non-blocking)
        loop.run_in_executor(None, _run_pipeline_if_due)

        # Thread 2: monitoring loop ogni ora
        loop.run_in_executor(None, _run_monitoring_loop)

        # Thread 3: trading loop ogni 5 minuti
        loop.run_in_executor(None, _run_trading_loop)

    yield
    await _alpaca_stream.stop()


app = FastAPI(
    title="Trading Agents API",
    description="API for the multi-agent trading system",
    version="0.1.0",
    lifespan=lifespan,
)

_DASHBOARDS_DIR = str(Paths.DASHBOARDS_DIR)
if os.path.isdir(_DASHBOARDS_DIR):
    app.mount("/dashboards", StaticFiles(directory=_DASHBOARDS_DIR, html=True), name="dashboards")
else:
    logger.warning("Dashboards directory not found at %s — static files disabled", _DASHBOARDS_DIR)


class TradeRequest(BaseModel):
    """Trade request model."""
    symbol: str
    action: str
    quantity: float


class ResearchRequest(BaseModel):
    """Research request model."""
    query: str = "trading OR quantitative finance"
    max_results: int = 10


class ModelInfo(BaseModel):
    """Model information."""
    name: str
    type: str
    status: str


class StrategyCreateRequest(BaseModel):
    """Internal V2 strategy creation payload."""
    name: str
    spec: dict
    status: str = "draft"


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboards/")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0"}


@app.get("/ping")
async def ping():
    """Keep-alive endpoint — used by UptimeRobot every 14 min to prevent Render spin-down.

    Configure UptimeRobot: Monitor type=HTTP(s), URL=https://<app>.onrender.com/ping,
    interval=14 minutes. Free plan supports up to 50 monitors.
    """
    return {"pong": True}


@app.post("/research")
async def run_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Trigger research agent — runs in background, saves results to Neon."""
    def _run():
        from agents.research.research_agent import ResearchAgent
        agent = ResearchAgent()
        # Override defaults if caller supplied a custom query
        if request.query != "trading OR quantitative finance":
            papers = agent.search_arxiv(search_query=request.query, max_results=request.max_results)
            relevant = agent.filter_relevant_papers(papers)
            saved = 0
            for paper in relevant:
                try:
                    agent.db.save_research({
                        "id":              str(paper.get("id", "")),
                        "title":           str(paper.get("title", "")),
                        "authors":         str(paper.get("authors", [])),
                        "published":       str(paper.get("published", "")),
                        "categories":      str(paper.get("categories", [])),
                        "abstract":        str(paper.get("summary", "")),
                        "pdf_url":         str(paper.get("pdf_url", "")),
                        "relevance_score": float(paper.get("relevance_score", 0)),
                    })
                    saved += 1
                except Exception:
                    pass
            return {"relevant": len(relevant), "saved": saved}
        else:
            return agent.run()

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "Research agent started in background"}


@app.post("/api/agents/research/run")
async def trigger_research_now(background_tasks: BackgroundTasks):
    """Manually trigger the research agent regardless of last-run date."""
    def _run():
        from agents.research.research_agent import ResearchAgent
        ResearchAgent().run()

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "ResearchAgent triggered — results will appear in /research GET"}


@app.get("/models")
async def list_models():
    """List all models from the database."""
    try:
        rows = get_db().get_models()
        return {"models": rows, "count": len(rows)}
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        return {"models": [], "count": 0}


@app.post("/trade/execute")
async def execute_trade(request: TradeRequest):
    """Execute a trade."""
    try:
        from agents.trading.trading_executor import TradingExecutorAgent
        
        agent = TradingExecutorAgent(paper_trading=True)
        
        # Get current price
        data = agent.fetch_realtime_data(request.symbol)
        if not data:
            raise HTTPException(status_code=400, detail="Could not fetch price")
        
        price = data.get("latest_price", 0)
        trade = agent.execute_trade(
            symbol=request.symbol,
            action=request.action,
            quantity=request.quantity,
            price=price
        )
        
        return {
            "status": "executed",
            "trade": {
                "symbol": trade.symbol,
                "action": trade.action,
                "quantity": trade.quantity,
                "price": trade.price
            }
        }
    except Exception as e:
        logger.error(f"Error executing trade: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/performance")
async def get_performance():
    """Get current performance."""
    try:
        from agents.trading.trading_executor import TradingExecutorAgent
        
        agent = TradingExecutorAgent()
        summary = agent.get_performance_summary()
        
        return summary
    except Exception as e:
        logger.error(f"Error getting performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard endpoints
@app.get("/dashboard/summary")
async def get_dashboard_summary():
    """Get dashboard summary data from Neon PostgreSQL."""
    try:
        return get_db().get_dashboard_summary()
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/dashboard/summary")
async def get_api_dashboard_summary():
    """Aggregated global summary for all dashboard pages."""
    from datetime import timezone

    def _safe(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            logger.warning("api_dashboard_summary: %s", exc)
            return None

    try:
        db = get_db()
    except Exception as exc:
        logger.warning("api_dashboard_summary: DB unavailable — %s", exc)
        db = None

    if db is None:
        base = {}; risk = []; strats = []; agents = []; trades = []
    else:
        base      = _safe(db.get_dashboard_summary) or {}
        risk      = _safe(db.get_performance, days=30) or []
        strats    = _safe(db.get_strategies_v2, limit=500) or []
        agents    = _safe(db.get_agent_status) or []
        trades    = _safe(db.get_trades, limit=1) or []

    # Portfolio KPIs
    latest = risk[0] if risk else {}
    equity    = float(latest.get("equity") or 0)
    t_return  = float(latest.get("total_return") or 0)
    sharpe    = float(latest.get("sharpe_ratio") or 0)
    max_dd    = float(latest.get("max_drawdown") or 0)

    # Pipeline by_status
    by_status: dict = {}
    for s in strats:
        st = str(s.get("status", "draft"))
        by_status[st] = by_status.get(st, 0) + 1

    # Agents
    active = sum(1 for a in agents if str(a.get("status", "")).lower() == "running")

    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "portfolio": {
            "equity":       equity,
            "total_return": t_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
        },
        "strategies": {
            "total":    len(strats),
            "approved": by_status.get("approved", 0),
            "deployed": by_status.get("deployed", 0),
            "by_status": by_status,
        },
        "models": {
            "total":    int(base.get("models_implemented", 0)),
            "approved": int(base.get("models_validated", 0)),
        },
        "research": {
            "papers": int(base.get("research_papers", 0)),
            "specs":  int(base.get("specs_created", 0)),
        },
        "agents": {
            "total":  len(agents),
            "active": active,
            "idle":   max(0, len(agents) - active),
        },
        "trades": {
            "total": int(base.get("total_trades", 0)),
        },
    }


@app.get("/dashboard/agent-activity")
async def get_agent_activity(limit: int = 20):
    """Get agent activity logs from Neon PostgreSQL."""
    try:
        logs = get_db().get_agent_logs(limit=limit)
        return {"activities": logs}
    except Exception as e:
        logger.error(f"Error getting agent activity: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/dashboard/strategy/{strategy_name}")
async def get_strategy_performance(strategy_name: str):
    """Get performance for a specific strategy from Neon PostgreSQL."""
    try:
        performance = get_db().get_performance(model_name=strategy_name, days=30)
        if not performance:
            raise HTTPException(status_code=404, detail=f"No performance data for '{strategy_name}'")
        latest = performance[0]
        return {
            "strategy": strategy_name,
            "equity":       latest.get("equity", 0),
            "total_return": latest.get("total_return", 0),
            "sharpe_ratio": latest.get("sharpe_ratio", 0),
            "max_drawdown": latest.get("max_drawdown", 0),
            "win_rate":     latest.get("win_rate", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/strategies")
async def list_strategies():
    """List all strategies (models + validation) from Neon PostgreSQL."""
    try:
        return {"strategies": get_db().get_strategies()}
    except Exception as e:
        logger.error(f"Error listing strategies: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.post("/internal/v2/strategies")
async def create_strategy_v2(request: StrategyCreateRequest):
    """Internal API: create strategy record in V2 table."""
    try:
        strategy_id = get_db().save_strategy(
            {"name": request.name, "spec": request.spec, "status": request.status}
        )
        return {"status": "created", "strategy_id": str(strategy_id)}
    except Exception as e:
        logger.error(f"Error creating V2 strategy: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/internal/v2/strategies")
async def list_strategies_v2(status: Optional[str] = None, limit: int = 100):
    """Internal API: list strategies from V2 table."""
    try:
        rows = get_db().get_strategies_v2(status=status, limit=limit)
        return {"count": len(rows), "strategies": rows}
    except Exception as e:
        logger.error(f"Error reading V2 strategies: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")




@app.get("/internal/v2/orchestration/metrics")
async def get_v2_orchestration_metrics():
    """Expose event-driven orchestration metrics (latency/errors/retries)."""
    if not is_v2_event_driven_enabled():
        return {"enabled": False, "metrics": {}}
    orchestrator = get_event_orchestrator()
    return {"enabled": True, "metrics": orchestrator.snapshot_metrics()}


@app.get("/api/pipeline/overview")
async def pipeline_overview():
    """Aggregated pipeline snapshot — per-stage counts + recent agent events."""
    db = get_db()

    # Query each counter independently so a missing table never blocks the whole response
    def _safe_count(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("pipeline_overview: count failed — %s", exc)
            return None

    summary   = _safe_count(db.get_dashboard_summary)
    strategies = _safe_count(db.get_strategies_v2, limit=500) or []
    logs       = _safe_count(db.get_agent_logs, limit=20) or []

    # Stage counts from dashboard_summary (legacy pipeline: research→specs→models→validated)
    stage_counts: dict = {}
    if summary:
        stage_counts = {
            "research":  summary.get("research_papers", 0),
            "specs":     summary.get("specs_created", 0),
            "models":    summary.get("models_implemented", 0),
            "validated": summary.get("models_validated", 0),
        }

    # V2 strategy counts by status (draft/approved/human_review/…)
    by_status: dict[str, int] = {}
    for s in strategies:
        st = str(s.get("status", "draft"))
        by_status[st] = by_status.get(st, 0) + 1

    recent_events = [
        {
            "timestamp": row.get("timestamp"),
            "agent":     row.get("agent_name"),
            "status":    row.get("status"),
            "message":   row.get("message"),
        }
        for row in logs
    ]

    return {
        "generated_at":       datetime.utcnow().isoformat(),
        "counts":             stage_counts or by_status,
        "by_status":          by_status,
        "total_strategies":   len(strategies),
        "human_review_count": by_status.get("human_review", 0),
        "recent_events":      recent_events,
    }


@app.get("/api/pipeline/kanban")
async def pipeline_kanban(limit: int = 300):
    """Strategies grouped by lifecycle status for kanban dashboards."""
    try:
        strategies = get_db().get_strategies_v2(limit=limit)
    except Exception as e:
        logger.error(f"Error reading pipeline kanban: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    grouped: dict[str, list[dict]] = {}
    for strategy in strategies:
        status = str(strategy.get("status", "draft"))
        grouped.setdefault(status, []).append(
            {
                "id": strategy.get("id"),
                "name": strategy.get("name"),
                "updated_at": strategy.get("updated_at"),
                "retry_count": strategy.get("retry_count", 0),
            }
        )
    return {"columns": grouped, "count": len(strategies)}


@app.get("/api/strategies/{strategy_id}/backtest")
async def strategy_backtest(strategy_id: str):
    """Backtest reports for a specific strategy."""
    try:
        reports = get_db().get_backtest_reports(strategy_id=strategy_id, limit=50)
    except Exception as e:
        logger.error(f"Error reading backtests for {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"strategy_id": strategy_id, "reports": reports, "count": len(reports)}


_SSE_PRICE_INTERVAL = 5   # emit a price event every N heartbeats (1 heartbeat = 2s → every 10s)

@app.get("/api/events/stream")
async def events_stream():
    """SSE stream: heartbeat every 2s + agent log + price tick every 10s.

    Price source priority:
    1. AlpacaStream WebSocket cache (real-time, ~100ms latency)
    2. Alpaca REST fallback (if WebSocket not yet connected)
    3. yfinance fallback (if Alpaca credentials absent)
    """
    async def event_generator():
        tick = 0
        while True:
            ts = datetime.utcnow().isoformat()
            # Agent activity event
            try:
                logs = get_db().get_agent_logs(limit=1)
                latest = logs[0] if logs else {}
            except Exception:
                latest = {}
            yield f"data: {json.dumps({'type':'agent','timestamp':ts,'event':latest.get('status','heartbeat'),'agent':latest.get('agent_name'),'message':latest.get('message')})}\n\n"

            # Price event — one symbol per interval, cycling through all symbols
            if tick % _SSE_PRICE_INTERVAL == 0:
                sym = _SSE_SYMBOLS[(tick // _SSE_PRICE_INTERVAL) % len(_SSE_SYMBOLS)]
                price = _alpaca_stream.get(sym)   # 1. WebSocket cache
                if price is None:
                    price = get_latest_quote(sym)  # 2. Alpaca REST
                if price is None:
                    try:                           # 3. yfinance fallback
                        import yfinance as yf
                        data = yf.Ticker(sym).history(period="1d", interval="1m")
                        price = float(data["Close"].iloc[-1]) if not data.empty else None
                    except Exception:
                        price = None
                if price is not None:
                    yield f"data: {json.dumps({'type':'price','timestamp':ts,'symbol':sym,'price':round(price,2)})}\n\n"

            tick += 1
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/price")
async def get_price(symbol: str):
    """Return latest price for symbol. Source: Alpaca WebSocket cache → REST → yfinance."""
    sym = symbol.upper()
    price = _alpaca_stream.get(sym) or get_latest_quote(sym)
    if price is None:
        try:
            import yfinance as yf
            data = yf.Ticker(sym).history(period="1d", interval="1m")
            price = float(data["Close"].iloc[-1]) if not data.empty else None
        except Exception:
            price = None
    if price is None:
        raise HTTPException(status_code=404, detail=f"No price data for {sym}")
    source = "alpaca_ws" if _alpaca_stream.get(sym) else ("alpaca_rest" if get_latest_quote(sym) else "yfinance")
    return {"symbol": sym, "price": round(price, 2), "source": source}


@app.get("/api/alpaca/account")
async def get_alpaca_account():
    """Return Alpaca paper account snapshot: equity, cash, buying_power."""
    data = get_account()
    if not data:
        raise HTTPException(status_code=503, detail="Alpaca credentials not configured or unavailable")
    return data


@app.get("/research")
async def list_research(limit: int = 50):
    """List research papers from Neon PostgreSQL."""
    try:
        papers = get_db().get_research(limit=limit)
        return {"papers": papers, "count": len(papers)}
    except Exception as e:
        logger.error(f"Error listing research: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/equity-curve")
async def get_equity_curve(period: str = "1M", model_name: Optional[str] = None):
    """Return equity curve time-series for Chart.js dashboards.
    period: 1D | 1W | 1M | 3M | 6M | 1Y
    """
    period_days = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = period_days.get(period.upper(), 30)
    try:
        rows = get_db().get_performance(model_name=model_name, days=days)
    except Exception as e:
        logger.error(f"Error getting equity curve: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    if not rows:
        return {"labels": [], "equity": [], "benchmark": [], "period": period}

    rows = list(reversed(rows))  # ASC per il grafico
    labels   = [str(r.get("timestamp", ""))[:10] for r in rows]
    equity   = [float(r.get("equity", 0) or 0) for r in rows]
    benchmark = [round(e * 0.98, 2) for e in equity]
    returns_pct = [round(float(r.get("total_return", 0) or 0) * 100, 4) for r in rows]

    return {
        "labels": labels,
        "equity": equity,
        "benchmark": benchmark,
        "total_return_pct": returns_pct,
        "period": period,
        "count": len(rows),
    }


@app.get("/api/backtest/results")
async def get_backtest_results():
    """Return model validation results.

    Primary: Neon DB (strategies table).
    Fallback: models/validated/*.json local files (always present after pipeline run).
    """
    import json as _json
    results = []
    try:
        strategies = get_db().get_strategies()
        results = [
            {
                "name":            s.get("name"),
                "model_type":      s.get("model_type"),
                "status":          s.get("status"),
                "validation_date": s.get("validation_date"),
                "risk_level":      s.get("risk_level") or "UNKNOWN",
                "sharpe_ratio":    float(s.get("sharpe_ratio") or 0),
                "robustness":      s.get("robustness") or "UNKNOWN",
            }
            for s in strategies
        ]
    except Exception:
        pass

    if not results:
        # Fallback: read local validation JSON files
        for vf in sorted(Paths.VALIDATED_DIR.glob("*_validation.json")):
            try:
                d = _json.loads(vf.read_text())
                rr = d.get("risk_return_profile", {})
                rob = d.get("statistical_robustness", {})
                results.append({
                    "name":         d.get("model_name", vf.stem),
                    "model_type":   d.get("model_type", "unknown"),
                    "status":       d.get("validation_status", "UNKNOWN"),
                    "validation_date": d.get("validation_timestamp", ""),
                    "risk_level":   rr.get("risk_score", "UNKNOWN"),
                    "sharpe_ratio": float(rr.get("sharpe_ratio") or 0),
                    "robustness":   rob.get("robustness_score", "UNKNOWN"),
                })
            except Exception:
                pass

    return {"results": results, "count": len(results)}


@app.get("/api/backtest/summary")
async def get_backtest_summary():
    """Aggregate stats for the backtest dashboard header cards.

    Returns: total, approved, rejected, best_sharpe, avg_win_rate.
    """
    import json as _json
    rows = (await get_backtest_results())["results"]
    approved = [r for r in rows if r.get("status") == "APPROVED"]
    rejected  = [r for r in rows if r.get("status") == "REJECTED"]
    sharpes   = [r["sharpe_ratio"] for r in approved]
    return {
        "total":      len(rows),
        "approved":   len(approved),
        "rejected":   len(rejected),
        "best_sharpe": round(max(sharpes), 3) if sharpes else 0.0,
    }


@app.get("/api/risk/summary")
async def get_risk_summary():
    """Return portfolio risk metrics computed from Neon data."""
    import math
    try:
        perf_rows  = get_db().get_performance(days=30)
        trade_rows = get_db().get_trades(limit=200)
    except Exception as e:
        logger.error(f"Error getting risk summary: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    if not perf_rows:
        return {"var_95": 0, "cvar_95": 0, "max_drawdown_pct": 0,
                "volatility_annual_pct": 0, "sharpe_ratio": 0,
                "current_equity": 0, "total_trades": len(trade_rows)}

    equities = [float(r.get("equity", 0) or 0) for r in reversed(perf_rows)]
    daily_returns = [
        (equities[i] - equities[i-1]) / equities[i-1]
        for i in range(1, len(equities)) if equities[i-1] > 0
    ]

    if daily_returns:
        n = len(daily_returns)
        mean_r = sum(daily_returns) / n
        vol_daily = math.sqrt(sum((r - mean_r) ** 2 for r in daily_returns) / n)
        vol_annual = vol_daily * math.sqrt(252) * 100
        sorted_r = sorted(daily_returns)
        idx_5 = max(0, int(n * 0.05))
        last_eq = equities[-1]
        var_95  = round(abs(sorted_r[idx_5]) * last_eq, 2)
        cvar_95 = round(abs(sum(sorted_r[:idx_5+1]) / max(1, idx_5+1)) * last_eq, 2)
    else:
        var_95 = cvar_95 = vol_annual = 0.0

    latest = perf_rows[0]
    return {
        "current_equity":        float(latest.get("equity") or 0),
        "var_95":                var_95,
        "cvar_95":               cvar_95,
        "max_drawdown_pct":      round(float(latest.get("max_drawdown") or 0) * 100, 2),
        "volatility_annual_pct": round(vol_annual, 2),
        "sharpe_ratio":          round(float(latest.get("sharpe_ratio") or 0), 2),
        "total_trades":          len(trade_rows),
        "period_days":           len(perf_rows),
    }


@app.get("/api/agents/status")
async def get_agents_status():
    """Stato corrente di tutti gli agenti (ultimo log per ciascuno, con duration/records)."""
    # Keys pre-normalised (lowercase, no spaces, no underscores) so the lookup
    # works regardless of how the name was stored (ml_engineer, MLEngineerAgent…)
    _CANONICAL_RAW = {
        "research":             "ResearchAgent",
        "researchagent":        "ResearchAgent",
        "spec":                 "SpecAgent",
        "specagent":            "SpecAgent",
        "mlengineer":           "MLEngineerAgent",
        "mlengineeer":          "MLEngineerAgent",
        "mlengineeragent":      "MLEngineerAgent",
        "validation":           "ValidationAgent",
        "validationagent":      "ValidationAgent",
        "improvement":          "ImprovementAgent",
        "improvementagent":     "ImprovementAgent",
        "trading":              "TradingExecutorAgent",
        "tradingexecutor":      "TradingExecutorAgent",
        "tradingexecutoragent": "TradingExecutorAgent",
        "monitoring":           "MonitoringAgent",
        "monitoringagent":      "MonitoringAgent",
        "chat":                 "ChatAgent",
        "chatagent":            "ChatAgent",
        "pipeline":             "PipelineOrchestrator",
        "pipelineorchestrator": "PipelineOrchestrator",
    }
    _CANONICAL = {k.lower().replace(" ", "").replace("_", ""): v
                  for k, v in _CANONICAL_RAW.items()}
    _KNOWN = [
        "ResearchAgent", "SpecAgent", "MLEngineerAgent", "ValidationAgent",
        "ImprovementAgent", "TradingExecutorAgent", "MonitoringAgent",
        "ChatAgent", "PipelineOrchestrator",
    ]

    def _canonical(name: str) -> str:
        return _CANONICAL.get(name.lower().replace(" ", "").replace("_", ""), name)

    try:
        raw = get_db().get_agent_status()
    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Merge rows with the same canonical name — keep the most recent run
    merged: dict[str, dict] = {}
    for row in raw:
        canon = _canonical(row["agent_name"])
        row["agent_name"] = canon
        prev = merged.get(canon)
        if prev is None or (row.get("last_run") or "") > (prev.get("last_run") or ""):
            merged[canon] = row

    # Add known agents that produced no logs yet
    for name in _KNOWN:
        if name not in merged:
            merged[name] = {
                "agent_name": name, "last_run": None, "last_status": "never_run",
                "last_message": "No activity recorded", "duration_ms": 0,
                "records_written": 0, "error_detail": None,
            }

    agents = list(merged.values())
    # Sort: active/running first, then by last_run descending
    agents.sort(key=lambda a: (
        0 if a.get("last_status") in ("running", "active") else 1,
        -(len(a.get("last_run") or "")),
    ))
    return {"agents": agents, "count": len(agents)}


@app.get("/api/agent-status")
async def get_agent_status_legacy():
    """Legacy endpoint — redirects to /api/agents/status."""
    return await get_agents_status()


@app.get("/api/agents/{agent_name}/history")
async def get_agent_history(agent_name: str, limit: int = 20):
    """Storico delle run di un agente specifico."""
    try:
        history = get_db().get_agent_run_history(agent_name, limit=limit)
        return {"agent_name": agent_name, "history": history, "count": len(history)}
    except Exception as e:
        logger.error(f"Error getting agent history: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/trades")
async def get_trades(limit: int = 100, model_name: Optional[str] = None):
    """Get trade history from Neon PostgreSQL."""
    try:
        trades = get_db().get_trades(model_name=model_name, limit=limit)
        return {"trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"Error getting trades: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/positions")
async def get_positions():
    """Compute open positions by aggregating trades (buy qty - sell qty per symbol)."""
    try:
        trades = get_db().get_trades(limit=1000)

        # Aggregate per symbol
        agg: dict = {}
        for t in trades:
            sym = t.get("symbol", "").upper()
            if not sym:
                continue
            if sym not in agg:
                agg[sym] = {"symbol": sym, "qty": 0.0, "cost": 0.0, "trades": 0}
            action = (t.get("action") or "").upper()
            qty = float(t.get("quantity") or 0)
            price = float(t.get("price") or 0)
            if action == "BUY":
                agg[sym]["cost"] += qty * price
                agg[sym]["qty"] += qty
            elif action == "SELL":
                # Reduce position proportionally
                sell_qty = min(qty, agg[sym]["qty"])
                if agg[sym]["qty"] > 0:
                    agg[sym]["cost"] *= (agg[sym]["qty"] - sell_qty) / agg[sym]["qty"]
                agg[sym]["qty"] -= sell_qty
            agg[sym]["trades"] += 1

        positions = []
        for sym, data in agg.items():
            qty = round(data["qty"], 4)
            if qty <= 0:
                continue
            avg_entry = round(data["cost"] / qty, 4) if qty > 0 else 0
            positions.append({
                "symbol": sym,
                "quantity": qty,
                "avg_entry": avg_entry,
                "side": "LONG",
                "num_trades": data["trades"],
            })

        return {"positions": positions, "count": len(positions)}
    except Exception as e:
        logger.error(f"Error computing positions: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


# === Pipeline Orchestration ===

@app.post("/api/pipeline/run")
async def run_full_pipeline(background_tasks: BackgroundTasks, stop_after: Optional[str] = None):
    """Avvia il pipeline completo in background (research→spec→ml→validation→improvement→monitoring)."""
    def _run():
        from agents.orchestration.pipeline_orchestrator import PipelineOrchestrator
        PipelineOrchestrator().run_full_pipeline(stop_after=stop_after)
    background_tasks.add_task(_run)
    return {"status": "accepted", "message": f"Pipeline started (stop_after={stop_after})"}


@app.post("/api/pipeline/run/{phase}")
async def run_pipeline_phase(phase: str, background_tasks: BackgroundTasks):
    """Avvia una singola fase del pipeline in background."""
    def _run():
        from agents.orchestration.pipeline_orchestrator import PipelineOrchestrator
        PipelineOrchestrator().run_phase(phase)
    background_tasks.add_task(_run)
    return {"status": "accepted", "phase": phase}


@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """Stato corrente di ogni fase del pipeline dal DB."""
    try:
        from agents.orchestration.pipeline_orchestrator import PipelineOrchestrator
        return PipelineOrchestrator().get_pipeline_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

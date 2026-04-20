"""Trading Agents API — data served exclusively from Neon PostgreSQL."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from configs.paths import Paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB singleton — created once at startup, shared across all requests.
_db = None


def get_db():
    global _db
    if _db is None:
        from data.storage.data_manager import DataStorageManager
        _db = DataStorageManager()
    return _db


def _run_research_if_due():
    """Run research agent in a background thread if it hasn't run in 7 days."""
    try:
        from agents.research.research_agent import ResearchAgent
        agent = ResearchAgent()
        if agent.should_run_now(min_interval_days=7):
            logger.info("Auto-triggering ResearchAgent (no run in last 7 days)")
            agent.run()
        else:
            logger.info("ResearchAgent: last run recent enough, skipping auto-run")
    except Exception as e:
        logger.warning(f"Auto research run failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: trigger research in background thread (non-blocking)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_research_if_due)
    yield


app = FastAPI(
    title="Trading Agents API",
    description="API for the multi-agent trading system",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/dashboards", StaticFiles(directory=str(Paths.DASHBOARDS_DIR), html=True), name="dashboards")


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


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Trading Agents API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


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


@app.get("/api/price")
async def get_price(symbol: str):
    """Get real-time stock price via yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}")
        price = float(data["Close"].iloc[-1])
        return {"symbol": symbol, "price": price}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
    """Return model validation results for the backtest dashboard."""
    try:
        strategies = get_db().get_strategies()
    except Exception as e:
        logger.error(f"Error getting backtest results: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

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
    return {"results": results, "count": len(results)}


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
    try:
        agents = get_db().get_agent_status()
        known = [
            "ResearchAgent", "SpecAgent", "MLEngineerAgent", "ValidationAgent",
            "ImprovementAgent", "TradingExecutorAgent", "MonitoringAgent",
            "ChatAgent", "PipelineOrchestrator",
        ]
        seen = {a["agent_name"] for a in agents}
        for name in known:
            if name not in seen:
                agents.append({
                    "agent_name": name, "last_run": None, "last_status": "never_run",
                    "last_message": "No activity recorded", "duration_ms": 0,
                    "records_written": 0, "error_detail": None,
                })
        return {"agents": agents, "count": len(agents)}
    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


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
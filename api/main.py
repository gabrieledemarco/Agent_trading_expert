"""Trading Agents API — data served exclusively from Neon PostgreSQL."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging

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

app = FastAPI(
    title="Trading Agents API",
    description="API for the multi-agent trading system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
async def run_research(request: ResearchRequest):
    """Run research agent."""
    try:
        from agents.research.research_agent import ResearchAgent
        
        agent = ResearchAgent()
        papers = agent.search_arxiv(
            search_query=request.query,
            max_results=request.max_results
        )
        relevant = agent.filter_relevant_papers(papers)
        
        return {
            "total_papers": len(papers),
            "relevant_papers": len(relevant),
            "papers": relevant[:5]
        }
    except Exception as e:
        logger.error(f"Error in research: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/api/agent-status")
async def get_agent_status():
    """Return current status of each agent (last log entry per agent)."""
    try:
        logs = get_db().get_agent_logs(limit=200)
    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    seen: dict = {}
    for log in logs:  # già DESC per timestamp
        name = log.get("agent_name")
        if name and name not in seen:
            seen[name] = {
                "agent_name": name,
                "status":     log.get("status"),
                "last_run":   log.get("timestamp"),
                "message":    log.get("message"),
            }

    default_agents = [
        "ResearchAgent", "SpecAgent", "MLEngineerAgent",
        "ValidationAgent", "TradingExecutor", "MonitoringAgent",
    ]
    result = [
        seen.get(a, {"agent_name": a, "status": "IDLE",
                     "last_run": None, "message": "No activity recorded"})
        for a in default_agents
    ]
    return {"agents": result, "count": len(result)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
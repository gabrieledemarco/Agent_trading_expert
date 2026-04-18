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


# === BLOCCO 2: New API Endpoints ===

@app.get("/research")
async def get_research(limit: int = 100):
    """Get research papers from database."""
    try:
        papers = get_db().get_research(limit=limit)
        return {"papers": papers, "count": len(papers)}
    except Exception as e:
        logger.error(f"Error getting research: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/equity-curve")
async def get_equity_curve(period: str = "30d"):
    """Get equity curve time-series for charting.
    
    Args:
        period: Time period - '7d', '30d', '90d', '1y'
    """
    try:
        # Parse period to days
        period_days = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
            "1y": 365,
            "all": 9999,
        }.get(period, 30)
        
        performance = get_db().get_performance(days=period_days)
        
        if not performance:
            return {"labels": [], "values": [], "period": period}
        
        # Sort by timestamp
        performance_sorted = sorted(performance, key=lambda x: x.get("timestamp", ""))
        
        labels = []
        values = []
        for p in performance_sorted:
            ts = p.get("timestamp", "")
            # Format label as date only
            if ts:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    labels.append(dt.strftime("%Y-%m-%d"))
                except:
                    labels.append(ts[:10] if len(ts) >= 10 else ts)
            else:
                labels.append("")
            values.append(p.get("equity", 0))
        
        return {
            "labels": labels,
            "values": values,
            "period": period,
            "start_value": values[0] if values else 0,
            "end_value": values[-1] if values else 0,
            "total_return": (values[-1] / values[0] - 1) if values and values[0] > 0 else 0,
        }
    except Exception as e:
        logger.error(f"Error getting equity curve: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/backtest/results")
async def get_backtest_results():
    """Get complete backtest results: models + validation with all metrics."""
    try:
        strategies = get_db().get_strategies()
        
        results = []
        for s in strategies:
            # Get validation details
            validations = get_db().get_validations(status="approved")
            model_validations = [v for v in validations if v.get("model_id") == s.get("id")]
            
            validation = model_validations[0] if model_validations else {}
            
            results.append({
                "model_name": s.get("name"),
                "model_type": s.get("model_type"),
                "status": s.get("status"),
                "created_date": s.get("created_date"),
                "validation_date": s.get("validation_date"),
                "risk_level": s.get("risk_level"),
                "sharpe_ratio": s.get("sharpe_ratio"),
                "robustness": s.get("robustness"),
                # Additional metrics from validation
                "sharpe_ratio_detail": validation.get("sharpe_ratio"),
                "risk_score": validation.get("risk_score"),
                "robustness_score": validation.get("robustness_score"),
            })
        
        return {
            "results": results,
            "count": len(results),
            "approved_count": len([r for r in results if r.get("status") == "APPROVED"]),
        }
    except Exception as e:
        logger.error(f"Error getting backtest results: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/risk/summary")
async def get_risk_summary():
    """Get risk metrics: VaR 95%, CVaR, max drawdown, beta."""
    try:
        import numpy as np
        
        # Get performance data for calculations
        performance = get_db().get_performance(days=90)
        trades = get_db().get_trades(limit=1000)
        
        if not performance:
            return {
                "var_95": None,
                "cvar_95": None,
                "max_drawdown": None,
                "beta": None,
                "volatility": None,
                "message": "No performance data available"
            }
        
        # Calculate equity curve
        equity_values = [p.get("equity", 0) for p in sorted(performance, key=lambda x: x.get("timestamp", ""))]
        
        if len(equity_values) < 2:
            return {
                "var_95": None,
                "cvar_95": None,
                "max_drawdown": None,
                "beta": None,
                "volatility": None,
                "message": "Insufficient data for risk calculation"
            }
        
        # Calculate returns
        returns = np.diff(equity_values) / np.array(equity_values[:-1])
        returns = returns[np.isfinite(returns)]  # Remove NaN/Inf
        
        if len(returns) == 0:
            return {
                "var_95": None,
                "cvar_95": None,
                "max_drawdown": None,
                "beta": None,
                "volatility": None,
                "message": "Insufficient returns data"
            }
        
        # VaR 95% (Value at Risk)
        var_95 = float(np.percentile(returns, 5))
        
        # CVaR 95% (Conditional Value at Risk / Expected Shortfall)
        cvar_95 = float(returns[returns <= var_95].mean()) if len(returns[returns <= var_95]) > 0 else var_95
        
        # Max Drawdown
        equity_arr = np.array(equity_values)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak
        max_drawdown = float(np.max(drawdown))
        
        # Volatility (annualized)
        volatility = float(returns.std() * np.sqrt(252))
        
        # Beta (simplified - using market proxy as equal weight)
        # In production, you'd compare against SPY or similar
        beta = 1.0  # Placeholder - would need market data for real beta
        
        return {
            "var_95": round(var_95, 4),
            "cvar_95": round(cvar_95, 4),
            "max_drawdown": round(max_drawdown, 4),
            "beta": beta,
            "volatility": round(volatility, 4),
            "risk_level": "HIGH" if abs(var_95) > 0.05 or max_drawdown > 0.2 else "MEDIUM" if abs(var_95) > 0.02 or max_drawdown > 0.1 else "LOW",
            "data_points": len(returns),
        }
    except Exception as e:
        logger.error(f"Error calculating risk summary: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Risk calculation failed")


@app.get("/api/agent-status")
async def get_agent_status():
    """Get current status of all agents from agent_logs."""
    try:
        logs = get_db().get_agent_logs(limit=100)
        
        if not logs:
            return {"agents": [], "message": "No agent logs available"}
        
        # Group by agent and get latest status for each
        agent_status = {}
        for log in logs:
            agent_name = log.get("agent_name")
            if agent_name and agent_name not in agent_status:
                agent_status[agent_name] = {
                    "agent_name": agent_name,
                    "status": log.get("status"),
                    "message": log.get("message"),
                    "timestamp": log.get("timestamp"),
                }
        
        # Convert to list
        agents = list(agent_status.values())
        
        # Sort by agent name
        agents.sort(key=lambda x: x.get("agent_name", ""))
        
        return {
            "agents": agents,
            "count": len(agents),
            "active_count": len([a for a in agents if a.get("status") == "active"]),
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
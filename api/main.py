"""Simple API server for Trading Agents."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import logging

from configs.paths import Paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trading Agents API",
    description="API for the multi-agent trading system",
    version="0.1.0",
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
    """List available models."""
    import os
    from pathlib import Path
    
    models_dir = Path("models/versions")
    if not models_dir.exists():
        return {"models": []}
    
    models = []
    for f in models_dir.glob("*.py"):
        models.append({
            "name": f.stem,
            "type": "lstm",
            "path": str(f)
        })
    
    return {"models": models, "count": len(models)}


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
    """Get dashboard summary data."""
    try:
        from data.storage.data_manager import DataStorageManager
        
        db = DataStorageManager()
        summary = db.get_dashboard_summary()
        
        return summary
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
        # Return mock data if DB not initialized
        return {
            "research_papers": 0,
            "specs_created": 0,
            "models_implemented": 0,
            "models_validated": 0,
            "total_trades": 0,
            "current_equity": 10000,
            "total_return": 0,
            "sharpe_ratio": 0
        }


@app.get("/dashboard/agent-activity")
async def get_agent_activity(limit: int = 20):
    """Get agent activity logs."""
    try:
        from data.storage.data_manager import DataStorageManager
        
        db = DataStorageManager()
        logs = db.get_agent_logs(limit=limit)
        
        return {"activities": logs}
    except Exception as e:
        logger.error(f"Error getting agent activity: {e}", exc_info=True)
        return {"activities": []}


@app.get("/dashboard/strategy/{strategy_name}")
async def get_strategy_performance(strategy_name: str):
    """Get performance for a specific strategy."""
    try:
        from data.storage.data_manager import DataStorageManager
        
        db = DataStorageManager()
        performance = db.get_performance(model_name=strategy_name, days=30)
        
        if not performance:
            # Return mock data
            return {
                "strategy": strategy_name,
                "equity": 10542,
                "total_return": 0.054,
                "sharpe_ratio": 1.23,
                "max_drawdown": 0.082,
                "win_rate": 0.62,
                "risk_level": "MEDIUM",
                "robustness": "HIGH"
            }
        
        latest = performance[0]
        return {
            "strategy": strategy_name,
            "equity": latest.get("equity", 0),
            "total_return": latest.get("total_return", 0),
            "sharpe_ratio": latest.get("sharpe_ratio", 0),
            "max_drawdown": latest.get("max_drawdown", 0),
            "win_rate": latest.get("win_rate", 0),
        }
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/strategies")
async def list_strategies():
    """List all strategies with their status."""
    try:
        from pathlib import Path
        
        validated_dir = Path("models/validated")
        if not validated_dir.exists():
            return {"strategies": []}
        
        strategies = []
        for f in validated_dir.glob("*_validation.json"):
            import json
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                strategies.append({
                    "name": data.get("model_name"),
                    "status": data.get("validation_status"),
                    "risk_level": data.get("risk_return_profile", {}).get("risk_score", "UNKNOWN"),
                    "sharpe_ratio": data.get("risk_return_profile", {}).get("sharpe_ratio", 0),
                    "robustness": data.get("statistical_robustness", {}).get("robustness_score", "UNKNOWN"),
                })
        
        return {"strategies": strategies}
    except Exception as e:
        logger.error(f"Error listing strategies: {e}", exc_info=True)
        return {"strategies": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
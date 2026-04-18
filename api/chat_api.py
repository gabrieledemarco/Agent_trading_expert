"""Chat API — data served from Neon PostgreSQL only."""

from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_db = None

def get_db():
    global _db
    if _db is None:
        from data.storage.data_manager import DataStorageManager
        _db = DataStorageManager()
    return _db


class ChatRequest(BaseModel):
    message: str = ""


@app.get("/api/chat/data")
async def get_chat_data():
    """Return model data from Neon PostgreSQL for the chat assistant."""
    try:
        strategies = get_db().get_strategies()
    except Exception as e:
        logger.error(f"DB error in /api/chat/data: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    approved = [s for s in strategies if (s.get("status") or "").upper() == "APPROVED"]
    total_sharpe = sum(float(s.get("sharpe_ratio") or 0) for s in approved)
    avg_sharpe = total_sharpe / len(approved) if approved else 0

    return {
        "total_models":   len(strategies),
        "approved_models": len(approved),
        "models": [
            {
                "name":   s.get("name"),
                "sharpe": s.get("sharpe_ratio", 0),
                "status": s.get("status"),
                "risk":   s.get("risk_level"),
            }
            for s in strategies
        ],
        "avg_sharpe": avg_sharpe,
    }


@app.post("/api/chat/message")
async def chat_message(request: ChatRequest):
    msg = request.message.lower()
    if "strategy" in msg or "strategie" in msg:
        return {"response": "Usa /strategies per la lista completa delle strategie.", "type": "strategy"}
    elif "performance" in msg or "rendimenti" in msg:
        return {"response": "Usa /dashboard/summary per un riepilogo delle performance.", "type": "performance"}
    elif "backtest" in msg or "test" in msg:
        return {"response": "Dati di backtest disponibili via /strategies.", "type": "backtest"}
    return {"response": "Chiedi di strategie, performance o backtest.", "type": "info"}

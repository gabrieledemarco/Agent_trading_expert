
import json
import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    message: str = ""


@app.get("/api/chat/data")
async def get_chat_data():
    models = []
    approved = 0
    total_sharpe = 0
    total_win = 0

    validated_dir = "models/validated"
    if os.path.exists(validated_dir):
        for f in os.listdir(validated_dir):
            if not f.endswith("_validation.json"):
                continue
            safe_path = os.path.join(validated_dir, os.path.basename(f))
            with open(safe_path, encoding="utf-8") as fp:
                data = json.load(fp)
                rr = data.get("risk_return_profile", {})
                status = data.get("validation_status", "REJECTED")
                models.append({
                    "name": data.get("model_name", ""),
                    "sharpe": rr.get("sharpe_ratio", 0),
                    "return": rr.get("expected_return", 0),
                    "status": status
                })
                if status == "APPROVED":
                    approved += 1
                    total_sharpe += rr.get("sharpe_ratio", 0)
                    total_win += rr.get("win_rate", 0)

    reports = []
    if os.path.exists(validated_dir):
        for f in os.listdir(validated_dir):
            if f.endswith("_documentation.md"):
                reports.append({
                    "name": f.replace("_documentation.md", ""),
                    "robustness": "See JSON",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                })

    avg_sharpe = total_sharpe / approved if approved > 0 else 0
    avg_win = total_win / approved if approved > 0 else 0

    return {
        "total_models": len(models),
        "approved_models": approved,
        "models": models,
        "avg_sharpe": avg_sharpe,
        "win_rate": avg_win,
        "reports": reports[:5]
    }


@app.post("/api/chat/message")
async def chat_message(request: ChatRequest):
    msg = request.message.lower()
    if "strategy" in msg or "strategie" in msg:
        return {
            "response": "Strategie APPROVATE:\n- model_intraday_momentum\n- model_highfrequency\n- model_dynamic_time",
            "type": "strategy",
        }
    elif "performance" in msg or "rendimenti" in msg:
        return {
            "response": "Sharpe: -0.39\nReturn: -0.9%\nWin Rate: 47.6%",
            "type": "performance",
        }
    elif "backtest" in msg or "test" in msg:
        return {
            "response": "Backtest: 4 modelli\nRobustezza: Varia",
            "type": "backtest",
        }
    return {"response": "Chiedi di strategie, performance, backtest o report.", "type": "info"}


import json, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"жа

@app.get("/api/chat/data")
async def get_chat_data():
    models = []
    approved = 0
    total_sharpe = 0
    total_win = 0
    
    validated_dir = "models/validated"
    if os.path.exists(validated_dir):
        for f in os.listdir(validated_dir):
            if f.endswith("_validation.json"):
                with open(os.path.join(validated_dir, f)) as fp:
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
                reports.append({"name": f.replace("_documentation.md", ""), "robustness": "See JSON", "date": "2026-04-16"})
    
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
async def chat_message(request: dict):
    msg = request.get("message", "").lower()
    if "strategy" in msg or "strategie" in msg:
        return {"response": "Strategie APPROVATE:
- model_intraday_momentum
- model_highfrequency
- model_dynamic_time", "type": "strategy"}
    elif "performance" in msg or "rendimenti" in msg:
        return {"response": "Sharpe: -0.39
Return: -0.9%
Win Rate: 47.6%", "type": "performance"}
    elif "backtest" in msg or "test" in msg:
        return {"response": "Backtest: 4 modelli
Robustezza: Varia", "type": "backtest"}
    return {"response": "Chiedi di strategie, performance, backtest o report.", "type": "info"}

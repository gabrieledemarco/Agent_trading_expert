"""Chat Agent for interacting with users about strategies and performance."""
import json
import os
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ChatAgent:
    """Agent that answers user questions about the trading system."""

    def __init__(self, data_dir: str = "data", models_dir: str = "models"):
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.conversation_history: List[Dict] = []

    def process_message(self, user_message: str) -> Dict:
        """Process user message and generate response."""
        user_message = user_message.lower().strip()
        
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        response = self._generate_response(user_message)
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response["message"],
            "timestamp": datetime.now().isoformat()
        })
        
        return response

    def _generate_response(self, query: str) -> Dict:
        """Generate response based on query."""
        if any(kw in query for kw in ["strategy", "strategie", "approccio", "metodo"]):
            return self._handle_strategy_query(query)
        elif any(kw in query for kw in ["performance", "performace", "rendimenti", "return"]):
            return self._handle_performance_query(query)
        elif any(kw in query for kw in ["backtest", "test", "validazione"]):
            return self._handle_backtest_query(query)
        elif any(kw in query for kw in ["report", "document", "documentazion"]):
            return self._handle_report_query(query)
        elif any(kw in query for kw in ["modello", "model", "ml", "machine learning"]):
            return self._handle_model_query(query)
        elif any(kw in query for kw in ["aiuto", "help", "cosa puoi", "capabilities"]):
            return self._handle_help_query()
        else:
            return {
                "message": "Posso aiutarti con:\n- Strategie di trading\n- Performance e rendimenti\n- Backtest e validazione\n- Report e documentazione\n- Modelli ML\n\nCosa vorresti sapere?",
                "type": "info",
                "data": {}
            }

    def _handle_strategy_query(self, query: str) -> Dict:
        """Handle strategy-related queries."""
        validated_dir = os.path.join(self.models_dir, "validated")
        approved = []
        
        if os.path.exists(validated_dir):
            for f in os.listdir(validated_dir):
                if f.endswith("_validation.json"):
                    with open(os.path.join(validated_dir, f)) as fp:
                        data = json.load(fp)
                        if data.get("validation_status") == "APPROVED":
                            approved.append(data.get("model_name", f))
        
        message = "Strategie APPROVATE per trading:\n\n"
        if approved:
            for a in approved:
                message += f"- {a}\n"
        else:
            message += "- Nessuna strategia approvata\n"
        
        return {"message": message, "type": "strategy", "data": {"strategies": approved}}

    def _handle_performance_query(self, query: str) -> Dict:
        """Handle performance queries."""
        validated_dir = os.path.join(self.models_dir, "validated")
        performance = []
        
        if os.path.exists(validated_dir):
            for f in os.listdir(validated_dir):
                if f.endswith("_validation.json"):
                    with open(os.path.join(validated_dir, f)) as fp:
                        data = json.load(fp)
                        if data.get("validation_status") == "APPROVED":
                            rr = data.get("risk_return_profile", {})
                            performance.append({
                                "model": data.get("model_name", ""),
                                "sharpe": rr.get("sharpe_ratio", 0),
                                "return": rr.get("expected_return", 0),
                                "win_rate": rr.get("win_rate", 0)
                            })
        
        if performance:
            message = "Performance modelli approvati:\n\n"
            for p in performance:
                message += f"{p['model']}:\n"
                message += f"  Sharpe: {p['sharpe']:.2f}\n"
                message += f"  Return: {p['return']*100:.1f}%\n"
                message += f"  Win Rate: {p['win_rate']*100:.1f}%\n\n"
        else:
            message = "Nessuna performance disponibile."
        
        return {"message": message, "type": "performance", "data": {"performance": performance}}

    def _handle_backtest_query(self, query: str) -> Dict:
        """Handle backtest queries."""
        validated_dir = os.path.join(self.models_dir, "validated")
        backtests = []
        
        if os.path.exists(validated_dir):
            for f in os.listdir(validated_dir):
                if f.endswith("_validation.json"):
                    with open(os.path.join(validated_dir, f)) as fp:
                        data = json.load(fp)
                        if data.get("validation_status") == "APPROVED":
                            rb = data.get("statistical_robustness", {})
                            backtests.append({
                                "model": data.get("model_name", ""),
                                "mean_return": rb.get("mean_return", 0),
                                "prob_positive": rb.get("prob_positive_return", 0),
                                "robustness": rb.get("robustness_score", "N/A")
                            })
        
        if backtests:
            message = "Risultati Backtest:\n\n"
            for b in backtests:
                message += f"{b['model']}:\n"
                message += f"  Mean Return: {b['mean_return']*100:.1f}%\n"
                message += f"  Prob. Positive: {b['prob_positive']*100:.1f}%\n"
                message += f"  Robustness: {b['robustness']}\n\n"
        else:
            message = "Nessun backtest disponibile."
        
        return {"message": message, "type": "backtest", "data": {"backtests": backtests}}

    def _handle_report_query(self, query: str) -> Dict:
        """Handle report queries."""
        validated_dir = os.path.join(self.models_dir, "validated")
        docs = []
        
        if os.path.exists(validated_dir):
            for f in os.listdir(validated_dir):
                if f.endswith("_documentation.md"):
                    docs.append(f.replace("_documentation.md", ""))
        
        message = "Report disponibili:\n\n"
        if docs:
            for d in docs:
                message += f"- {d}\n"
        else:
            message += "- Nessun report disponibile\n"
        
        return {"message": message, "type": "report", "data": {"reports": docs}}

    def _handle_model_query(self, query: str) -> Dict:
        """Handle model queries."""
        message = "Modelli disponibili:\n\n"
        message += "- model_intraday_momentum_trading_with_machine (5m, 15m)\n"
        message += "- model_highfrequency_statistical_arbitrage (1m)\n"
        message += "- model_dynamic_time_window_optimization_for (Adaptive)\n"
        
        return {"message": message, "type": "model", "data": {}}

    def _handle_help_query(self) -> Dict:
        """Handle help queries."""
        message = """Cosa posso fare:

- Strategie: Ti mostro le strategie disponibili
- Performance: Report sui rendimenti
- Backtest: Risultati validazione
- Report: Documentazione modelli
- Modelli: Info sui modelli ML

Esempi:
- "Mostrami le performance"
- "Quali strategie sono approvate?"
- "Risultati backtest"

Come posso aiutarti?"""
        
        return {"message": message, "type": "help", "data": {}}

    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        """Get recent conversation history."""
        return self.conversation_history[-limit:]


if __name__ == "__main__":
    agent = ChatAgent()
    print("Chat Agent attivo!")
    print("Digita 'exit' per uscire.\n")
    
    while True:
        user_input = input("Tu: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break
        response = agent.process_message(user_input)
        print(f"Bot: {response['message']}\n")

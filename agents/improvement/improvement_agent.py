"""ImprovementAgent — iterative optimization of rejected/underperforming strategies.

Responsibility (PDR): reasoning only.
- Reads validation results from models/validated/
- Identifies why a strategy was REJECTED or has poor metrics
- Proposes parameter adjustments (no numerics — only reasoning)
- Submits improved version via ExecutionClient
- Loops until APPROVED or max_iterations reached
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.base.base_agent import BaseAgent
from configs.paths import Paths

logger = logging.getLogger(__name__)


class ImprovementAgent(BaseAgent):
    """Iteratively improves strategies rejected by ValidationAgent.

    Loop:
        read validation JSON  →  analyze failure reasons
        →  adjust parameters (LLM reasoning)
        →  ExecutionClient.execute_backtest()
        →  compare metrics  →  repeat if worse, stop if better
    """

    def __init__(
        self,
        validated_dir: str = str(Paths.VALIDATED_DIR),
        output_dir: str = str(Paths.MODELS_VERSIONS),
        max_iterations: int = 3,
        engine_url: Optional[str] = None,
    ):
        super().__init__(engine_url=engine_url)
        self.validated_dir = Path(validated_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, model_name: Optional[str] = None) -> list[dict]:
        """Run improvement loop for all REJECTED strategies (or a specific one)."""
        targets = self._find_targets(model_name)
        results = []
        for validation in targets:
            try:
                result = self.improve(validation)
                results.append(result)
            except Exception as e:
                name = validation.get("model_name", "unknown")
                logger.error("Improvement failed for %s: %s", name, e)
                results.append({"model_name": name, "status": "error", "error": str(e)})
        return results

    def improve(self, validation: dict) -> dict:
        """Run the improvement loop for one strategy."""
        model_name = validation.get("model_name", "unknown")
        logger.info("Starting improvement loop for: %s", model_name)
        self.log_activity("RUNNING", f"Improving {model_name}")

        current_params = self._extract_params(validation)
        best_sharpe = validation.get("risk_return_profile", {}).get("sharpe_ratio", 0.0)
        history = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info("[%s] Iteration %d/%d — current sharpe=%.3f",
                        model_name, iteration, self.max_iterations, best_sharpe)

            # Reasoning step: propose new parameters
            new_params = self._propose_params(validation, current_params, history)

            # Numerical step: delegate to ExecutionClient
            result = self.execution_client.execute_backtest({
                "strategy_id": f"{model_name}_iter{iteration}",
                "strategy_code": self._load_strategy_code(model_name),
                "parameters": new_params,
                "dataset": {"symbols": ["AAPL", "MSFT"], "start": "2022-01-01", "end": "2023-12-31"},
                "backtest_config": {"initial_capital": 10000, "transaction_cost": 0.001, "seed": 42},
            })

            new_sharpe = result.get("risk_return", {}).get("sharpe_ratio", 0.0)
            improved = new_sharpe > best_sharpe

            history.append({
                "iteration": iteration,
                "params": new_params,
                "sharpe": new_sharpe,
                "improved": improved,
            })

            logger.info("[%s] iter=%d sharpe: %.3f → %.3f (%s)",
                        model_name, iteration, best_sharpe, new_sharpe,
                        "↑ IMPROVED" if improved else "↓ no gain")

            if improved:
                best_sharpe = new_sharpe
                current_params = new_params
                self._save_improved_params(model_name, new_params, result)

        final_status = "improved" if best_sharpe > validation.get("risk_return_profile", {}).get("sharpe_ratio", 0) else "no_improvement"
        self.log_activity("COMPLETED", f"{model_name}: {final_status}, best_sharpe={best_sharpe:.3f}")

        return {
            "model_name": model_name,
            "status": final_status,
            "initial_sharpe": validation.get("risk_return_profile", {}).get("sharpe_ratio", 0.0),
            "best_sharpe": best_sharpe,
            "iterations": history,
            "best_params": current_params,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Parameter reasoning ───────────────────────────────────────────────────

    def _propose_params(self, validation: dict, current_params: dict, history: list) -> dict:
        """Propose new parameters — LLM reasoning or heuristic fallback."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                return self._llm_propose(validation, current_params, history, api_key)
            except Exception as e:
                logger.warning("LLM proposal failed (%s), using heuristic", e)
        return self._heuristic_propose(current_params, history)

    def _llm_propose(self, validation: dict, params: dict, history: list, api_key: str) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        anomalies = validation.get("anomalies", [])
        risk_profile = validation.get("risk_return_profile", {})
        prompt = f"""You are a quantitative strategy optimizer. Suggest improved parameters.

Model: {validation.get("model_name")}
Current params: {json.dumps(params, indent=2)}
Validation status: {validation.get("validation_status")}
Anomalies: {json.dumps(anomalies, indent=2)[:500]}
Current metrics:
  - Sharpe ratio: {risk_profile.get("sharpe_ratio", 0):.3f}
  - Max drawdown: {risk_profile.get("max_drawdown", 0):.3f}
  - Win rate: {risk_profile.get("win_rate", 0):.3f}
Iteration history: {json.dumps(history[-3:], indent=2) if history else "[]"}

Suggest adjusted parameters to improve the Sharpe ratio.
Return ONLY a valid JSON object with the new parameter values. No explanation."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)

    def _heuristic_propose(self, current_params: dict, history: list) -> dict:
        """Deterministic heuristic: adjust lookback and threshold."""
        new_params = dict(current_params)

        if not history:
            # First iteration: widen lookback
            new_params["lookback"] = int(current_params.get("lookback", 20) * 1.5)
            new_params["threshold"] = current_params.get("threshold", 0.02) * 0.8
        else:
            last = history[-1]
            if not last["improved"]:
                # Tighten threshold if no improvement
                new_params["threshold"] = current_params.get("threshold", 0.02) * 1.2
                new_params["lookback"] = max(5, int(current_params.get("lookback", 20) * 0.8))
            else:
                # Keep going in same direction
                new_params["lookback"] = int(current_params.get("lookback", 20) * 1.2)

        return new_params

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_targets(self, model_name: Optional[str]) -> list[dict]:
        """Load REJECTED validations (or all if model_name given)."""
        if not self.validated_dir.exists():
            return []
        targets = []
        for f in self.validated_dir.glob("*_validation.json"):
            with open(f) as fp:
                v = json.load(fp)
            name = v.get("model_name")
            status = v.get("validation_status")
            if model_name:
                if name == model_name:
                    targets.append(v)
            elif status == "REJECTED":
                targets.append(v)
        return targets

    def _extract_params(self, validation: dict) -> dict:
        """Extract usable parameters from validation or use defaults."""
        return {"lookback": 20, "threshold": 0.02, "stop_loss": 0.05}

    def _load_strategy_code(self, model_name: str) -> str:
        strategy_file = self.output_dir / f"{model_name}.py"
        if strategy_file.exists():
            return strategy_file.read_text()
        # Fallback minimal strategy
        return "def run(data, params):\n    n=len(data['prices'])\n    return {'signals':['hold']*n,'position_sizes':[0.0]*n}"

    def _save_improved_params(self, model_name: str, params: dict, result: dict):
        params_file = self.output_dir / f"{model_name}_best_params.json"
        payload = {
            "model_name": model_name,
            "params": params,
            "risk_return": result.get("risk_return", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }
        params_file.write_text(json.dumps(payload, indent=2))

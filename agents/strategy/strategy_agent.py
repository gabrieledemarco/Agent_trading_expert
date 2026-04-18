"""StrategyAgent — converts research specs into Python strategy code.

Responsibility (PDR): reasoning only.
- Reads a spec YAML
- Uses Anthropic Claude to generate a backtest-compatible Python strategy
- Submits the code to ExecutionClient for numerical validation
- Saves the result to models/versions/

No numerical computation here — all numbers come from ExecutionClient.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from agents.base.base_agent import BaseAgent
from configs.paths import Paths

logger = logging.getLogger(__name__)

# Strategy code template — generated code must conform to this interface
_STRATEGY_TEMPLATE = '''
def run(data: dict, params: dict) -> dict:
    """
    Backtest-compatible strategy function.

    Args:
        data: dict with keys 'prices' (list[float]), 'dates' (list[str]),
              'volume' (list[float]), 'symbols' (list[str])
        params: strategy parameters dict

    Returns:
        dict with keys:
          signals: list[str]  — "buy" | "sell" | "hold" per date
          position_sizes: list[float]  — fraction of capital [0, 1]
    """
    prices = data["prices"]
    n = len(prices)
    signals = ["hold"] * n
    sizes = [0.0] * n
    # --- strategy logic here ---
    return {"signals": signals, "position_sizes": sizes}
'''


class StrategyAgent(BaseAgent):
    """Generates executable strategy code from a model specification.

    Pipeline:
        spec YAML  →  [LLM reasoning]  →  Python strategy code
                  →  ExecutionClient.execute_backtest()
                  →  strategy file saved to models/versions/
    """

    def __init__(
        self,
        specs_dir: str = str(Paths.SPECS_DIR),
        output_dir: str = str(Paths.MODELS_VERSIONS),
        engine_url: Optional[str] = None,
    ):
        super().__init__(engine_url=engine_url)
        self.specs_dir = Path(specs_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._client = None  # lazy Anthropic client

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, model_name: Optional[str] = None) -> list[dict]:
        """Generate strategies for all specs (or a specific one)."""
        specs = self._load_specs(model_name)
        results = []
        for spec in specs:
            try:
                result = self.generate_strategy(spec)
                results.append(result)
            except Exception as e:
                logger.error("Failed to generate strategy for %s: %s", spec.get("model", {}).get("name"), e)
                results.append({"status": "error", "error": str(e)})
        return results

    def generate_strategy(self, spec: dict) -> dict:
        """Generate and validate a strategy from a single spec."""
        model_name = spec.get("model", {}).get("name", f"strategy_{uuid.uuid4().hex[:8]}")
        logger.info("Generating strategy for: %s", model_name)
        self.log_activity("RUNNING", f"Generating strategy for {model_name}")

        # Step 1: Generate Python code (LLM or template)
        code = self._generate_code(spec)

        # Step 2: Validate via ExecutionClient (no numerics here)
        backtest_result = self.execution_client.execute_backtest({
            "strategy_id": model_name,
            "strategy_code": code,
            "parameters": spec.get("training", {}).get("hyperparameters", {}),
            "dataset": {
                "symbols": spec.get("data_requirements", {}).get("sources", ["AAPL"]),
                "start": "2022-01-01",
                "end": "2023-12-31",
                "frequency": "1d",
            },
            "backtest_config": {
                "initial_capital": 10000,
                "transaction_cost": 0.001,
                "walk_forward_windows": 12,
                "seed": 42,
            },
        })

        # Step 3: Save strategy file
        output_path = self._save_strategy(model_name, code, spec, backtest_result)

        result = {
            "model_name": model_name,
            "status": "generated",
            "output_file": str(output_path),
            "execution_id": backtest_result.get("execution_id"),
            "risk_return": backtest_result.get("risk_return", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.log_activity("COMPLETED", f"Strategy generated: {model_name}")
        logger.info("Strategy generated: %s → %s", model_name, output_path)
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _generate_code(self, spec: dict) -> str:
        """Generate Python strategy code from spec.

        Uses Anthropic Claude when ANTHROPIC_API_KEY is set,
        otherwise falls back to a deterministic template.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            return self._llm_generate(spec, api_key)
        return self._template_generate(spec)

    def _llm_generate(self, spec: dict, api_key: str) -> str:
        """Generate strategy code via Claude."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)

            prompt = self._build_prompt(spec)
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            # Extract Python code block if present
            if "```python" in raw:
                code = raw.split("```python")[1].split("```")[0].strip()
            elif "```" in raw:
                code = raw.split("```")[1].split("```")[0].strip()
            else:
                code = raw.strip()
            return code
        except Exception as e:
            logger.warning("LLM generation failed (%s), falling back to template", e)
            return self._template_generate(spec)

    def _template_generate(self, spec: dict) -> str:
        """Generate a deterministic strategy from spec metadata."""
        model = spec.get("model", {})
        arch = spec.get("architecture", {})
        training = spec.get("training", {})

        model_type = model.get("type", "mean_reversion")
        lookback = training.get("hyperparameters", {}).get("lookback_period", 20)
        threshold = training.get("hyperparameters", {}).get("signal_threshold", 0.02)

        if "momentum" in model_type.lower():
            return self._momentum_template(lookback, threshold)
        elif "mean_reversion" in model_type.lower() or "arbitrage" in model_type.lower():
            return self._mean_reversion_template(lookback, threshold)
        elif "lstm" in model_type.lower() or "neural" in model_type.lower():
            return self._ml_template(lookback, threshold)
        else:
            return self._momentum_template(lookback, threshold)

    def _momentum_template(self, lookback: int, threshold: float) -> str:
        return f'''
def run(data: dict, params: dict) -> dict:
    prices = data["prices"]
    lookback = params.get("lookback", {lookback})
    threshold = params.get("threshold", {threshold})
    n = len(prices)
    signals = ["hold"] * n
    sizes = [0.0] * n

    for i in range(lookback, n):
        window = prices[i - lookback:i]
        momentum = (prices[i] - window[0]) / window[0] if window[0] != 0 else 0
        if momentum > threshold:
            signals[i] = "buy"
            sizes[i] = min(1.0, abs(momentum) * 5)
        elif momentum < -threshold:
            signals[i] = "sell"
            sizes[i] = min(1.0, abs(momentum) * 5)

    return {{"signals": signals, "position_sizes": sizes}}
'''.strip()

    def _mean_reversion_template(self, lookback: int, threshold: float) -> str:
        return f'''
def run(data: dict, params: dict) -> dict:
    prices = data["prices"]
    lookback = params.get("lookback", {lookback})
    threshold = params.get("threshold", {threshold})
    n = len(prices)
    signals = ["hold"] * n
    sizes = [0.0] * n

    for i in range(lookback, n):
        window = prices[i - lookback:i]
        mean = sum(window) / len(window)
        std = (sum((x - mean) ** 2 for x in window) / len(window)) ** 0.5
        z_score = (prices[i] - mean) / std if std > 0 else 0
        if z_score < -threshold:
            signals[i] = "buy"
            sizes[i] = min(1.0, abs(z_score) / 3)
        elif z_score > threshold:
            signals[i] = "sell"
            sizes[i] = min(1.0, abs(z_score) / 3)

    return {{"signals": signals, "position_sizes": sizes}}
'''.strip()

    def _ml_template(self, lookback: int, threshold: float) -> str:
        return f'''
def run(data: dict, params: dict) -> dict:
    prices = data["prices"]
    lookback = params.get("lookback", {lookback})
    threshold = params.get("threshold", {threshold})
    n = len(prices)
    signals = ["hold"] * n
    sizes = [0.0] * n

    for i in range(lookback + 1, n):
        window = prices[i - lookback - 1:i]
        returns = [(window[j] - window[j-1]) / window[j-1] for j in range(1, len(window)) if window[j-1] != 0]
        avg_return = sum(returns) / len(returns) if returns else 0
        if avg_return > threshold:
            signals[i] = "buy"
            sizes[i] = 0.5
        elif avg_return < -threshold:
            signals[i] = "sell"
            sizes[i] = 0.5

    return {{"signals": signals, "position_sizes": sizes}}
'''.strip()

    def _build_prompt(self, spec: dict) -> str:
        model = spec.get("model", {})
        arch = spec.get("architecture", {})
        training = spec.get("training", {})
        source = spec.get("source_paper", {})

        return f"""You are a quantitative trading engineer. Generate a Python strategy function based on this model specification.

Model: {model.get("name")}
Type: {model.get("type")}
Description: {model.get("description", "")[:400]}
Source paper: {source.get("title", "N/A")}
Architecture: {json.dumps(arch, indent=2)[:500]}
Training params: {json.dumps(training.get("hyperparameters", {}), indent=2)}

REQUIREMENTS:
1. The function MUST have this exact signature:
   def run(data: dict, params: dict) -> dict

2. data contains: 'prices' (list[float]), 'dates' (list[str]), 'volume' (list[float])
3. Return dict must have: 'signals' (list of "buy"/"sell"/"hold"), 'position_sizes' (list[float] 0-1)
4. Use only Python stdlib (no imports needed — numpy/pandas not available in sandbox)
5. Keep it under 60 lines

Return ONLY the Python function, no explanation."""

    def _save_strategy(self, model_name: str, code: str, spec: dict, backtest_result: dict) -> Path:
        """Save strategy code with metadata header."""
        output_path = self.output_dir / f"{model_name}.py"
        risk = backtest_result.get("risk_return", {})
        header = f'''# Strategy: {model_name}
# Generated: {datetime.utcnow().isoformat()}
# Type: {spec.get("model", {}).get("type", "unknown")}
# Sharpe (estimated): {risk.get("sharpe_ratio", 0):.3f}
# Risk score: {risk.get("risk_score", "UNKNOWN")}
# Execution ID: {backtest_result.get("execution_id", "local")}

'''
        output_path.write_text(header + code)
        return output_path

    def _load_specs(self, model_name: Optional[str] = None) -> list[dict]:
        if not self.specs_dir.exists():
            return []
        specs = []
        for f in self.specs_dir.glob("*.yaml"):
            with open(f) as fp:
                spec = yaml.safe_load(fp)
                if model_name is None or spec.get("model", {}).get("name") == model_name:
                    spec["_source_file"] = str(f)
                    specs.append(spec)
        return specs

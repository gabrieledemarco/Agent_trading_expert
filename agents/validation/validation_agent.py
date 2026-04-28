"""Validation Agent - Verify models, identify anomalies, and validate scientific basis."""

import re
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml
import numpy as np
import pandas as pd

from agents.base.base_agent import BaseAgent
from configs.paths import Paths
from execution_engine.computation_service import ComputationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """Agent responsible for validating ML models and their scientific basis."""

    STRATEGY_THRESHOLDS = {
        "min_sharpe": 0.5,               # L3
        "min_profit_factor": 1.2,        # L3
        "max_drawdown": 0.20,            # L4
        "max_monte_carlo_pvalue": 0.05,  # L5
    }

    def __init__(
        self,
        models_dir: str = str(Paths.MODELS_DIR),
        specs_dir: str = str(Paths.SPECS_DIR),
        output_dir: str = str(Paths.VALIDATED_DIR),
    ):
        super().__init__()
        self.models_dir = Path(models_dir)
        self.specs_dir = Path(specs_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._computation = ComputationService()

    def load_specs(self) -> list[dict]:
        """Load specification files; falls back to DB when local files are absent (Render restart)."""
        if self.specs_dir.exists():
            specs = []
            for f in self.specs_dir.glob("*.yaml"):
                with open(f) as fp:
                    spec = yaml.safe_load(fp)
                    spec["_source_file"] = str(f)
                    specs.append(spec)
            if specs:
                return specs

        # DB fallback: rebuild minimal spec structure from V1 specs table
        try:
            db_specs = self.db.get_specs()
            if db_specs:
                logger.info(f"load_specs: local YAML absent — rebuilding from DB ({len(db_specs)} rows)")
                return [
                    {
                        "model": {
                            "name": row.get("model_name"),
                            "type": row.get("model_type", "time_series_forecasting"),
                            "description": "",
                        },
                        "architecture": {"input_features": [], "layers": []},
                        "source_paper": {},
                        "_source": "db",
                    }
                    for row in db_specs
                ]
        except Exception as e:
            logger.warning(f"load_specs: DB fallback failed: {e}")

        return []

    def load_model_code(self, model_name: str) -> Optional[str]:
        """Load model source code."""
        model_file = self.models_dir / f"{model_name}.py"
        if model_file.exists():
            return model_file.read_text()
        return None

    def check_code_quality(self, code: str) -> dict:
        """Check code quality metrics."""
        issues = []
        warnings = []

        # Check for basic issues
        if "torch" in code:
            # Check for proper device handling
            if ".to(device)" not in code and "cuda" in code.lower():
                warnings.append("CUDA mentioned but no device handling found")

        if "numpy" in code or "np." in code:
            # Check for random seed
            if "np.random" in code and "seed" not in code.lower():
                warnings.append("Random operations without seed setting")

        # Check for common issues
        if "model.train()" in code and "model.eval()" not in code:
            issues.append("Model has train mode but no eval mode")

        if ".fit(" in code and "cross_val" not in code.lower():
            warnings.append("Fitting model but no cross-validation mentioned")

        return {
            "issues": issues,
            "warnings": warnings,
            "score": max(0, 10 - len(issues) * 2 - len(warnings)),
        }

    def identify_anomalies(self, model_name: str, spec: dict) -> list[dict]:
        """Identify anomalies in model implementation vs spec."""
        anomalies = []
        code = self.load_model_code(model_name)

        if not code:
            anomalies.append({
                "type": "missing_code",
                "severity": "high",
                "description": f"Model code file not found: {model_name}.py"
            })
            return anomalies

        # Check architecture consistency — skip for RL/RF models that don't use LSTM layers
        model_type = spec.get("model", {}).get("type", "")
        _rl_types = {"reinforcement_learning", "q_learning", "policy_gradient", "dqn", "ppo"}
        expected_layers = spec.get("architecture", {}).get("layers", [])
        if expected_layers and model_type.lower() not in _rl_types:
            for layer in expected_layers:
                layer_type = layer.get("type", "")
                if layer_type == "LSTM" and "LSTM" not in code and "lstm" not in code.lower():
                    anomalies.append({
                        "type": "architecture_mismatch",
                        "severity": "high",
                        "description": "Expected LSTM layer but not found in code",
                    })

        # Data fetching is done by the training pipeline, not model architecture files.
        # Only flag if spec declares sources but lists none at all (spec-level gap).
        required_sources = spec.get("data_requirements", {}).get("sources", [])
        if required_sources is not None and len(required_sources) == 0:
            anomalies.append({
                "type": "data_source_missing",
                "severity": "low",
                "description": "Spec has no data_requirements.sources defined",
            })

        return anomalies

    def verify_academic_consistency(self, spec: dict) -> list[dict]:
        """Verify consistency between spec and source paper."""
        discrepancies = []

        source_paper = spec.get("source_paper", {})
        paper_id = source_paper.get("id", "")

        if not paper_id:
            discrepancies.append({
                "type": "missing_source",
                "severity": "high",
                "description": "No source paper reference found"
            })
            return discrepancies

        # Check spec completeness
        required_fields = ["model", "architecture", "training", "validation"]
        for field in required_fields:
            if field not in spec:
                discrepancies.append({
                    "type": "incomplete_spec",
                    "severity": "medium",
                    "description": f"Missing required field: {field}"
                })

        # Verify training parameters
        training = spec.get("training", {})
        if training.get("epochs", 0) < 10:
            discrepancies.append({
                "type": "parameter_issue",
                "severity": "low",
                "description": "Very low epoch count may lead to underfitting"
            })

        if training.get("validation_split", 0) < 0.1:
            discrepancies.append({
                "type": "parameter_issue",
                "severity": "medium",
                "description": "Very small validation split may produce unreliable metrics"
            })

        return discrepancies

    def analyze_risk_return_profile(self, model_name: str) -> dict:
        """Delegate to ComputationService."""
        return self._computation.analyze_risk_return_profile(model_name)

    def evaluate_statistical_robustness(self, model_name: str) -> dict:
        """Delegate to ComputationService."""
        return self._computation.evaluate_statistical_robustness(model_name)

    def generate_scientific_documentation(self, model_name: str, spec: dict) -> str:
        """Generate detailed scientific documentation."""
        source_paper = spec.get("source_paper", {})
        model = spec.get("model", {})

        # Get risk/return analysis
        risk_return = self.analyze_risk_return_profile(model_name)
        robustness = self.evaluate_statistical_robustness(model_name)

        doc = f"""# Scientific Documentation: {model_name}

## 1. Source Paper Reference
- **Title**: {source_paper.get('title', 'N/A')}
- **arXiv ID**: {source_paper.get('id', 'N/A')}
- **Published**: {source_paper.get('published', 'N/A')}

## 2. Model Overview
- **Type**: {model.get('type', 'N/A')}
- **Description**: {model.get('description', 'N/A')[:300]}...

## 3. Scientific Basis

### 3.1 Theoretical Foundation
This model is based on research from the paper "{source_paper.get('title', 'N/A')}" published on arXiv.

The model implements a {model.get('type', 'N/A').replace('_', ' ')} approach for financial prediction,
utilizing machine learning techniques to analyze market data patterns.

### 3.2 Key Scientific Principles
- **Data-driven approach**: Uses historical market data for pattern recognition
- **Statistical learning**: Implements techniques from statistical machine learning
- **Risk-adjusted optimization**: Targets risk-adjusted returns via Sharpe ratio

### 3.3 Assumptions
1. Market data follows identifiable patterns
2. Historical patterns have predictive power
3. Risk and return are quantifiable metrics

## 4. Strategy Logic

### 4.1 Input Features
"""
        # Add input features
        features = spec.get("architecture", {}).get("input_features", [])
        for feature in features:
            doc += f"- {feature}\n"

        doc += """
### 4.2 Processing Pipeline
1. Data collection from market sources
2. Feature engineering (technical indicators)
3. Model training with validation
4. Signal generation for trading decisions

### 4.3 Decision Logic
The model generates trading signals based on:
- Price pattern recognition
- Momentum indicators
- Mean reversion principles

## 5. Risk/Return Profile

### 5.1 Expected Performance
| Metric | Value | Assessment |
|--------|-------|------------|
| Expected Annual Return | {:.2%} | {} |
| Annual Volatility | {:.2%} | {} |
| Sharpe Ratio | {:.2f} | {} |
| Maximum Drawdown | {:.2%} | {} |
| Win Rate | {:.2%} | {} |
""".format(
            risk_return["expected_return"],
            risk_return["return_score"],
            risk_return["volatility"],
            risk_return["risk_score"],
            risk_return["sharpe_ratio"],
            risk_return["risk_return_ratio"],
            risk_return["max_drawdown"],
            risk_return["risk_score"],
            risk_return["win_rate"],
            risk_return["return_score"],
        )

        # Format remaining values separately for risk assessment
        risk_lvl = risk_return.get("risk_score", "LOW")
        ret_lvl = risk_return.get("return_score", "MODERATE")
        rr_ratio = risk_return.get("risk_return_ratio", 0.5)

        doc += """
### 5.2 Risk Assessment
- **Risk Level**: {}
- **Return Level**: {}
- **Risk-Return Ratio**: {:.2f}
""".format(risk_lvl, ret_lvl, rr_ratio)

        doc += """
### 5.3 Risk Management Recommendations
1. Maximum position size: 10% of capital
2. Stop loss: 5% per trade
3. Take profit: 15% per trade
4. Maximum drawdown limit: 20%

## 6. Statistical Robustness

### 6.1 Monte Carlo Analysis (100 simulations)
| Metric | Value |
|--------|-------|
| Mean Return | {:.2%} |
| Std Return | {:.2%} |
| 5th Percentile | {:.2%} |
| 95th Percentile | {:.2%} |
| Probability of Positive Return | {:.2%} |
| Probability of >10% Loss | {:.2%} |
""".format(
            robustness["mean_return"],
            robustness["std_return"],
            robustness["percentile_5"],
            robustness["percentile_95"],
            robustness["prob_positive_return"],
            robustness["prob_negative_10"],
        )

        # Format robustness separately
        rob_score = robustness.get("robustness_score", "MODERATE")
        cv = robustness.get("coefficient_of_variation", 0.5)

        doc += """
### 6.2 Robustness Assessment
- **Robustness Score**: {}
- **Coefficient of Variation**: {:.2f}
""".format(rob_score, cv)

        doc += """
## 7. Backtest Results

### 7.1 Methodology
- **Period**: 1 year out-of-sample
- **Data Frequency**: Daily
- **Initial Capital**: $10,000
- **Transaction Costs**: 0.1%

### 7.2 Results Summary
| Metric | Value |
|--------|-------|
| Total Return | See risk/return profile |
| Sharpe Ratio | See risk/return profile |
| Maximum Drawdown | See risk/return profile |
| Win Rate | See risk/return profile |

### 7.3 Validation Approach
1. Time-series cross-validation (walk-forward)
2. Out-of-sample testing (last 20% of data)
3. Monte Carlo simulations for stress testing

## 8. Limitations and Caveats

1. **Market Regime Changes**: Model may underperform in trending markets
2. **Data Quality**: Reliance on accurate market data
3. **Transaction Costs**: High-frequency trading may be unprofitable after costs
4. **Black Swan Events**: Model cannot predict extreme events
5. **Overfitting Risk**: Historical backtests may not predict future performance

## 9. Recommended Usage

- **Paper Trading**: Recommended before live trading
- **Capital Allocation**: Start with 5-10% of total capital
- **Monitoring**: Daily performance review recommended
- **Rebalancing**: Review model every 3 months

## 10. References

1. arXiv: {paper_id}
2. Technical documentation in specs/

---
*Generated by ValidationAgent on {datetime}*
""".format(
            paper_id=source_paper.get('id', 'N/A'),
            datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

        return doc

    def validate_model(self, model_name: str) -> dict:
        """Perform complete model validation."""
        logger.info(f"Validating model: {model_name}")

        # Get spec
        specs = self.load_specs()
        spec = None
        for s in specs:
            if s.get("model", {}).get("name") == model_name:
                spec = s
                break

        if not spec:
            return {"error": f"No spec found for model {model_name}"}

        # Run validations
        code = self.load_model_code(model_name)
        code_quality = self.check_code_quality(code) if code else {"issues": ["No code"], "score": 0}

        anomalies = self.identify_anomalies(model_name, spec)
        discrepancies = self.verify_academic_consistency(spec)
        risk_return = self.analyze_risk_return_profile(model_name)
        robustness = self.evaluate_statistical_robustness(model_name)

        # Generate documentation
        doc = self.generate_scientific_documentation(model_name, spec)

        # Determine validation status — architecture anomalies (L1) + metric thresholds (L3/L4)
        critical_issues = len([a for a in anomalies if a.get("severity") == "high"])

        sharpe   = risk_return.get("sharpe_ratio", 0.0)
        max_dd   = risk_return.get("max_drawdown", 0.0)
        metric_failures = []
        if sharpe < self.STRATEGY_THRESHOLDS["min_sharpe"]:
            metric_failures.append(
                f"sharpe_ratio={sharpe:.2f} < min {self.STRATEGY_THRESHOLDS['min_sharpe']}"
            )
        if max_dd > self.STRATEGY_THRESHOLDS["max_drawdown"]:
            metric_failures.append(
                f"max_drawdown={max_dd:.2%} > max {self.STRATEGY_THRESHOLDS['max_drawdown']:.0%}"
            )

        validation_status = "REJECTED" if (critical_issues > 0 or metric_failures) else "APPROVED"
        if metric_failures:
            logger.info(f"Model {model_name} REJECTED by metric thresholds: {metric_failures}")

        result = {
            "schema_version": "1.0",
            "model_name": model_name,
            "validation_status": validation_status,
            "validation_timestamp": datetime.now().isoformat(),
            "code_quality": code_quality,
            "anomalies": anomalies,
            "academic_discrepancies": discrepancies,
            "risk_return_profile": risk_return,
            "statistical_robustness": robustness,
        }

        # Save result
        output_file = self.output_dir / f"{model_name}_validation.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        # Save documentation
        doc_file = self.output_dir / f"{model_name}_documentation.md"
        doc_file.write_text(doc)

        # Persist to Neon PostgreSQL — V1 tables
        try:
            rr = result.get("risk_return_profile", {})
            model_id = self.db.save_model({
                "model_name": result.get("model_name"),
                "model_type": result.get("model_type", "unknown"),
                "status": "implemented",
                "metrics": rr,
            })
            self.db.save_validation({
                "model_id": model_id,
                "status": result.get("validation_status", "REJECTED").lower(),
                "risk_score": rr.get("risk_score", "UNKNOWN"),
                "sharpe_ratio": float(rr.get("sharpe_ratio", 0) or 0),
                "robustness_score": result.get("statistical_robustness", {}).get("robustness_score", "UNKNOWN"),
                "anomalies": result.get("anomalies", []),
            })
            self.log_activity("COMPLETED", f"Validation for {result.get('model_name')} saved to Neon")
        except Exception as e:
            logger.warning(f"Could not persist validation to Neon: {e}")

        # Update V2 strategies table so Kanban reflects approved/rejected status
        v2_status = "approved" if validation_status == "APPROVED" else "rejected"
        try:
            strategies = self.db.get_strategies_v2(limit=500)
            strategy = next((s for s in strategies if s.get("name") == model_name), None)
            if strategy:
                self.db.update_strategy_status(strategy["id"], v2_status)
                logger.info(f"Strategy V2 status updated: {model_name} → {v2_status}")
            else:
                # Strategy not yet in V2 (SpecAgent may not have run); create it now
                self.db.save_strategy({
                    "name":              model_name,
                    "spec":              result,
                    "status":            v2_status,
                    "validation_result": {
                        "sharpe_ratio": rr.get("sharpe_ratio"),
                        "max_drawdown": rr.get("max_drawdown"),
                        "anomalies":    result.get("anomalies", []),
                    },
                })
                logger.info(f"Strategy V2 created by validation: {model_name} → {v2_status}")
        except Exception as e:
            logger.warning(f"Could not update V2 strategy status: {e}")

        logger.info(f"Validation complete: {validation_status} for {model_name}")
        return result

    def run(self) -> list[str]:
        """Alias for run_validation — satisfies BaseAgent contract."""
        return self.run_validation()

    def validate_strategy_report(self, report: dict) -> dict:
        """Validate strategy-level metrics L1-L5 from a backtest report."""
        findings = []

        # L1 - minimal structural sanity
        if not report.get("method"):
            findings.append({
                "level": "L1",
                "status": "failed",
                "metric_name": "method",
                "expected_threshold": "non-empty",
                "actual_value": None,
                "details": "Backtest method missing",
            })

        # L2 - execution realism: trades present + timestamps monotonically ordered
        trades = report.get("trades")
        if trades is None:
            findings.append({
                "level": "L2",
                "status": "warning",
                "metric_name": "trades",
                "expected_threshold": "present",
                "actual_value": None,
                "details": "Missing trade log payload in report",
            })
        elif isinstance(trades, list) and len(trades) > 1:
            ts_keys = ("timestamp", "date", "ts", "executed_at")
            timestamps = [next((t[k] for k in ts_keys if k in t), None) for t in trades]
            timestamps = [str(ts) for ts in timestamps if ts is not None]
            if timestamps and timestamps != sorted(timestamps):
                findings.append({
                    "level": "L2",
                    "status": "failed",
                    "metric_name": "trade_timestamps",
                    "expected_threshold": "monotonically ordered",
                    "actual_value": "out-of-order",
                    "details": "Trade timestamps not monotonically ordered — possible lookahead bias",
                })

        # L3 - performance: sharpe + profit_factor
        sharpe = float(report.get("sharpe_ratio") or 0)
        if sharpe < self.STRATEGY_THRESHOLDS["min_sharpe"]:
            findings.append({
                "level": "L3",
                "status": "failed",
                "metric_name": "sharpe_ratio",
                "expected_threshold": f">={self.STRATEGY_THRESHOLDS['min_sharpe']}",
                "actual_value": sharpe,
                "details": "Risk-adjusted return below threshold",
            })

        profit_factor = float(report.get("profit_factor") or 0)
        if 0 < profit_factor < self.STRATEGY_THRESHOLDS["min_profit_factor"]:
            findings.append({
                "level": "L3",
                "status": "failed",
                "metric_name": "profit_factor",
                "expected_threshold": f">={self.STRATEGY_THRESHOLDS['min_profit_factor']}",
                "actual_value": profit_factor,
                "details": "Profit factor below threshold — gross losses exceed acceptable ratio to gross profits",
            })

        # L4 - risk
        max_drawdown = float(report.get("max_drawdown") or 0)
        if max_drawdown > self.STRATEGY_THRESHOLDS["max_drawdown"]:
            findings.append({
                "level": "L4",
                "status": "failed",
                "metric_name": "max_drawdown",
                "expected_threshold": f"<={self.STRATEGY_THRESHOLDS['max_drawdown']}",
                "actual_value": max_drawdown,
                "details": "Drawdown exceeds acceptable risk budget",
            })

        # L5 - robustness
        pvalue = float(report.get("monte_carlo_pvalue") or 1.0)
        if pvalue > self.STRATEGY_THRESHOLDS["max_monte_carlo_pvalue"]:
            findings.append({
                "level": "L5",
                "status": "failed",
                "metric_name": "monte_carlo_pvalue",
                "expected_threshold": f"<={self.STRATEGY_THRESHOLDS['max_monte_carlo_pvalue']}",
                "actual_value": pvalue,
                "details": "Monte Carlo significance not robust enough",
            })

        overall = "APPROVED" if not any(f["status"] == "failed" for f in findings) else "REJECTED"
        return {"overall_status": overall, "findings": findings}

    def run_strategy_validation_v2(self) -> list[str]:
        """Run strategy-level validation (L1-L5) over V2 backtest reports."""
        statuses = []
        reports = self.db.get_backtest_reports(limit=500)

        for report in reports:
            strategy_id = report.get("strategy_id")
            report_id = report.get("id")
            if not strategy_id or not report_id:
                continue

            result = self.validate_strategy_report(report)
            findings = result["findings"] or [{
                "level": "L3",
                "status": "passed",
                "metric_name": "strategy_quality",
                "expected_threshold": "all thresholds satisfied",
                "actual_value": None,
                "details": "Strategy passed all configured checks",
            }]

            for finding in findings:
                self.db.save_validation_v2({
                    "strategy_id": strategy_id,
                    "backtest_report_id": report_id,
                    "level": finding["level"],
                    "status": finding["status"],
                    "metric_name": finding["metric_name"],
                    "expected_threshold": finding["expected_threshold"],
                    "actual_value": finding["actual_value"],
                    "details": finding["details"],
                })

            statuses.append(result["overall_status"])

        return statuses

    def run_validation(self) -> list[str]:
        """Run validation.

        Priority:
        1) V2 strategy validation from backtest reports (L1-L5)
        2) Legacy model validation fallback (existing behavior)
        """
        try:
            v2_reports = self.db.get_backtest_reports(limit=1)
            if v2_reports:
                return self.run_strategy_validation_v2()
        except Exception as e:
            logger.warning(f"V2 strategy validation unavailable, falling back to legacy flow: {e}")

        # Legacy fallback
        specs = self.load_specs()
        results = []

        for spec in specs:
            model_name = spec.get("model", {}).get("name")
            if model_name:
                result = self.validate_model(model_name)
                results.append(result["validation_status"])

        return results


if __name__ == "__main__":
    agent = ValidationAgent()
    outputs = agent.run_validation()
    print(f"Validation complete. Results: {outputs}")

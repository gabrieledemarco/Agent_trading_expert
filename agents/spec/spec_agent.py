"""Spec Agent - Transform research into technical specifications."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpecAgent:
    """Agent responsible for creating technical specifications from research."""

    def __init__(self, research_dir: str = "data/research_findings", output_dir: str = "specs"):
        self.research_dir = Path(research_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def read_latest_research(self) -> Optional[str]:
        """Read the most recent research findings."""
        if not self.research_dir.exists():
            logger.warning(f"Research directory {self.research_dir} does not exist")
            return None

        md_files = sorted(self.research_dir.glob("research_*.md"), reverse=True)
        if not md_files:
            logger.warning("No research files found")
            return None

        latest = md_files[0]
        logger.info(f"Reading research from {latest}")
        return latest.read_text()

    def extract_paper_info(self, research_text: str) -> list[dict]:
        """Extract structured paper information from markdown."""
        papers = []
        current_paper = {}

        lines = research_text.split("\n")
        in_abstract = False
        abstract_lines = []

        for line in lines:
            # Match numbered heading (e.g., "### 1. Title")
            match = re.match(r"^###\s+\d+\.\s+(.+)$", line)
            if match:
                if current_paper:
                    papers.append(current_paper)
                current_paper = {"title": match.group(1).strip()}
                in_abstract = False
                abstract_lines = []
                continue

            # Match metadata fields
            if line.startswith("- **ID**:"):
                current_paper["id"] = line.split(":**")[1].strip()
            elif line.startswith("- **Published**:"):
                current_paper["published"] = line.split(":**")[1].strip()
            elif line.startswith("- **Authors**:"):
                current_paper["authors"] = line.split(":**")[1].strip()
            elif line.startswith("- **Categories**:"):
                current_paper["categories"] = line.split(":**")[1].strip()
            elif line.startswith("- **PDF**:"):
                current_paper["pdf_url"] = line.split(":**")[1].strip()
            elif "**Abstract**" in line:
                in_abstract = True
                continue

            # Collect abstract
            if in_abstract:
                if line.strip() and not line.startswith("- "):
                    abstract_lines.append(line.strip())
                elif line.startswith("-"):
                    in_abstract = False
                    current_paper["abstract"] = " ".join(abstract_lines)

        if current_paper:
            papers.append(current_paper)

        return papers

    def generate_spec(self, paper: dict) -> dict:
        """Generate technical specification from paper info."""
        title = paper.get("title", "Unknown").lower()

        # Determine model type based on title/abstract
        model_type = "time_series_forecasting"
        if "reinforcement" in title or "rl" in title:
            model_type = "reinforcement_learning"
        elif "portfolio" in title or "allocation" in title:
            model_type = "portfolio_optimization"
        elif "sentiment" in title:
            model_type = "sentiment_analysis"
        elif " GAN " in title or "gan" in title:
            model_type = "gan_generation"

        spec = {
            "spec_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "source_paper": {
                "title": paper.get("title"),
                "id": paper.get("id"),
                "published": paper.get("published"),
            },
            "model": {
                "name": self._generate_model_name(paper.get("title", "")),
                "type": model_type,
                "description": paper.get("abstract", "")[:500],
            },
            "architecture": {
                "input_features": self._infer_features(model_type),
                "output_type": "price_prediction",
                "layers": self._generate_architecture(model_type),
            },
            "data_requirements": {
                "sources": ["yfinance", "alpha_vantage"],
                "frequency": "daily",
                "lookback_period": "2 years",
                "required_columns": ["open", "high", "low", "close", "volume"],
            },
            "training": {
                "framework": "pytorch",
                "epochs": 100,
                "batch_size": 32,
                "validation_split": 0.2,
                "early_stopping_patience": 10,
            },
            "validation": {
                "backtest_period": "1 year",
                "metrics": ["sharpe_ratio", "max_drawdown", "total_return"],
                "out_of_sample_testing": True,
            },
            "action_plan": [
                f"Clone/fork paper implementation if available",
                f"Set up data pipeline for {model_type}",
                f"Implement model architecture",
                f"Train on historical data",
                f"Run backtesting validation",
                f"Test with paper trading",
            ],
        }

        return spec

    def _generate_model_name(self, title: str) -> str:
        """Generate a clean model name from paper title."""
        # Remove special chars, lowercase, replace spaces with underscores
        name = re.sub(r"[^a-zA-Z0-9\s]", "", title)
        name = "_".join(name.split()[:5]).lower()
        return f"model_{name}"

    def _infer_features(self, model_type: str) -> list[str]:
        """Infer input features based on model type."""
        base_features = [
            "close_price",
            "volume",
            "price_returns",
            "moving_averages",
        ]

        type_specific = {
            "reinforcement_learning": ["state_vector", "action_space", "reward_signal"],
            "portfolio_optimization": ["asset_weights", "covariance_matrix"],
            "sentiment_analysis": ["text_features", "sentiment_score"],
            "gan_generation": ["noise_vector", "conditioning_features"],
        }

        return base_features + type_specific.get(model_type, [])

    def _generate_architecture(self, model_type: str) -> list[dict]:
        """Generate architecture specification."""
        common_layers = [
            {"type": "Input", "shape": "[None, 60, 10]"},
            {"type": "LSTM", "units": 128, "return_sequences": True},
            {"type": "Dropout", "rate": 0.2},
            {"type": "LSTM", "units": 64},
            {"type": "Dropout", "rate": 0.2},
            {"type": "Dense", "units": 32, "activation": "relu"},
            {"type": "Output", "units": 1},
        ]

        return common_layers

    def create_action_plan(self, spec: dict) -> str:
        """Create detailed action plan from specification."""
        plan = f"""# Action Plan: {spec['model']['name']}

## Overview
- **Type**: {spec['model']['type']}
- **Source**: {spec['source_paper']['title']}

## Implementation Steps

### Phase 1: Data Pipeline
1. Set up data fetching from {', '.join(spec['data_requirements']['sources'])}
2. Implement data preprocessing for {spec['data_requirements']['frequency']} data
3. Create feature engineering pipeline

### Phase 2: Model Implementation
1. Build model architecture:
{self._format_architecture(spec['architecture']['layers'])}
2. Implement loss functions and optimizers
3. Set up training loop with early stopping

### Phase 3: Validation
1. Run backtesting on {spec['validation']['backtest_period']}
2. Calculate metrics: {', '.join(spec['validation']['metrics'])}
3. Perform out-of-sample testing

### Phase 4: Trading Integration
1. Connect model to trading executor
2. Set up paper trading simulation
3. Configure risk management rules

## Success Criteria
- Sharpe Ratio > 1.0
- Maximum Drawdown < 20%
- Out-of-sample performance matches in-sample
"""
        return plan

    def _format_architecture(self, layers: list[dict]) -> str:
        """Format architecture for action plan."""
        lines = []
        for layer in layers:
            if "units" in layer:
                lines.append(f"   - {layer['type']}({layer['units']} units)")
            else:
                lines.append(f"   - {layer['type']}")
        return "\n".join(lines)

    def run_spec_generation(self) -> list[str]:
        """Run specification generation from latest research."""
        logger.info("Starting spec generation...")

        # Read research
        research_text = self.read_latest_research()
        if not research_text:
            logger.warning("No research text to process")
            return []

        # Extract paper info
        papers = self.extract_paper_info(research_text)
        logger.info(f"Extracted {len(papers)} papers")

        # Generate specs
        spec_files = []
        for paper in papers[:3]:  # Process top 3 papers
            spec = self.generate_spec(paper)

            # Save spec
            output_file = self.output_dir / f"{spec['model']['name']}.yaml"
            with open(output_file, "w") as f:
                yaml.dump(spec, f, default_flow_style=False)
            logger.info(f"Saved spec to {output_file}")
            spec_files.append(str(output_file))

            # Create action plan
            action_plan = self.create_action_plan(spec)
            plan_file = self.output_dir / f"{spec['model']['name']}_action_plan.md"
            plan_file.write_text(action_plan)
            logger.info(f"Saved action plan to {plan_file}")

        return spec_files


if __name__ == "__main__":
    agent = SpecAgent()
    outputs = agent.run_spec_generation()
    print(f"Spec generation complete. Outputs: {outputs}")
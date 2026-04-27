"""Spec Agent - Transform research into technical specifications."""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from agents.base.base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpecAgent(BaseAgent):
    """Agent responsible for creating technical specifications from research."""

    def __init__(self, research_dir: str = "data/research_findings", output_dir: str = "specs"):
        super().__init__()
        self.research_dir = Path(research_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def read_latest_research(self) -> Optional[str]:
        """Read the most recent research findings.

        Tries local markdown first (fast path), then falls back to the Neon
        research table so SpecAgent works after a Render restart (no persistent disk).
        """
        if self.research_dir.exists():
            md_files = sorted(self.research_dir.glob("research_*.md"), reverse=True)
            if md_files:
                logger.info(f"Reading research from {md_files[0]}")
                return md_files[0].read_text()

        # Fallback: rebuild markdown from DB research rows
        try:
            papers = self.db.get_research(limit=10)
            if papers:
                logger.info(f"Building research text from DB ({len(papers)} papers)")
                lines = ["# Research Findings — DB\n"]
                for i, p in enumerate(papers, 1):
                    lines.append(f"### {i}. {p.get('title', 'Unknown')} (score: {p.get('relevance_score', 0):.2f})\n")
                    lines.append(f"- **ID**: {p.get('id', '')}")
                    lines.append(f"- **Published**: {p.get('published', '')}")
                    lines.append(f"- **Authors**: {p.get('authors', '')}")
                    lines.append(f"- **Categories**: {p.get('categories', '')}")
                    lines.append(f"\nAbstract\n\n{p.get('abstract', '')[:500]}")
                    lines.append(f"\n- **PDF**: {p.get('pdf_url', '')}")
                    lines.append("\n---\n")
                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Could not read research from DB: {e}")

        logger.warning("No research files or DB data available")
        return None

    def extract_paper_info(self, research_text: str) -> list[dict]:
        """Extract structured paper information from markdown."""
        papers = []
        current_paper = {}

        lines = research_text.split("\n")
        in_abstract = False
        abstract_lines = []

        for line in lines:
            # Match numbered heading (handle both plain text and $ formats)
            clean_line = line.replace("$", "")
            match = re.match(r"^###\s+\d+\.\s+(.+)$", clean_line)
            if match:
                if current_paper:
                    papers.append(current_paper)
                current_paper = {"title": match.group(1).strip()}
                in_abstract = False
                abstract_lines = []
                continue

            # Match metadata fields - handle all bold formats
            clean_line = line.replace("$", "").replace("**", "").replace("*", "")
            # Now format is "- ID:" so strip the "- " prefix first
            if clean_line.startswith("- "):
                field_line = clean_line[2:]  # Remove "- " prefix
                if field_line.startswith("ID:"):
                    current_paper["id"] = field_line[3:].strip()
                elif field_line.startswith("Published:"):
                    current_paper["published"] = field_line[10:].strip()
                elif field_line.startswith("Authors:"):
                    current_paper["authors"] = field_line[8:].strip()
                elif field_line.startswith("Categories:"):
                    current_paper["categories"] = field_line[12:].strip()
                elif field_line.startswith("PDF:"):
                    current_paper["pdf_url"] = field_line[4:].strip()
            elif "Abstract" in clean_line:
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

    def run(self) -> list[str]:
        """Alias for run_spec_generation — satisfies BaseAgent contract."""
        return self.run_spec_generation()

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

            # Persist to V1 specs table
            try:
                row_id = self.db.save_spec({
                    "model_name":      spec["model"]["name"],
                    "source_paper_id": paper.get("id", ""),
                    "model_type":      spec["model"]["type"],
                    "status":          "pending",
                })
                self.log_activity("active", f"Spec saved to DB: {spec['model']['name']} (id={row_id})")
            except Exception as e:
                self.log_activity("warning", f"Could not save spec to DB: {e}")

            # Persist to V2 strategies table so Kanban shows draft card
            try:
                strategy_id = self.db.save_strategy({
                    "name":   spec["model"]["name"],
                    "spec":   spec,
                    "status": "draft",
                })
                spec["strategy_id"] = strategy_id
                self.log_activity("active", f"Strategy V2 created: {spec['model']['name']} (id={strategy_id})")
            except Exception as e:
                self.log_activity("warning", f"Could not save strategy V2: {e}")

        return spec_files


if __name__ == "__main__":
    agent = SpecAgent()
    outputs = agent.run_spec_generation()
    print(f"Spec generation complete. Outputs: {outputs}")
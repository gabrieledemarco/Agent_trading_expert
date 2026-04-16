"""Tests for Validation Agent."""

import pytest
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.validation.validation_agent import ValidationAgent


class TestValidationAgent:
    """Test suite for ValidationAgent."""

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = ValidationAgent()
        assert agent is not None

    def test_check_code_quality(self):
        """Test code quality checking."""
        agent = ValidationAgent()

        # Test good code
        good_code = """
import torch
model.train()
model.eval()
torch.manual_seed(42)
np.random.seed(42)
"""
        quality = agent.check_code_quality(good_code)
        assert "score" in quality
        assert quality["score"] >= 8

        # Test problematic code
        bad_code = """
import torch
model.train()
# No eval mode
# No seed
"""
        quality = agent.check_code_quality(bad_code)
        assert quality["score"] < 10

    def test_analyze_risk_return_profile(self):
        """Test risk/return profile analysis."""
        agent = ValidationAgent()

        profile = agent.analyze_risk_return_profile("test_model")
        assert "expected_return" in profile
        assert "sharpe_ratio" in profile
        assert "risk_score" in profile
        assert "max_drawdown" in profile

    def test_evaluate_statistical_robustness(self):
        """Test statistical robustness evaluation."""
        agent = ValidationAgent()

        robustness = agent.evaluate_statistical_robustness("test_model")
        assert "mean_return" in robustness
        assert "prob_positive_return" in robustness
        assert "robustness_score" in robustness

    def test_generate_scientific_documentation(self):
        """Test scientific documentation generation."""
        agent = ValidationAgent()

        spec = {
            "source_paper": {
                "title": "Test Paper",
                "id": "test123",
                "published": "2024-01-01",
            },
            "model": {
                "type": "time_series_forecasting",
                "description": "Test model description",
            },
            "architecture": {
                "input_features": ["close_price", "volume"],
                "layers": [],
            },
        }

        doc = agent.generate_scientific_documentation("test_model", spec)
        assert "Test Paper" in doc
        assert "Scientific Basis" in doc
        assert "Risk/Return Profile" in doc
        assert "Backtest Results" in doc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
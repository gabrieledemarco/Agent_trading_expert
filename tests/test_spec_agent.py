"""Tests for Spec Agent."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.spec.spec_agent import SpecAgent


class TestSpecAgent:
    """Test suite for SpecAgent."""

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = SpecAgent()
        assert agent is not None

    def test_generate_model_name(self):
        """Test model name generation."""
        agent = SpecAgent()
        name = agent._generate_model_name("Deep Learning for Stock Trading")
        assert "model" in name
        assert "deep" in name or "learning" in name or "stock" in name

    def test_infer_features(self):
        """Test feature inference."""
        agent = SpecAgent()
        features = agent._infer_features("time_series_forecasting")
        assert isinstance(features, list)
        assert "close_price" in features

    def test_generate_spec(self):
        """Test spec generation."""
        agent = SpecAgent()
        paper = {
            "title": "Test Paper",
            "id": "test123",
            "published": "2024-01-01",
            "abstract": "Test abstract about trading.",
        }
        spec = agent.generate_spec(paper)
        assert "model" in spec
        assert "architecture" in spec
        assert "action_plan" in spec


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
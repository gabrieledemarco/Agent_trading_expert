"""Tests for Research Agent."""

import pytest
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.research.research_agent import ResearchAgent


class TestResearchAgent:
    """Test suite for ResearchAgent."""

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = ResearchAgent()
        assert agent is not None
        assert agent.output_dir.exists()

    def test_search_arxiv(self):
        """Test arXiv search functionality."""
        agent = ResearchAgent()
        papers = agent.search_arxiv(search_query="trading", max_results=5)
        assert isinstance(papers, list)

    def test_filter_relevant_papers(self):
        """Test paper filtering."""
        agent = ResearchAgent()
        papers = [
            {"title": "Deep Learning for Stock Trading", "summary": "Using ML for trading"},
            {"title": "Weather Prediction", "summary": "Forecasting weather patterns"},
        ]
        relevant = agent.filter_relevant_papers(papers)
        assert len(relevant) == 1
        assert "trading" in relevant[0]["title"].lower()

    def test_create_summary(self):
        """Test summary generation."""
        agent = ResearchAgent()
        papers = [
            {
                "title": "Test Paper",
                "id": "test123",
                "published": "2024-01-01",
                "authors": ["Author 1"],
                "categories": ["cs.LG"],
                "summary": "This is a test abstract.",
            }
        ]
        summary = agent.create_summary(papers)
        assert "Test Paper" in summary
        assert "Test Paper" in summary
        assert "1." in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""Tests for Trading Executor Agent."""

import pytest
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.trading.trading_executor import TradingExecutorAgent, Trade, PerformanceMetrics


class TestTradingExecutorAgent:
    """Test suite for TradingExecutorAgent."""

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = TradingExecutorAgent(paper_trading=True)
        assert agent is not None
        assert agent.paper_trading is True
        assert agent.initial_capital == 10000

    def test_fetch_realtime_data(self):
        """Test fetching real-time data."""
        agent = TradingExecutorAgent()
        data = agent.fetch_realtime_data("AAPL", interval="1m")
        # May be empty if API fails, but should not raise
        assert isinstance(data, dict)

    def test_generate_signal(self):
        """Test signal generation."""
        agent = TradingExecutorAgent()
        
        # Test with empty data
        signal = agent.generate_signal(None, {})
        assert signal in ["buy", "sell", "hold"]
        
        # Test with sufficient data
        data = {
            "data": [{"close": 100 + i} for i in range(30)],
            "latest_price": 110,
        }
        signal = agent.generate_signal(None, data)
        assert signal in ["buy", "sell", "hold"]

    def test_execute_trade(self):
        """Test trade execution."""
        agent = TradingExecutorAgent()
        trade = agent.execute_trade("AAPL", "buy", 10, 100)
        
        assert trade.symbol == "AAPL"
        assert trade.action == "buy"
        assert trade.quantity == 10
        assert trade.price == 100

    def test_calculate_metrics(self):
        """Test metrics calculation."""
        agent = TradingExecutorAgent()
        
        # Add some trades
        agent.equity_curve = [10000, 10500, 11000, 10800]
        
        metrics = agent.calculate_metrics()
        
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return > 0
        assert metrics.num_trades == 0

    def test_get_performance_summary(self):
        """Test performance summary."""
        agent = TradingExecutorAgent()
        
        summary = agent.get_performance_summary()
        
        assert "current_equity" in summary
        assert "total_return" in summary
        assert "positions" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
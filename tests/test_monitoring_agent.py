"""Tests for Monitoring Agent."""

import pytest
from pathlib import Path
import sys
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.monitoring.monitoring_agent import MonitoringAgent, Alert, PerformanceSnapshot


class TestMonitoringAgent:
    """Test suite for MonitoringAgent."""

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = MonitoringAgent()
        assert agent is not None
        assert agent.alert_threshold is not None

    def test_alert_thresholds(self):
        """Test default alert thresholds."""
        agent = MonitoringAgent()
        assert agent.alert_threshold["max_drawdown"] == 0.15
        assert agent.alert_threshold["min_sharpe"] == 0.5
        assert agent.alert_threshold["max_daily_loss"] == 0.05

    def test_detect_drawdown_alert(self):
        """Test drawdown alert detection."""
        agent = MonitoringAgent()

        current = {"max_drawdown": 0.20, "sharpe_ratio": 0.8}
        alerts = agent.detect_performance_anomalies(current, {})

        dd_alerts = [a for a in alerts if a.alert_type == "DRAWDOWN"]
        assert len(dd_alerts) == 1
        assert dd_alerts[0].severity == "CRITICAL"

    def test_detect_sharpe_alert(self):
        """Test Sharpe ratio alert detection."""
        agent = MonitoringAgent()

        current = {"max_drawdown": 0.05, "sharpe_ratio": 0.3}
        alerts = agent.detect_performance_anomalies(current, {})

        sharpe_alerts = [a for a in alerts if a.alert_type == "SHARPE"]
        assert len(sharpe_alerts) == 1
        assert sharpe_alerts[0].severity == "WARNING"

    def test_detect_daily_loss_alert(self):
        """Test daily loss alert detection."""
        agent = MonitoringAgent()

        current = {"max_drawdown": 0.05, "sharpe_ratio": 0.8, "worst_day": -0.08}
        alerts = agent.detect_performance_anomalies(current, {})

        loss_alerts = [a for a in alerts if a.alert_type == "DAILY_LOSS"]
        assert len(loss_alerts) == 1

    def test_compare_to_baseline(self):
        """Test baseline comparison."""
        agent = MonitoringAgent()

        current = {"sharpe_ratio": 0.2, "total_return": 0.01}
        baseline = {"expected_sharpe": 1.0, "expected_return": 0.10}

        alerts = agent.compare_to_baseline(current, baseline)
        assert len(alerts) > 0

    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation."""
        agent = MonitoringAgent()

        snapshots = [
            PerformanceSnapshot(
                timestamp=datetime.now().isoformat(),
                equity=10000,
                daily_return=0.01,
                cumulative_return=0.01,
                sharpe_ratio=1.0,
                max_drawdown=0.05,
                win_rate=0.6,
                num_trades=10,
                active_positions=2,
                model_name="test_model",
                risk_profile="MEDIUM",
            )
        ]

        metrics = agent.calculate_performance_metrics(snapshots)
        assert metrics["current_equity"] == 10000
        assert metrics["sharpe_ratio"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
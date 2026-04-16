"""Monitoring Agent - Real-time performance monitoring and alerting in production."""

import os
import logging
import time
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Performance snapshot at a point in time."""
    timestamp: str
    equity: float
    daily_return: float
    cumulative_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    active_positions: int
    model_name: str
    risk_profile: str


@dataclass
class Alert:
    """Alert data structure."""
    timestamp: str
    alert_type: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    message: str
    metrics: dict


class MonitoringAgent:
    """Agent responsible for monitoring trading performance in production."""

    def __init__(
        self,
        trading_log_dir: str = "trading_logs",
        validated_dir: str = "models/validated",
        monitoring_log_dir: str = "trading_logs/monitoring",
        alert_threshold: dict = None,
    ):
        self.trading_log_dir = Path(trading_log_dir)
        self.validated_dir = Path(validated_dir)
        self.monitoring_log_dir = Path(monitoring_log_dir)
        self.monitoring_log_dir.mkdir(parents=True, exist_ok=True)

        # Default alert thresholds
        self.alert_threshold = alert_threshold or {
            "max_drawdown": 0.15,  # 15% max drawdown
            "min_sharpe": 0.5,  # Minimum Sharpe ratio
            "max_daily_loss": 0.05,  # 5% max daily loss
            "min_win_rate": 0.40,  # Minimum 40% win rate
            "max_positions": 10,  # Max 10 simultaneous positions
            "min_equity": 8000,  # Minimum $8000 equity (20% loss)
        }

        self.baseline_metrics = None
        self.alert_history = []
        self.performance_history = []

    def load_performance_data(self, days: int = 30) -> list[PerformanceSnapshot]:
        """Load performance data from trading logs."""
        snapshots = []

        if not self.trading_log_dir.exists():
            logger.warning(f"Trading log directory {self.trading_log_dir} not found")
            return snapshots

        # Read metrics files
        for metrics_file in sorted(self.trading_log_dir.glob("metrics_*.jsonl"))[-days:]:
            try:
                with open(metrics_file) as f:
                    for line in f:
                        data = json.loads(line)
                        snapshot = PerformanceSnapshot(
                            timestamp=data.get("timestamp"),
                            equity=data.get("current_equity", 0),
                            daily_return=data.get("total_return", 0),
                            cumulative_return=data.get("total_return", 0),
                            sharpe_ratio=data.get("sharpe_ratio", 0),
                            max_drawdown=data.get("max_drawdown", 0),
                            win_rate=data.get("win_rate", 0),
                            num_trades=data.get("num_trades", 0),
                            active_positions=data.get("active_positions", 0),
                            model_name=data.get("model_name", "unknown"),
                            risk_profile=data.get("risk_profile", "UNKNOWN"),
                        )
                        snapshots.append(snapshot)
            except Exception as e:
                logger.error(f"Error reading metrics file {metrics_file}: {e}")

        return snapshots

    def load_strategy_profiles(self) -> dict:
        """Load strategy profiles from validated models."""
        profiles = {}

        if not self.validated_dir.exists():
            return profiles

        for validation_file in self.validated_dir.glob("*_validation.json"):
            try:
                with open(validation_file) as f:
                    validation = json.load(f)

                model_name = validation.get("model_name")
                risk_profile = validation.get("risk_return_profile", {})
                robustness = validation.get("statistical_robustness", {})

                profiles[model_name] = {
                    "expected_sharpe": risk_profile.get("sharpe_ratio", 0),
                    "expected_return": risk_profile.get("expected_return", 0),
                    "max_drawdown": risk_profile.get("max_drawdown", 0),
                    "risk_level": risk_profile.get("risk_score", "UNKNOWN"),
                    "robustness": robustness.get("robustness_score", "UNKNOWN"),
                    "documentation": str(self.validated_dir / f"{model_name}_documentation.md"),
                }
            except Exception as e:
                logger.error(f"Error loading validation file {validation_file}: {e}")

        return profiles

    def calculate_performance_metrics(self, snapshots: list[PerformanceSnapshot]) -> dict:
        """Calculate current performance metrics."""
        if not snapshots:
            return {}

        latest = snapshots[-1]
        returns = [s.daily_return for s in snapshots]

        return {
            "current_equity": latest.equity,
            "total_return": latest.cumulative_return,
            "sharpe_ratio": latest.sharpe_ratio,
            "max_drawdown": latest.max_drawdown,
            "win_rate": latest.win_rate,
            "total_trades": latest.num_trades,
            "avg_daily_return": np.mean(returns) if returns else 0,
            "volatility": np.std(returns) if returns else 0,
            "best_day": max(returns) if returns else 0,
            "worst_day": min(returns) if returns else 0,
        }

    def detect_performance_anomalies(self, current: dict, baseline: dict) -> list[Alert]:
        """Detect performance anomalies compared to baseline."""
        alerts = []
        timestamp = datetime.now().isoformat()

        # Check drawdown
        current_dd = current.get("max_drawdown", 0)
        threshold_dd = self.alert_threshold["max_drawdown"]
        if current_dd > threshold_dd:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="DRAWDOWN",
                severity="CRITICAL",
                message=f"Maximum drawdown {current_dd:.2%} exceeds threshold {threshold_dd:.2%}",
                metrics={"current": current_dd, "threshold": threshold_dd}
            ))

        # Check Sharpe ratio
        current_sharpe = current.get("sharpe_ratio", 0)
        min_sharpe = self.alert_threshold["min_sharpe"]
        if current_sharpe < min_sharpe:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="SHARPE",
                severity="WARNING",
                message=f"Sharpe ratio {current_sharpe:.2f} below threshold {min_sharpe}",
                metrics={"current": current_sharpe, "threshold": min_sharpe}
            ))

        # Check daily loss
        worst_day = current.get("worst_day", 0)
        max_loss = self.alert_threshold["max_daily_loss"]
        if worst_day < -max_loss:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="DAILY_LOSS",
                severity="CRITICAL",
                message=f"Daily loss {abs(worst_day):.2%} exceeds threshold {max_loss:.2%}",
                metrics={"worst_day": worst_day, "threshold": -max_loss}
            ))

        # Check win rate
        win_rate = current.get("win_rate", 0)
        min_win_rate = self.alert_threshold["min_win_rate"]
        if win_rate < min_win_rate:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="WIN_RATE",
                severity="WARNING",
                message=f"Win rate {win_rate:.2%} below threshold {min_win_rate:.2%}",
                metrics={"current": win_rate, "threshold": min_win_rate}
            ))

        # Check equity floor
        equity = current.get("current_equity", 0)
        min_equity = self.alert_threshold["min_equity"]
        if equity < min_equity:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="EQUITY_FLOOR",
                severity="CRITICAL",
                message=f"Equity ${equity:.2f} below minimum ${min_equity:.2f}",
                metrics={"current": equity, "minimum": min_equity}
            ))

        return alerts

    def compare_to_baseline(self, current: dict, baseline: dict) -> list[Alert]:
        """Compare current performance to expected baseline."""
        alerts = []
        timestamp = datetime.now().isoformat()

        if not baseline:
            return alerts

        # Compare Sharpe
        expected_sharpe = baseline.get("expected_sharpe", 0)
        current_sharpe = current.get("sharpe_ratio", 0)
        if expected_sharpe > 0 and current_sharpe < expected_sharpe * 0.5:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="UNDERPERFORMANCE",
                severity="WARNING",
                message=f"Sharpe ratio {current_sharpe:.2f} significantly below expected {expected_sharpe:.2f}",
                metrics={"current": current_sharpe, "expected": expected_sharpe}
            ))

        # Compare return
        expected_return = baseline.get("expected_return", 0)
        current_return = current.get("total_return", 0)
        if current_return < expected_return * 0.5:
            alerts.append(Alert(
                timestamp=timestamp,
                alert_type="UNDERPERFORMANCE",
                severity="WARNING",
                message=f"Return {current_return:.2%} significantly below expected {expected_return:.2%}",
                metrics={"current": current_return, "expected": expected_return}
            ))

        return alerts

    def generate_performance_report(self, snapshots: list[PerformanceSnapshot], baseline: dict) -> str:
        """Generate a detailed performance report."""
        if not snapshots:
            return "No performance data available"

        current = self.calculate_performance_metrics(snapshots)
        model_name = snapshots[-1].model_name if snapshots else "unknown"

        report = f"""# Performance Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Current Status

| Metric | Value |
|--------|-------|
| **Model** | {model_name} |
| **Equity** | ${current.get('current_equity', 0):.2f} |
| **Total Return** | {current.get('total_return', 0):.2%} |
| **Sharpe Ratio** | {current.get('sharpe_ratio', 0):.2f} |
| **Max Drawdown** | {current.get('max_drawdown', 0):.2%} |
| **Win Rate** | {current.get('win_rate', 0):.2%} |
| **Total Trades** | {current.get('total_trades', 0)} |

## Daily Statistics

| Metric | Value |
|--------|-------|
| **Average Daily Return** | {current.get('avg_daily_return', 0):.2%} |
| **Volatility** | {current.get('volatility', 0):.2%} |
| **Best Day** | {current.get('best_day', 0):.2%} |
| **Worst Day** | {current.get('worst_day', 0):.2%} |

## Expected Performance (Baseline)

"""
        if baseline:
            report += f"""| Metric | Expected | Current | Status |
|----------|----------|----------|--------|
| Sharpe Ratio | {baseline.get('expected_sharpe', 0):.2f} | {current.get('sharpe_ratio', 0):.2f} | {'OK' if current.get('sharpe_ratio', 0) >= baseline.get('expected_sharpe', 0) * 0.5 else 'BELOW'} |
| Return | {baseline.get('expected_return', 0):.2%} | {current.get('total_return', 0):.2%} | {'OK' if current.get('total_return', 0) >= baseline.get('expected_return', 0) * 0.5 else 'BELOW'} |
| Max Drawdown | {baseline.get('max_drawdown', 0):.2%} | {current.get('max_drawdown', 0):.2%} | {'OK' if current.get('max_drawdown', 0) <= baseline.get('max_drawdown', 0) * 1.5 else 'EXCEEDED'} |

## Risk Assessment

- **Risk Level**: {baseline.get('risk_level', 'UNKNOWN')}
- **Robustness**: {baseline.get('robustness', 'UNKNOWN')}

## Alerts

"""
        else:
            report += "No baseline data available.\n\n## Alerts\n"

        # Check for alerts
        alerts = self.detect_performance_anomalies(current, baseline)
        if alerts:
            for alert in alerts:
                report += f"- **[{alert.severity}]** {alert.alert_type}: {alert.message}\n"
        else:
            report += "- No alerts at this time.\n"

        report += f"""
---
*Generated by MonitoringAgent*
"""
        return report

    def run_monitoring_cycle(self) -> list[Alert]:
        """Run a complete monitoring cycle."""
        logger.info("Running monitoring cycle...")

        # Load data
        snapshots = self.load_performance_data(days=7)
        strategies = self.load_strategy_profiles()

        if not snapshots:
            logger.warning("No performance data to monitor")
            return []

        # Get current metrics
        current = self.calculate_performance_metrics(snapshots)
        model_name = snapshots[-1].model_name

        # Get baseline for current model
        baseline = strategies.get(model_name, {})

        # Detect anomalies
        alerts = self.detect_performance_anomalies(current, baseline)

        # Compare to baseline
        baseline_alerts = self.compare_to_baseline(current, baseline)
        alerts.extend(baseline_alerts)

        # Log alerts
        for alert in alerts:
            self._log_alert(alert)
            logger.warning(f"Alert: {alert.alert_type} - {alert.message}")

        # Generate report
        report = self.generate_performance_report(snapshots, baseline)
        report_file = self.monitoring_log_dir / f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
        report_file.write_text(report)
        logger.info(f"Performance report saved to {report_file}")

        return alerts

    def run_continuous_monitoring(self, interval_seconds: int = 300, duration_minutes: int = 60):
        """Run continuous monitoring."""
        logger.info(f"Starting continuous monitoring (every {interval_seconds}s for {duration_minutes}m)")

        start_time = datetime.now()
        iterations = 0

        while (datetime.now() - start_time).total_seconds() < duration_minutes * 60:
            alerts = self.run_monitoring_cycle()
            iterations += 1

            if alerts:
                # Send alerts
                self.send_alerts(alerts)

            time.sleep(interval_seconds)

        logger.info(f"Continuous monitoring completed after {iterations} cycles")

    def send_alerts(self, alerts: list[Alert]):
        """Send alerts via configured channels."""
        # Filter critical and warning alerts
        critical_alerts = [a for a in alerts if a.severity in ["CRITICAL", "WARNING"]]

        if not critical_alerts:
            return

        logger.info(f"Sending {len(critical_alerts)} alerts...")

        # Log to file
        alert_file = self.monitoring_log_dir / f"alerts_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(alert_file, "a") as f:
            for alert in critical_alerts:
                f.write(json.dumps(asdict(alert)) + "\n")

        # Note: In production, implement webhook/email notifications here
        # Example webhook (disabled):
        # if os.getenv("ALERT_WEBHOOK_URL"):
        #     self._send_webhook(critical_alerts)

    def _log_alert(self, alert: Alert):
        """Log alert to history."""
        self.alert_history.append(alert)

    def get_performance_summary(self) -> dict:
        """Get current performance summary."""
        snapshots = self.load_performance_data(days=7)
        strategies = self.load_strategy_profiles()

        if not snapshots:
            return {"status": "NO_DATA"}

        current = self.calculate_performance_metrics(snapshots)
        model_name = snapshots[-1].model_name
        baseline = strategies.get(model_name, {})

        return {
            "status": "MONITORING",
            "model": model_name,
            "equity": current.get("current_equity", 0),
            "total_return": current.get("total_return", 0),
            "sharpe_ratio": current.get("sharpe_ratio", 0),
            "max_drawdown": current.get("max_drawdown", 0),
            "risk_level": baseline.get("risk_level", "UNKNOWN"),
            "baseline_sharpe": baseline.get("expected_sharpe", 0),
            "alerts_count": len(self.alert_history),
        }


if __name__ == "__main__":
    agent = MonitoringAgent()
    alerts = agent.run_monitoring_cycle()
    summary = agent.get_performance_summary()

    print("Performance Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if alerts:
        print(f"\nAlerts: {len(alerts)}")
        for alert in alerts:
            print(f"  [{alert.severity}] {alert.message}")
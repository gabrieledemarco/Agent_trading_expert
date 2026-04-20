"""Trading Executor Agent - Execute and monitor trading strategies with validated models."""

import logging
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import numpy as np

from agents.base.base_agent import BaseAgent
from configs.paths import Paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade data structure."""
    timestamp: str
    symbol: str
    action: str  # "buy" or "sell"
    quantity: float
    price: float
    value: float
    signal: str
    model_name: str


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    current_equity: float
    risk_profile: str
    model_name: str


@dataclass
class StrategyProfile:
    """Trading strategy profile."""
    model_name: str
    risk_level: str
    expected_return: float
    max_drawdown: float
    sharpe_ratio: float
    robustness_score: str
    scientific_basis: str
    documentation_path: str


class TradingExecutorAgent(BaseAgent):
    """Agent responsible for executing and monitoring trading strategies."""

    def __init__(
        self,
        model_path: str = str(Paths.MODELS_VERSIONS),
        validated_dir: str = str(Paths.VALIDATED_DIR),
        trading_log_dir: str = str(Paths.TRADING_LOGS),
        initial_capital: float = 10000,
        paper_trading: bool = True,
    ):
        super().__init__()
        self.model_path = Path(model_path)
        self.validated_dir = Path(validated_dir)
        self.log_dir = Path(trading_log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.initial_capital = initial_capital
        self.paper_trading = paper_trading

        self.current_capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.equity_curve = [initial_capital]
        self.active_strategy = None
        self.strategy_profiles = {}
        self._lock = threading.Lock()

    def should_run_now(self, min_interval_days: int = 0) -> bool:
        return True  # Trading gira sempre quando chiamato dal loop

    def run(
        self,
        symbols: list = None,
        interval_seconds: int = 60,
        max_iterations: int = 100,
    ):
        """Alias for run_trading_loop — satisfies BaseAgent contract."""
        return self.run_trading_loop(
            symbols=symbols or ["AAPL", "MSFT", "GOOG"],
            interval_seconds=interval_seconds,
            max_iterations=max_iterations,
        )

    def load_validated_strategies(self) -> list[StrategyProfile]:
        """Load all validated strategies."""
        strategies = []

        if not self.validated_dir.exists():
            logger.warning(f"Validated directory {self.validated_dir} not found")
            return strategies

        for validation_file in self.validated_dir.glob("*_validation.json"):
            try:
                with open(validation_file) as f:
                    validation = json.load(f)

                if validation.get("schema_version") != "1.0":
                    logger.warning(
                        "validation file %s missing schema_version=1.0 (got %r)",
                        validation_file.name,
                        validation.get("schema_version"),
                    )

                if validation.get("validation_status") == "APPROVED":
                    risk_profile = validation.get("risk_return_profile", {})
                    robustness = validation.get("statistical_robustness", {})

                    # Get documentation path
                    doc_file = self.validated_dir / validation_file.name.replace("_validation.json", "_documentation.md")
                    doc_path = str(doc_file) if doc_file.exists() else ""

                    strategy = StrategyProfile(
                        model_name=validation.get("model_name"),
                        risk_level=risk_profile.get("risk_score", "UNKNOWN"),
                        expected_return=risk_profile.get("expected_return", 0),
                        max_drawdown=risk_profile.get("max_drawdown", 0),
                        sharpe_ratio=risk_profile.get("sharpe_ratio", 0),
                        robustness_score=robustness.get("robustness_score", "UNKNOWN"),
                        scientific_basis=f"Based on arXiv paper research",
                        documentation_path=doc_path,
                    )
                    strategies.append(strategy)
                    self.strategy_profiles[strategy.model_name] = strategy
                    logger.info(f"Loaded validated strategy: {strategy.model_name}")
            except Exception as e:
                logger.error(f"Error loading validation file {validation_file}: {e}")

        return strategies

    def select_strategy(self, risk_tolerance: str = "MEDIUM") -> Optional[StrategyProfile]:
        """Select appropriate strategy based on risk tolerance."""
        strategies = self.load_validated_strategies()

        if not strategies:
            logger.warning("No validated strategies found, using default")
            return None

        # Filter by risk tolerance
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        target_level = risk_order.get(risk_tolerance, 1)

        suitable = [s for s in strategies if risk_order.get(s.risk_level, 1) <= target_level]

        if not suitable:
            suitable = strategies

        # Select best by Sharpe ratio
        best = max(suitable, key=lambda s: s.sharpe_ratio)
        self.active_strategy = best

        logger.info(f"Selected strategy: {best.model_name} (risk: {best.risk_level})")
        return best

    def load_model(self, model_name: str):
        """Load a trained model."""
        import torch
        import sys

        sys.path.insert(0, str(self.model_path.parent))

        model_file = self.model_path / f"{model_name}.py"
        if not model_file.exists():
            logger.warning(f"Model file {model_file} not found")
            return None

        logger.info(f"Loading model: {model_name}")
        return model_file

    def fetch_realtime_data(self, symbol: str, interval: str = "1m") -> dict:
        """Fetch real-time market data."""
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval=interval)

            if data.empty:
                return {}

            df = data.reset_index()
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]

            return {
                "symbol": symbol,
                "data": df.to_dict(orient="records"),
                "latest_price": float(df["close"].iloc[-1]),
            }
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return {}

    def generate_signal(self, model, data: dict) -> str:
        """Generate trading signal from model and data."""
        if model is None:
            # Default to random for testing
            import numpy as np

            return np.random.choice(["buy", "sell", "hold"], p=[0.3, 0.2, 0.5])

        # In production, use model to predict
        # For now, use a simple heuristic
        if not data or "latest_price" not in data:
            return "hold"

        # Simple moving average crossover
        prices = [d["close"] for d in data.get("data", [])]
        if len(prices) < 20:
            return "hold"

        ma_5 = sum(prices[-5:]) / 5
        ma_20 = sum(prices[-20:]) / 20

        if ma_5 > ma_20 * 1.02:
            return "buy"
        elif ma_5 < ma_20 * 0.98:
            return "sell"
        return "hold"

    def execute_trade(self, symbol: str, action: str, quantity: float, price: float, model_name: str = "default") -> Trade:
        """Execute a trade."""
        timestamp = datetime.now().isoformat()
        value = quantity * price

        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            value=value,
            signal="ma_crossover",
            model_name=model_name or (self.active_strategy.model_name if self.active_strategy else "default"),
        )

        if not self.paper_trading:
            logger.warning("Real trading not implemented - using paper trading")
            # In production, connect to broker API here

        # Update positions and capital under lock to prevent race conditions
        with self._lock:
            self.trade_history.append(trade)
            if action == "buy":
                self.current_capital -= value
                self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            elif action == "sell":
                self.current_capital += value
                self.positions[symbol] = max(0, self.positions.get(symbol, 0) - quantity)

        # Log trade
        self._log_trade(trade)

        logger.info(f"Executed {action} {quantity} {symbol} at {price} using model {trade.model_name}")
        return trade

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate current performance metrics."""
        import numpy as np

        equity = np.array(self.equity_curve)
        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0])

        total_return = (equity[-1] - self.initial_capital) / self.initial_capital

        # Sharpe ratio
        if len(returns) > 1 and returns.std() > 0:
            sharpe = np.sqrt(252) * returns.mean() / returns.std()
        else:
            sharpe = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)

        # Win rate
        win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0.0

        # Get risk profile from active strategy
        risk_profile = "UNKNOWN"
        if self.active_strategy:
            risk_profile = self.active_strategy.risk_level
        elif self.strategy_profiles:
            # Get from first available strategy
            first_strategy = next(iter(self.strategy_profiles.values()))
            risk_profile = first_strategy.risk_level

        model_name = self.active_strategy.model_name if self.active_strategy else "default"

        metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            num_trades=len(self.trade_history),
            current_equity=equity[-1],
            risk_profile=risk_profile,
            model_name=model_name,
        )

        return metrics

    def run_trading_loop(
        self,
        symbols: list[str],
        interval_seconds: int = 60,
        max_iterations: int = 100,
    ):
        """Run continuous trading loop."""
        logger.info(f"Starting trading loop for {symbols}")
        logger.info(f"Paper trading mode: {self.paper_trading}")

        iteration = 0
        latest_prices: dict[str, float] = {}

        while iteration < max_iterations:
            for symbol in symbols:
                # Fetch data
                data = self.fetch_realtime_data(symbol, interval="5m")

                if not data:
                    continue

                price = data["latest_price"]
                latest_prices[symbol] = price

                # Generate signal
                model = None  # Load actual model in production
                signal = self.generate_signal(model, data)

                # Execute trade if signal is buy or sell
                if signal in ["buy", "sell"]:
                    quantity = self.current_capital * 0.1 / price  # 10% of capital

                    if signal == "buy" and self.current_capital >= price * quantity:
                        self.execute_trade(symbol, signal, quantity, price)
                    elif signal == "sell":
                        current_position = self.positions.get(symbol, 0)
                        if current_position > 0:
                            self.execute_trade(symbol, signal, current_position, price)

            # Update equity curve once per iteration using all known prices
            with self._lock:
                current_value = self.current_capital + sum(
                    self.positions.get(s, 0) * latest_prices.get(s, 0)
                    for s in symbols
                )
                self.equity_curve.append(current_value)

            # Calculate and log metrics
            metrics = self.calculate_metrics()
            self._log_metrics(metrics)

            logger.info(
                f"Iteration {iteration}: Equity={metrics.current_equity:.2f}, "
                f"Return={metrics.total_return:.2%}, Sharpe={metrics.sharpe_ratio:.2f}"
            )

            iteration += 1
            time.sleep(interval_seconds)

        logger.info("Trading loop completed")
        return self.calculate_metrics()

    def _log_trade(self, trade: Trade):
        """Log trade to file."""
        log_file = self.log_dir / f"trades_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(trade)) + "\n")
        try:
            t = asdict(trade)
            self.db.save_trade({
                "timestamp":  str(t.get("timestamp", "")),
                "symbol":     str(t.get("symbol", "")),
                "action":     str(t.get("action", "")),
                "quantity":   float(t.get("quantity", 0) or 0),
                "price":      float(t.get("price", 0) or 0),
                "value":      float(t.get("value", 0) or 0),
                "model_name": str(t.get("model_name", "")),
                "status":     "executed",
            })
        except Exception as _e:
            logger.warning(f"Could not save trade to Neon: {_e}")

    def _log_metrics(self, metrics: PerformanceMetrics):
        """Log metrics to file."""
        log_file = self.log_dir / f"metrics_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")
        try:
            m = asdict(metrics)
            self.db.save_performance({
                "timestamp":    str(m.get("timestamp", "")),
                "model_name":   str(m.get("model_name", "portfolio")),
                "equity":       float(m.get("current_equity", 0) or 0),
                "total_return": float(m.get("total_return", 0) or 0),
                "sharpe_ratio": float(m.get("sharpe_ratio", 0) or 0),
                "max_drawdown": float(m.get("max_drawdown", 0) or 0),
                "win_rate":     float(m.get("win_rate", 0) or 0),
                "num_trades":   int(m.get("num_trades", 0) or 0),
            })
        except Exception as _e:
            logger.warning(f"Could not save performance to Neon: {_e}")

    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        metrics = self.calculate_metrics()

        return {
            "current_equity": metrics.current_equity,
            "total_return": metrics.total_return,
            "sharpe_ratio": metrics.sharpe_ratio,
            "max_drawdown": metrics.max_drawdown,
            "win_rate": metrics.win_rate,
            "total_trades": metrics.num_trades,
            "positions": self.positions,
        }


if __name__ == "__main__":
    agent = TradingExecutorAgent(paper_trading=True)
    metrics = agent.run_trading_loop(
        symbols=["AAPL", "MSFT", "GOOG"],
        interval_seconds=30,
        max_iterations=5,
    )
    summary = agent.get_performance_summary()
    print("Performance Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
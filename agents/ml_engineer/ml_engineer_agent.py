"""ML Engineer Agent - Implement and validate ML models from specifications."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from agents.base.base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLEngineerAgent(BaseAgent):
    """Agent responsible for implementing and validating ML models."""

    def __init__(self, specs_dir: str = "specs", models_dir: str = "models"):
        super().__init__()
        self.specs_dir = Path(specs_dir)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def read_specs(self) -> list[dict]:
        """Read all specification files."""
        if not self.specs_dir.exists():
            logger.warning(f"Specs directory {self.specs_dir} does not exist")
            return []

        yaml_files = list(self.specs_dir.glob("*.yaml"))
        specs = []

        for spec_file in yaml_files:
            with open(spec_file) as f:
                spec = yaml.safe_load(f)
                spec["_source_file"] = str(spec_file)
                specs.append(spec)

        return specs

    def fetch_market_data(
        self,
        symbol: str = "AAPL",
        period: str = "2y",
        interval: str = "1d",
    ) -> dict:
        """Fetch real market data using yfinance."""
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)

            if data.empty:
                logger.warning(f"No data fetched for {symbol}")
                return {}

            df = data.reset_index()
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]

            return {
                "symbol": symbol,
                "data": df.to_dict(orient="records"),
                "columns": list(df.columns),
                "shape": df.shape,
            }
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return {}

    def create_feature_engineering_pipeline(self, spec: dict) -> str:
        """Create feature engineering code from spec."""
        features = spec.get("architecture", {}).get("input_features", [])

        code = '''"""Feature engineering pipeline."""

import pandas as pd
import numpy as np
from typing import List


def create_features(df: pd.DataFrame, lookback: int = 60) -> pd.DataFrame:
    """Create features for model training."""
    features = df.copy()
    
    # Price-based features
    features["returns"] = features["close"].pct_change()
    features["log_returns"] = np.log(features["close"] / features["close"].shift(1))
    
    # Moving averages
    for window in [5, 10, 20, 50]:
        features[f"ma_{window}"] = features["close"].rolling(window).mean()
        features[f"ma_ratio_{window}"] = features["close"] / features[f"ma_{window}"]
    
    # Volatility
    features["volatility_10"] = features["returns"].rolling(10).std()
    features["volatility_20"] = features["returns"].rolling(20).std()
    
    # RSI
    delta = features["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    features["rsi"] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = features["close"].ewm(span=12, adjust=False).mean()
    ema26 = features["close"].ewm(span=26, adjust=False).mean()
    features["macd"] = ema12 - ema26
    features["macd_signal"] = features["macd"].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    features["bb_middle"] = features["close"].rolling(20).mean()
    std = features["close"].rolling(20).std()
    features["bb_upper"] = features["bb_middle"] + (std * 2)
    features["bb_lower"] = features["bb_middle"] - (std * 2)
    features["bb_position"] = (features["close"] - features["bb_lower"]) / (features["bb_upper"] - features["bb_lower"])
    
    # Volume features
    features["volume_ma"] = features["volume"].rolling(20).mean()
    features["volume_ratio"] = features["volume"] / features["volume_ma"]
    
    # Lag features
    for lag in range(1, 6):
        features[f"returns_lag_{lag}"] = features["returns"].shift(lag)
    
    # Drop NaN values
    features = features.dropna()
    
    return features


def prepare_sequences(df: pd.DataFrame, lookback: int = 60) -> tuple:
    """Prepare sequences for LSTM model."""
    feature_cols = [c for c in df.columns if c not in ["close", "volume", " Dividends", " Stock Splits"]]
    
    X = []
    y = []
    
    for i in range(lookback, len(df)):
        X.append(df[feature_cols].iloc[i-lookback:i].values)
        y.append(df["close"].iloc[i])
    
    return np.array(X), np.array(y)


if __name__ == "__main__":
    # Test feature engineering
    import yfinance as yf
    
    data = yf.download("AAPL", period="2y")
    df = pd.DataFrame(data)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    
    features = create_features(df)
    print(f"Created {len(features.columns)} features")
    print(f"Shape: {features.shape}")
'''
        return code

    def create_model_code(self, spec: dict) -> str:
        """Create model implementation code from spec."""
        model_type = spec.get("model", {}).get("type", "time_series_forecasting")
        model_name = spec.get("model", {}).get("name", "model")

        if model_type == "reinforcement_learning":
            return self._create_rl_model(model_name)
        elif model_type == "portfolio_optimization":
            return self._create_portfolio_model(model_name)
        else:
            return self._create_lstm_model(model_name)

    def _create_lstm_model(self, model_name: str) -> str:
        """Create LSTM model code."""
        return f'''"""LSTM model for price prediction - {model_name}."""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from typing import Tuple


class PricePredictionDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class LSTMPriceModel(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_output = lstm_out[:, -1, :]
        return self.fc(last_output)


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 100,
    lr: float = 0.001,
    patience: int = 10,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
) -> dict:
    """Train the model with early stopping."""
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    
    best_val_loss = float("inf")
    patience_counter = 0
    history = {{"train": [], "val": []}}
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        for X, y in train_loader:
            X, y = X.to(device), y.to(device)
            optimizer.zero_grad()
            output = model(X)
            loss = criterion(output.squeeze(), y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for X, y in val_loader:
                X, y = X.to(device), y.to(device)
                output = model(X)
                loss = criterion(output.squeeze(), y)
                val_loss += loss.item()
        
        train_loss /= len(train_loader)
        val_loss /= len(val_loader)
        
        history["train"].append(train_loss)
        history["val"].append(val_loss)
        
        print(f"Epoch {{epoch+1}}/{{epochs}} - Train Loss: {{train_loss:.4f}} - Val Loss: {{val_loss:.4f}}")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            torch.save(model.state_dict(), "models/versions/{model_name}_best.pth")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {{epoch+1}}")
                break
    
    return history


def predict(model: nn.Module, X: torch.Tensor, device: str = "cpu") -> np.ndarray:
    """Make predictions."""
    model.eval()
    with torch.no_grad():
        X = X.to(device)
        predictions = model(X).cpu().numpy()
    return predictions.squeeze()


if __name__ == "__main__":
    # Quick test
    model = LSTMPriceModel(input_size=20)
    print(model)
    print(f"Parameters: {{sum(p.numel() for p in model.parameters())}}")
'''

    def _create_rl_model(self, model_name: str) -> str:
        """Create RL trading model code."""
        return f'''"""Reinforcement Learning model - {model_name}."""

import torch
import torch.nn as nn
import numpy as np
from collections import deque
import random


class TradingEnvironment:
    """Trading environment for RL agent."""
    
    def __init__(self, data: np.ndarray, initial_balance: float = 10000):
        self.data = data
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0
        self.current_step = 0
        self.transaction_cost = 0.001
        
    def reset(self):
        self.balance = self.initial_balance
        self.position = 0
        self.current_step = 0
        return self._get_state()
    
    def _get_state(self):
        return np.array([
            self.balance / self.initial_balance,
            self.position / 100,  # Max position
            self.data[self.current_step] / np.max(self.data),
        ])
    
    def step(self, action: int):
        # Actions: 0 = hold, 1 = buy, 2 = sell
        price = self.data[self.current_step]
        
        if action == 1 and self.balance >= price:
            self.balance -= price
            self.position += 1
        elif action == 2 and self.position > 0:
            self.balance += price
            self.position -= 1
        
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1
        
        reward = self.balance + self.position * price - self.initial_balance
        return self._get_state(), reward, done


class DQNAgent(nn.Module):
    def __init__(self, state_size: int, action_size: int, hidden_size: int = 128):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, action_size),
        )
    
    def forward(self, x):
        return self.fc(x)


class RLTrader:
    def __init__(self, state_size: int, action_size: int):
        self.agent = DQNAgent(state_size, action_size)
        self.replay_buffer = deque(maxlen=10000)
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        
    def act(self, state, epsilon=None):
        if epsilon is None:
            epsilon = self.epsilon
        if np.random.random() < epsilon:
            return np.random.randint(0, 3)
        with torch.no_grad():
            return self.agent(torch.FloatTensor(state)).argmax().item()
    
    def replay(self, batch_size: int = 32):
        if len(self.replay_buffer) < batch_size:
            return
        
        batch = random.sample(self.replay_buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        states = torch.FloatTensor(states)
        next_states = torch.FloatTensor(next_states)
        rewards = torch.FloatTensor(rewards)
        actions = torch.LongTensor(actions)
        dones = torch.FloatTensor(dones)
        
        current_q = self.agent(states).gather(1, actions.unsqueeze(1)).squeeze()
        next_q = self.agent(next_states).max(1)[0]
        target_q = rewards + (1 - dones) * self.gamma * next_q
        
        loss = nn.MSELoss()(current_q, target_q)
        
        optimizer = torch.optim.Adam(self.agent.parameters())
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay


if __name__ == "__main__":
    # Quick test
    data = np.random.randn(100).cumsum() + 100
    env = TradingEnvironment(data)
    agent = RLTrader(state_size=3, action_size=3)
    print(f"RL Agent initialized with {{sum(p.numel() for p in agent.agent.parameters())}} parameters")
'''

    def _create_portfolio_model(self, model_name: str) -> str:
        """Create portfolio optimization model code."""
        return f'''"""Portfolio optimization model - {model_name}."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Tuple


class PortfolioOptimizer:
    """Mean-variance portfolio optimization."""
    
    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate
        
    def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        return prices.pct_change().dropna()
    
    def calculate_portfolio_stats(
        self, returns: pd.DataFrame, weights: np.ndarray
    ) -> Tuple[float, float]:
        portfolio_return = np.sum(returns.mean() * weights) * 252
        portfolio_std = np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
        return portfolio_return, portfolio_std
    
    def sharpe_ratio(self, returns: pd.DataFrame, weights: np.ndarray) -> float:
        port_return, port_std = self.calculate_portfolio_stats(returns, weights)
        return (port_return - self.risk_free_rate) / port_std
    
    def negative_sharpe(self, returns: pd.DataFrame, weights: np.ndarray) -> float:
        return -self.sharpe_ratio(returns, weights)
    
    def optimize_sharpe(self, returns: pd.DataFrame) -> np.ndarray:
        n_assets = len(returns.columns)
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = {{"type": "eq", "fun": lambda x: np.sum(x) - 1}}
        
        result = minimize(
            self.negative_sharpe,
            initial_weights,
            args=(returns,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        
        return result.x
    
    def optimize_min_variance(self, returns: pd.DataFrame) -> np.ndarray:
        n_assets = len(returns.columns)
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        
        def portfolio_variance(weights, returns):
            return self.calculate_portfolio_stats(returns, weights)[1] ** 2
        
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = {{"type": "eq", "fun": lambda x: np.sum(x) - 1}}
        
        result = minimize(
            portfolio_variance,
            initial_weights,
            args=(returns,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        
        return result.x


class RiskManager:
    """Risk management for portfolio."""
    
    def __init__(self, max_drawdown: float = 0.2, max_position_size: float = 0.1):
        self.max_drawdown = max_drawdown
        self.max_position_size = max_position_size
        
    def calculate_drawdown(self, equity_curve: np.ndarray) -> float:
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        return np.max(drawdown)
    
    def adjust_position_size(self, current_drawdown: float) -> float:
        if current_drawdown > self.max_drawdown:
            return 0.0
        return self.max_position_size * (1 - current_drawdown / self.max_drawdown)


if __name__ == "__main__":
    # Quick test
    np.random.seed(42)
    prices = pd.DataFrame({{
        "AAPL": np.random.randn(252).cumsum() + 100,
        "GOOG": np.random.randn(252).cumsum() + 100,
        "MSFT": np.random.randn(252).cumsum() + 100,
    }})
    
    optimizer = PortfolioOptimizer()
    returns = optimizer.calculate_returns(prices)
    weights = optimizer.optimize_sharpe(returns)
    
    print("Optimal weights:", weights)
    print("Sharpe ratio:", optimizer.sharpe_ratio(returns, weights))
'''

    def create_test_code(self, spec: dict) -> str:
        """Create test code for model."""
        model_name = spec.get("model", {}).get("name", "model")

        return f'''"""Tests for {model_name}."""

import pytest
import numpy as np
import torch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class Test{model_name.replace("model_", "").title().replace("_", "")}:
    """Test suite for {model_name}."""
    
    def test_model_creation(self):
        """Test model can be created."""
        from models.{model_name} import LSTMPriceModel
        model = LSTMPriceModel(input_size=20)
        assert model is not None
        
    def test_model_forward(self):
        """Test model forward pass."""
        from models.{model_name} import LSTMPriceModel
        model = LSTMPriceModel(input_size=20)
        x = torch.randn(8, 60, 20)
        output = model(x)
        assert output.shape == (8, 1)
        
    def test_feature_engineering(self):
        """Test feature engineering pipeline."""
        from features import create_features
        import pandas as pd
        
        df = pd.DataFrame({{
            "close": np.random.randn(100).cumsum() + 100,
            "volume": np.random.randint(1000, 10000, 100),
        }})
        features = create_features(df)
        assert "returns" in features.columns
        assert "rsi" in features.columns
        assert "macd" in features.columns
        
    def test_backtest(self):
        """Test backtesting function."""
        from backtest import run_backtest
        import pandas as pd
        
        predictions = np.random.randn(100)
        actual = np.random.randn(100).cumsum() + 100
        
        metrics = run_backtest(predictions, actual)
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    def create_backtest_code(self, spec: dict) -> str:
        """Create backtesting code."""
        return '''"""Backtesting framework."""

import numpy as np
import pandas as pd
from typing import Dict, List


def calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio."""
    excess_returns = returns - risk_free_rate / 252
    if excess_returns.std() == 0:
        return 0.0
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def calculate_max_drawdown(equity_curve: np.ndarray) -> float:
    """Calculate maximum drawdown."""
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (peak - equity_curve) / peak
    return np.max(drawdown)


def calculate_sortino(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sortino ratio."""
    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0
    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()


def run_backtest(
    predictions: np.ndarray,
    actual_prices: np.ndarray,
    initial_capital: float = 10000,
    transaction_cost: float = 0.001,
) -> Dict:
    """Run backtest simulation."""
    
    # Simple trading strategy: buy when prediction > actual, sell otherwise
    signals = np.sign(predictions[:-1] - actual_prices[:-1])
    
    equity = [initial_capital]
    positions = []
    
    for i in range(len(signals)):
        current_price = actual_prices[i]
        next_price = actual_prices[i + 1]
        
        # Execute trade
        if signals[i] > 0 and equity[-1] > current_price:
            shares = (equity[-1] * 0.95) / current_price  # Use 95% of capital
            position_value = shares * next_price
            equity.append(equity[-1] - shares * current_price + position_value)
            positions.append(shares)
        else:
            equity.append(equity[-1])
            positions.append(0)
    
    equity = np.array(equity)
    returns = pd.Series(np.diff(equity) / equity[:-1])
    
    metrics = {
        "total_return": (equity[-1] - initial_capital) / initial_capital,
        "sharpe_ratio": calculate_sharpe(returns),
        "sortino_ratio": calculate_sortino(returns),
        "max_drawdown": calculate_max_drawdown(equity),
        "win_rate": (returns > 0).sum() / len(returns),
        "avg_return": returns.mean(),
        "volatility": returns.std() * np.sqrt(252),
    }
    
    return metrics


def walk_forward_validation(
    prices: np.ndarray,
    model,
    window_size: int = 252,
    step_size: int = 63,
) -> List[Dict]:
    """Walk-forward validation."""
    results = []
    
    for i in range(0, len(prices) - window_size, step_size):
        train_data = prices[i:i+window_size]
        test_data = prices[i+window_size:i+window_size+step_size]
        
        # Train model on train_data
        # (Implementation depends on model type)
        
        # Predict on test_data
        predictions = model.predict(test_data)
        
        # Calculate metrics
        metrics = run_backtest(predictions, test_data)
        results.append(metrics)
    
    return results


if __name__ == "__main__":
    # Test backtest
    np.random.seed(42)
    predictions = np.random.randn(100)
    actual = np.random.randn(100).cumsum() + 100
    
    metrics = run_backtest(predictions, actual)
    print("Backtest Results:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
'''

    def implement_model(self, spec: dict) -> str:
        """Implement a model from specification."""
        model_name = spec.get("model", {}).get("name", "model")

        logger.info(f"Implementing model: {model_name}")

        # Create feature engineering
        feature_code = self.create_feature_engineering_pipeline(spec)
        feature_file = self.models_dir / "features.py"
        feature_file.write_text(feature_code)

        # Create model code
        model_code = self.create_model_code(spec)
        model_file = self.models_dir / f"{model_name}.py"
        model_file.write_text(model_code)

        # Create test code
        test_code = self.create_test_code(spec)
        test_file = self.models_dir / f"test_{model_name}.py"
        test_file.write_text(test_code)

        # Create backtest code
        backtest_code = self.create_backtest_code(spec)
        backtest_file = self.models_dir / "backtest.py"
        backtest_file.write_text(backtest_code)

        logger.info(f"Model implementation complete for {model_name}")
        return str(model_file)

    def run(self) -> list[str]:
        """Alias for run_implementation — satisfies BaseAgent contract."""
        return self.run_implementation()

    def run_implementation(self) -> list[str]:
        """Run model implementation for all specs."""
        specs = self.read_specs()
        implemented = []

        for spec in specs:
            model_file = self.implement_model(spec)
            implemented.append(model_file)

        return implemented


if __name__ == "__main__":
    agent = MLEngineerAgent()
    outputs = agent.run_implementation()
    print(f"Implementation complete. Models: {outputs}")
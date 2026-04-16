"""Backtesting framework."""

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

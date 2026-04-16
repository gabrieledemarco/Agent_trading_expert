"""Tests for model_momentum_further_constrains_sharpness_at."""

import pytest
import numpy as np
import torch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMomentumFurtherConstrainsSharpnessAt:
    """Test suite for model_momentum_further_constrains_sharpness_at."""
    
    def test_model_creation(self):
        """Test model can be created."""
        from models.model_momentum_further_constrains_sharpness_at import LSTMPriceModel
        model = LSTMPriceModel(input_size=20)
        assert model is not None
        
    def test_model_forward(self):
        """Test model forward pass."""
        from models.model_momentum_further_constrains_sharpness_at import LSTMPriceModel
        model = LSTMPriceModel(input_size=20)
        x = torch.randn(8, 60, 20)
        output = model(x)
        assert output.shape == (8, 1)
        
    def test_feature_engineering(self):
        """Test feature engineering pipeline."""
        from features import create_features
        import pandas as pd
        
        df = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100,
            "volume": np.random.randint(1000, 10000, 100),
        })
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

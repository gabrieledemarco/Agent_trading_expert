"""Feature engineering pipeline."""

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
